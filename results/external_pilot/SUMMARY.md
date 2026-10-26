# External benchmark pilot: summary

Pilot observations only. Rates show Wilson 95% intervals. When2Call rows from one upstream item are correlated (clusters reported), so its intervals are optimistic. MetaTool runs under the name + description condition (no source schemas) and is not pooled with schema-bearing datasets. BFCL `live_relevance` (sanity only) and the BFCL diagnostic subsets are not part of these results.

- Records: 2250 (2250 runs, 0 aborted)
- Provider calls: {'anthropic/claude-haiku-4.5': 2329, 'typesafe/jev-1.13-20260917': 7500}
- Cost: $3.2232 actual vs $5.5618 estimated (ratio 0.58)
- Manifests: A `f300e18e9399`, B `513e54111c7d`, C `56c70adcd7f3`

## Results by dataset and arm

| dataset | arm | selection accuracy | task success | grounded task success | abstained | selector err | arg err | exec err |
|---|---|---|---|---|---|---|---|---|
| bfcl_irrelevance | native_llm | 88% [80%, 93%] (n=100) | 88% [80%, 93%] (n=100) | 88% [80%, 93%] (n=100) | 88% [80%, 93%] (n=100) | 2% [1%, 7%] (n=100) | 0% [0%, 28%] (n=10) | 0% [0%, 28%] (n=10) |
| bfcl_irrelevance | matched_llm | 88% [80%, 93%] (n=100) | 88% [80%, 93%] (n=100) | 88% [80%, 93%] (n=100) | 88% [80%, 93%] (n=100) | 0% [0%, 4%] (n=100) | 8% [1%, 35%] (n=12) | 9% [2%, 38%] (n=11) |
| bfcl_irrelevance | jev | 93% [86%, 97%] (n=100) | 93% [86%, 97%] (n=100) | 93% [86%, 97%] (n=100) | 93% [86%, 97%] (n=100) | 0% [0%, 4%] (n=100) | 14% [3%, 51%] (n=7) | 17% [3%, 56%] (n=6) |
| bfcl_live_irrelevance | native_llm | 86% [78%, 91%] (n=100) | 86% [78%, 91%] (n=100) | 86% [78%, 91%] (n=100) | 86% [78%, 91%] (n=100) | 1% [0%, 5%] (n=100) | 0% [0%, 23%] (n=13) | 0% [0%, 23%] (n=13) |
| bfcl_live_irrelevance | matched_llm | 80% [71%, 87%] (n=100) | 80% [71%, 87%] (n=100) | 80% [71%, 87%] (n=100) | 80% [71%, 87%] (n=100) | 0% [0%, 4%] (n=100) | 0% [0%, 16%] (n=20) | 30% [15%, 52%] (n=20) |
| bfcl_live_irrelevance | jev | 79% [70%, 86%] (n=100) | 79% [70%, 86%] (n=100) | 79% [70%, 86%] (n=100) | 79% [70%, 86%] (n=100) | 0% [0%, 4%] (n=100) | 0% [0%, 15%] (n=21) | 33% [17%, 55%] (n=21) |
| bfcl_live_simple | native_llm | 93% [86%, 97%] (n=100) | 86% [78%, 91%] (n=100) | 86% [78%, 91%] (n=100) | 6% [3%, 12%] (n=100) | 1% [0%, 5%] (n=100) | 0% [0%, 4%] (n=93) | 0% [0%, 4%] (n=93) |
| bfcl_live_simple | matched_llm | 97% [92%, 99%] (n=100) | 89% [81%, 94%] (n=100) | 89% [81%, 94%] (n=100) | 3% [1%, 8%] (n=100) | 0% [0%, 4%] (n=100) | 1% [0%, 6%] (n=97) | 0% [0%, 4%] (n=96) |
| bfcl_live_simple | jev | 95% [89%, 98%] (n=100) | 87% [79%, 92%] (n=100) | 87% [79%, 92%] (n=100) | 5% [2%, 11%] (n=100) | 0% [0%, 4%] (n=100) | 1% [0%, 6%] (n=95) | 0% [0%, 4%] (n=94) |
| bfcl_simple_python | native_llm | 99% [95%, 100%] (n=100) | 97% [92%, 99%] (n=100) | 97% [92%, 99%] (n=100) | 1% [0%, 5%] (n=100) | 0% [0%, 4%] (n=100) | 0% [0%, 4%] (n=99) | 0% [0%, 4%] (n=99) |
| bfcl_simple_python | matched_llm | 100% [96%, 100%] (n=100) | 98% [93%, 99%] (n=100) | 98% [93%, 99%] (n=100) | 0% [0%, 4%] (n=100) | 0% [0%, 4%] (n=100) | 0% [0%, 4%] (n=100) | 0% [0%, 4%] (n=100) |
| bfcl_simple_python | jev | 99% [95%, 100%] (n=100) | 97% [92%, 99%] (n=100) | 97% [92%, 99%] (n=100) | 1% [0%, 5%] (n=100) | 0% [0%, 4%] (n=100) | 0% [0%, 4%] (n=99) | 0% [0%, 4%] (n=99) |
| metatool_s1 | native_llm | 56% [46%, 65%] (n=100) | 56% [46%, 65%] (n=100) | 56% [46%, 65%] (n=100) | 33% [25%, 43%] (n=100) | 2% [1%, 7%] (n=100) | 0% [0%, 6%] (n=65) | 0% [0%, 6%] (n=65) |
| metatool_s1 | matched_llm | 78% [69%, 85%] (n=100) | 78% [69%, 85%] (n=100) | 78% [69%, 85%] (n=100) | 10% [6%, 17%] (n=100) | 0% [0%, 4%] (n=100) | 0% [0%, 4%] (n=90) | 0% [0%, 4%] (n=90) |
| metatool_s1 | jev | 73% [64%, 81%] (n=100) | 73% [64%, 81%] (n=100) | 73% [64%, 81%] (n=100) | 12% [7%, 20%] (n=100) | 0% [0%, 4%] (n=100) | 0% [0%, 4%] (n=88) | 0% [0%, 4%] (n=88) |
| metatool_s3 | native_llm | 95% [89%, 98%] (n=100) | 95% [89%, 98%] (n=100) | 95% [89%, 98%] (n=100) | 95% [89%, 98%] (n=100) | 0% [0%, 4%] (n=100) | 0% [0%, 43%] (n=5) | 0% [0%, 43%] (n=5) |
| metatool_s3 | matched_llm | 84% [76%, 90%] (n=100) | 84% [76%, 90%] (n=100) | 84% [76%, 90%] (n=100) | 84% [76%, 90%] (n=100) | 0% [0%, 4%] (n=100) | 0% [0%, 19%] (n=16) | 6% [1%, 28%] (n=16) |
| metatool_s3 | jev | 93% [86%, 97%] (n=100) | 93% [86%, 97%] (n=100) | 93% [86%, 97%] (n=100) | 93% [86%, 97%] (n=100) | 0% [0%, 4%] (n=100) | 0% [0%, 35%] (n=7) | 0% [0%, 35%] (n=7) |
| when2call | native_llm | 81% [74%, 87%] (n=150) | 79% [72%, 85%] (n=150) | 77% [69%, 83%] (n=150) | 59% [51%, 66%] (n=150) | 3% [1%, 8%] (n=150) | 0% [0%, 6%] (n=57) | 5% [2%, 14%] (n=57) |
| when2call | matched_llm | 69% [62%, 76%] (n=150) | 65% [57%, 72%] (n=150) | 62% [54%, 69%] (n=150) | 40% [33%, 48%] (n=150) | 0% [0%, 2%] (n=150) | 6% [2%, 12%] (n=90) | 16% [10%, 26%] (n=85) |
| when2call | jev | 72% [64%, 79%] (n=150) | 68% [60%, 75%] (n=150) | 64% [56%, 71%] (n=150) | 40% [33%, 48%] (n=150) | 0% [0%, 2%] (n=150) | 7% [3%, 14%] (n=90) | 23% [15%, 33%] (n=84) |

