# RLCDSelect — Research Review (Phase R gate)

- Snapshot date: **2026-10-14**
- Status: **awaiting human approval.** No implementation has started.
- Companion files: [`references.md`](references.md) (full citations) and [`provenance.md`](provenance.md) (SHAs, licenses, files inspected).

Evidence levels used throughout:

- **[code]**: verified by reading source at the pinned SHA.
- **[readme]**: verified from the repository README or docs at the pinned SHA.
- **[paper]**: verified from the arXiv abstract or HTML.
- **[secondary]**: from a search summary, an issue tracker or a blog; not independently verified.
- **[prior]**: from background knowledge of the literature, not re-read for this review. These must be re-checked before they are cited in a paper.

---

## 2.1 Executive finding

### Q1. Has anyone compared native LLM tool calling with RLCD tool selection on the same tools and tasks?

**Yes, in weak or unmatched forms. No matched comparison was found.**

- **`ini8labs/jev-mcp-router`** [code/readme]. Same 649 real MCP tools and 111 labeled requests for both arms.
  - Jev answers one *Noul* per server and per tool, as a multi-label pre-filter.
  - The LLM baseline is a *prompted* router, not native tool calling. It gets the catalog as a cached system prompt and returns a JSON list of tool ids.
  - Both arms see descriptions truncated to 300 characters.
  - There is one run, no attacks, and no argument evaluation. The authors wrote the labels themselves.
- **`nekuda-ai/WindTunnel`** [code/readme]. Jev + Mercury 2.5 versus native WebMCP LLM arms on the same 49 tasks and scorers.
  - The repo states that these are "complete setups with different harnesses, not an isolated interface ablation."
  - It reports task success, cost and time. It does not report selection accuracy.
- **`baibizhe/jev-decision-benchmarks`** [readme]. Jev runs on BFCL, MetaTool and When2Call are compared against **published** native function-calling numbers. The baseline models were not rerun under the same protocol, and the repo says so explicitly.
- **`daniel-farina/nitro`** [readme]. Jev pre-filters Grok Build's tools. It reports cost and tokens only, on 3 tasks with 2 runs each.

### Q2. Has anyone compared matched decomposed LLM selection with RLCD selection under the same decision contract?

**Not found published.** The infrastructure for it exists:

- **`typesafe-ai/system-one-adapter-python`** exists to answer `state + Choice(criteria)` with an ordinary LLM. Its README says it is for "comparing TypeSafe against an LLM." I found no tool-selection study that uses it.
- **WindTunnel's frozen decision agent** [code] has a `selector: 'luna'` path. It sends the *same action menu* to an LLM through a forced `submit_arguments` enum call. No published WindTunnel results use that path (`PROVENANCE.md`: "No follow-up A/B/C experiments are included").
- **jev-mcp-router** gives its LLM routers the same truncated catalog. The output contract differs, though: a JSON list versus per-tool Noul probabilities.

### Q3. Has anyone evaluated tool-metadata perturbations against RLCD selectors specifically?

**No adversarial evaluation was found.** The closest work:

- **jev-decision-benchmarks** [readme/data] ran *clean, non-adversarial* robustness checks on Jev with BFCL:
  - two tool-order shuffles (prediction agreement 0.993 on `live_multiple`);
  - a parameter-schema-removal ablation (agreement 0.978).
- **"Hidden Risks of Jev"** (arXiv 2610.04985, 2026-10-04) [paper] attacks Jev through **user/state input**: context ignoring, fake completion, role spoofing, persuasion and a universal suffix (100% attack success on support routing). It also covers backdoors and membership inference.
  - Its attacker cannot modify candidate options: "The attacker can craft and submit arbitrary user queries but cannot directly modify the internal state."
  - No tools, no MCP, no LLM baseline.
- **`sdras/jev-webmcp-extension`** [code] ships a Jev **defense**: a per-tool Noul that screens each description for "instructions aimed at an AI agent," with threshold 0.5. It has no adversarial evaluation.
- `jakenbear/the-jev-enator` issue #34 proposes adversarial fixtures for a Jev danger gate [secondary, not inspected].

### Q4. Has anyone measured shifts in the selection probability or distribution, rather than only final attack success or task success?

- **For LLM selectors: yes.**
  - ToolTweak (arXiv 2510.02554) reports selection rates rising from about 20% to up to 81% and "distributional shifts in tool usage" [paper/secondary].
  - Faghih et al., EMNLP 2025 (arXiv 2505.18135), report more than 10× usage share for edited descriptions across 17 models [paper/secondary].
- **For RLCD selectors: not under attack.** jev-decision-benchmarks reports ECE, Brier and NLL plus prediction agreement under order shuffles. It has no ΔP(attacker), TV or JS measurements.

### Q5. Has anyone implemented Jev + MCP?

**Yes, many times.**

- **MCP → Jev as the tool selector:**
  - `abhishekashokvkumar/jev-mcp-dispatcher` (no LLM at all; Jev also extracts arguments);
  - `ini8labs/jev-mcp-router` (an MCP gateway).
- **Jev exposed as an MCP tool** (the opposite direction, not a selector): at least 13 repos named `*/jev-mcp`, e.g. `jkudish/jev-mcp` (★523) and `blakestone-x/jev-mcp`.

### Q6. Has anyone implemented Jev + WebMCP?

**Yes.**

