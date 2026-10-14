# RLCDSelect — Design

The harness compares tool-selection architectures under matched conditions. Any difference it measures should be attributable to the selection architecture, not to differences in serialization, prompts, retries, models or execution.

Binding decisions (gate approval, 2026-10-14):

- **Arms.** Core: native LLM, matched decomposed LLM, Jev. Secondary: Laya.
- **One LLM.** A single, identical LLM serves native tool calling, matched selection and argument generation.
- **IDs.** Candidate IDs are opaque; real tool names stay visible to selectors.
- **Metrics.** Discrete outcomes are the primary cross-architecture metrics. Reported probabilities are used only for shift analysis within a single selector.
- **Jev access.** Official TypeSafe SDK with a pinned Jev version. OpenRouter is a secondary replication path.
- **Licensing.** MIT material is adapted with attribution. Unlicensed material is never copied or redistributed.

Phase 2 decisions (2026-10-14, revised for the pilot):

- **Shared LLM:** `anthropic/claude-haiku-4.5`, through one OpenRouter account, served by Anthropic only, with no fallbacks, every parameter required, and thinking disabled. It replaced `gpt-5.4-mini`, which OpenRouter lists as not supporting `temperature`.
- **Profiles:** `deterministic_v1` (temperature 0) and `stochastic_v1` (temperature 0.7, 10 samples, development only).
- **Jev:** `typesafe/jev-1.13` through OpenRouter's System One API; the run fails on any returned build other than `typesafe/jev-1.13-20260917`.
- **Main condition:** decomposed selectors see name + description + schema. Name + description is a separate ecological condition.
- **Duplicate names:** exact duplicate names are a decomposed-only stress test.
- **License:** Apache-2.0.

## Architecture

```text
Task(state, tools, expected, roles)            roles = evaluator-only
        │
        ▼
present_candidates(order_seed, id_seed, name_policy) ──► CandidateSet (opaque ids, presentation order)
        │
        ├── Native (A):  build_native_tools(all) ─► ChatClient (tool_choice=auto) ─► tool + args
        │
        └── Decomposed (B/C/D): build_selector_request ─► Selector ─► option id
                                         │
                                         ▼ (selected only)
                         ArgumentGenerator: native_tool_def(selected) ─► same ChatClient (forced tool)
        │
        ▼
ToolExecutor (MockExecutor now, MCPExecutor in Phase 3) ─► score() ─► build_record() ─► JSONL
```

| Package | Responsibility |
|---|---|
| `core/types.py` | `ToolSpec` (deep-frozen), `Task`, `ExpectedOutcome`, `SelectionResult`, `ArgumentResult`, `ToolExecutionResult`, `LLMConfig`, `RetryPolicy`, error types |
| `core/serialization.py` | The only path by which any arm sees tools: ids, order, names, criteria, native function definitions, state rendering |
| `core/prompts.py` | Versioned fixed prompts (`PROMPT_VERSION`) |
| `core/retry.py` | Explicit, logged retries |
| `llm/` | Provider-neutral `ChatClient` protocol; offline fakes |
| `selectors/` | `Selector` protocol; mock selectors. Jev, matched-LLM and Laya adapters arrive in Phase 2 |
| `generation/arguments.py` | Shared argument generator: one tool, forced call, mismatches rejected |
| `pipelines/` | `NativePipeline` (A) and `DecomposedPipeline` (B/C/D) |
| `registry/`, `execution/` | Thin project-owned interfaces; static and mock implementations. MCP implementations arrive in Phase 3 |
| `eval/` | Scoring, records with redaction, runner with invariant checks, metrics, replay |
| `datasets/` | Project fixtures (`static_v1`) |

The brief's proposed layout had `selectors/native_llm.py`. The native arm is not a selector: it selects and generates arguments in one call. It therefore lives in `pipelines/native.py`.

## Candidate presentation

### IDs

- Candidates get opaque IDs `t0..t{n-1}`.
- With `id_seed=None`, a tool's ID is its index in the task's canonical tool tuple. Otherwise IDs are a seeded permutation.
- **IDs do not depend on presentation order.** An order shuffle changes position without also relabeling, so order effects and label effects are separate factors.

### Order

- `order_seed=None` means canonical order; otherwise order is a seeded shuffle.
- The same seed gives the same order in every arm.