## Abstention by original label

| dataset | arm | label | n | abstained | correct |
|---|---|---|---|---|---|
| bfcl_irrelevance | native_llm | irrelevance | 100 | 88% [80%, 93%] (n=100) | 88% [80%, 93%] (n=100) |
| bfcl_irrelevance | matched_llm | irrelevance | 100 | 88% [80%, 93%] (n=100) | 88% [80%, 93%] (n=100) |
| bfcl_irrelevance | jev | irrelevance | 100 | 93% [86%, 97%] (n=100) | 93% [86%, 97%] (n=100) |
| bfcl_live_irrelevance | native_llm | irrelevance | 100 | 86% [78%, 91%] (n=100) | 86% [78%, 91%] (n=100) |
| bfcl_live_irrelevance | matched_llm | irrelevance | 100 | 80% [71%, 87%] (n=100) | 80% [71%, 87%] (n=100) |
| bfcl_live_irrelevance | jev | irrelevance | 100 | 79% [70%, 86%] (n=100) | 79% [70%, 86%] (n=100) |
| bfcl_live_simple | native_llm | call | 100 | 6% [3%, 12%] (n=100) | 93% [86%, 97%] (n=100) |
| bfcl_live_simple | matched_llm | call | 100 | 3% [1%, 8%] (n=100) | 97% [92%, 99%] (n=100) |
| bfcl_live_simple | jev | call | 100 | 5% [2%, 11%] (n=100) | 95% [89%, 98%] (n=100) |
| bfcl_simple_python | native_llm | call | 100 | 1% [0%, 5%] (n=100) | 99% [95%, 100%] (n=100) |
| bfcl_simple_python | matched_llm | call | 100 | 0% [0%, 4%] (n=100) | 100% [96%, 100%] (n=100) |
| bfcl_simple_python | jev | call | 100 | 1% [0%, 5%] (n=100) | 99% [95%, 100%] (n=100) |
| metatool_s1 | native_llm | tool | 100 | 33% [25%, 43%] (n=100) | 56% [46%, 65%] (n=100) |
| metatool_s1 | matched_llm | tool | 100 | 10% [6%, 17%] (n=100) | 78% [69%, 85%] (n=100) |
| metatool_s1 | jev | tool | 100 | 12% [7%, 20%] (n=100) | 73% [64%, 81%] (n=100) |
| metatool_s3 | native_llm | none_in_list | 100 | 95% [89%, 98%] (n=100) | 95% [89%, 98%] (n=100) |
| metatool_s3 | matched_llm | none_in_list | 100 | 84% [76%, 90%] (n=100) | 84% [76%, 90%] (n=100) |
| metatool_s3 | jev | none_in_list | 100 | 93% [86%, 97%] (n=100) | 93% [86%, 97%] (n=100) |
| when2call | native_llm | cannot_answer | 50 | 84% [71%, 92%] (n=50) | 84% [71%, 92%] (n=50) |
| when2call | native_llm | request_for_info | 50 | 80% [67%, 89%] (n=50) | 80% [67%, 89%] (n=50) |
| when2call | native_llm | tool_call | 50 | 12% [6%, 24%] (n=50) | 80% [67%, 89%] (n=50) |
| when2call | matched_llm | cannot_answer | 50 | 70% [56%, 81%] (n=50) | 70% [56%, 81%] (n=50) |
| when2call | matched_llm | request_for_info | 50 | 44% [31%, 58%] (n=50) | 44% [31%, 58%] (n=50) |
| when2call | matched_llm | tool_call | 50 | 6% [2%, 16%] (n=50) | 94% [84%, 98%] (n=50) |
| when2call | jev | cannot_answer | 50 | 78% [65%, 87%] (n=50) | 78% [65%, 87%] (n=50) |
| when2call | jev | request_for_info | 50 | 40% [28%, 54%] (n=50) | 40% [28%, 54%] (n=50) |
| when2call | jev | tool_call | 50 | 2% [0%, 10%] (n=50) | 98% [90%, 100%] (n=50) |

