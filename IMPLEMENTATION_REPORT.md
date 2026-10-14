# Implementation Report

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