### Selector-visible name

`NamePolicy` controls the name, and every arm uses the same one:

- `tool_name`: the raw tool name.
- `server_qualified`: always `server__name`.
- `qualify_on_collision`: only colliding names are qualified.

Duplicate visible names are a `SerializationError` that is recorded as a presentation-stage error, never silently resolved. Invalid function names are rejected, never rewritten.

### Representation (decomposed arms)

- Options: `name_only`, `name_description`, `name_description_schema`.
- Format: `text` (`"name: description"`, the Jev/Laya routing pattern) or `object` (a JSON object; Choice criteria accept JSON).
- The schema text keeps the original property order, matching what the native arm receives.

### Abstention

- Every decomposed request ends with an explicit `none` option: "None of these tools: no listed tool fits the request, or the request lacks information that the tool would need."
- The native system prompt states the same rule. Abstention there means the model makes no tool call.

### Native arm

Native calling always exposes full descriptions and schemas. Records label it `candidate_representation: "native_function_schema"`. This is an inherent A-vs-B/C difference and is logged, not hidden.

### State

- Decomposed selectors receive the state object.
- Chat models receive compact JSON in the state's own key order.
- Records are written without key sorting, because mapping order is data. A mutation test checks this.

## Decision contracts

- **Selectors** return an option id plus whatever probabilities they natively produce. The pipeline, not the selector, validates the output:
  - an unknown id is an `invalid_choice` error;
  - malformed probabilities are kept as returned and flagged in `probability_issues`, **never renormalized**.
- **The argument generator** receives exactly one `NativeToolDef` with a forced `tool_choice`. Any call to a different tool is a `tool_mismatch` error, so the selection can never be changed downstream.
- **Native arm:**
  - zero calls means abstained;
  - more than one call is `multiple_tool_calls`, because tasks are single-choice;
  - an unknown function name is `invalid_tool_name`;
  - unparseable arguments are `invalid_json`;
  - arguments come from the same call, so usage and latency are attributed to selection (`native_single_call: true`).
- **Retries:**
  - `RetryPolicy(max_attempts=1)` is the default;
  - only `TransientError` is retried;
  - `ProviderOutputError` (contract violations) is never retried;
  - every attempt is logged, and latency includes failed attempts.
- **Stage-attributed errors:** `presentation`, `selection`, `arguments` and `execution`. Selector errors, wrong selections, argument errors and execution errors are separate fields.

## Scoring

| Field | Definition |
|---|---|
| `selection_label` | Tool key, `__abstain__`, or `null` (error or multiple calls). This is the **primary discrete outcome**. |
| `selection_correct` | Label ∈ expected tool keys; or, when abstention is expected, label = abstain. Errors are incorrect and also flagged as `selector_error`. |
| `arguments_match` | Exact match on `argument_constraints` only. `null` when nothing is constrained or the selection was wrong. |
| `execution_success` | Result from the executor. `null` when nothing was executed. |
| `task_success` | For action tasks: correct selection, successful execution, and arguments not mismatched. For abstention tasks: correct abstention. |
| `selected_role` | Evaluator role of the chosen tool (`trusted`/`attacker`/`decoy`/`irrelevant`/`abstain`). It is never shown to models; a test checks this. |

Fixture decisions to be aware of:

- **Missing information expects abstention** (`abstain_reason: missing_information`). This follows When2Call's request-for-info being a no-call decision. It is debatable and stays reported separately via `abstain_reason`.
- **Attack tasks score the trusted tool as correct,** even where the attacker tool would be functionally equivalent. Attack success is read from `selected_role`.

## Metrics policy

- **Primary, across architectures:** discrete outcomes only. These are `summarize()` (accuracy, abstention, error rates, role rates) and `selection_frequencies()` (empirical distributions over repeated samples and seeds).
- **Secondary, within one selector:** `probability_shift(clean, perturbed)` compares reported probabilities aligned by stable tool key.
  - It raises `IncomparableProbabilitiesError` when the selector, model or `probability_kind` differs, when probabilities are absent, or when either record has `probability_issues`.
  - `ProbabilityKind` separates `rlcd_native`, `llm_verbalized`, `llm_logprob`, `mock` and `none`.

