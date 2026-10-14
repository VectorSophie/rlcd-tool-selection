# References

Snapshot: 2026-10-14. Evidence tags match those in `RESEARCH_REVIEW.md`:

- **[code]**: read the source at the pinned SHA.
- **[readme]**: README or docs at the pinned SHA.
- **[paper]**: arXiv abstract or HTML.
- **[secondary]**: a search summary or third party.
- **[prior]**: background knowledge, not re-read for this review.

## RLCD / System One / Jev core

- **TypeSafe Python SDK.** `typesafe-ai/typesafe-sdk-python` @ e70bf99a, v0.7.4 (2026-10-09), MIT. https://github.com/typesafe-ai/typesafe-sdk-python [code]
- **TypeSafe docs, Choice primitive.** https://docs.typesafe.ai/primitives/choice, fetched 2026-10-14. Up to 255 options; probabilities sum to 1; the confidence formula is not documented; nothing on adversarial state or criteria; nothing on temperature. [readme]
- **System One Adapter.** `typesafe-ai/system-one-adapter-python` @ e1d4cc93, v0.2.1, MIT. https://github.com/typesafe-ai/system-one-adapter-python [code]
- **OpenJev-RLCD: A Working RLCD Implementation.** Zhimin Gao, Pichao Wang. arXiv:2609.38850. Code: `ZimmyGao/openjev-rlcd` @ 22db40ad, MIT. [readme]
- **Laya.** `NandhaKishorM/laya` @ 432312b3, v0.4.7, Apache-2.0. https://github.com/NandhaKishorM/laya. Checkpoints: HF `convaiinnovations/laya`, `laya-multilingual`, `laya-typed-decisions`. [code/readme]
- **Hidden Risks of Jev: An Empirical Study of Security, Privacy, and Dual Use.** Wang, Zhu, Chen, Li, Yang, Liu. arXiv:2610.04985 (2026-10-04). Code: `shihe98/Security_Privacy_Jev` (not inspected). [paper]
- **Calibrated Decision Models for Autonomous Penetration-Testing Harnesses: JEV and Laya as System One Decision Layers for LLM-Driven Pentest Agents.** J. A. dos Santos. arXiv:2609.28940. A position paper with one uncontrolled case study. [paper]

## Direct Jev / Laya + tool / MCP / WebMCP precedents