## Native vs matched (same Claude model; paired by task)

| dataset | pairs | both correct | native only | matched only | both wrong | disagreement | McNemar exact p |
|---|---|---|---|---|---|---|---|
| bfcl_irrelevance | 100 | 85 | 3 | 3 | 9 | 7% [3%, 14%] (n=100) | 1 |
| bfcl_live_irrelevance | 100 | 77 | 9 | 3 | 11 | 12% [7%, 20%] (n=100) | 0.146 |
| bfcl_live_simple | 100 | 91 | 2 | 6 | 1 | 8% [4%, 15%] (n=100) | 0.289 |
| bfcl_simple_python | 100 | 99 | 0 | 1 | 0 | 1% [0%, 5%] (n=100) | 1 |
| metatool_s1 | 100 | 56 | 0 | 22 | 22 | 27% [19%, 36%] (n=100) | 4.77e-07 |
| metatool_s3 | 100 | 84 | 11 | 0 | 5 | 11% [6%, 19%] (n=100) | 0.000977 |
| when2call | 150 | 96 | 26 | 8 | 20 | 25% [18%, 32%] (n=150) | 0.00294 |

## Jev selector stability (10 back-to-back draws per task)

| dataset | tasks | tasks with any flip | mean flip rate | mean entropy (bits) | mean max prob. range | max prob. range | executed = majority |
|---|---|---|---|---|---|---|---|
| bfcl_irrelevance | 100 | 2% [1%, 7%] (n=100) | 0.008 | 0.016 | 0.014 | 0.120 | 100% [96%, 100%] (n=100) |
| bfcl_live_irrelevance | 100 | 2% [1%, 7%] (n=100) | 0.004 | 0.009 | 0.024 | 0.180 | 99% [95%, 100%] (n=100) |
| bfcl_live_simple | 100 | 0% [0%, 4%] (n=100) | 0.000 | 0.000 | 0.016 | 0.130 | 100% [96%, 100%] (n=100) |
| bfcl_simple_python | 100 | 2% [1%, 7%] (n=100) | 0.008 | 0.016 | 0.007 | 0.090 | 99% [95%, 100%] (n=100) |
| metatool_s1 | 100 | 5% [2%, 11%] (n=100) | 0.020 | 0.042 | 0.031 | 0.180 | 99% [95%, 100%] (n=100) |
| metatool_s3 | 100 | 2% [1%, 7%] (n=100) | 0.010 | 0.019 | 0.019 | 0.150 | 99% [95%, 100%] (n=100) |
| when2call | 150 | 4% [2%, 8%] (n=150) | 0.014 | 0.027 | 0.035 | 0.130 | 99% [95%, 100%] (n=150) |