- `sdras/jev-webmcp-extension`: a Chrome extension in which Jev picks the tool and fills arguments from spans.
- WindTunnel `wm-jev-mercury-v3`: Jev selects WebMCP actions and Mercury fills the arguments.
- `jangya/jev-webmcp` also exists [not inspected].

### Q7. Has anyone done the same with Laya?

**Integrations exist; no evaluation was found.**

- Laya ships `LayaSingleSelector` and `LayaMultiSelector` as drop-in replacements for LlamaIndex's `LLMSingleSelector`/`LLMMultiSelector` [code]. It also ships CrewAI and LangChain routing integrations and an MCP server (`laya/mcp`).
- It has a Jev-compatible `/v1/systemone` HTTP server [code].
- Around 15 community `laya-mcp` repos expose Laya as tools.
- I found no tool-selection or metadata-attack evaluation of Laya.

### Q8. Which systems let the decision model do what?

| System | Selects tool only | Selects tool + arguments | Gates/reviews an LLM-proposed call |
|---|---|---|---|
| jev-mcp-router | ✔ multi-label pre-filter; LLM picks the final tool and arguments | | |
| WindTunnel Jev+Mercury | ✔ Jev picks the action; Mercury fills arguments | | |
| nitro, openclaw-jev-router | ✔ tool or tool-family narrowing | | |
| Laya LlamaIndex selector | ✔ | | |
| jev-webmcp-extension | | ✔ Choice over spans and enums, Noul for booleans | policy gate on confidence and annotations; manifest screening |
| jev-mcp-dispatcher | | ✔ Noul per word to highlight spans; enums via Choice | |
| MS MCP Gateway PR #93 | | | ✔ argument-level pre-execution gate (closed, unmerged) |
| the-jev-enator | | | ✔ danger gate [secondary] |
| **RLCDSelect (proposed)** | ✔ selection only; a shared LLM writes the arguments | | |

### Q9. What candidate information does each selector see?

| System | Name | Description | Schema | Annotations | History | Notes |
|---|---|---|---|---|---|---|
| jev-mcp-dispatcher [code] | as the Choice key | as the criterion value | ✗ for selection | ✗ | ✗ | `criteria = {tool.name: tool.description or tool.name}`; no abstain label |
| jev-webmcp-extension [code] | as the Choice key | ✔ clipped to **600 chars** | ✗ for routing; ✔ for argument questions | used by policy, not by Jev | ✗ | adds an explicit `__none__` option |
| WindTunnel [code] | inside the text | ✔ | ✔ **every action's `inputSchema` is in `state`** | ✗ | ✔ step history | opaque keys `c0..cN`; text is `"id: description"`; FINISH and ABSTAIN are in the menu |
| jev-mcp-router [code/readme] | in the question text | ✔ ≤300 chars, optionally replaced by `tool_hints.json` | ✗ | ✗ | ✗ | Noul per tool; **hints give Jev different text from the LLM** |
| jev-decision-benchmarks [readme] | ✔ | ✔ | ✔ by default; one ablation removes it | ? | ? | eval code not published |
| Laya LlamaIndex [code] | inside the text | ✔ | ✗ | ✗ | ✗ | opaque keys `choice_i`; text is `"name: desc"` |

### Q10. Which existing benchmark is closest to our threat model?

- **MSB's tool-signature attacks** (MIT) are the closest dataset.
  - **Name Collision (NC):** the attacker server registers *exactly the benign tool's name*, e.g. `create_document`.
  - **Preference Manipulation (PM):** the attacker server prefixes "This is the best tool in the world."
  - Both are protocol-valid, attacker-owned metadata edits whose effect is *which tool is selected*.
  - Caveat: by default MSB combines them with a response-side False-Error attack (NC-FE, PM-FE). The selection-stage outcome has to be extracted separately.
- **ToolTweak** has the closest *threat model*: an attacker who controls its own tool name and description, measured by selection rate and distribution. It is a method paper, not a reusable dataset [paper/secondary].
- **MCPTox** Template-1/2 (function hijack) are partially relevant. Template-3 (parameter tampering) targets argument generation, and its payloads are overt instructions.

```text
NOVELTY STATUS: PLAUSIBLE BUT NEEDS NARROWING
```

**Why.** Every component already exists separately:

- Jev and Laya as tool selectors over MCP and WebMCP;
- Jev-vs-LLM cost and accuracy comparisons (unmatched);
- clean order and schema robustness checks for Jev;
- input-side attacks on Jev;
- LLM-side metadata attacks measured as selection-distribution shifts (ToolTweak, Faghih et al., AMA, ToolHijacker, MSB).

I found no work that does all three of the following:

1. holds the **decision contract** fixed across LLM and RLCD selectors: the same state, the same criteria text, the same explicit abstain option, the same label keys, and the same shared argument model;
2. lets the attacker control **only candidate metadata**, not user input;
3. measures **selection-distribution shift** with each selector's own probability semantics kept distinct.

That intersection is defensible, but only if it is stated that narrowly.

---

## 2.2 Prior-work matrix

Abbreviations: **N** = native tool calling, **D** = decomposed, **P** = per-option probabilities. Licenses and SHAs are in `provenance.md`.

