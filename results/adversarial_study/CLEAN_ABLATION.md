# Clean architecture ablation

Same 350 tasks as the external pilot's group A, 3 presentation orderings per task, four arms. Pairs pooled over orderings are not independent; intervals and p-values are descriptive.

| dataset | arm | accuracy | abstention | action rate | ordering-sensitive tasks |
|---|---|---|---|---|---|
| metatool_s1 | native_llm | 56% [50%, 62%] (n=300) | 33% [28%, 39%] (n=300) | 65% [60%, 70%] (n=300) | 10% [6%, 17%] (n=100) |
| metatool_s1 | matched_systemone | 76% [71%, 80%] (n=300) | 10% [7%, 14%] (n=300) | 90% [86%, 93%] (n=300) | 9% [5%, 16%] (n=100) |
| metatool_s1 | matched_neutral | 75% [70%, 80%] (n=300) | 5% [3%, 8%] (n=300) | 95% [92%, 97%] (n=300) | 12% [7%, 20%] (n=100) |
| metatool_s1 | jev | 72% [67%, 77%] (n=300) | 11% [8%, 15%] (n=300) | 89% [85%, 92%] (n=300) | 6% [3%, 12%] (n=100) |
| metatool_s3 | native_llm | 94% [91%, 96%] (n=300) | 94% [91%, 96%] (n=300) | 5% [3%, 8%] (n=300) | 2% [1%, 7%] (n=100) |
| metatool_s3 | matched_systemone | 86% [82%, 89%] (n=300) | 86% [82%, 89%] (n=300) | 14% [11%, 18%] (n=300) | 7% [3%, 14%] (n=100) |
| metatool_s3 | matched_neutral | 82% [77%, 86%] (n=300) | 82% [77%, 86%] (n=300) | 18% [14%, 23%] (n=300) | 11% [6%, 19%] (n=100) |
| metatool_s3 | jev | 92% [88%, 94%] (n=300) | 92% [88%, 94%] (n=300) | 8% [6%, 12%] (n=300) | 1% [0%, 5%] (n=100) |
| when2call | native_llm | 81% [77%, 84%] (n=450) | 59% [54%, 63%] (n=450) | 38% [34%, 43%] (n=450) | 5% [3%, 10%] (n=150) |
| when2call | matched_systemone | 70% [65%, 74%] (n=450) | 42% [37%, 46%] (n=450) | 58% [54%, 63%] (n=450) | 9% [6%, 15%] (n=150) |
| when2call | matched_neutral | 56% [51%, 60%] (n=450) | 23% [20%, 27%] (n=450) | 77% [73%, 80%] (n=450) | 4% [2%, 8%] (n=150) |
| when2call | jev | 71% [67%, 75%] (n=450) | 39% [34%, 43%] (n=450) | 61% [57%, 66%] (n=450) | 3% [1%, 8%] (n=150) |

## Paired with native

| dataset | arm | pairs | native only | arm only | disagreement | McNemar p |
|---|---|---|---|---|---|---|
| metatool_s1 | matched_systemone | 300 | 2 | 61 | 28% [23%, 33%] (n=300) | 4.37e-16 |
| metatool_s1 | matched_neutral | 300 | 6 | 64 | 34% [29%, 40%] (n=300) | 2.44e-13 |
| metatool_s1 | jev | 300 | 10 | 59 | 31% [26%, 37%] (n=300) | 1.38e-09 |
| metatool_s3 | matched_systemone | 300 | 25 | 0 | 9% [6%, 12%] (n=300) | 5.96e-08 |
| metatool_s3 | matched_neutral | 300 | 38 | 0 | 13% [10%, 17%] (n=300) | 7.28e-12 |
| metatool_s3 | jev | 300 | 11 | 3 | 5% [3%, 8%] (n=300) | 0.0574 |
| when2call | matched_systemone | 450 | 73 | 24 | 24% [20%, 28%] (n=450) | 6.4e-07 |
| when2call | matched_neutral | 450 | 141 | 29 | 40% [35%, 44%] (n=450) | 7.24e-19 |
| when2call | jev | 450 | 81 | 37 | 28% [24%, 32%] (n=450) | 6.29e-05 |

