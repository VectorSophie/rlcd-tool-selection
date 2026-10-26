# Implementation Report

## Controlled external benchmark pilot

- Date: 2026-10-26. Harness commit `92824d3` (all three manifests were frozen and verified at it, with a clean tree). Docs and summaries are in the following commit.
- Tests: **162 passed**. Each of 6 pilot mutations makes the tests fail.
- Full tables: [`results/external_pilot/SUMMARY.md`](results/external_pilot/SUMMARY.md). Raw `records.jsonl` and `diagnostics_bfcl.jsonl` stay local.
- Three core arms (native, matched, Jev). Shared LLM: `anthropic/claude-haiku-4.5`, profile `deterministic_v1`. Jev: `typesafe/jev-1.13`, 10 back-to-back selector draws, with draw 0 executed. One seeded presentation ordering per task (per-task seed). `MockExecutor`.

| Group | Datasets | Manifest | Estimate | Cap | Actual |
|---|---|---|---|---|---|
| A | when2call 150, metatool_s1 100, metatool_s3 100 | `f300e18e9399` | $2.8021 | $4.2031 | $1.6301 |
| B | bfcl_simple_python 100, bfcl_irrelevance 100 | `513e54111c7d` | $1.2415 | $1.8622 | $0.7172 |
| C | bfcl_live_simple 100, bfcl_live_irrelevance 100 | `56c70adcd7f3` | $1.5182 | $2.2774 | $0.8759 |
| **Total** | 750 tasks, 2,250 records | | **$5.5618** | | **$3.2232** (ratio 0.58) |

- 0 aborts.
- Provider calls: 2,329 to Claude, all served by Anthropic, and 7,500 to Jev, all served by TypeSafe.

**Dataset counts**

| Dataset | Source rows | Eligible | Sampled | Not eligible |
|---|---|---|---|---|
| when2call | 3,652 | 3,394 | 150 (50/50/50; 146 clusters) | 258 no candidate tools |
| metatool_s1 | 995 | 995 | 100 | — |
| metatool_s3 | 995 | 995 | 100 | — |
| bfcl_simple_python | 400 | 399 | 100 | 1 schema-inconsistent |
| bfcl_irrelevance | 240 | 240 | 100 | — |
| bfcl_live_simple | 258 | 217 | 100 | 41 schema-inconsistent, 20 N/A gold, 2 empty-alternative (overlapping) |
| bfcl_live_irrelevance | 884 | 871 | 100 | 8 conversation history, 4 no candidate tools, 1 multiple user messages |

- Diagnostic subsets were not run: 173 schema-inconsistent, 20 N/A gold and 2 ambiguous empty-alternative items, across all four answered BFCL splits. They are listed in `diagnostics_summary.json`.
- `bfcl_live_relevance` (sanity only) was not run.

**Selection accuracy** (Wilson 95%)

| Dataset | Native | Matched | Jev |
|---|---|---|---|
| when2call | 81% [74, 87] | 69% [62, 76] | 72% [64, 79] |
| metatool_s1 (name + description) | 56% [46, 65] | 78% [69, 85] | 73% [64, 81] |
| metatool_s3 (name + description) | 95% [89, 98] | 84% [76, 90] | 93% [86, 97] |
| bfcl_simple_python | 99% [95, 100] | 100% [96, 100] | 99% [95, 100] |
| bfcl_irrelevance | 88% [80, 93] | 88% [80, 93] | 93% [86, 97] |
| bfcl_live_simple | 93% [86, 97] | 97% [92, 99] | 95% [89, 98] |
| bfcl_live_irrelevance | 86% [78, 91] | 80% [71, 87] | 79% [70, 86] |

- Task success and grounded task success equal selection accuracy except on the call datasets. There, grounded task success was:
  - when2call: native 77%, matched 62%, Jev 64%;
  - bfcl_live_simple: 86 / 89 / 87%;
  - bfcl_simple_python: 97 / 98 / 97%.
- **When2Call by original label** (correct out of 50; `request_for_info` and `cannot_answer` are kept distinct):

  | Label | Native | Matched | Jev |
  |---|---|---|---|
  | `tool_call` | 40 | 47 | 49 |
  | `request_for_info` | 40 | 22 | 20 |
  | `cannot_answer` | 42 | 35 | 39 |

- When2Call intervals ignore within-cluster correlation (146 clusters in 150 rows), so they are optimistic.

**Native vs matched** (same Claude model; paired by task id)

| Dataset | Both correct | Native only | Matched only | Both wrong | Choice disagreement | McNemar p |
|---|---|---|---|---|---|---|
| when2call | 96 | 26 | 8 | 20 | 25% | 0.0029 |
| metatool_s1 | 56 | 0 | 22 | 22 | 27% | 4.8e-7 |
| metatool_s3 | 84 | 11 | 0 | 5 | 11% | 0.00098 |
| bfcl_simple_python | 99 | 0 | 1 | 0 | 1% | 1 |
| bfcl_irrelevance | 85 | 3 | 3 | 9 | 7% | 1 |
| bfcl_live_simple | 91 | 2 | 6 | 1 | 8% | 0.29 |
| bfcl_live_irrelevance | 77 | 9 | 3 | 11 | 12% | 0.15 |

Choice disagreement counts tasks where the two arms picked different options, including both-wrong pairs with different picks. Task ids for every cell are in `summary.json`. The p-values are descriptive: they are uncorrected across seven datasets, and When2Call rows are clustered.