## Grounding (argument values)

| dataset | arm | placeholders | unsupported required | unsupported optional | unknown |
|---|---|---|---|---|---|
| bfcl_irrelevance | native_llm | 0 | 5 | 5 | 5 |
| bfcl_irrelevance | matched_llm | 2 | 9 | 4 | 2 |
| bfcl_irrelevance | jev | 2 | 1 | 0 | 0 |
| bfcl_live_irrelevance | native_llm | 0 | 8 | 4 | 4 |
| bfcl_live_irrelevance | matched_llm | 10 | 7 | 2 | 4 |
| bfcl_live_irrelevance | jev | 13 | 7 | 5 | 9 |
| bfcl_live_simple | native_llm | 0 | 0 | 0 | 29 |
| bfcl_live_simple | matched_llm | 0 | 0 | 0 | 29 |
| bfcl_live_simple | jev | 0 | 0 | 0 | 29 |
| bfcl_simple_python | native_llm | 0 | 1 | 0 | 22 |
| bfcl_simple_python | matched_llm | 0 | 1 | 0 | 23 |
| bfcl_simple_python | jev | 0 | 1 | 0 | 22 |
| metatool_s1 | native_llm | 0 | 0 | 0 | 0 |
| metatool_s1 | matched_llm | 0 | 0 | 1 | 1 |
| metatool_s1 | jev | 0 | 0 | 1 | 2 |
| metatool_s3 | native_llm | 0 | 0 | 0 | 1 |
| metatool_s3 | matched_llm | 1 | 0 | 4 | 2 |
| metatool_s3 | jev | 0 | 0 | 2 | 2 |
| when2call | native_llm | 0 | 7 | 10 | 28 |
| when2call | matched_llm | 14 | 21 | 12 | 40 |
| when2call | jev | 19 | 19 | 12 | 39 |

## Cost (reported by OpenRouter)

| dataset | arm | selection $ | arguments $ | total $ |
|---|---|---|---|---|
| bfcl_irrelevance | jev | 0.0220 | 0.0085 | 0.0305 |
| bfcl_irrelevance | matched_llm | 0.0657 | 0.0143 | 0.0799 |
| bfcl_irrelevance | native_llm | 0.1663 | 0.0000 | 0.1663 |
| bfcl_live_irrelevance | jev | 0.0428 | 0.0319 | 0.0748 |
| bfcl_live_irrelevance | matched_llm | 0.1133 | 0.0265 | 0.1399 |
| bfcl_live_irrelevance | native_llm | 0.1989 | 0.0000 | 0.1989 |
| bfcl_live_simple | jev | 0.0254 | 0.1165 | 0.1419 |
| bfcl_live_simple | matched_llm | 0.0742 | 0.1178 | 0.1920 |
| bfcl_live_simple | native_llm | 0.1285 | 0.0000 | 0.1285 |
| bfcl_simple_python | jev | 0.0225 | 0.1146 | 0.1371 |
| bfcl_simple_python | matched_llm | 0.0672 | 0.1158 | 0.1829 |
| bfcl_simple_python | native_llm | 0.1203 | 0.0000 | 0.1203 |
| metatool_s1 | jev | 0.0300 | 0.0721 | 0.1021 |
| metatool_s1 | matched_llm | 0.0878 | 0.0737 | 0.1615 |
| metatool_s1 | native_llm | 0.1701 | 0.0000 | 0.1701 |
| metatool_s3 | jev | 0.0300 | 0.0065 | 0.0365 |
| metatool_s3 | matched_llm | 0.0877 | 0.0145 | 0.1022 |
| metatool_s3 | native_llm | 0.2344 | 0.0000 | 0.2344 |
| when2call | jev | 0.0804 | 0.1207 | 0.2011 |
| when2call | matched_llm | 0.2055 | 0.1195 | 0.3250 |
| when2call | native_llm | 0.2972 | 0.0000 | 0.2972 |

By arm: jev $0.7240, matched_llm $1.1834, native_llm $1.3158
By stage: selection $2.2704, arguments $0.9528
