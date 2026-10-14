# Provenance

Every repository below was fetched on **2026-10-14** with `git ls-remote` or a shallow clone. Nothing has been copied into this project yet; every "Planned use" entry is a proposal awaiting approval.

Legend for **Planned use**:

- **dep**: a pinned package dependency.
- **adapt**: a modified copy, with attribution.
- **data**: a dataset adapter.
- **fetch**: downloaded at run time, verified by hash, and not redistributed.
- **ref**: reference only, nothing copied.

## Repositories inspected at code or data level

| Repo | Commit SHA | Last commit | License | Files inspected | Planned use | Attribution required | Data redistribution | API keys | Offline path |
|---|---|---|---|---|---|---|---|---|---|
| typesafe-ai/typesafe-sdk-python | e70bf99a89f27102247613bcd5d1aa8923a1cda9 | 2026-10-09 | MIT (the LICENSE file has an unfilled `[year] [fullname]` template header; pyproject says MIT) | README.md, pyproject.toml, docs/changelog.md, src/typesafe_sdk/{__init__, constants}.py, _core/{question_types, response_types, retry, endpoints, constants}.py, _schemas/models.py | dep `typesafe-sdk==0.7.4` | license notice via package | n/a | TYPESAFE_API_KEY (or OpenRouter) | no; a mock selector is required |
| typesafe-ai/system-one-adapter-python | e1d4cc938204b22fc5a3c3aca7044072fe3f712d | 2026-09-22 | MIT | README.md, docs/changelog.md, src/system_one_adapter/{_client, _schema}.py, _utils/{probability_normalization, confidence_metrics}.py; file list of providers/ and tests/ | dep `system-one-adapter==0.2.1` | via package | n/a | OpenAI / Anthropic / Gemini | `tests/test_client_with_fake_model.py` pattern |
| ZimmyGao/openjev-rlcd | 22db40ad3333f5cf0bc5139097da70e0f8c05018 | 2026-10-01 | MIT | README.md, LICENSE, layout | ref (methodology) | cite paper | ✔ | none | ✔ |
| NandhaKishorM/laya | 432312b36714d8889eba405507b37eda25257d9c | 2026-10-14 | Apache-2.0 | README.md (install, quickstart, Jev differences, server), laya/integrations/llamaindex.py (`_format_choices_criteria`), laya/common.py (`build_head`, `option_order`, truncation), laya/serve.py header, research/results/position_sensitivity_multilingual.json | dep `laya==0.4.7`; thin `LayaSelector` | NOTICE if code is copied (not planned) | weights on HF, check the model card | none | ✔ local |
| nekuda-ai/WindTunnel | 5ca8644e23826ebb30108e7bad240b61043bfe67 | 2026-09-18 | Apache-2.0 | README.md, docs/SPEC.md §6, experiments/jev/README.md, experiments/jev/source-manifest.json, experiments/jev/webmcp/{arm, mercury}.mjs, experiments/jev/frozen/arms/{decision-agent, decision-providers}.mjs, results/2026-09-18-jev-mercury/PROVENANCE.md, results/model-comparison.md | ref; patterns may be adapted (opaque labels, abstain option, argument prompt) | ✔ if adapted | results are redacted | TypeSafe, Inception | fixture checks |
| sdras/jev-webmcp-extension | 1ec3afb6cebf116d811a3c8a073414edaf5cb67c | 2026-09-20 | Apache-2.0 (vendor/lz-string is MIT) | README.md, src/core/{questions, screen, policy}.js, evals/run.js; file list of src/, test/ | ref; abstain wording may be adapted | ✔ if adapted | n/a | TypeSafe | mock platform harness |
| abhishekashokvkumar/jev-mcp-dispatcher | 35279642cf6784a38ebb6c289f4ad3f3edd72d07 | 2026-09-18 | **none** | README.md, jev_mcp_dispatcher.py (selection, enum, split code paths), requirements.txt | **ref only** | cite | ✗ | TypeSafe | ✗ |
| baibizhe/jev-decision-benchmarks | 32705c33920b710c11593c8ef99e557d450f933b | 2026-09-20 | **none** | README.md, data/metatool/protocol.json, data/bfcl/summary.json, reports/bfcl.zh-CN.md (grep) | **ref only** | cite | ✗ | n/a | ✔ (tables) |
| ini8labs/jev-mcp-router | 168bbce8112c5543243edd3fbd2ada2b71cace16 | 2026-10-04 | MIT | README.md, tool_hints.json (head), bench/run.py (grep), jevmcp/jev.py (grep), bench/ listing | **adapt** `bench/catalog/*` and `bench/requests.jsonl` | ✔ required (MIT notice) | ✔ | OpenRouter / TypeSafe | `JEV_FAKE=1` |
| dongsenzhang/MSB | c1d6a70171e4d2c44c87a2ae909d13df00c6aa8d | 2026-03-24 | MIT | README.md, LICENSE.txt, metrics.py (grep), data/attack_type.jsonl, data/tools/attack_tools/office_assistance/Office_Word_Document_Server/word_document_server/attack.py (NC, PM) | **adapt** NC/PM tool metadata only | ✔ required | ✔ | LLM keys (not needed for metadata) | ✔ for metadata |
| zhiqiangwang4/MCPTox-Benchmark | f85189f9ad12504c197c7f920ab818a40657b1fa | 2025-12-03 | **none** | README.md (contains only "# AAAI26"), pure_tool.json (schema, counts) | **fetch** pinned by SHA-256 | cite | **✗** | none | ✔ after fetch |
| stefanoamorelli/inspect-evals-mcptox | d45705b0a7ae6697c851e311187b06bf7488b13f | 2026-06-04 | MIT | README.md, file list | ref (loader and hash-pin pattern) | ✔ if adapted | does not redistribute | judge model | tests |
| HowieHwong/MetaTool | 35e81bb7576826e980c80fed8f8c0a2b4a1e6fbb | 2024-03-22 | MIT | LICENSE, dataset/ listing, dataset/tmp_dataset/Task2-Subtask1.json (first record) | data | ✔ | ✔ | none | ✔ |
| NVIDIA/When2Call | ecc8d42388e91ab37e7e737d48e16e8ecea3d1dc | 2025-04-29 | Apache-2.0 (+ LICENSE-3rd-party.txt to review) | LICENSE.txt, data/ listing | data | ✔ | review the 3rd-party file | none | ✔ |
| YE-YI7/asm-spec | a3710eff6f881b8ce4286f63281b87fe2a3c7be1 | 2026-10-05 | MIT | benchmark/README.md | ref | — | — | OpenRouter | ✔ |
| master-senses/ContextBench-MCP | 828e59a64682f05625a47968222246ec1b48b83b | 2026-05-31 | **none** | README.md | ref (cautionary example) | cite | ✗ | — | — |
| daniel-farina/nitro | 99b8749d3474fd30cbbeed5f0e859f8266d7c180 | 2026-09-20 | none detected | README.md | ref | — | — | — | — |
| arunav25/jev-mcp | dcd5e5feca6167c2f4ae7b4ffd4c40ed14e99cc7 | 2026-09-21 | MIT | README.md | ref | — | — | — | — |
| larches-technologies/openclaw-jev-router | 588a823f1620abc826685c7abd28c520ce8816c7 | 2026-09-20 | MIT | README.md | ref | — | — | — | — |
| AbdelStark/jev-benchmarks | 0d610cc53e79bcbec691312b0c4adb4a0e371642 | 2026-09-17 | Apache-2.0 | README.md | ref | — | — | — | — |
| jorgehara/gentle-jev-lab | a0cd44fa66bace99e8d050848f37f85359417967 | 2026-09-20 | none | README.md | ref | — | — | — | — |