**Jev stability (10 back-to-back draws).**
- Per dataset, 0–5% of tasks had any choice flip; the mean flip rate was ≤ 0.02.
- The mean per-tool probability range was ≤ 0.035, and the largest range within a task was 0.18.
- The executed draw 0 matched the 10-draw majority in 99–100% of tasks; no majority vote was used.
- Jev probabilities are not compared numerically with Claude choice frequencies.

**Grounding.**
- Placeholders and unsupported required values cluster in the decomposed arms on When2Call. Placeholders: matched 14, Jev 19, native 0. Unsupported required: matched 21, Jev 19, native 7. They also appear on irrelevance items where a tool was wrongly selected.
- BFCL call datasets give 22–29 `unknown` values per arm: values whose source has no rule. These are left unknown, not judged.

**Cost by arm:** native $1.3158, matched $1.1834, Jev $0.7240.
- By stage: selection $2.2704, argument generation $0.9528.
- Jev's 7,500 draws cost $0.2531 in total. The rest of the Jev arm is Claude argument generation.

**Unexpected findings (observations only)**
- **MetaTool S1 under shuffled order:** native abstained on 33% of single-tool tasks, against 10–12% for the decomposed arms. All 22 discordant pairs favour matched.
- **When2Call `request_for_info`:** the decomposed arms selected a tool and then filled placeholders or invented values where native asked for the missing information (40 vs 22 / 20 of 50). On `tool_call` the order reverses (40 vs 47 / 49). This is consistent with a selection-then-arguments split losing the "ask first" option at the argument stage. It is a hypothesis.
- **MetaTool S3 ("none of these"):** matched over-selects (84%) compared with native (95%) and Jev (93%).
- **An upstream schema defect:** 5 When2Call tasks have a parameter declared `type: integer` with a string `enum` (`province_id`, `num_passengers`), so no value can satisfy it. Every arm fails these identically. They are left in the sample, because they were not a pre-registered exclusion.
- The actual cost was 0.58× the estimate, as in earlier runs: the chars/3 token estimate with a 1.25 margin is conservative.

**Next recommendation (not started)**
- **Multiple orderings:** 3 seeded orderings on MetaTool S1/S3 and When2Call, to separate ordering effects from architecture effects. This matters most for MetaTool S1's native abstention.
- **Larger samples** on the datasets where the arms differ (When2Call, MetaTool S1/S3), with cluster-aware intervals for When2Call.
- **A diagnostic-subset run,** to measure how much the BFCL quality flags would change the results.
- **Perturbation studies** (description and name changes), using native probabilities only for within-selector shifts.
- **A temporal-spacing study for Jev:** draws minutes or hours apart, since earlier fixture runs showed more drift between runs than within one.

## Refined grounding, Jev policy, Phase 4 adapters, MCP runner mode, live regression check

- Date: 2026-10-26. Implementation commit `0200ece`; docs and results in the following commit.
- Tests: **151 passed** (`uv run --extra laya pytest`), up from 129. Each of 8 new mutations makes the tests fail:
  - an optional unsupported value treated as a hard failure;
  - the `critical` flag ignored;
  - a BFCL rule value invented;
  - `request_for_info` collapsed into `cannot_answer`;
  - a source-order-only MetaTool run allowed;
  - the execution sample chosen by majority vote;
  - source ids rewritten;
  - "that day" resolved with several candidate dates.
- Paid calls: one small fixture verification run, **$0.1707** (cap $0.50, estimate $0.282). No external datasets or MCP services were used.

| Item | Status |
|---|---|
| `bbf1663` pushed after tests, secret scan and ignore checks | ✔ |
| Grounding policy `refined_v1`: required vs optional unsupported separated; fixture `critical` paths; strict metric kept | ✔ |
| Old pilot rescored under both policies (records unchanged) | ✔ `scripts/rescore_pilot.py` |
| Evaluator-only `evaluation_context` (reference datetime, timezone); `anaphoric_day`; `reference_source` logged | ✔ |
| Jev policy documented and configurable (`--jev-selector-repetitions`), explicit `execution_sample_index` | ✔ |
| When2Call, MetaTool, BFCL adapters with provenance and exclusion reports | ✔ `datasets/external/` |
| Adapter validation tests (all 10 listed checks) on synthetic rows | ✔ `tests/test_adapters.py` |
| `--registry static|mcp`, `--executor mock|mcp`, `--mcp-fixture`, `--mcp-stdio` | ✔ |
| Local MCP smoke mode (`smoke_offline.py --mcp`), identical outcomes to the static path | ✔ |

### Old vs refined grounding on the 1,554 pilot records

| | Records whose grounded outcome differs |
|---|---|
| strict old grounding vs original `task_success` | 6 |
| **refined grounding vs strict old grounding** | **6** (all `obvious_search_web`: an invented optional `max_results`; native 1, matched 4, Jev 1) |
| refined grounding vs original `task_success` | 0 |

Across the pilot there were 130 placeholder values, 42 unsupported *required* values (the invented calendar dates), 6 unsupported *optional* values and 50 `unknown` values. Every placeholder and unsupported required value was on a missing-information task, which already counted as a failure.

### Live regression check (fixture, main condition, 3 orderings, 3 arms, 5 Jev draws)

Records were written under schema v3 with the current code.