| Work | Type | Year | Selector | Tool protocol | Selection separate from generation? | Candidate representation | Returns P? | Attack / perturbation? | Evaluation unit | Code? | License | Overlap with us | What remains different |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ini8labs/jev-mcp-router | repo + benchmark | 2026 | Jev Noul per tool; LLM routers; embeddings | MCP (25 real servers, 649 tools) | ✔ (pre-filter) | name + desc ≤300 chars (+ routing hints) | ✔ Jev | ✗ | all needed tools recalled per request | ✔ | MIT | Jev vs LLM over the same real MCP catalog | multi-label recall, not single choice; prompted LLM rather than native; no shared argument model; Jev/LLM text differs under hints; one run; no attacks |
| nekuda-ai/WindTunnel (Jev+Mercury) | benchmark | 2026 | Jev Choice (LLM selector path unused) | WebMCP + DOM | ✔ | `"id: desc"` + schemas in state | ✔ logged | ✗ (harness has `perturbations.mjs` for sites, not tool metadata) | end-to-end task success, cost, time | ✔ | Apache-2.0 | same decomposition as our Pipeline C | complete-setup comparison; no matched LLM selector results; no selection-level metrics; no attacks |
| baibizhe/jev-decision-benchmarks | evaluation report | 2026 | Jev Choice / binary | none (dataset transformation) | n/a | name + desc (+ schema) | ✔ | clean order shuffle, schema removal | per-example decision accuracy, ECE | partial (data and tables only) | **none** | Jev on MetaTool, When2Call, BFCL; order robustness | baselines are published numbers, not reruns; no attacks; no shared argument model |
| sdras/jev-webmcp-extension | tool | 2026 | Jev | WebMCP | ✗ (Jev does both) | name → desc (600 chars) + `__none__` | ✔ | defense: manifest screening | 17-case smoke eval | ✔ | Apache-2.0 | Jev + WebMCP; abstain option; screening | no LLM baseline; no attack evaluation |
| abhishekashokvkumar/jev-mcp-dispatcher | proof of concept | 2026 | Jev | MCP | ✗ (Jev does both) | name → desc | ✔ | ✗ | demo commands | ✔ | **none** | Jev + MCP `list_tools` → Choice | no evaluation; no abstain option; no LLM |
| typesafe-ai/system-one-adapter-python | library | 2026 | LLM via the Choice contract | n/a | n/a | same as Jev | ✔ *verbalized* or discrete | ✗ | n/a | ✔ | MIT | our matched-LLM arm | not a study |
| NandhaKishorM/laya (integrations) | model + library | 2026 | Laya | LlamaIndex/CrewAI/LangChain; MCP server | ✔ | `"name: desc"` in a 192–256-token option budget | ✔ | ✗ for tools | n/a for tools | ✔ | Apache-2.0 | RLCD selector with open weights | no tool-selection evaluation |
| ToolTweak (2510.02554) | paper | 2025 | LLMs | function lists | n/a | name + desc | empirical frequency | ✔ black-box optimization of name + desc | selection rate, distribution | [prior: check] | ? | attacker-owned metadata; distribution shift | LLMs only; no RLCD; no decomposition |
| Faghih et al. (2505.18135) | paper (EMNLP 2025) | 2025 | 17 LLMs | function lists | n/a | desc edits | empirical usage | ✔ assertive cues, etc. | usage share | ✔ | ? | description-edit bias | LLMs only |
| AMA (2508.02110) | paper (NeurIPS 2025) | 2025 | LLM agents | simulated tools; MCP | n/a | name + desc + schema | ✗ | ✔ optimized metadata | attack success, leakage | ? | ? | attractive-metadata selection | LLMs only |
| ToolHijacker (2504.19793) | paper (NDSS 2026) | 2025 | retriever + LLM | tool library | retrieval vs selection | tool document | ✗ | ✔ injected tool document | attack success (MetaTool) | ? | ? | attacker tool insertion | LLMs only; retrieval focus |
| MSB (2510.15994) | benchmark (ICLR 2026) | 2025–26 | LLM agents | MCP | ✗ | MCP tools | ✗ | ✔ 12 attack types incl. NC, PM | attack success, task success | ✔ | MIT | NC/PM = our threat model | LLM agents only; NC/PM bundled with response attacks |
| MCPTox (2508.14925) | benchmark (AAAI 2026) | 2025 | LLM agents | 45 real MCP servers | ✗ | system prompt listing tools | ✗ | ✔ 3 poisoning templates | attack success via LLM judge | ✔ (data, notebook) | **none** | real MCP tool poisoning | targets legitimate-tool hijack and args; overt payloads |
| Hidden Risks of Jev (2610.04985) | paper | 2026 | Jev, NanoJev | none | n/a | support-routing options | ✔ | ✔ state-side injection, backdoor, inference | accuracy, attack success | ✔ (`shihe98/Security_Privacy_Jev`) | ? | adversarial Jev | attacker controls user input, not options; no tools |
| Think Twice / Tool-Guard (2606.20922) | paper (ICML 2026) | 2026 | LLM planner | AgentDojo, ASB | isolated planning | descriptions | ✗ | ✔ description poisoning | attack success, utility | ✔ [secondary] | ? | description = planner attack surface | defense; LLM only |
| MCP-ITP (2601.07395) | paper | 2026 | LLM agents | MCPTox | ✗ | metadata | ✗ | ✔ automated implicit poisoning | attack success, detection rate | ? | ? | attacker metadata optimization | LLM only; out of first-milestone scope |
| Semantic Attacks (2512.06556) | paper | 2025–26 | 3 LLMs × 8 prompting strategies | MCP | ✗ | metadata | ✗ | ✔ poisoning, shadowing, rug pull | unsafe-invocation rate | ✗ | n/a | descriptor attacks shift selection | LLM only |
| ToolSelect-Bench (YE-YI7/asm-spec) | benchmark | 2026 | LLMs | ASM manifests | n/a | names_only vs ASM manifest | ✗ | metadata *richness* | correct / violation / overspend | ✔ | MIT | metadata changes selection | not adversarial; 50 tasks; LLMs only |
| ContextBench-MCP | repo | 2026 | LLM | MCP fixtures | ✗ | serialization formats | ✗ | serialization | selection accuracy | ✔ | **none** | serialization effect | **README admits the agent re-serialized the tools, which invalidated the study** |
| MetaTool (2310.03128) | benchmark | 2023 | LLMs | names + descriptions | n/a | name + desc (no schema) | ✗ | ✗ | correct-selection rate | ✔ | MIT | clean and similar-tool selection | no schemas, so no arguments |
| When2Call | benchmark (NAACL 2025) | 2025 | LLMs | function schemas | n/a | schemas | MCQ log-likelihood | ✗ | 4-way decision | ✔ | Apache-2.0 | abstention | not tool choice among many |
| BFCL V4 | leaderboard | 2024–26 | LLMs (FC/prompt) | function schemas | ✗ | schemas | ✗ | ✗ | AST/exec/relevance | ✔ (gorilla) | Apache-2.0 | relevance/irrelevance subsets | overall score ≠ selection |
| MCP-Bench / MCPMark | benchmarks | 2025 | LLM agents | real MCP | ✗ | MCP | ✗ | ✗ | end-to-end task success | ✔ | MCP-Bench: none detected; MCPMark: Apache-2.0 | realistic MCP | end-to-end, not selection |