## Repositories pinned (HEAD SHA) but checked only for metadata or license

| Repo | HEAD SHA | License | Notes |
|---|---|---|---|
| modelcontextprotocol/python-sdk | 754254c08fe1c3eda18b69da3d336106fe8d72d6 | MIT | release v2.3.0 (2026-10-02); re-verify client API at Phase 3 |
| microsoft/mcp-gateway | f57c4f049dcc7bb5a56fe1f06efa85647c52a225 | MIT | PR #93, PR #36 and issue #108 read; no code inspected |
| openai/openai-agents-python | 1c1a28df92f359dded4eed83976301c2f9850e89 | MIT | not inspected |
| ShishirPatil/gorilla (BFCL) | 6ea57973c7a6097fd7c5915698c54c17c5b1b6c8 | Apache-2.0 | not inspected |
| Accenture/mcp-bench | 7a8eaeae83a842a2949080acc5473f65e1569daf | **none detected** | top-level listing only |
| eval-sys/mcpmark | cd45b7f57923b9b3985467f5139927575f83141c | Apache-2.0 | release v1.2.0 |
| apple/ToolSandbox (= apple-aiml-research/ToolSandbox) | c8571d7854316d2e1c5f288e59fe1e34e53f6dd1 | Apple custom (NOASSERTION) | the two names resolve to the same SHA |
| OpenBMB/ToolBench | d56fdd89faf8c91fa135090b212bb9057ee5cfc2 | Apache-2.0 | |
| dyabel/AnyTool | 6202212ce45329282cf812ae48427f8765cf164c | Apache-2.0 | |
| nyit-vancouver/mcp-security | 9c354050e9f911a55f6bbf8aa94274ce0ca5fc03 | none detected | |
| invariantlabs-ai/mcp-scan | 2d3ca361e33452dcfb8e74f7b7db6db0ee08d59e | Apache-2.0 | |
| ethz-spylab/agentdojo | 089ed468cf3ed0322acc66b0211f26d9d90dbf60 | MIT | |
| ryoungj/ToolEmu | ac4a7ab7ed8c7985d96231e214bd6b54304b7ddb | Apache-2.0 | |

## Model / service versions observed (to pin at Phase 2)

- **Jev:** the default alias is `jev-latest` (SDK `DEFAULT_MODEL`).
  - WindTunnel asserted `jev-1.13.0`.
  - jev-decision-benchmarks recorded `typesafe/jev-1.13-20260917` via the OpenRouter Decisions API.
  - Log the response `model` field on every call.
- **Laya:** HF `convaiinnovations/laya` (ModernBERT-large, 421M, 512 ctx), `laya-multilingual` (mmBERT-base, 322M, 1024–8192 ctx) and `laya-typed-decisions`. Pin HF revision hashes at Phase 2.
- **Mercury 2.5** (WindTunnel's argument model): not planned for use.