- 126 records, no aborts and no errors.
- Every Claude call was served by Anthropic as `anthropic/claude-haiku-4.5` (149 distinct calls); every Jev call by TypeSafe as `typesafe/jev-1.13-20260917` (210 distinct calls, 5 per Jev run).
- Cost: native $0.0567, matched $0.0697, Jev $0.0443. Jev's figure comprises $0.0371 of Claude argument generation and $0.0072 for all 210 Jev draws. The 168 extra selector-only draws cost $0.0058.

| Arm | `task_success` | `grounded_task_success` (refined) | strict | placeholders | unsupported required | unsupported optional | previous 3-ordering run (`015303Z`) |
|---|---|---|---|---|---|---|---|
| native | 35/42 | 35 | 35 | 0 | 0 | 0 | 35/42 |
| matched | 30/42 | 30 | 30 | 0 | 0 | 0 | 30/42 |
| Jev | 28/42 | 28 | 28 | 9 | 4 | 0 | 27/42 |

**Jev selector stability within a run (5 back-to-back draws per run):**
- 41 of 42 runs gave the same choice in all 5 draws.
- 25 of 42 gave byte-identical probabilities in all 5. These are low-ambiguity tasks where the two-decimal outputs don't move.
- The largest per-tool probability range within a run was 0.08; the median was 0.0.
- The one flip was the near-name task in canonical order: `send_email` 4×, `send_mail` 1×, at 0.51/0.49 → 0.48/0.52.
- Every draw had its own generation id, was billed, and took about 0.4 s, so the draws are not cache hits.

**Comparison with the pilot.** Variation between runs made minutes or hours apart was larger than within one run:
- In the pilot, the same canonical-order calendar request was acted on in one run and declined in another.
- Here, Jev declined it in all 5 draws (mean 0.51 decline vs 0.49 act); in the previous run it acted.
- Across the pilot, the probability range reached 0.13.

This is a **pilot observation**. It suggests Jev's variance may have a time-correlated component that back-to-back draws under-sample. It is not established; 5 draws on 14 tasks cannot separate the two.

**Qualitative pilot findings: unchanged.**
- Clean and no-tool tasks: all arms correct.
- Missing information: both LLM arms decline (6/6 each); Jev acts on `missing_info_email` in all 3 orderings, and on `missing_info_calendar` in 2 of 3, the only selection that changed from the previous run.
- Preference-wording and decoy attacks: every arm picks the attacker's tool every time.
- Near-name attack: native and Jev resist (3/3); matched Claude selects the attacker's tool (3/3).
- Schema-description attack: native resists in 2 of 3 orderings, the exception being canonical order; matched and Jev fall for it 3/3.

These remain fixture-level observations on 14 hand-written tasks.

### Dataset adapter inclusion / exclusion (pinned upstream files, adapted offline)

| Dataset / subset | Source rows | Included | Excluded (reason) |
|---|---|---|---|
| When2Call test MCQ | 3,652 | 3,394 (1,295 `tool_call`, 1,062 `request_for_info`, 1,037 `cannot_answer`) | 258 `no_candidate_tools` (cannot_answer rows with every tool removed) |
| MetaTool Task2-Subtask1 | 995 | 995 | 0 |
| MetaTool Task2-Subtask3 | 995 | 995 | 0 |
| BFCL `simple_python` | 400 | 400 | 0 |
| BFCL `multiple` | 200 | 200 | 0 |
| BFCL `live_simple` | 258 | 258 | 0 |
| BFCL `live_multiple` | 1,053 | 1,053 | 0 |
| BFCL `irrelevance` | 240 | 240 | 0 |
| BFCL `live_irrelevance` | 884 | 871 | 8 `conversation_history`, 4 `no_candidate_tools`, 1 `multiple_user_messages` |
| BFCL `live_relevance` | 16 | 5 | 11 `relevance_gold_function_ambiguous` |

Not adapted: BFCL parallel, multi-turn, memory, web-search, Java/JavaScript and format-sensitivity subsets; MetaTool Task 1 and Task 2 Subtasks 2 and 4; When2Call's train and LLM-judge files.

Every included item passes the native and decomposed serialization paths in both conditions. For every BFCL item with arguments, the first accepted gold call passes the matcher (100%) and the refined grounding check, except the 20 `"N/A"` items below.

### Adapter ambiguities (kept and flagged, not reconciled)

1. **Name sanitization.** Native function calling rejects dotted names, so `.` becomes `_`. Affected: When2Call 617 tasks, MetaTool 65, BFCL 1,011. Originals are kept in `tool_name_map`. This is applied identically to every arm, but it is a change to the source.
2. **BFCL ground truth vs its own schema.** 173 items are tagged `gold_schema_inconsistent` (1 / 41 / 131 in `simple_python` / `live_simple` / `live_multiple`), mostly explicit `null` accepted on a string field or a value outside an enum.
3. **BFCL accepts `"N/A"` as a gold value** for `unit` in 20 `live_simple` items, while this project's placeholder rule treats it as a hard failure. They are tagged `gold_contains_placeholder`; an analysis should decide whether to exclude them.
4. **`[]` alternatives in BFCL** are read as "must be omitted or empty". This is an interpretation.
5. **When2Call `tool_call` reference arguments** are single calls with no alternatives, so they are kept as reference only and not scored. The three labels are variants of one upstream item (`source_group_id`): cluster on it.
6. **When2Call `cannot_answer` items with no tools** (258) are excluded, because an empty candidate set is not a selection.
7. **MetaTool has no input schemas.** It is selection-only, with an empty object schema added. The gold tool is first in every Subtask1 source row, so seeded permutations are enforced.
8. **BFCL `live_relevance`** has no gold function. Only single-function items are kept.