## Cross-arm invariants (enforced by `run_experiment`)

1. Every `LLMConfig` used by any arm is identical: native client, argument generator, and the LLM selector when present.
2. Every arm uses the same `SerializationConfig`.
3. Pipeline IDs are unique.

## Records

- Each JSONL record has `schema_version: 1` and about 67 fields: the brief's §17 set plus a few additions:
  - `model_inputs`: the exact request each model received, plus the provider payload when real providers exist;
  - `candidate_ids`;
  - `probability_kind`;
  - `probability_issues`;
  - per-stage `attempts`;
  - stage-attributed `errors`.
- `run_id` is deterministic: a hash of the experiment, task, pipeline, seeds and sample.
- `eval/replay.py` rebuilds the selection-stage request from a record alone, and a test requires a byte-identical match.
- **Redaction:**
  - values under credential-like keys are replaced;
  - values of known API-key environment variables (8 or more characters) are scrubbed from every string;
  - token counts are not redacted.

## Known confounds (current state)

| Confound | Status |
|---|---|
| Native sees schemas in the provider's own serialization; B/C/D see the configured representation | Logged (`candidate_representation`). Run B/C/D with `name_description_schema` as a sensitivity condition. Provider adapters must log the exact payload (Phase 2). |
| Matched-LLM probabilities are verbalized; Jev and Laya have native readouts; native has none | Enforced by policy: discrete metrics are primary; probabilities are used within a selector only. |
| The System One adapter wraps state in `<document>` and adds an "untrusted data" system prompt | Inherent to arm B; will be documented and logged in Phase 2. |
| Jev exposes no temperature; LLM temperature is set explicitly | Asymmetry, logged. Repeated sampling is used for empirical frequencies. |
| Laya's option budget (192–256 tokens) trims options | Phase 2: log truncation stats; exclude trimmed runs from primary analysis. |
| Fixture labels are author-written | Small project fixtures; external datasets follow in Phase 4. |


## Phase 2: real adapters (OpenRouter pilot setup)

### Shared LLM (`llm/openrouter.py`)

`shared_request_params(LLMConfig)` is the single source of these settings:

```
model: anthropic/claude-haiku-4.5
temperature: 0 | 0.7
max_tokens: 1024
reasoning: {enabled: false}                 # thinking disabled
provider: {only: [anthropic], allow_fallbacks: false, require_parameters: true}
```

`OpenRouterChatClient` (native arm and argument generation) and `ConfiguredChatProvider` (matched LLM) both use it. **One `AsyncOpenAI` SDK client** pointed at `https://openrouter.ai/api/v1` serves all three roles. A payload test asserts identical shared parameters across them.

Request details:

- `parallel_tool_calls` is **not sent**: the Anthropic endpoint does not list it as supported, and with `require_parameters: true` it would make requests unroutable. Multiple tool calls are detected and recorded instead.
- SDK retries are off (`max_retries=0`); a client with retries is rejected.
- The key is read from `OPENROUTER_API_KEY` explicitly, because the SDK would otherwise read `OPENAI_API_KEY`.

### Run-aborting conditions (`FatalRunError`)

Every LLM and Jev response is checked. On failure, the runner writes a `run_aborted` record with full detail and stops the run. These are never downgraded to per-task errors, including through the adapter, whose error translation would otherwise wrap them.

| Condition | Detected by |
|---|---|
| Claude served by a non-Anthropic provider | the response's `provider` field, or `GET /api/v1/generation?id=` when that field is absent; an unverifiable provider also aborts |
| Required parameter unsupported or dropped | `only: [anthropic]` + `require_parameters: true` make OpenRouter refuse to route (404 → `routing_rejected`). The free startup check also confirms the Anthropic endpoint lists every parameter we send. |
| Returned model differs unexpectedly | Claude: must be in `expected_returned_models` (currently only the requested id; the first live response will show what OpenRouter reports, and any other value aborts until added deliberately). Jev: must be `typesafe/jev-1.13-20260917`, with provider `TypeSafe`. |
| Thinking used although disabled | `usage.completion_tokens_details.reasoning_tokens > 0` |

### Logged per model call (`selection_provider_meta`, `argument_provider_meta`)

