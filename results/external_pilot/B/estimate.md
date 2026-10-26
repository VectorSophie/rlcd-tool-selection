# External pilot cost estimate

Conservative estimate (chars/3 tokens, fixed output allowances, x1.25 margin, live OpenRouter prices). Argument generation is assumed for every decomposed task.

| group | dataset | tasks | condition | arm | selection $ | arguments $ | total $ |
|---|---|---|---|---|---|---|---|
| B | bfcl_simple_python | 100 | architecture_matched_v1 | native_llm | 0.1671 | 0.0000 | 0.1671 |
| B | bfcl_simple_python | 100 | architecture_matched_v1 | matched_llm | 0.1197 | 0.1616 | 0.2814 |
| B | bfcl_simple_python | 100 | architecture_matched_v1 | jev | 0.0135 | 0.1616 | 0.1752 |
| B | bfcl_irrelevance | 100 | architecture_matched_v1 | native_llm | 0.1658 | 0.0000 | 0.1658 |
| B | bfcl_irrelevance | 100 | architecture_matched_v1 | matched_llm | 0.1184 | 0.1603 | 0.2787 |
| B | bfcl_irrelevance | 100 | architecture_matched_v1 | jev | 0.0130 | 0.1603 | 0.1733 |

| group | estimate $ | cap $ |
|---|---|---|
| B | 1.2415 | 1.8622 |

**Total estimate: $1.2415** (approved limit $10.00).