### MCP runner notes

- Fixture task definitions served over MCP are identical to the static ones: 0 differences.
- Under `smoke_offline.py --mcp`, selections, arguments and task outcomes match the static path record for record.
- Issue found and fixed: `rebind_tasks` tried to rebuild a task without its missing tool before reporting it, and that raised a `Task` validation error instead of the intended `ToolSourceError`. It now reports missing tools first.
- MCP mode is not yet wired to the external-dataset tasks. Each dataset item has its own tool set, so serving them over MCP would need one server per item, or a per-item server factory.

### Bugs caught by the new tests

- Child `selector_sample_run` records were logged with `execution_sample_index` 0 instead of their own draw index.
- `canonical_call` treated an accepted `null` as "absent".

### Remaining before the first real external-benchmark pilot

1. **Decide on the flagged items:** BFCL `gold_contains_placeholder` (20) and `gold_schema_inconsistent` (173). Include and report separately, or exclude?
2. **Wire the dataset tasks into `run_experiment.py`:** a `--dataset` option that selects adapter subsets and draws a seeded, stratified sample, with cost estimated up front. For MetaTool, order seeds must be non-canonical.
3. **Choose the sample:** e.g. 100–200 items per dataset, stratified by label, with clustering by When2Call `source_group_id`. Run with `--jev-selector-repetitions 10`, then compare within-run and across-run Jev variance before fixing N.
4. **Budget:** on these fixtures, cost per arm-run is about $0.0013 for native and $0.0017 for matched. BFCL `live_multiple` requests are much longer (up to 37 tools), so estimate before running.
5. **Spread Jev draws over time:** decide whether to space draws apart, given the across-run vs within-run difference observed here.

---

## Measurement hardening + Phase 3 (MCP registry and executor)

- Date: 2026-10-26
- **No paid provider calls and no benchmark runs were made in this phase.** The pilot rescore below reads existing records offline.
- Tests: **129 passed** (`uv run --extra laya pytest`), up from 94. Mutation checks: each of 8 deliberate breakages (selector-only draws triggering argument generation, majority vote replacing the selection, child records re-charging selection, free text marked unsupported, grounding rules leaking into the selector or argument LLM, the executor skipping validation, MCP exceptions left wrapped) makes the new tests fail.

| Item | Status |
|---|---|
| A. `SelectorSamplingPolicy`; repeated identical Jev draws, all kept; selector-only by default, end-to-end only on request | ✔ |
| A. Stability metrics: empirical frequencies, abstain/trusted/attacker frequency, entropy, flip rate, derived majority, native-probability mean/std/range | ✔ `eval/stability.py` |
| A. `deterministic_v1` semantics documented; 5 selector-only Jev draws per run (development default) | ✔ |
| A. Budget guard and estimate account for repeated draws | ✔ |
| B. Deterministic provenance checker (7 statuses, per path, no LLM judge) | ✔ `eval/grounding.py` |
| B. Evaluator-only grounding rules on tasks; never reach a model | ✔ tested + mutation-checked |
| B. `grounded_task_success` added; `task_success` unchanged | ✔ |
| B. Pilot rescored offline without modifying records | ✔ `scripts/rescore_pilot.py` |
| C. `MCPToolRegistry`, `MCPExecutor` on the official SDK (`mcp==2.3.0`) | ✔ |
| C. Local deterministic MCP fixture servers (in-process and stdio) | ✔ |
| C. Static vs MCP `ToolSpec` equivalence (required test 7, MCP side) | ✔ all 11 fixture tools, in-process and over stdio |

### Pilot rescore (grounding-aware; records unchanged)

| File | Arm | `task_success` | `grounded_task_success` |
|---|---|---|---|
| first run (1 ordering) | native / matched / Jev | 11 / 10 / 10 of 14 | unchanged |
| deterministic, main condition, 3 orderings | native / matched / Jev | 35 / 30 / 27 of 42 | unchanged |
| deterministic, name + description, 3 orderings | native / matched / Jev | 35 / 30 / 30 of 42 | unchanged |
| stochastic, 3 orderings × 10 | native / matched / Jev | 349 / 300 / 279 of 420 | **348 / 296 / 278** |

- **Only 6 of 1,554 runs change**, all `obvious_search_web`: Claude added an optional `max_results` (5 or 10) the request never mentioned, which is `unsupported` (optional, not required). Native 1, matched 4, Jev 1.
- Every placeholder (`<UNKNOWN>`) and every invented date (`2024-01-01` … `2024-12-31`) occurred on missing-information tasks, which already counted as failures because abstention was expected. The grounding fields now show *why* those actions were harmful: 100 placeholder and 27 unsupported values on the Jev arm in the stochastic run alone.
- In the name + description condition, the matched LLM also acted on missing-information tasks and produced placeholders and unsupported dates (9 placeholder, 4 unsupported values).
- Reworded queries (`"today euro to US dollar exchange rate"`, `"TODO.*payment"`) are `derived` (`token_subset`); composed email bodies are `unknown`, not `unsupported`.
- Pooled Jev stability from pilot records (`selector_stability`): act/abstain flips on `missing_info_calendar` (flip rate 0.36–0.47 per ordering at n=10), a 0.13 native-probability range on the near-name task, and a canonical-order deterministic pair that disagreed (abstain in the first run, act in the second).

