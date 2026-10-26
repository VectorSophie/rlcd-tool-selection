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

| group | estimate $ | cap $ |
|---|---|---|
| A | 2.8021 | 4.2031 |

**Total estimate: $2.8021** (approved limit $10.00).