---

## 2.3 Closest-work ranking

### 1. `ini8labs/jev-mcp-router` (newly found; not in the brief)

- **Why it is close:**
  - Jev picks MCP tools over a real 649-tool, 25-server catalog.
  - It is compared against Sonnet 5, Haiku 4.5 and GPT-5 nano routers on the same 111 labeled requests, with the same 300-character descriptions.
  - It reports cost and latency.
- **Why it is not the same experiment:**
  - The task is multi-label *recall* (the LLM picks the final tool afterwards).
  - The LLM baselines are prompted JSON-list routers, not native tool calling and not the Choice contract.
  - There is no matched argument generator.
  - `tool_hints.json` gives Jev different text from the LLM; a `router_nohints.json` result exists.
  - There is one run, labels written by the tuner, and no attacks.
- **What we can reuse (MIT):** the **real `tools/list` catalog** in `bench/catalog/` (25 servers) and `requests.jsonl` as a realistic, offline, selection-only external-validity set. This needs attribution, and the labels need re-auditing.
- **What claim it prevents:** "first Jev MCP tool router," "first Jev-vs-LLM tool-selection cost comparison," and "first realistic-catalog RLCD tool selection."

### 2. `nekuda-ai/WindTunnel` (Jev + Mercury 2.5)

- **Why it is close:**
  - Exactly our Pipeline C shape: Jev chooses the action over `"id: description"` labels with opaque keys `c0..cN`.
  - Mercury receives `{state, selected:{name, description}}` and **only the selected action's schema** (`mercury.mjs`), with "Do not choose a different action."
  - Probabilities and confidence are logged.
- **Why it is not the same experiment:**
  - It compares complete frozen setups against native WebMCP arms built on different harnesses; the repo says so explicitly.
  - Jev's `state` includes *every* action's `inputSchema`, so "name + description only" is not true there.
  - It has no published matched-LLM-selector results and no attacks.
- **What we can reuse (Apache-2.0):**
  - design patterns: opaque labels, an ABSTAIN option in the menu, a "do not change the action" argument prompt, a hash-pinned frozen-source manifest, provider-model assertions, and cost accounting;
  - the `selector:'luna'` forced-enum pattern as a template for the matched LLM selector.
- **What claim it prevents:** "first Jev selector + LLM argument decomposition," "first Jev WebMCP benchmark," and "first cost comparison of Jev vs native WebMCP agents."

### 3. `baibizhe/jev-decision-benchmarks`

- **Why it is close:**
  - Jev on MetaTool, When2Call and BFCL V4.
  - Calibration (ECE, Brier, NLL), repetition agreement, order-shuffle robustness and a schema-removal ablation.
- **Why it is not the same experiment:**
  - Baselines are published paper and leaderboard numbers, not reruns under the Choice contract.
  - The evaluation programs are not published, so how the transformation was done is only partly visible.
  - No attacks, no arguments.
- **What we can reuse:** **reference only, since there is no license.**
  - Protocol ideas: a label sidecar never loaded at run time, Wilson intervals, three-run agreement, and order-shuffle seeds.
  - Its finding that MetaTool Task2-Subtask1 **always places the gold tool at position 1** (995/995; verified in `data/metatool/protocol.json`). Any MetaTool use must shuffle.
- **What claim it prevents:** "first Jev tool-selection benchmark," "first calibration analysis of Jev tool selection," and "first order-robustness check of Jev."

### 4. `sdras/jev-webmcp-extension`

- **Why it is close:**
  - The full WebMCP manifest → Jev questions → tool and arguments → policy pipeline.
  - An explicit `__none__` option ("None of these: the request is conversation, unclear, unfinished, or needs something these actions do not do.").
  - Manifest screening for agent-directed instructions.
