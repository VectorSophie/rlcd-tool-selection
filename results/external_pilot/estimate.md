# External pilot cost estimate

Conservative estimate (chars/3 tokens, fixed output allowances, x1.25 margin, live OpenRouter prices). Argument generation is assumed for every decomposed task.

| group | dataset | tasks | condition | arm | selection $ | arguments $ | total $ |
|---|---|---|---|---|---|---|---|
| A | when2call | 150 | architecture_matched_v1 | native_llm | 0.3950 | 0.0000 | 0.3950 |
| A | when2call | 150 | architecture_matched_v1 | matched_llm | 0.3207 | 0.2780 | 0.5988 |
| A | when2call | 150 | architecture_matched_v1 | jev | 0.0796 | 0.2780 | 0.3576 |
| A | metatool_s1 | 100 | ecological_name_description_v1 | native_llm | 0.2411 | 0.0000 | 0.2411 |
| A | metatool_s1 | 100 | ecological_name_description_v1 | matched_llm | 0.1513 | 0.1542 | 0.3055 |
| A | metatool_s1 | 100 | ecological_name_description_v1 | jev | 0.0268 | 0.1542 | 0.1810 |
| A | metatool_s3 | 100 | ecological_name_description_v1 | native_llm | 0.2393 | 0.0000 | 0.2393 |
| A | metatool_s3 | 100 | ecological_name_description_v1 | matched_llm | 0.1496 | 0.1540 | 0.3036 |
| A | metatool_s3 | 100 | ecological_name_description_v1 | jev | 0.0261 | 0.1540 | 0.1801 |
| B | bfcl_simple_python | 100 | architecture_matched_v1 | native_llm | 0.1671 | 0.0000 | 0.1671 |
| B | bfcl_simple_python | 100 | architecture_matched_v1 | matched_llm | 0.1197 | 0.1616 | 0.2814 |
| B | bfcl_simple_python | 100 | architecture_matched_v1 | jev | 0.0135 | 0.1616 | 0.1752 |
| B | bfcl_irrelevance | 100 | architecture_matched_v1 | native_llm | 0.1658 | 0.0000 | 0.1658 |
| B | bfcl_irrelevance | 100 | architecture_matched_v1 | matched_llm | 0.1184 | 0.1603 | 0.2787 |
| B | bfcl_irrelevance | 100 | architecture_matched_v1 | jev | 0.0130 | 0.1603 | 0.1733 |
| C | bfcl_live_simple | 100 | architecture_matched_v1 | native_llm | 0.1774 | 0.0000 | 0.1774 |
| C | bfcl_live_simple | 100 | architecture_matched_v1 | matched_llm | 0.1300 | 0.1720 | 0.3020 |
| C | bfcl_live_simple | 100 | architecture_matched_v1 | jev | 0.0179 | 0.1720 | 0.1898 |
| C | bfcl_live_irrelevance | 100 | architecture_matched_v1 | native_llm | 0.2325 | 0.0000 | 0.2325 |
| C | bfcl_live_irrelevance | 100 | architecture_matched_v1 | matched_llm | 0.1841 | 0.1959 | 0.3800 |
| C | bfcl_live_irrelevance | 100 | architecture_matched_v1 | jev | 0.0406 | 0.1959 | 0.2365 |

| group | estimate $ | cap $ |
|---|---|---|
| A | 2.8021 | 4.2031 |
| B | 1.2415 | 1.8622 |
| C | 1.5182 | 2.2774 |

**Total estimate: $5.5618** (approved limit $10.00).