## Accuracy by ordering

| dataset | arm | ordering 0 | ordering 1 | ordering 2 |
|---|---|---|---|---|
| metatool_s1 | native_llm | 56% [46%, 65%] (n=100) | 56% [46%, 65%] (n=100) | 56% [46%, 65%] (n=100) |
| metatool_s1 | matched_systemone | 76% [67%, 83%] (n=100) | 76% [67%, 83%] (n=100) | 75% [66%, 82%] (n=100) |
| metatool_s1 | matched_neutral | 75% [66%, 82%] (n=100) | 75% [66%, 82%] (n=100) | 76% [67%, 83%] (n=100) |
| metatool_s1 | jev | 72% [63%, 80%] (n=100) | 72% [63%, 80%] (n=100) | 73% [64%, 81%] (n=100) |
| metatool_s3 | native_llm | 95% [89%, 98%] (n=100) | 94% [88%, 97%] (n=100) | 94% [88%, 97%] (n=100) |
| metatool_s3 | matched_systemone | 83% [74%, 89%] (n=100) | 88% [80%, 93%] (n=100) | 87% [79%, 92%] (n=100) |
| metatool_s3 | matched_neutral | 81% [72%, 87%] (n=100) | 80% [71%, 87%] (n=100) | 84% [76%, 90%] (n=100) |
| metatool_s3 | jev | 92% [85%, 96%] (n=100) | 92% [85%, 96%] (n=100) | 91% [84%, 95%] (n=100) |
| when2call | native_llm | 81% [74%, 86%] (n=150) | 81% [74%, 86%] (n=150) | 81% [74%, 86%] (n=150) |
| when2call | matched_systemone | 70% [62%, 77%] (n=150) | 69% [62%, 76%] (n=150) | 70% [62%, 77%] (n=150) |
| when2call | matched_neutral | 55% [47%, 63%] (n=150) | 55% [47%, 63%] (n=150) | 57% [49%, 64%] (n=150) |
| when2call | jev | 72% [64%, 79%] (n=150) | 70% [62%, 77%] (n=150) | 71% [63%, 77%] (n=150) |

## Action rate by original label

| dataset | arm | label | P(tool call) |
|---|---|---|---|
| metatool_s1 | native_llm | tool | 65% [60%, 70%] (n=300) |
| metatool_s1 | matched_systemone | tool | 90% [86%, 93%] (n=300) |
| metatool_s1 | matched_neutral | tool | 95% [92%, 97%] (n=300) |
| metatool_s1 | jev | tool | 89% [85%, 92%] (n=300) |
| metatool_s3 | native_llm | none_in_list | 5% [3%, 8%] (n=300) |
| metatool_s3 | matched_systemone | none_in_list | 14% [11%, 18%] (n=300) |
| metatool_s3 | matched_neutral | none_in_list | 18% [14%, 23%] (n=300) |
| metatool_s3 | jev | none_in_list | 8% [6%, 12%] (n=300) |
| when2call | native_llm | cannot_answer | 17% [12%, 24%] (n=150) |
| when2call | native_llm | request_for_info | 18% [13%, 25%] (n=150) |
| when2call | native_llm | tool_call | 79% [71%, 84%] (n=150) |
| when2call | matched_systemone | cannot_answer | 31% [24%, 38%] (n=150) |
| when2call | matched_systemone | request_for_info | 52% [44%, 60%] (n=150) |
| when2call | matched_systemone | tool_call | 92% [87%, 95%] (n=150) |
| when2call | matched_neutral | cannot_answer | 43% [35%, 51%] (n=150) |
| when2call | matched_neutral | request_for_info | 88% [82%, 92%] (n=150) |
| when2call | matched_neutral | tool_call | 99% [96%, 100%] (n=150) |
| when2call | jev | cannot_answer | 21% [15%, 28%] (n=150) |
| when2call | jev | request_for_info | 65% [57%, 72%] (n=150) |
| when2call | jev | tool_call | 98% [94%, 99%] (n=150) |