- **Why it is not the same experiment:** Jev does both selection *and* argument filling, there is no LLM comparison, and the eval is 17 cases on one manifest.
- **What we can reuse (Apache-2.0):**
  - the abstain-option wording pattern;
  - the 600-character description clip as a *documented* precedent (description length becomes a confound we must log);
  - the screening Noul as an optional defense arm later.
- **What claim it prevents:** "first Jev WebMCP integration" and "first RLCD-based manifest screening."

### 5. `abhishekashokvkumar/jev-mcp-dispatcher`

- **Why it is close:** a live `list_tools()` → `Choice({name: description})` → arguments → `call_tool` pipeline over MCP with no general-purpose LLM.
- **Why it is not the same experiment:** no evaluation, no LLM baseline, no abstain option for tool choice, no attacks. Arguments come from Jev span highlighting, not an LLM.
- **What we can reuse:** **reference only (no license).** The exact Choice wording ("Which function should be invoked to carry out `command`?") is a documented community pattern.
- **What claim it prevents:** "first Jev + MCP dispatcher" and "first LLM-free MCP tool dispatch with Jev."

### 6. ToolTweak (Sneh et al., arXiv 2510.02554)

- **Why it is close:** the same threat model. A tool provider controls its own name and description, and selection rate and distribution shifts are measured.
- **Why it is not the same experiment:** LLM selectors only, no RLCD, no decomposition, black-box optimization.
- **What we can reuse:** the threat-model wording, metrics, and the paraphrasing and perplexity-filter defenses as later arms.
- **What claim it prevents:** "first to show metadata manipulation shifts tool-selection distributions" and "first selection-distribution metric for tool attacks."

### 7. MCP Security Bench (MSB)

- **Why it is close:** NC and PM are protocol-valid attacker-metadata attacks on real MCP tool servers, run against LLM agents.
- **Why it is not the same experiment:**
  - LLM agents only.
  - NC and PM are bundled with response-side attacks by default.
  - Its outcome is attack success and task success, not selection probability.
- **What we can reuse (MIT):** the NC and PM tool definitions and the benign/attacker server pairs in `data/tools/attack_tools/*/attack.py`. Extract the *metadata only* and drop the response payloads.
- **What claim it prevents:** "first benchmark of name-collision or preference attacks on MCP."

### 8. `typesafe-ai/system-one-adapter-python`

- **Why it is close:** it is literally the matched-LLM control: the same `system_one(state, questions)` API and the same `SystemOneResponse` type, backed by OpenAI, Anthropic or Gemini.
- **Why it is not the same experiment:** it is a tool, not a study. Its probabilities are **verbalized** by the LLM ("return an object mapping every allowed label to its probability"), not computed from logprobs. It **does not set temperature**, so the provider default applies.
- **What we can reuse (MIT):** use it as a dependency for Pipeline B.
- **What claim it prevents:** "we built the first System One-compatible LLM control."

### 9. "Hidden Risks of Jev" (Wang et al., arXiv 2610.04985, 2026-10-04)

- **Why it is close:** an adversarial study of Jev Choice and Noul decisions with attack success metrics, plus RLCD backdoor poisoning on NanoJev.
- **Why it is not the same experiment:** the attacker controls *user input*, not options; there are no tools, no MCP and no LLM baseline.
- **What we can reuse:** the attack-taxonomy framing and the "typed outputs do not prevent manipulation" takeaway; its code is `shihe98/Security_Privacy_Jev`, which I have not inspected.
- **What claim it prevents:** "first adversarial or security evaluation of Jev" and "first RLCD backdoor study."

### 10. Laya routing integrations (`laya/integrations/llamaindex.py`, `laya/serve.py`)

- **Why it is close:** a drop-in RLCD replacement for LlamaIndex's LLM tool selectors (`"name: desc"`, opaque `choice_i` keys) and a Jev-wire-compatible server.
- **Why it is not the same experiment:** no tool-selection evaluation and no attacks.
- **What we can reuse (Apache-2.0):** call `Router.predict` directly in a thin `LayaSelector`, using `option_order` and `return_truncation_stats`.
- **What claim it prevents:** "first Laya tool selector."

Also relevant but ranked lower: Faghih et al. (description-edit bias across 17 LLMs), AMA, ToolHijacker, Think Twice / Tool-Guard, MCP-ITP, `daniel-farina/nitro`, `larches-technologies/openclaw-jev-router`, `arunav25/jev-mcp` (Jev-vs-LLM judgment harness with Brier and McNemar statistics), and ToolSelect-Bench.

---

## 2.4 Research-gap statement

### Conservative

> We provide a reproducible harness that compares native LLM tool calling, decomposed LLM selection, and RLCD selection (Jev, Laya) on identical tasks. Candidate serialization, abstention option, argument generator and execution are held fixed and logged per run. We report selection, argument, execution and task outcomes separately.

### Main-paper candidate

> Prior work shows that attacker-controlled tool metadata shifts **LLM** tool-selection distributions, and separately that Jev can serve as an MCP or WebMCP tool selector. We give a **matched-contract comparison**: the same state, criteria text, label keys, abstain option and argument model. It measures how protocol-valid, attacker-owned metadata edits (name collision, preference wording, semantic mimicry, description length, decoys) shift the selection distribution of **RLCD selectors versus LLM selectors**. It also measures whether decomposing selection from argument generation changes that susceptibility, independent of the selector family.