### Compatibility changes

- Record `schema_version` 2 → **3**. New fields: `selector_samples`, `selector_sample_summary`, `selector_sampling`, `parent_run_id`, `selector_sample_index`, `argument_provenance`, `argument_grounding_ok`, the four grounding counts, `grounded_task_success`, `execution_meta`, `execution_attempts`, and `expected.argument_grounding`. A new record type `selector_sample_run` appears only with `execute_each_sample`. Old records stay readable: metrics, replay and `selector_stability` treat a missing field as absent / one draw (tested on a committed schema-1 file).
- `deterministic_v1` now makes 5 selector-only Jev calls per run. Same name, so compare runs by their logged `selector_sampling`.
- `Task` has an optional `argument_grounding`; `ToolExecutionResult` has optional `attempts` and `meta`; `ProviderError` subclasses are unchanged.
- The default placeholder set dropped `TODO` (a legitimate code-search query) and added `TBA`, `???`, `none provided`, `not provided`, `unspecified`.
- New dependency `mcp==2.3.0` (MIT; latest release, 2026-10-02).

### MCP SDK behavior that forced design changes

1. `Client.call_tool` silently resends after `HEADER_MISMATCH` and auto-answers input requests. → The executor uses `client.session.call_tool(..., allow_input_required=True)`; both cases become typed execution errors.
2. `tools/list` responses are cached client-side by default. → Caching off, explicit refresh, paginated walk with a page cap.
3. `FastMCP` was removed in 2.x; `MCPServer` generates schemas from Python signatures. → Fixture servers use the low-level `Server` with the fixture's exact JSON schemas.
4. Low-level servers do not validate tool arguments. → The executor validates before calling.
5. Exceptions raised inside an open client context come back as nested `ExceptionGroup`s, which would have hidden `FatalRunError`. → `MCPToolRegistry.connect` re-raises a single underlying exception unchanged.
6. The negotiated protocol is `2026-07-28`; `MCPError(REQUEST_TIMEOUT)` signals timeouts. → Only timeouts are `TransientError` and retried, under the explicit policy.

### Remaining before external benchmark integration (Phase 4)

1. Decide the grounding policy for invented *optional* parameters (currently `unsupported`; see `DESIGN.md`).
2. Add `reference_date` / `timezone` to fixture states where relative dates are intended, so `derived` dates can be scored.
3. Dataset adapters (When2Call, BFCL live_multiple / irrelevance, MetaTool with shuffling) that map each dataset's gold arguments and missing-information cases onto `ExpectedOutcome` and `argument_grounding` rules; serve their tools through the MCP fixture servers or the static registry.
4. Choose Jev's repetition count for real runs from the observed variance (5 is a development default).
5. Point `run_experiment.py` at MCP-backed tool sources (it still builds tasks from the static registry and uses `MockExecutor`).
6. A paid run of the current fixture with the new profile, to validate selector sampling and grounding live. Estimated cost for 3 orderings in the main condition: $0.28, of which the extra Jev draws add $0.004. This needs your approval.

---

## Phase 2 revision: OpenRouter pilot setup (Claude Haiku 4.5 + Jev 1.13)