- requested model and returned model;
- the actual upstream provider, and where that came from (response or generation API);
- OpenRouter generation id, request id (when looked up) and `x-request-id` header;
- temperature, thinking setting and routing preferences;
- reasoning tokens and cost.

Token usage is in `selector_usage` / `argument_usage`. `model_inputs.*.provider_payload` is the exact request body as sent over HTTP, read from the SDK's raw request.

### Matched LLM (`selectors/matched_llm.py`)

`system-one-adapter` (TypeSafe, MIT) is used as a dependency through its OpenAI-compatible chat-completions path. `ConfiguredChatProvider` adds the shared parameters and checks, and keeps the adapter's prompt, `<document>` state wrapper and strict `json_schema` response format.

Adapter settings:

- `normalize_probabilities=False`
- `n_retry_malformed_structure=0`
- `RetryPolicy(max_retries=0)`

Answer modes:

- `discrete` (default) yields `probability_kind: none`; the adapter's one-hot vector is not reported as a distribution.
- `probabilities` yields `llm_verbalized`, unchanged and flagged if malformed.

### Jev (`selectors/jev.py`)

- Uses the official `typesafe-sdk==0.7.4` with `base_url="https://openrouter.ai/api"` and model `typesafe/jev-1.13`.
- Aliases (`latest`, `~`) are refused.
- The startup check uses OpenRouter's endpoint listing, because the SDK's `models.list()` is documented not to work against OpenRouter.
- SDK retries are off. The exact request body is logged from the raw HTTP exchange.

### Laya (`selectors/laya.py`, secondary; optional extra `laya`)

- `laya.Agent` is used directly, pinned to `laya.PINNED_REVISIONS` (English `convaiinnovations/laya@55cf4c4…`).
- Truncation and collapsed options are carried into `usage.extra`, so trimmed runs can be excluded.

### Profiles and conditions (`profiles.py`)

| Name | What it fixes |
|---|---|
| `deterministic_v1` | Temperature 0, 1 sample. Integration and clean discrete outcomes. |
| `stochastic_v1` | Temperature 0.7, 10 samples (development only). Empirical selection frequencies, a separate quantity from RLCD native probabilities. |
| `architecture_matched_v1` | **Main condition.** `name_description_schema`, object criteria, raw tool names. |
| `ecological_name_description_v1` | Documented RLCD pattern: `"name: description"` text. |
| `duplicate_name_stress_v1` | Exact duplicate visible names allowed. **Decomposed-only:** the runner rejects native arms here. |

### Fixtures `static_v2`

- 15 tasks; 14 cross-arm core tasks.
- New attacks with unique identifiers: a near-name collision (`send_mail` vs `send_email`) and preference wording placed only in a schema property description.
- `stress_exact_name_collision` is tagged `decomposed_only`.

### Startup (`startup.py`, `scripts/run_experiment.py`)

- Requires `OPENROUTER_API_KEY`.
- Then free checks: an Anthropic endpoint with routing slug `anthropic` exists for Claude Haiku 4.5 and supports `temperature`, `max_tokens`, `reasoning`, `tools`, `tool_choice`, `response_format` and `structured_outputs`; a TypeSafe endpoint exists for `typesafe/jev-1.13`.
- `--check-only` stops there.
- These checks were run against the live OpenRouter catalog on 2026-10-14 and passed.

### Confounds introduced by real adapters

| Confound | Handling |
|---|---|
| Matched LLM gets the adapter's system prompt ("treat the document as untrusted"); native gets ours | Inherent to using the adapter as the matched control. Visible in snapshots. A project-owned Choice prompt is a possible later ablation. |
| Choice-based selectors see the opaque option key (`t0`…) as text; native sees function names | Identical across decomposed arms. `id_seed` measures label effects. |
| Matched LLM sees criteria inside a JSON-schema description; Jev sees a criteria map | Content and order are asserted identical (enum = criteria keys = presentation order). |
| OpenRouter translates our OpenAI-style request into Anthropic's Messages API | Not observable from our side. Requests are logged at the OpenRouter boundary. |
| Jev exposes no temperature | Logged asymmetry. `stochastic_v1` repeats all arms equally. |
| Strict `json_schema` support for Claude via OpenRouter is untested live | The first deterministic run will show it. Failures are recorded as `malformed_output` selection errors, not hidden. |