### Aggressive (requires verification; do not use without results)

> RLCD selectors do not remove metadata-induced selection bias; they *transform* it. They resist imperative and authority wording that LLMs follow, but they remain or become more susceptible to semantic mimicry and near-duplicate decoys. Their calibrated probabilities can stay confident under attack, so confidence gating is not a sufficient defense.

### Claims we must not make

- "first Jev MCP integration"
- "first Jev WebMCP implementation"
- "first RLCD tool selector"
- "first RLCD/Jev tool benchmark"
- "first adversarial study of Jev"
- "first selection-distribution attack metric"
- "first Jev vs LLM tool-selection comparison"

All have direct precedents (§2.3).

---

## 2.5 Architecture recommendation

**Recommendation:** implement **A (native LLM), B (matched decomposed LLM) and C (Jev)** as the core. Include **D (Laya)** as a *secondary* arm, restricted to candidate sets that fit Laya's option budget without trimming. Do not postpone Laya, because it is the only open-weight, locally reproducible RLCD selector.

| | A Native | B Matched LLM | C Jev | D Laya |
|---|---|---|---|---|
| Scientific value | real-world baseline; isolates the effect of decomposition (A vs B) | key control: separates decomposition from selector family | main RLCD arm; hosted production model | reproducible RLCD (open weights, local, deterministic) |
| Implementation complexity | low (provider tool-calling API) | low (`system-one-adapter` dependency) | low (`typesafe-sdk` dependency) | low–medium (thin wrapper; GPU or CPU; checkpoint pinning) |
| API/model availability | any FC model | OpenAI, Anthropic, Gemini, OpenAI-compatible | `TYPESAFE_API_KEY` or OpenRouter Decisions API; **model is an alias (`jev-latest`); pin `jev-1.13.x` if possible and log the returned `model`** | HF checkpoints `convaiinnovations/laya*`; pin revision hashes |
| Expected confounds | sees full schemas and a different prompt format; provider tool-serialization is hidden (see ContextBench lesson) | verbalized probabilities; provider default temperature unless set; `<document>` wrapper on state | no temperature control; alias drift; unpublished confidence formula; 255-option cap | **option budget 192–256 tokens, with trimming beyond about 20 options**; 512/1024-token context; confidence = 1 − normalized entropy (≠ Jev); English vs multilingual routing |
| Estimated cost | depends on model, roughly $0.25–$3 per M input tokens [prior] | same model as A × (1 selector call + 1 argument call) | about **$0.04 per M input tokens, output free** (jev-mcp-router README; jev-decision-benchmarks 10.75M tokens cost $0.45) | ≈ $0 marginal; GPU time |
| Reproducibility | medium (provider drift) | medium | low–medium (hosted alias; no seed) | **high** |

### Controls required by the evidence

1. **Explicit abstention in every arm.**
   - Choice has no native "none." Add a fixed `__none__` criterion with identical wording in B, C and D, following the WebMCP-extension pattern.
   - Give A an explicit no-tool path (`tool_choice: auto` plus a text answer counted as abstention).
2. **Opaque label keys.** Use keys like `t0..tN`, with the text `"name: description"`.
   - MSB name-collision attacks produce *duplicate names*, which collide as Choice keys.
   - Key-as-name versus opaque key should be a logged factor; WindTunnel and Laya use opaque keys, the dispatcher and WebMCP use names.
3. **The same model family everywhere.**
   - The same LLM (model and snapshot) serves as A's tool caller, B's selector and the shared argument generator for B, C and D.
   - Otherwise A vs B confounds decomposition with model.
4. **Schema visibility is a factor, not an accident.**
   - A necessarily sees schemas; B, C and D see what `candidate_representation` says.
   - Run B, C and D under both `name_description` and `name_description_schema`.
   - Choice criteria values may be JSON objects [code: `JSONContent`], so schemas can be placed *inside criteria* identically for Jev and the adapter.
   - Laya's option budget makes the schema variant infeasible beyond a few tools; log truncation.
5. **Probability semantics kept separate.** Record and report separately:
   - Jev native probabilities;
   - Laya probabilities;
   - adapter **verbalized** probabilities (`llm_answer_mode="probabilities"`);
   - **empirical frequencies** from N discrete-mode samples (adapter `discrete`, plus A with repeated sampling);
   - token logprobs when a provider exposes them.
   Never compare `confidence` across selectors: Jev/adapter use `(n·pmax−1)/(n−1)` and Laya uses 1 − normalized entropy.
6. **Explicit temperature.** Set it explicitly for every LLM call and log it. Jev exposes none; note this as an asymmetry.
7. **Identical `state`.** Use one JSON state, e.g. `{"user_request": ..., "history": [...]}`.
   - The adapter wraps it in `<document>` and adds an "untrusted data" system prompt. That is an inherent part of arm B and must be documented.
   - A gets the same content as the user turn.
8. **Verify the bytes sent.** Snapshot-test the exact serialized request body each arm sends, which addresses the ContextBench-MCP lesson. For A, also log the provider-side tool definitions exactly as submitted.

---

## 2.6 Dataset recommendation