- Date: 2026-10-14
- **Still no paid calls and no benchmark runs.** No API key is configured.
- The free startup checks (OpenRouter's public endpoint listing) **were run live and passed**:
  - Claude Haiku 4.5 has an `Anthropic` endpoint (slug `anthropic`) supporting every parameter we send;
  - `typesafe/jev-1.13` has its `TypeSafe` endpoint.

| Change | Status |
|---|---|
| Shared LLM switched to `anthropic/claude-haiku-4.5` via OpenRouter; routing `only: [anthropic]`, `allow_fallbacks: false`, `require_parameters: true`; `reasoning: {enabled: false}` | ✔ |
| One OpenRouter SDK client shared by native calling, matched selection and argument generation | ✔ |
| Jev via OpenRouter System One API (official SDK, base URL swap), model `typesafe/jev-1.13`, no aliases | ✔ |
| Run aborts (`FatalRunError` + `run_aborted` record) on wrong provider, unexpected returned model, unroutable request, or reasoning tokens | ✔ native, matched and Jev paths |
| Per-call logging of requested/returned model, provider (+ source), generation id, request id, `x-request-id`, temperature, thinking, routing, cost, tokens | ✔ (`*_provider_meta`, record schema v2) |
| Startup checks via the endpoint listing (free) | ✔, run live |
| OpenAI Responses client removed (superseded) | ✔ |
| Budget guard: conservative pre-run estimate from live prices, `--budget-usd` cap, refusal up front, stop on reaching the cap, actual vs estimated spend | ✔ |
| Tests | ✔ **82 passed** |

### Findings during the revision

1. **`parallel_tool_calls` must not be sent.** It isn't in the Anthropic endpoint's supported parameters, and `require_parameters: true` would make every request unroutable. It's omitted; multiple tool calls are detected and recorded.
2. **The adapter's error translation wraps every non-SDK exception** in a generic `TypeSafeError`. That would have turned a fatal provider or model mismatch into an ordinary per-task error. The checks now run outside the adapter's translation block, and tests cover all fatal conditions on the matched path.
3. **The OpenAI SDK reads `OPENAI_API_KEY` by default.** The OpenRouter client now reads `OPENROUTER_API_KEY` explicitly.
4. **The chat response schema doesn't document a `provider` field.** The client uses it when present, otherwise looks it up via `GET /api/v1/generation`. If neither yields a provider, the run aborts.
5. **The TypeSafe SDK's `models.list()` doesn't work against OpenRouter** (per OpenRouter's docs), so Jev availability is checked through the endpoint listing.

### Unknowns the first live call will settle (each fails loudly rather than silently)

- **The exact `model` string OpenRouter returns for Claude.** Only `anthropic/claude-haiku-4.5` is accepted now. If it reports something else, such as a dated id, the run aborts and the value goes into `SHARED_LLM_EXPECTED_RETURNED_MODELS` only by an explicit decision.
- **Whether the response carries `provider`,** or the generation-API fallback is needed.
- **Whether strict `json_schema` output works for Claude via OpenRouter** in the matched arm. If not, the failures are recorded as `malformed_output`.

### Next steps (need your OpenRouter key)

Conservative estimates use live prices: Haiku 4.5 at $1 / $5 per million tokens, Jev at $0.042 per million input tokens.

1. `--check-only`. Free; prints the estimate.
2. First deterministic fixture run: 14 tasks × 3 arms × 1 ordering, 42 runs. Estimate **≤ $0.09**; suggested cap `--budget-usd 0.25`.
3. Later: 3 orderings × 2 conditions, about $0.54. Stochastic (3 orderings × 10 samples), about $2.78.

---

## Phase 2 (initial version, OpenAI Responses; superseded by the revision above)

- Date: 2026-10-14
- **No live API calls were made.** No API keys are configured in this environment. All provider behavior was verified at the HTTP-transport level with mocked responses.
- **No benchmark runs have been done.** Per instructions, provider payload snapshot tests come first; they now exist and pass.

### Status

| Item | Status |
|---|---|
| Apache-2.0 `LICENSE` (official text, SHA-256 `cfc7749b…`) + `pyproject` `license = "Apache-2.0"` | ✔ |
| `OpenAIResponsesClient`: shared LLM, `gpt-5.4-mini-2026-03-17`, `reasoning.effort=none` | ✔ offline |
| Profiles `deterministic_v1` (T=0) and `stochastic_v1` (T=0.7, 10 samples) | ✔ |
| `MatchedLLMSelector` on `system-one-adapter` with a configured provider | ✔ offline |
| `JevSelector`: official SDK, pinned `jev-1.13.0`, startup availability check, no fallback | ✔ offline |
| `LayaSelector` (secondary): pinned checkpoint revision, truncation/collapse logging | ✔ adapter contract tested with an injected agent; **live model run not completed** (see below) |
| Conditions `architecture_matched_v1` (main), `ecological_name_description_v1`, `duplicate_name_stress_v1` (decomposed-only) | ✔ |
| Fixtures `static_v2`: near-name and schema-description attacks; exact-duplicate task moved to decomposed-only stress | ✔ |
| Provider-level payload snapshot tests (Jev, matched LLM in both modes, native, argument generator) | ✔ |
| `scripts/run_experiment.py` with startup checks (`--check-only`) | ✔; verified that it fails cleanly without keys |
| Tests | ✔ **65 passed** (`uv run --extra laya pytest`) |

### Findings while building the adapters

1. **`system-one-adapter`'s OpenAI provider sends no `temperature` and no `reasoning`.** Used as shipped, the matched-LLM arm would have run at provider defaults, unlike the native arm. Fixed by subclassing (`ConfiguredOpenAIProvider`). A test asserts that all three LLM roles send identical model and sampling parameters.
2. **SDK-level retries are on by default** in the OpenAI SDK (2), the TypeSafe SDK (2) and the adapter (transient plus corrective). All are disabled. Tests assert that a 429 or 500 produces exactly one HTTP request and is surfaced as a logged transient error.
3. **In `discrete` mode the adapter returns a one-hot "probability" vector.** It is not logged as a distribution (`probability_kind: none`).
4. **The adapter renders options to the LLM inside the JSON-schema description.** The snapshots confirm that every schema-bearing criterion reaches the model in presentation order, with ids identical to Jev's criteria keys.
5. **Choice-based selectors see the opaque option key as text** (Laya renders `"t0: …"`; the TypeSafe docs say names are sent). This is identical across decomposed arms. `id_seed` exists to measure label effects.

### Laya live test: attempted, deferred

- Laya 0.4.7 and `torch 2.9.1+cu128` were installed. The torch wheel came from the local uv cache. CUDA is available on both RTX PRO 6000 GPUs.
- The checkpoint download (`convaiinnovations/laya`; `snapshot_download` fetches the whole 2.37 GB repo, all three checkpoints) ran at about 92 KB/s because the concurrent GLM download is using the bandwidth. I stopped it after about 70 MB so it wouldn't slow the GLM transfer.
- The partial files are in `HF_HOME=/data/jackb/krasis/huggingface` (the krasis cache your environment points to) and will resume.
- The GPUs were never used. The live Laya probe should be rerun once the GLM download completes.

### Dependencies added

| Package | Version | Use |
|---|---|---|
| typesafe-sdk | ==0.7.4 | Jev (official SDK) |
| system-one-adapter[openai] | ==0.2.1 | Matched-LLM Choice contract |
| openai | 3.31.0 (constraint `>=2`) | Responses API |
| laya (optional extra `laya`) | ==0.4.7 | Secondary RLCD arm |
| torch (optional extra `laya`) | ==2.9.1 (+cu128 wheel) | Laya inference |

`uv run` without `--extra laya` re-syncs the environment and removes the optional extra. Use `uv run --extra laya …`.

### Upstream code reuse

- **Imported, not copied:** `system-one-adapter` (MIT) is subclassed. `ConfiguredOpenAIProvider` imports the private helpers `_responses_request_kwargs` and `_responses_result` from the pinned 0.2.1. The payload snapshot test will fail if they change.
- **Copied:** no upstream code. The `LICENSE` file is the official Apache-2.0 text.

### Before the first live run (needs you)

1. Provide `OPENAI_API_KEY` and `TYPESAFE_API_KEY` (in the environment or `.env`; never committed).
2. Run `uv run --extra laya python scripts/run_experiment.py --profile deterministic_v1 --condition architecture_matched_v1 --check-only`. It verifies that `gpt-5.4-mini-2026-03-17` and `jev-1.13.0` are available, with no paid calls.
3. Unverified assumptions that the check-only and first deterministic run will settle:
   - that `temperature` is accepted together with `reasoning.effort=none` for this model;
   - that Jev's response `model` field equals `jev-1.13.0` exactly. If not, every Jev call fails with `model_mismatch` and the mapping must be decided explicitly, not loosened silently.

---

## Phase 1: offline core

- Date: 2026-10-14
- Scope: Phase 1 only, as authorized at the research gate. **No network or model calls were made, and no API keys are used.**

## Status

| Item | Status |
|---|---|
| Common types, serialization, prompts, retry | ✔ |
| Static registry, mock executor | ✔ |
| Selector protocol, mock selectors (keyword, scripted) | ✔ |
| Native baseline pipeline (provider-neutral; runs against a fake LLM) | ✔ |
| Decomposed pipeline + shared argument generator | ✔ |
| JSONL logger with redaction; deterministic run ids; replay | ✔ |
| Runner with cross-arm invariant checks | ✔ |
| Discrete metrics; within-selector probability-shift guard | ✔ |
| Static fixtures (9 tools, 13 tasks) | ✔ |
| Tests | ✔ **45 passed** (`uv run pytest`) |
| Offline smoke test | ✔ `uv run python scripts/smoke_offline.py`: 78 records, 13 tasks × 3 order seeds × 2 arms |
| Example JSONL | `results/examples/smoke_offline_v1.jsonl` (fake models; demonstrates the format only) |
| Real selectors (matched LLM, Jev, Laya), real LLM clients | Phase 2, not started |
| MCP registry and executor | Phase 3, not started |
| Perturbations | Phase 5, not started |

"Example run for each available selector": the only selectors available offline are `mock_keyword` and `mock_scripted`. Runs for Jev, the matched LLM and Laya need Phase 2 and credentials.

## Files added

- **Top level:** `pyproject.toml`, `.gitignore`, `.env.example`, `README.md`, `DESIGN.md`, `IMPLEMENTATION_REPORT.md`
- **`src/rlcdselect/`:**
  - `core/{types, serialization, prompts, retry, jsonutil}.py`
  - `llm/{base, fake}.py`
  - `selectors/{base, mock}.py`
  - `generation/arguments.py`
  - `pipelines/{base, native, decomposed}.py`
  - `registry/{base, static}.py`
  - `execution/{base, mock}.py`
  - `eval/{scoring, logging, runner, metrics, replay}.py`
  - `datasets/fixtures.py`
  - `datasets/fixture_data/static_v1.json`
- **`scripts/`:** `smoke_offline.py`
- **`tests/`:**
  - `conftest.py`, `helpers.py`
  - `test_serialization.py`, `test_pipelines.py`, `test_eval.py`, `test_registry_and_fixtures.py`
  - `snapshots/*.json` (5 snapshots)

## Dependencies

| Package | Version resolved | Purpose |
|---|---|---|
| jsonschema | 4.26.0 (constraint `>=4.23`) | Argument validation (Draft 2020-12) |
| pytest (dev) | 9.1.1 | Tests |

Phase 2 will add pinned `typesafe-sdk==0.7.4`, `system-one-adapter==0.2.1` and `laya==0.4.7`. Phase 3 will add the `mcp` SDK (v2.3.0 at review time). These are not installed yet.

## Upstream code: copied, adapted, referenced

- **Copied or adapted:** nothing. All Phase 1 code and fixtures are project-authored.
- **Design patterns, referenced only, no code copied** (SHAs in `research/provenance.md`):
  - opaque option keys with the real name in criteria text: WindTunnel (Apache-2.0), Laya LlamaIndex integration (Apache-2.0);
  - an explicit "none of these" option: jev-webmcp-extension (Apache-2.0);
  - a forced-tool argument call with a "do not choose a different tool" instruction: WindTunnel `mercury.mjs` (Apache-2.0).

  If later phases adapt any of their code, attribution will be added.
- **Unlicensed sources:** nothing copied or redistributed. This covers jev-mcp-dispatcher, jev-decision-benchmarks, MCPTox and ContextBench-MCP.

## Mocked components

| Component | Mock | Note |
|---|---|---|
| LLM (native, argument generation) | `KeywordChatClient` (word overlap; heuristic argument filling), `ScriptedChatClient` | Deterministic; not a model. Ties go to the earliest presented tool, so order effects are visible. |
| Decomposed selector | `KeywordSelector`, `ScriptedSelector` | `KeywordSelector` scores only the criteria text it receives. |
| Executor | `MockExecutor` | Validates against the JSON schema; canned or handler outputs; records calls. |
| Registry | `StaticToolRegistry` | Normalizes MCP-style `inputSchema` and internal `input_schema` dicts identically. |

The smoke metrics for the two offline arms are identical by construction, because both use the same keyword scorer. They demonstrate wiring, not behavior.

## API requirements

- Phase 1: none.
- Phase 2 will need:
  - `TYPESAFE_API_KEY`, plus a pinned Jev model id;
  - one provider key for the shared LLM;
  - optionally `OPENROUTER_API_KEY` for the secondary Jev replication path.

## Required tests (brief §19) — coverage

| # | Requirement | Status | Test |
|---|---|---|---|
| 1 | Native receives all candidates | ✔ | `test_native_receives_all_candidate_tools` |
| 2 | Matched LLM receives the configured representation | ✔ at pipeline level | `test_decomposed_selector_receives_configured_representation` |
| 3, 4 | Jev and Laya receive the same representation | ✔ structurally: one request builder, identical requests across selector ids | `test_every_decomposed_selector_receives_the_identical_request`. Adapter-level payload tests come in Phase 2. |
| 5 | Argument generator receives exactly one tool | ✔ | `test_argument_generator_receives_exactly_the_selected_tool` |
| 6 | Argument generator cannot change the tool | ✔ | `test_argument_generator_cannot_change_the_selected_tool` |
| 7 | Static and MCP registries normalize equivalently | ◐ static side | `test_mcp_style_and_internal_dicts_normalize_identically`. The MCP side comes in Phase 3. |
| 8 | Order deterministic under seed | ✔ | `test_order_is_deterministic_under_seed` |
| 9 | Perturbations don't mutate originals | ◐ | Deep-frozen `ToolSpec`/`Task` plus `test_pipeline_runs_do_not_mutate_fixtures`. Perturbation tests come in Phase 5. |
| 10 | Attacker perturbations can't touch trusted metadata | ✗ | Phase 5 |
| 11 | Abstention explicit | ✔ | `test_abstention_is_explicit_in_both_arms`, `test_abstain_option_is_explicit_and_last` |
| 12 | Selector errors ≠ wrong selections | ✔ | `test_selector_errors_are_distinct_from_wrong_selections` |
| 13 | Execution errors ≠ wrong selections | ✔ | `test_execution_errors_are_distinct_from_wrong_selections` |
| 14 | JSONL sufficient to reproduce | ✔ selection-stage inputs, byte-identical including criteria order | `test_records_are_sufficient_to_reproduce_inputs` |
| 15 | Mocks allow complete offline tests | ✔ | `test_complete_offline_run_writes_valid_records`, smoke script |
| 16 | No secrets committed | ✔ | `test_no_secrets_in_repository`, redaction tests, `.gitignore` |
| 17 | Retries explicit and logged | ✔ | `test_retries_are_explicit_and_logged` |
| 18 | Serialization snapshot-tested | ✔ | `test_selector_request_snapshots` (4), `test_native_tools_snapshot` |

Other tests check that roles never reach models, that probabilities are flagged rather than normalized, that cross-selector probability comparison is refused, that cross-arm invariants are enforced, and that fixture gold positions vary (avoiding the MetaTool position-1 artifact).

## A bug found during review, and the fix

The first version wrote JSONL and snapshots with `sort_keys=True`. That erased criteria order, which is presentation order and an experimental variable. The replay test still passed, because Python dict equality ignores order.

- **Fix:** records and snapshots now keep insertion order. Replay compares serialized text and asserts that criteria order matches `tool_order`.
- **Verification:** a mutation check (re-enabling key sorting) makes the replay test fail.
- **Related fix:** schema text and rendered state now keep the original key order, consistent with the native payload and with what Jev receives.

## Known limitations

- The fake LLM and keyword selector are crude. Smoke metrics carry no scientific meaning.
- `ChatClient` provider adapters don't exist yet. Their contract requires logging the exact provider payload (`request_payload`); until then, `provider_payload` is `null` in records.
- There's no concurrency: runs are sequential.
- Fixture labels are author-written, 13 tasks.
- The native arm's usage is reported under `selector_usage` (single call). The argument-usage fields are null for the native arm by design.
- The repository is not a git repo yet (`git init` was not run).

## Remaining confounds

See the `DESIGN.md` table. The largest is still probability semantics, now handled by policy and code: discrete outcomes are primary, and probabilities are compared within one selector only. Next is native-arm schema visibility and provider-side tool re-serialization, which needs payload logging in Phase 2.

## Decisions needed before Phase 2

1. **The shared LLM:** provider, model snapshot and temperature. One config serves native calling, matched selection and argument generation.
2. **The exact pinned Jev model id.** The SDK default is `jev-latest`; WindTunnel asserted `jev-1.13.0`. I need to confirm which pinned ids the TypeSafe API accepts for your account.
3. **The matched-LLM answer mode:** `discrete` (recommended as primary, plus repeated sampling) and/or `probabilities` (verbalized, within-selector analysis only).

## Next attack-evaluation steps (after Phases 2–4)

These are Phase 5:

- the `ToolPerturbation` interface with seeded, field-restricted edits that never touch trusted tools;
- order shuffle, name, description, length, property-description and preference wording, semantic mimic, decoy insertion;
- MSB NC/PM metadata adapted with MIT attribution;
- empirical-frequency shift as the primary measure, and within-selector probability shift as secondary.
