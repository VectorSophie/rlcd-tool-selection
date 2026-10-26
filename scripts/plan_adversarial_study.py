"""Plan the adversarial tool-metadata study: build every clean, control and attacked task, audit
the transformations, check the exact provider payloads offline, estimate the cost, and freeze one
manifest per group only if the whole planned study is within the global cap. No model is called
(prices come from OpenRouter's free endpoint listing).

    uv run --extra laya python scripts/plan_adversarial_study.py            # audit + estimate (+ freeze if approved)
    uv run --extra laya python scripts/plan_adversarial_study.py --no-freeze

Writes `results/adversarial_study/ATTACK_AUDIT.md`, `cost_estimates/ESTIMATE.md`,
`cost_estimates/estimate.json` and, when approved, `<group>/manifest.json`.

Approval rule: the primary groups (A, B, C) must be estimated at or under the global cap ($55) together, or nothing
is frozen and a reduced-design proposal is printed. The BFCL holdout (D) is added only if the
total including it is still within the cap.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from rlcdselect.eval.adversarial import (  # noqa: E402
    GLOBAL_CAP_USD,
    GROUPS,
    OPTIONAL_GROUPS,
    PRIMARY_GROUPS,
    StudyError,
    allocate,
    audit_failures,
    audit_markdown,
    cost_breakdown_text,
    freeze,
    plan_group,
)
from rlcdselect.eval.budget import prices_from_catalog  # noqa: E402
from rlcdselect.llm.openrouter import OpenRouterCatalog  # noqa: E402
from rlcdselect.profiles import DETERMINISTIC_V1  # noqa: E402
from rlcdselect.selectors.jev import JevSelector  # noqa: E402
from rlcdselect.startup import load_dotenv, require_env, verify_live_models  # noqa: E402


def estimate_markdown(plans, status: str, note: str) -> str:
    lines = ["# Adversarial study cost estimate", "",
             "Conservative estimator, unchanged from the external pilot (chars/3 tokens, fixed output allowances, "
             "x1.25 margin, live OpenRouter prices; argument generation assumed for every decomposed task). Not "
             "discounted, although the pilot's actual spend was 0.58x its estimate.", "",
             f"**Status: {status}.** {note}", "",
             "| group | dataset | family | estimate $ |", "|---|---|---|---|"]
    for p in plans:
        for d in p["datasets"]:
            for f, s in d["estimate"]["by_family"].items():
                lines.append(f"| {p['group']} | {d['dataset']} | {f} | {sum(s.values()):.4f} |")
    lines += ["", "| group | arm | selection $ | arguments $ |", "|---|---|---|---|"]
    for p in plans:
        arms: dict = {}
        for d in p["datasets"]:
            for a, s in d["estimate"]["by_arm"].items():
                arms.setdefault(a, [0.0, 0.0])
                arms[a][0] += s["selection"]
                arms[a][1] += s["arguments"]
        lines += [f"| {p['group']} | {a} | {v[0]:.4f} | {v[1]:.4f} |" for a, v in arms.items()]
    lines += ["", "| group | orderings | variants | estimate $ | nominal cap $ |", "|---|---|---|---|---|"]
    for p in plans:
        n = sum(len(d["variants"]) for d in p["datasets"])
        cap = p.get("budget_cap_usd")
        lines.append(f"| {p['group']} | {p['orderings_per_task']} | {n} | {p['estimate_usd']:.4f} | "
                     f"{'–' if cap is None else f'{cap:.4f}'} |")
    primary = sum(p["estimate_usd"] for p in plans if p["group"] in PRIMARY_GROUPS)
    lines += ["", f"Primary groups (A-C): **${primary:.4f}**. All groups: **${sum(p['estimate_usd'] for p in plans):.4f}**. "
              f"Global cap ${GLOBAL_CAP_USD:.2f}."]
    return "\n".join(lines) + "\n"


def reduced_designs(plans) -> list[str]:
    g = {p["group"]: p["estimate_usd"] for p in plans}
    a, b, c, d = (g.get(k, 0.0) for k in ("A_clean", "B_displacement", "C_abstention", "D_bfcl_holdout"))
    return [
        f"R1: clean ablation at 3 orderings, attack groups B and C at 2 orderings (orderings 0 and 1), no BFCL "
        f"holdout: ${a + (b + c) * 2 / 3:.2f}",
        f"R2: 2 orderings for A, B and C, no BFCL holdout: ${(a + b + c) * 2 / 3:.2f}; with the holdout "
        f"${(a + b + c) * 2 / 3 + d:.2f}",
        f"R3: the full design under a raised cap of ${(a + b + c) * 1.0:.2f} (primary) or ${(a + b + c + d):.2f} (with "
        "holdout); expected actual spend about 0.58x the estimate if the pilot ratio holds",
    ]


async def prices():
    if loaded := load_dotenv(ROOT / ".env"):
        print(f"Loaded from .env: {loaded}")
    require_env(["OPENROUTER_API_KEY"])
    catalog = OpenRouterCatalog()
    try:
        verified = await verify_live_models(DETERMINISTIC_V1.llm, JevSelector(), catalog)
    finally:
        await catalog.aclose()
    return prices_from_catalog(verified["llm"], verified.get("jev"))


def main(args) -> int:
    out = Path(args.out)
    p = asyncio.run(prices())
    print(f"Prices (free endpoint listing): {p}")
    plans, audit_rows = [], []
    for group in (*PRIMARY_GROUPS, *OPTIONAL_GROUPS):
        plan, rows = plan_group(group, profile=DETERMINISTIC_V1, prices=p)
        plans.append(plan)
        audit_rows += rows
        print(f"{group}: {sum(len(d['variants']) for d in plan['datasets'])} entries, estimate ${plan['estimate_usd']:.4f}")
    (out / "cost_estimates").mkdir(parents=True, exist_ok=True)
    (out / "ATTACK_AUDIT.md").write_text(audit_markdown(audit_rows), encoding="utf-8")
    fails = audit_failures(audit_rows)
    primary = [x for x in plans if x["group"] in PRIMARY_GROUPS]
    primary_total = sum(x["estimate_usd"] for x in primary)
    total = sum(x["estimate_usd"] for x in plans)
    if fails:
        status, note, run = "AUDIT FAILED", f"Failing checks: {dict(fails)}. Nothing frozen.", []
    elif primary_total > GLOBAL_CAP_USD:
        status = "STOPPED: over the global cap"
        note = ("The complete primary study is estimated above the cap, so nothing is frozen or run. Reduced designs "
                "(not adopted without approval): " + "; ".join(reduced_designs(plans)) + ".")
        run = []
    elif total > GLOBAL_CAP_USD:
        status, note, run = "APPROVED without the BFCL holdout", "A-C fit the cap; D would exceed it.", primary
    else:
        status, note, run = "APPROVED", "All groups fit the cap.", plans
    if run:
        allocate(run)
    (out / "cost_estimates" / "ESTIMATE.md").write_text(estimate_markdown(plans, status, note), encoding="utf-8")
    (out / "cost_estimates" / "estimate.json").write_text(json.dumps({
        "status": status, "note": note, "global_cap_usd": GLOBAL_CAP_USD, "primary_estimate_usd": primary_total,
        "total_estimate_usd": total, "reduced_designs": reduced_designs(plans),
        "groups": {x["group"]: {"estimate_usd": x["estimate_usd"], "budget_cap_usd": x.get("budget_cap_usd"),
                                "datasets": {d["dataset"]: d["estimate"] for d in x["datasets"]}} for x in plans},
    }, indent=2) + "\n", encoding="utf-8")
    print(cost_breakdown_text(plans))
    print(f"\n{status}. {note}")
    if not run:
        return 2 if (fails or primary_total > GLOBAL_CAP_USD) else 0
    if args.no_freeze:
        print("--no-freeze: nothing frozen")
        return 0
    for x in run:
        try:
            path = freeze(x, out)
        except StudyError as exc:
            print(f"Not frozen: {exc}")
            return 1
        print(f"Frozen {path} ({json.loads(path.read_text())['manifest_hash'][:16]})")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="results/adversarial_study")
    parser.add_argument("--no-freeze", action="store_true")
    sys.exit(main(parser.parse_args()))