| Dataset | Clean selection | Abstention | Similar-tool discrimination | Stateful execution | Real MCP execution | Metadata attacks | Security evaluation | End-to-end success | Notes |
|---|---|---|---|---|---|---|---|---|---|
| MetaTool (MIT) | ✔ | ✔ (Task2-Sub3) | ✔ (Task2-Sub1) | ✗ | ✗ | ✗ | ✗ | ✗ | **no input schemas, so selection only**; gold is always first in Sub1 → must shuffle |
| When2Call (Apache-2.0) | ~ (4-way) | ✔✔ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | has tool schemas; best abstention source |
| BFCL V4 (Apache-2.0) | ✔ (`multiple`, `live_multiple`) | ✔ (irrelevance) | ~ | ✔ multi-turn | ✗ | ✗ | ✗ | ~ | `multiple` is saturated for Jev (200/200) |
| MCP-Bench (license not detected) | ~ | ✗ | ~ | ✔ | ✔ | ✗ | ✗ | ✔ | needs license clarification before use [prior] |
| MCPMark (Apache-2.0) | ✗ | ✗ | ✗ | ✔ | ✔ (GitHub, Notion, FS, Postgres, Playwright) | ✗ | ✗ | ✔ | best end-to-end later [prior] |
| MCPTox (no license) | ✗ | ✗ | ✗ | ✗ | real tool *definitions* | ✔ | ✔ | ✗ | 1,312 valid instances; fetch at run time, don't redistribute |
| MSB (MIT) | ✗ | ✗ | ✔ (NC) | ~ | ✔ (local MCP servers) | ✔✔ (NC, PM) | ✔ | ✔ | best fit for the selector threat model |
| ToolSandbox (Apple license) | ~ | ✔ (insufficient info) | ✗ | ✔✔ | ✗ | ✗ | ✗ | ✔ | Apple custom license; design reference [prior] |
| ToolEmu (Apache-2.0) | ✗ | ✗ | ✗ | emulated | ✗ | ✗ | ✔ | ~ | LM-emulated; background only [prior] |
| AgentDojo (MIT) | ✗ | ✗ | ✗ | ✔ | ✗ | ✗ (injection is in tool *outputs*) | ✔ | ✔ | methodology: utility vs security [prior] |
| ToolBench (Apache-2.0) | ✔ (large) | ✗ | ~ | ✔ (RapidAPI) | ✗ | ✗ | ✗ | ✔ | large candidate spaces; retrieval [prior] |
| AnyToolBench (Apache-2.0) | ✔ (hierarchical) | ✗ | ~ | ✔ | ✗ | ✗ | ✗ | ✔ | scaling; critiques ToolBench's protocol [prior] |
| jev-mcp-router bench (MIT) | ✔ (649 real tools) | ✔ (3 no-tool requests) | ✔ (overlapping servers) | ✗ | real catalogs captured | ✗ | ✗ | ✗ | *newly found*; selection-only realism at scale |

### Recommendations

1. **Small clean dataset:** project fixtures (§12 of the brief), then **When2Call** (abstention, with schemas) plus **BFCL V4 `live_multiple`/`live_irrelevance`** (schemas, so arguments can be checked).
   - Use MetaTool Task2-Sub1 (similar tools) only with candidate-order shuffling, and for selection only, since it has no schemas.
2. **Realistic MCP set for external validity:**
   - **first**, the jev-mcp-router 25-server real `tools/list` catalog (selection-only, offline, MIT; labels need an independent audit);
   - **then** **MCPMark** (Filesystem and Postgres environments) for end-to-end runs.
   - Hold MCP-Bench until its license is clarified.
3. **Security dataset:** the **MSB tool-signature subset** (NC and PM metadata only, with response payloads stripped) as the primary attack dataset.
   - Use project-generated perturbations (mimic, length, decoy, order) on the clean sets as the controlled suite.
   - Use **MCPTox Template-1/2** as a secondary, clearly labeled "overt poisoning" set.
   - Note that in decomposed arms, MCPTox Template-3 payloads reach the argument LLM only if the poisoned tool is selected. That is a structural defense to *report*, not to hide.

---

## 2.7 Reproducibility and licensing audit (summary; details in `provenance.md`)

| Repo | License | SHA inspected | Use | Attribution | Data redistribution | Keys | Offline path |
|---|---|---|---|---|---|---|---|
| typesafe-ai/typesafe-sdk-python | MIT | e70bf99 | dependency (`typesafe-sdk==0.7.4`) | via package | n/a | TYPESAFE_API_KEY | ✗ (mock needed) |
| typesafe-ai/system-one-adapter-python | MIT | e1d4cc9 | dependency (`system-one-adapter==0.2.1`) | via package | n/a | provider keys | fake-model tests exist |
| NandhaKishorM/laya | Apache-2.0 | 432312b | dependency (`laya==0.4.7`) | NOTICE if copied | HF weights; check model card | none | ✔ |
| ZimmyGao/openjev-rlcd | MIT | 22db40a | reference | cite paper | ✔ | n/a | ✔ |
| nekuda-ai/WindTunnel | Apache-2.0 | 5ca8644 | reference; patterns may be adapted | ✔ if adapted | results are redacted | TypeSafe, Inception | fixture checks |
| sdras/jev-webmcp-extension | Apache-2.0 | 1ec3afb | reference | ✔ if adapted | n/a | TypeSafe | mock platform |
| abhishekashokvkumar/jev-mcp-dispatcher | **none** | 3527964 | **reference only** | cite | ✗ | TypeSafe | ✗ |
| baibizhe/jev-decision-benchmarks | **none** | 32705c3 | **reference only** | cite | ✗ | n/a | ✔ tables |
| ini8labs/jev-mcp-router | MIT | 168bbce | **adapt bench catalog and requests** | ✔ required | ✔ (MIT) | OpenRouter | `JEV_FAKE=1` |
| dongsenzhang/MSB | MIT | c1d6a70 | adapt NC/PM metadata | ✔ required | ✔ | LLM keys | partly |
| zhiqiangwang4/MCPTox-Benchmark | **none** | f85189f | fetch at run time, pinned by SHA-256 | cite | **✗ do not vendor** | n/a | ✔ after fetch |
| stefanoamorelli/inspect-evals-mcptox | MIT | d45705b | reference for loader and hash pinning | ✔ if adapted | n/a | judge model | tests offline |
| HowieHwong/MetaTool | MIT | 35e81bb | dataset adapter | ✔ | ✔ | n/a | ✔ |
| NVIDIA/When2Call | Apache-2.0 | ecc8d42 | dataset adapter | ✔ | ✔ (check 3rd-party licenses file) | n/a | ✔ |
| modelcontextprotocol/python-sdk | MIT | 754254c (release v2.3.0) | dependency | via package | n/a | n/a | ✔ |