- **WindTunnel.** `nekuda-ai/WindTunnel` @ 5ca8644e, Apache-2.0. See `experiments/jev/`, `docs/SPEC.md` §6 and `results/2026-09-18-jev-mercury/PROVENANCE.md`. [code]
- **Jev × WebMCP extension.** `sdras/jev-webmcp-extension` @ 1ec3afb6, Apache-2.0. [code]
- **Jev MCP dispatcher.** `abhishekashokvkumar/jev-mcp-dispatcher` @ 35279642, no license. [code]
- **Jev decision benchmarks.** `baibizhe/jev-decision-benchmarks` @ 32705c33, no license. [readme/data]
- **jev-mcp-router** (newly found). `ini8labs/jev-mcp-router` @ 168bbce8, MIT. [code/readme]
- **nitro** (newly found). `daniel-farina/nitro` @ 99b8749d, no license detected. [readme]
- **openclaw-jev-router** (newly found). `larches-technologies/openclaw-jev-router` @ 588a823f, MIT. [readme]
- **jev-mcp, Jev-vs-LLM judgment harness** (newly found). `arunav25/jev-mcp` @ dcd5e5fe, MIT. [readme]
- **jev-benchmarks** (newly found). `AbdelStark/jev-benchmarks` @ 0d610cc5, Apache-2.0. Classification calibration study; not about tools. [readme]
- **gentle-jev-lab.** `jorgehara/gentle-jev-lab` @ a0cd44fa, no license. [readme]
- **Discovered but not inspected:** `jangya/jev-webmcp`, `jkudish/jev-mcp`, `blakestone-x/jev-mcp`, the ~15 `*/laya-mcp` repos, `jakenbear/the-jev-enator` (issue #34), `wso2/api-platform` issue #3552 (Jev tool filtering), and `sseshachala/conductai` issue #2139 (Jev for tool selection). [secondary]

## MCP infrastructure

- **MCP Python SDK.** `modelcontextprotocol/python-sdk` @ 754254c0, latest release v2.3.0 (2026-10-02), MIT. [readme/metadata]
- **Microsoft MCP Gateway.** `microsoft/mcp-gateway` @ f57c4f04, MIT.
  - PR #93 "Add optional pre-execution judgment gate" (closed, unmerged).
  - Issue #108 "Detect tool-definition changes" (open).
  - PR #36 "tool-router gateway" (closed).
  - [metadata]
- **OpenAI Agents Python.** `openai/openai-agents-python` @ 1c1a28df, MIT. [metadata only]

## Tool-selection and tool-use benchmarks

- **MetaTool.** Huang et al., arXiv:2310.03128 (ICLR 2024). `HowieHwong/MetaTool` @ 35e81bb7, MIT. [code/data]
- **When2Call.** Ross et al., NAACL 2025. `NVIDIA/When2Call` @ ecc8d423, Apache-2.0. [data/metadata]
- **BFCL V4.** Patil et al., Berkeley Function Calling Leaderboard. `ShishirPatil/gorilla` @ 6ea57973, Apache-2.0. Leaderboard: https://gorilla.cs.berkeley.edu/leaderboard [prior/metadata]
- **MCP-Bench.** Accenture, arXiv:2508.20453. `Accenture/mcp-bench` @ 7a8eaeae, no license file detected. [prior/metadata]
- **MCPMark.** arXiv:2509.24002. `eval-sys/mcpmark` @ cd45b7f5, Apache-2.0, release v1.2.0. [prior/metadata]
- **ToolSandbox.** Lu et al., arXiv:2408.04682. `apple/ToolSandbox` @ c8571d78, Apple custom license. [prior/metadata]
- **ToolBench / ToolLLM.** Qin et al., arXiv:2307.16789. `OpenBMB/ToolBench` @ d56fdd89, Apache-2.0. [prior/metadata]
- **AnyTool.** Du et al., arXiv:2402.04253. `dyabel/AnyTool` @ 6202212c, Apache-2.0. [prior/metadata]
- **ToolNet.** Liu et al., arXiv:2403.00839. [prior]
- **ToolSelect-Bench (ASM).** `YE-YI7/asm-spec` @ a3710eff, `benchmark/`, MIT. [readme]
- **ContextBench-MCP.** `master-senses/ContextBench-MCP` @ 828e59a6, no license. Its README states that re-serialization invalidated the study. [readme]

## Security, poisoning, agent safety

- **MCPTox.** Wang et al., arXiv:2508.14925 (AAAI 2026). `zhiqiangwang4/MCPTox-Benchmark` @ f85189f9, no license. [data]
- **inspect-evals-mcptox.** `stefanoamorelli/inspect-evals-mcptox` @ d45705b0, MIT. [readme]
- **MCP Security Bench (MSB).** Zhang et al., ICLR 2026, arXiv:2510.15994. `dongsenzhang/MSB` @ c1d6a701, MIT. [code]
- **MCP Threat Modeling and Analyzing Vulnerabilities to Prompt Injection with Tool Poisoning.** Huang, Huang, Tran, Milani Fard. arXiv:2603.22489. Repo `nyit-vancouver/mcp-security` @ 9c354050, no license. [paper]
- **Invariant Labs, "MCP Security Notification: Tool Poisoning Attacks"** (2025 disclosure) and `invariantlabs-ai/mcp-scan` @ 2d3ca361, Apache-2.0. [prior/metadata]
- **MCP-ITP: An Automated Framework for Implicit Tool Poisoning in MCP.** arXiv:2601.07395 (2026-01-12). [paper/secondary]
- **Think Twice Before You Act: Protecting LLM Agents Against Tool Description Poisoning via Isolated Planning.** Shi et al., ICML 2026, arXiv:2606.20922. [secondary]
- **AgentDojo.** Debenedetti et al., arXiv:2406.13352 (NeurIPS 2024 D&B). `ethz-spylab/agentdojo` @ 089ed468, MIT. [prior/metadata]
- **ToolEmu.** Ruan et al., arXiv:2309.15817 (ICLR 2024). `ryoungj/ToolEmu` @ ac4a7ab7, Apache-2.0. [prior/metadata]
- **ToolTweak: An Attack on Tool Selection in LLM-based Agents.** Sneh et al., arXiv:2510.02554. [paper/secondary]
- **Tool Preferences in Agentic LLMs are Unreliable.** Faghih et al., EMNLP 2025, arXiv:2505.18135. [paper/secondary]
- **Attractive Metadata Attack: Inducing LLM Agents to Invoke Malicious Tools.** Mo et al., NeurIPS 2025, arXiv:2508.02110. [paper/secondary]
- **Prompt Injection Attack to Tool Selection in LLM Agents (ToolHijacker).** Shi et al., NDSS 2026, arXiv:2504.19793. [paper/secondary]
- **Semantic Attacks on Tool-Augmented LLMs: Securing the Model Context Protocol Against Descriptor-Level Manipulation.** Jamshidi et al., arXiv:2512.06556. [paper]
- **MCP-38: A Comprehensive Threat Taxonomy for MCP Systems.** arXiv:2603.18063. [secondary]
- **Same Payload, Different Channel: Measuring Trust Asymmetry in Tool-Using Language Models.** arXiv:2606.00566. Found in search; not reviewed. [secondary]
