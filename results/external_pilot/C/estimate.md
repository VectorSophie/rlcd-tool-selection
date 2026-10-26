# External pilot cost estimate

Conservative estimate (chars/3 tokens, fixed output allowances, x1.25 margin, live OpenRouter prices). Argument generation is assumed for every decomposed task.

| group | dataset | tasks | condition | arm | selection $ | arguments $ | total $ |
|---|---|---|---|---|---|---|---|
| C | bfcl_live_simple | 100 | architecture_matched_v1 | native_llm | 0.1774 | 0.0000 | 0.1774 |
| C | bfcl_live_simple | 100 | architecture_matched_v1 | matched_llm | 0.1300 | 0.1720 | 0.3020 |
| C | bfcl_live_simple | 100 | architecture_matched_v1 | jev | 0.0179 | 0.1720 | 0.1898 |
| C | bfcl_live_irrelevance | 100 | architecture_matched_v1 | native_llm | 0.2325 | 0.0000 | 0.2325 |
| C | bfcl_live_irrelevance | 100 | architecture_matched_v1 | matched_llm | 0.1841 | 0.1959 | 0.3800 |
| C | bfcl_live_irrelevance | 100 | architecture_matched_v1 | jev | 0.0406 | 0.1959 | 0.2365 |

| group | estimate $ | cap $ |
|---|---|---|
| C | 1.5182 | 2.2774 |

**Total estimate: $1.5182** (approved limit $10.00).