---

## Verified premise corrections to the brief

- The brief lists `apple-aiml-research/ToolSandbox`. It resolves to the same commit as `apple/ToolSandbox`, under a **custom Apple license (NOASSERTION)**, not OSI.
- No license was detected for `Accenture/mcp-bench`, `MCPTox-Benchmark`, `jev-mcp-dispatcher`, `jev-decision-benchmarks` or `ContextBench-MCP`. All of these are **reference-only** unless the authors clarify.
- MCP Python SDK is now **v2.x** (v2.3.0, 2026-10-02), and MCP spec `2026-07-28` is current. Re-verify the `list_tools`/`call_tool` API names at Phase 3 rather than assuming 1.x APIs.
- Jev is also served through **OpenRouter's Decisions API** (`/api/alpha/decisions`, model `typesafe/jev-latest`). Model identity must be logged per call.

## Not inspected at code level (this review relied on README, license metadata or prior knowledge)

- MCP-Bench, MCPMark, ToolSandbox, ToolEmu, AgentDojo, ToolBench, AnyTool, ToolNet;
- BFCL source code;
- openai-agents-python MCP conversion;
- MCP SDK client APIs;
- mcp-scan;
- `nyit-vancouver/mcp-security` contents;
- `shihe98/Security_Privacy_Jev`;
- the full ToolTweak, AMA and ToolHijacker PDFs.

These are marked [prior] or [secondary] above. They do not change the novelty finding, but the specific numbers must be re-checked before they are cited.

---

```text
Recommended novelty statement:
  Matched-contract comparison of LLM vs RLCD (Jev, Laya) tool selectors under
  protocol-valid, attacker-owned MCP tool-metadata manipulation, measuring
  selection-distribution shift with each selector's probability semantics kept
  distinct, and separating the effect of decomposition (native vs decomposed
  LLM) from the effect of selector family (LLM vs RLCD). (See §2.4 "Main".)

Recommended experimental arms:
  A Native LLM, B Matched decomposed LLM (system-one-adapter), C Jev — core.
  D Laya — secondary, restricted to candidate sets within its option budget
  (truncation logged; trimmed runs excluded from primary analysis).
  One LLM model/snapshot shared by A, B-selector, and the B/C/D argument generator.

Recommended clean dataset:
  Project fixtures → When2Call + BFCL V4 live_multiple/live_irrelevance;
  MetaTool Task2-Sub1 only with order shuffling (selection-only).

Recommended attack dataset:
  MSB tool-signature subset (Name Collision, Preference Manipulation; metadata
  only) + project-owned seeded perturbations; MCPTox Template-1/2 as secondary
  "overt poisoning" set (fetched at runtime, not redistributed).

Recommended MCP validation environment:
  jev-mcp-router's 25-server real tools/list catalog (selection-only, offline)
  first; MCPMark Filesystem/Postgres for end-to-end later.

Largest unresolved confound:
  Probability semantics differ by arm. Jev and Laya return native readout
  distributions (with different confidence formulas). The LLM adapter returns
  verbalized probabilities, and native tool calling returns none. ΔP(attacker)
  is therefore not commensurable across families, so the primary cross-family
  attack metric must be empirical selection frequency under repeated sampling
  (and the Jev/Laya argmax, which is deterministic per input), with native
  probabilities used as a within-family analysis only. Second largest: arm A
  necessarily sees full schemas in a provider-specific serialization, while
  B/C/D see the configured representation.

GO / NO-GO recommendation:
  GO, with the narrowed scope above. Phase 1 (offline core, mocks, fixtures,
  serialization snapshot tests) can start on approval; no paid API calls are
  needed until Phase 2.
```

## Decisions needed from you before Phase 1

1. Approve or adjust the novelty statement and the arm set: A, B, C core with D secondary.
2. Choose the shared LLM for A, the B selector and the argument generation. This determines cost and which logprob options exist.
3. Approve adapting the MIT-licensed jev-mcp-router catalog and the MSB NC/PM metadata (both require attribution). Confirm MCPTox is fetch-only.
4. Confirm whether Jev access goes through TypeSafe directly or OpenRouter, and whether a pinned Jev version (`jev-1.13.x`) is available to you.
