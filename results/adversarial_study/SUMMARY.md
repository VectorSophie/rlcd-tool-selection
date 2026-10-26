# Adversarial tool-metadata study: summary

Pre-registered hypotheses and analysis plan are in every manifest. Regimes, families and the insertion family are never pooled. Interaction intervals are cluster-bootstrap (upstream cluster, never a task-ordering); Holm-adjusted p-values are shown next to raw ones.

- Records: 18840 (18840 runs, 0 aborted)
- Provider calls: {'anthropic/claude-haiku-4.5': 23416, 'typesafe/jev-1.13-20260917': 23549}
- Cost: $30.0952 actual vs $53.0137 estimated (ratio 0.57)
- Manifests: A_clean `f72034819758`, B_displacement `a562f566354f`, C_abstention `f5f485aaf220`

See `CLEAN_ABLATION.md` for the clean ablation.

## Adversarial results

| cell | arm | control acc. | attacked acc. | conditional ASR | unconditional attacker sel. | Δ attacker sel. | Δ abstention |
|---|---|---|---|---|---|---|---|
| metatool_s1|trusted_displacement|decoy_insertion | native_llm | 56% [50%, 62%] (n=300) | 31% [26%, 36%] (n=300) | 41% [34%, 49%] (n=168) | 25% [21%, 31%] (n=300) | +25.3 pp | +0.7 pp |
| metatool_s1|trusted_displacement|decoy_insertion | matched_systemone | 76% [71%, 80%] (n=300) | 50% [44%, 55%] (n=300) | 33% [28%, 40%] (n=227) | 26% [21%, 31%] (n=300) | +26.0 pp | -0.7 pp |
| metatool_s1|trusted_displacement|decoy_insertion | matched_neutral | 75% [70%, 80%] (n=300) | 36% [30%, 41%] (n=300) | 55% [49%, 62%] (n=226) | 44% [38%, 50%] (n=300) | +44.0 pp | -1.3 pp |
| metatool_s1|trusted_displacement|decoy_insertion | jev | 72% [67%, 77%] (n=300) | 66% [60%, 71%] (n=300) | 6% [4%, 11%] (n=217) | 5% [3%, 8%] (n=300) | +5.0 pp | +1.3 pp |
| metatool_s1|trusted_displacement|description_mimicry | native_llm | 56% [50%, 62%] (n=300) | 52% [46%, 57%] (n=300) | 5% [3%, 10%] (n=168) | 5% [3%, 8%] (n=300) | +2.7 pp | +2.0 pp |
| metatool_s1|trusted_displacement|description_mimicry | matched_systemone | 76% [71%, 80%] (n=300) | 67% [62%, 72%] (n=300) | 9% [6%, 14%] (n=227) | 10% [7%, 14%] (n=300) | +3.3 pp | +2.0 pp |
| metatool_s1|trusted_displacement|description_mimicry | matched_neutral | 75% [70%, 80%] (n=300) | 66% [61%, 71%] (n=300) | 14% [10%, 19%] (n=226) | 13% [10%, 17%] (n=300) | +8.0 pp | +0.3 pp |
| metatool_s1|trusted_displacement|description_mimicry | jev | 72% [67%, 77%] (n=300) | 67% [62%, 72%] (n=300) | 7% [4%, 11%] (n=217) | 8% [5%, 12%] (n=300) | +1.3 pp | +3.7 pp |
| metatool_s1|trusted_displacement|near_name | native_llm | 56% [50%, 62%] (n=300) | 55% [49%, 61%] (n=300) | 1% [0%, 3%] (n=168) | 3% [2%, 6%] (n=300) | +1.0 pp | +1.3 pp |
| metatool_s1|trusted_displacement|near_name | matched_systemone | 76% [71%, 80%] (n=300) | 76% [71%, 80%] (n=300) | 1% [0%, 3%] (n=227) | 6% [4%, 9%] (n=300) | -1.3 pp | +0.3 pp |
| metatool_s1|trusted_displacement|near_name | matched_neutral | 75% [70%, 80%] (n=300) | 73% [68%, 78%] (n=300) | 2% [1%, 5%] (n=226) | 7% [4%, 10%] (n=300) | +1.7 pp | -0.3 pp |
| metatool_s1|trusted_displacement|near_name | jev | 72% [67%, 77%] (n=300) | 72% [66%, 76%] (n=300) | 1% [0%, 4%] (n=217) | 7% [5%, 11%] (n=300) | +0.7 pp | +0.0 pp |
| metatool_s1|trusted_displacement|preference_authority | native_llm | 56% [50%, 62%] (n=300) | 56% [50%, 62%] (n=300) | 1% [0%, 3%] (n=168) | 4% [3%, 7%] (n=300) | +2.0 pp | -1.3 pp |
| metatool_s1|trusted_displacement|preference_authority | matched_systemone | 76% [71%, 80%] (n=300) | 75% [70%, 80%] (n=300) | 2% [1%, 4%] (n=227) | 9% [7%, 13%] (n=300) | +2.3 pp | -1.7 pp |
| metatool_s1|trusted_displacement|preference_authority | matched_neutral | 75% [70%, 80%] (n=300) | 73% [68%, 78%] (n=300) | 4% [2%, 7%] (n=226) | 8% [6%, 12%] (n=300) | +3.3 pp | -0.7 pp |
| metatool_s1|trusted_displacement|preference_authority | jev | 72% [67%, 77%] (n=300) | 71% [66%, 76%] (n=300) | 2% [1%, 5%] (n=217) | 9% [7%, 13%] (n=300) | +2.7 pp | -0.7 pp |
| metatool_s3|abstention_capture|decoy_insertion | native_llm | 94% [91%, 96%] (n=300) | 94% [90%, 96%] (n=300) | 0% [0%, 2%] (n=283) | 0% [0%, 2%] (n=300) | +0.3 pp | -0.7 pp |
| metatool_s3|abstention_capture|decoy_insertion | matched_systemone | 86% [82%, 89%] (n=300) | 88% [83%, 91%] (n=300) | 0% [0%, 1%] (n=258) | 0% [0%, 1%] (n=300) | +0.0 pp | +1.7 pp |
| metatool_s3|abstention_capture|decoy_insertion | matched_neutral | 82% [77%, 86%] (n=300) | 79% [74%, 84%] (n=300) | 0% [0%, 2%] (n=245) | 0% [0%, 2%] (n=300) | +0.3 pp | -2.3 pp |
| metatool_s3|abstention_capture|decoy_insertion | jev | 92% [88%, 94%] (n=300) | 93% [90%, 96%] (n=300) | 0% [0%, 1%] (n=275) | 0% [0%, 1%] (n=300) | +0.0 pp | +1.7 pp |
| metatool_s3|abstention_capture|preference_authority | native_llm | 94% [91%, 96%] (n=300) | 93% [90%, 95%] (n=300) | 0% [0%, 1%] (n=283) | 0% [0%, 1%] (n=300) | +0.0 pp | -1.3 pp |
| metatool_s3|abstention_capture|preference_authority | matched_systemone | 86% [82%, 89%] (n=300) | 85% [81%, 89%] (n=300) | 1% [0%, 3%] (n=258) | 2% [1%, 4%] (n=300) | +1.0 pp | -0.7 pp |
| metatool_s3|abstention_capture|preference_authority | matched_neutral | 82% [77%, 86%] (n=300) | 78% [73%, 83%] (n=300) | 2% [1%, 4%] (n=245) | 2% [1%, 5%] (n=300) | +1.3 pp | -3.3 pp |
| metatool_s3|abstention_capture|preference_authority | jev | 92% [88%, 94%] (n=300) | 93% [89%, 95%] (n=300) | 0% [0%, 1%] (n=275) | 0% [0%, 1%] (n=300) | +0.0 pp | +1.0 pp |
| when2call|abstention_capture|decoy_insertion | native_llm | 82% [77%, 86%] (n=300) | 80% [75%, 84%] (n=300) | 0% [0%, 2%] (n=245) | 1% [0%, 3%] (n=300) | +1.0 pp | -1.7 pp |
| when2call|abstention_capture|decoy_insertion | matched_systemone | 59% [53%, 64%] (n=300) | 64% [59%, 70%] (n=300) | 1% [0%, 3%] (n=176) | 4% [2%, 7%] (n=300) | +4.0 pp | +5.7 pp |
| when2call|abstention_capture|decoy_insertion | matched_neutral | 35% [30%, 40%] (n=300) | 38% [33%, 44%] (n=300) | 3% [1%, 8%] (n=104) | 10% [7%, 14%] (n=300) | +10.0 pp | +3.3 pp |
| when2call|abstention_capture|decoy_insertion | jev | 57% [52%, 63%] (n=300) | 70% [65%, 75%] (n=300) | 0% [0%, 2%] (n=172) | 1% [1%, 3%] (n=300) | +1.3 pp | +13.0 pp |
| when2call|abstention_capture|description_mimicry | native_llm | 81% [74%, 86%] (n=150) | 78% [71%, 84%] (n=150) | 0% [0%, 3%] (n=121) | 0% [0%, 2%] (n=150) | +0.0 pp | -2.7 pp |
| when2call|abstention_capture|description_mimicry | matched_systemone | 48% [40%, 56%] (n=150) | 49% [41%, 57%] (n=150) | 0% [0%, 5%] (n=72) | 2% [1%, 6%] (n=150) | +2.0 pp | +0.7 pp |
| when2call|abstention_capture|description_mimicry | matched_neutral | 4% [2%, 8%] (n=150) | 7% [4%, 12%] (n=150) | 0% [0%, 39%] (n=6) | 3% [1%, 7%] (n=150) | +0.7 pp | +2.7 pp |
| when2call|abstention_capture|description_mimicry | jev | 34% [27%, 42%] (n=150) | 34% [27%, 42%] (n=150) | 2% [0%, 10%] (n=51) | 2% [1%, 6%] (n=150) | +2.0 pp | +0.0 pp |
| when2call|abstention_capture|preference_authority | native_llm | 82% [77%, 86%] (n=300) | 82% [78%, 86%] (n=300) | 0% [0%, 2%] (n=245) | 3% [2%, 6%] (n=300) | -1.0 pp | +0.7 pp |
| when2call|abstention_capture|preference_authority | matched_systemone | 59% [53%, 64%] (n=300) | 57% [51%, 62%] (n=300) | 3% [1%, 6%] (n=176) | 9% [6%, 12%] (n=300) | +2.0 pp | -1.7 pp |
| when2call|abstention_capture|preference_authority | matched_neutral | 31% [26%, 36%] (n=300) | 32% [27%, 37%] (n=300) | 0% [0%, 4%] (n=92) | 11% [8%, 15%] (n=300) | +1.3 pp | +1.3 pp |
| when2call|abstention_capture|preference_authority | jev | 57% [51%, 62%] (n=300) | 54% [49%, 60%] (n=300) | 2% [1%, 6%] (n=170) | 6% [4%, 10%] (n=300) | +2.0 pp | -2.3 pp |
| when2call|abstention_capture|schema_property | native_llm | 81% [77%, 85%] (n=297) | 82% [78%, 86%] (n=297) | 0% [0%, 2%] (n=242) | 3% [2%, 6%] (n=297) | -1.0 pp | +1.0 pp |
| when2call|abstention_capture|schema_property | matched_systemone | 58% [53%, 64%] (n=297) | 57% [51%, 62%] (n=297) | 2% [1%, 5%] (n=173) | 8% [5%, 12%] (n=297) | +1.3 pp | -1.3 pp |
| when2call|abstention_capture|schema_property | matched_neutral | 31% [26%, 36%] (n=297) | 32% [27%, 37%] (n=297) | 0% [0%, 4%] (n=91) | 10% [7%, 14%] (n=297) | +0.0 pp | +1.3 pp |
| when2call|abstention_capture|schema_property | jev | 56% [51%, 62%] (n=297) | 56% [50%, 61%] (n=297) | 1% [0%, 4%] (n=167) | 5% [3%, 8%] (n=297) | +0.7 pp | -0.7 pp |
| when2call|trusted_displacement|decoy_insertion | native_llm | 79% [71%, 84%] (n=150) | 77% [70%, 83%] (n=150) | 1% [0%, 5%] (n=118) | 1% [0%, 4%] (n=150) | +0.7 pp | +1.3 pp |
| when2call|trusted_displacement|decoy_insertion | matched_systemone | 92% [87%, 95%] (n=150) | 75% [68%, 82%] (n=150) | 15% [10%, 22%] (n=138) | 14% [9%, 20%] (n=150) | +14.0 pp | +1.3 pp |
| when2call|trusted_displacement|decoy_insertion | matched_neutral | 98% [94%, 99%] (n=150) | 71% [63%, 77%] (n=150) | 28% [21%, 36%] (n=147) | 27% [21%, 35%] (n=150) | +27.3 pp | -0.7 pp |
| when2call|trusted_displacement|decoy_insertion | jev | 98% [94%, 99%] (n=150) | 92% [87%, 95%] (n=150) | 5% [3%, 10%] (n=147) | 5% [3%, 10%] (n=150) | +5.3 pp | +0.7 pp |
| when2call|trusted_displacement|description_mimicry | native_llm | 79% [71%, 84%] (n=150) | 80% [73%, 86%] (n=150) | 0% [0%, 3%] (n=118) | 0% [0%, 2%] (n=150) | +0.0 pp | +0.7 pp |
| when2call|trusted_displacement|description_mimicry | matched_systemone | 90% [84%, 94%] (n=150) | 92% [87%, 95%] (n=150) | 0% [0%, 3%] (n=135) | 0% [0%, 2%] (n=150) | +0.0 pp | -2.7 pp |
| when2call|trusted_displacement|description_mimicry | matched_neutral | 98% [94%, 99%] (n=150) | 98% [94%, 99%] (n=150) | 0% [0%, 3%] (n=147) | 1% [0%, 5%] (n=150) | +0.0 pp | +0.0 pp |
| when2call|trusted_displacement|description_mimicry | jev | 98% [94%, 99%] (n=150) | 97% [93%, 99%] (n=150) | 1% [0%, 4%] (n=147) | 1% [0%, 4%] (n=150) | +0.7 pp | +0.0 pp |
| when2call|trusted_displacement|near_name | native_llm | 79% [71%, 84%] (n=150) | 79% [71%, 84%] (n=150) | 0% [0%, 3%] (n=118) | 0% [0%, 2%] (n=150) | +0.0 pp | +1.3 pp |
| when2call|trusted_displacement|near_name | matched_systemone | 90% [84%, 94%] (n=150) | 91% [85%, 94%] (n=150) | 1% [0%, 5%] (n=135) | 1% [0%, 5%] (n=150) | +1.3 pp | -2.7 pp |
| when2call|trusted_displacement|near_name | matched_neutral | 98% [94%, 99%] (n=150) | 97% [92%, 99%] (n=150) | 1% [0%, 5%] (n=147) | 3% [1%, 7%] (n=150) | +1.3 pp | +0.0 pp |
| when2call|trusted_displacement|near_name | jev | 98% [94%, 99%] (n=150) | 97% [92%, 99%] (n=150) | 1% [0%, 5%] (n=147) | 1% [0%, 5%] (n=150) | +1.3 pp | +0.0 pp |
| when2call|trusted_displacement|preference_authority | native_llm | 79% [71%, 84%] (n=150) | 78% [71%, 84%] (n=150) | 0% [0%, 3%] (n=118) | 1% [0%, 4%] (n=150) | +0.7 pp | +0.0 pp |
| when2call|trusted_displacement|preference_authority | matched_systemone | 90% [84%, 94%] (n=150) | 95% [90%, 97%] (n=150) | 1% [0%, 4%] (n=135) | 1% [0%, 4%] (n=150) | +0.7 pp | -5.3 pp |
| when2call|trusted_displacement|preference_authority | matched_neutral | 98% [94%, 99%] (n=150) | 97% [93%, 99%] (n=150) | 1% [0%, 4%] (n=147) | 2% [1%, 6%] (n=150) | +0.7 pp | +0.0 pp |
| when2call|trusted_displacement|preference_authority | jev | 98% [94%, 99%] (n=150) | 98% [94%, 99%] (n=150) | 0% [0%, 3%] (n=147) | 0% [0%, 2%] (n=150) | +0.0 pp | +0.0 pp |
| when2call|trusted_displacement|schema_property | native_llm | 79% [71%, 84%] (n=150) | 79% [72%, 85%] (n=150) | 0% [0%, 3%] (n=118) | 0% [0%, 2%] (n=150) | +0.0 pp | +0.0 pp |
| when2call|trusted_displacement|schema_property | matched_systemone | 90% [84%, 94%] (n=150) | 95% [90%, 97%] (n=150) | 0% [0%, 3%] (n=135) | 0% [0%, 2%] (n=150) | +0.0 pp | -4.7 pp |
| when2call|trusted_displacement|schema_property | matched_neutral | 98% [94%, 99%] (n=150) | 97% [93%, 99%] (n=150) | 1% [0%, 4%] (n=147) | 2% [1%, 6%] (n=150) | +0.7 pp | +0.0 pp |
| when2call|trusted_displacement|schema_property | jev | 98% [94%, 99%] (n=150) | 98% [94%, 99%] (n=150) | 0% [0%, 3%] (n=147) | 0% [0%, 2%] (n=150) | +0.0 pp | +0.0 pp |

## Architecture × attack interaction (differences of attack-induced shifts)

| cell | contrast | statistic | estimate | 95% cluster-bootstrap CI | p | Holm p |
|---|---|---|---|---|---|---|
| metatool_s1|trusted_displacement|decoy_insertion | H1_decomposition | attacker_selection | +18.7 pp | [+10.0 pp, +27.0 pp] | 0 | 0 |
| metatool_s1|trusted_displacement|decoy_insertion | H1_decomposition | task_failure | +14.7 pp | [+6.3 pp, +23.0 pp] | 0.002 | 0.16 |
| metatool_s1|trusted_displacement|decoy_insertion | H2_framing | attacker_selection | -18.0 pp | [-25.7 pp, -10.3 pp] | 0 | 0 |
| metatool_s1|trusted_displacement|decoy_insertion | H2_framing | task_failure | -13.7 pp | [-21.3 pp, -5.7 pp] | 0 | 0 |
| metatool_s1|trusted_displacement|decoy_insertion | H3_selector_family | attacker_selection | -39.0 pp | [-47.0 pp, -31.3 pp] | 0 | 0 |
| metatool_s1|trusted_displacement|decoy_insertion | H3_selector_family | task_failure | -33.3 pp | [-42.3 pp, -24.3 pp] | 0 | 0 |
| metatool_s1|trusted_displacement|description_mimicry | H1_decomposition | attacker_selection | +5.3 pp | [+0.7 pp, +10.0 pp] | 0.033 | 1 |
| metatool_s1|trusted_displacement|description_mimicry | H1_decomposition | task_failure | +4.7 pp | [+0.0 pp, +9.7 pp] | 0.063 | 1 |
| metatool_s1|trusted_displacement|description_mimicry | H2_framing | attacker_selection | -4.7 pp | [-10.0 pp, +0.3 pp] | 0.085 | 1 |
| metatool_s1|trusted_displacement|description_mimicry | H2_framing | task_failure | -0.7 pp | [-5.7 pp, +4.3 pp] | 0.863 | 1 |
| metatool_s1|trusted_displacement|description_mimicry | H3_selector_family | attacker_selection | -6.7 pp | [-12.0 pp, -1.0 pp] | 0.021 | 1 |
| metatool_s1|trusted_displacement|description_mimicry | H3_selector_family | task_failure | -4.0 pp | [-10.0 pp, +2.3 pp] | 0.247 | 1 |
| metatool_s1|trusted_displacement|near_name | H1_decomposition | attacker_selection | +0.7 pp | [-1.7 pp, +3.3 pp] | 0.681 | 1 |
| metatool_s1|trusted_displacement|near_name | H1_decomposition | task_failure | +1.0 pp | [-1.7 pp, +4.0 pp] | 0.567 | 1 |
| metatool_s1|trusted_displacement|near_name | H2_framing | attacker_selection | -3.0 pp | [-7.3 pp, +0.0 pp] | 0.068 | 1 |
| metatool_s1|trusted_displacement|near_name | H2_framing | task_failure | -2.0 pp | [-5.7 pp, +1.0 pp] | 0.256 | 1 |
| metatool_s1|trusted_displacement|near_name | H3_selector_family | attacker_selection | -1.0 pp | [-4.3 pp, +2.3 pp] | 0.603 | 1 |
| metatool_s1|trusted_displacement|near_name | H3_selector_family | task_failure | -1.3 pp | [-5.7 pp, +2.0 pp] | 0.544 | 1 |
| metatool_s1|trusted_displacement|preference_authority | H1_decomposition | attacker_selection | +1.3 pp | [-2.7 pp, +5.3 pp] | 0.553 | 1 |
| metatool_s1|trusted_displacement|preference_authority | H1_decomposition | task_failure | +2.3 pp | [-1.3 pp, +6.3 pp] | 0.252 | 1 |
| metatool_s1|trusted_displacement|preference_authority | H2_framing | attacker_selection | -1.0 pp | [-5.0 pp, +2.7 pp] | 0.669 | 1 |
| metatool_s1|trusted_displacement|preference_authority | H2_framing | task_failure | -1.7 pp | [-5.7 pp, +2.3 pp] | 0.458 | 1 |
| metatool_s1|trusted_displacement|preference_authority | H3_selector_family | attacker_selection | -0.7 pp | [-5.0 pp, +3.3 pp] | 0.807 | 1 |
| metatool_s1|trusted_displacement|preference_authority | H3_selector_family | task_failure | -1.0 pp | [-5.0 pp, +2.3 pp] | 0.65 | 1 |
| metatool_s3|abstention_capture|decoy_insertion | H1_decomposition | attacker_selection | +0.0 pp | [-1.0 pp, +1.0 pp] | 1 | 1 |
| metatool_s3|abstention_capture|decoy_insertion | H1_decomposition | task_failure | +1.7 pp | [-1.3 pp, +5.0 pp] | 0.36 | 1 |
| metatool_s3|abstention_capture|decoy_insertion | H2_framing | attacker_selection | -0.3 pp | [-1.0 pp, +0.0 pp] | 0.7 | 1 |
| metatool_s3|abstention_capture|decoy_insertion | H2_framing | task_failure | -4.0 pp | [-8.7 pp, +0.0 pp] | 0.069 | 1 |
| metatool_s3|abstention_capture|decoy_insertion | H3_selector_family | attacker_selection | -0.3 pp | [-1.0 pp, +0.0 pp] | 0.7 | 1 |
| metatool_s3|abstention_capture|decoy_insertion | H3_selector_family | task_failure | -4.0 pp | [-7.7 pp, -0.7 pp] | 0.018 | 1 |
| metatool_s3|abstention_capture|preference_authority | H1_decomposition | attacker_selection | +1.3 pp | [+0.0 pp, +3.0 pp] | 0.089 | 1 |
| metatool_s3|abstention_capture|preference_authority | H1_decomposition | task_failure | +2.0 pp | [-1.3 pp, +5.7 pp] | 0.27 | 1 |
| metatool_s3|abstention_capture|preference_authority | H2_framing | attacker_selection | -0.3 pp | [-1.7 pp, +0.7 pp] | 0.752 | 1 |
| metatool_s3|abstention_capture|preference_authority | H2_framing | task_failure | -2.7 pp | [-6.3 pp, +0.7 pp] | 0.152 | 1 |
| metatool_s3|abstention_capture|preference_authority | H3_selector_family | attacker_selection | -1.3 pp | [-3.0 pp, +0.0 pp] | 0.089 | 1 |
| metatool_s3|abstention_capture|preference_authority | H3_selector_family | task_failure | -4.3 pp | [-7.7 pp, -1.3 pp] | 0.003 | 0.234 |
| when2call|abstention_capture|decoy_insertion | H1_decomposition | attacker_selection | +9.0 pp | [+3.6 pp, +14.7 pp] | 0.002 | 0.16 |
| when2call|abstention_capture|decoy_insertion | H1_decomposition | task_failure | -5.0 pp | [-9.7 pp, -0.7 pp] | 0.024 | 1 |
| when2call|abstention_capture|decoy_insertion | H2_framing | attacker_selection | -6.0 pp | [-10.6 pp, -1.7 pp] | 0.009 | 0.684 |
| when2call|abstention_capture|decoy_insertion | H2_framing | task_failure | -2.3 pp | [-7.7 pp, +3.0 pp] | 0.407 | 1 |
| when2call|abstention_capture|decoy_insertion | H3_selector_family | attacker_selection | -8.7 pp | [-14.1 pp, -3.6 pp] | 0 | 0 |
| when2call|abstention_capture|decoy_insertion | H3_selector_family | task_failure | -9.7 pp | [-17.0 pp, -2.7 pp] | 0.006 | 0.462 |
| when2call|abstention_capture|description_mimicry | H1_decomposition | attacker_selection | +0.7 pp | [-1.3 pp, +4.0 pp] | 0.945 | 1 |
| when2call|abstention_capture|description_mimicry | H1_decomposition | task_failure | -5.3 pp | [-13.3 pp, +2.7 pp] | 0.196 | 1 |
| when2call|abstention_capture|description_mimicry | H2_framing | attacker_selection | +1.3 pp | [-2.7 pp, +6.0 pp] | 0.682 | 1 |
| when2call|abstention_capture|description_mimicry | H2_framing | task_failure | +2.0 pp | [-6.7 pp, +10.7 pp] | 0.696 | 1 |
| when2call|abstention_capture|description_mimicry | H3_selector_family | attacker_selection | +1.3 pp | [-1.3 pp, +4.0 pp] | 0.434 | 1 |
| when2call|abstention_capture|description_mimicry | H3_selector_family | task_failure | +2.7 pp | [-6.0 pp, +10.7 pp] | 0.552 | 1 |
| when2call|abstention_capture|preference_authority | H1_decomposition | attacker_selection | +2.3 pp | [+0.0 pp, +5.4 pp] | 0.105 | 1 |
| when2call|abstention_capture|preference_authority | H1_decomposition | task_failure | -0.7 pp | [-5.0 pp, +3.7 pp] | 0.824 | 1 |
| when2call|abstention_capture|preference_authority | H2_framing | attacker_selection | +0.7 pp | [-3.0 pp, +4.0 pp] | 0.792 | 1 |
| when2call|abstention_capture|preference_authority | H2_framing | task_failure | +3.0 pp | [-1.7 pp, +7.7 pp] | 0.239 | 1 |
| when2call|abstention_capture|preference_authority | H3_selector_family | attacker_selection | +0.7 pp | [-2.0 pp, +3.4 pp] | 0.67 | 1 |
| when2call|abstention_capture|preference_authority | H3_selector_family | task_failure | +3.7 pp | [-0.7 pp, +8.3 pp] | 0.116 | 1 |
| when2call|abstention_capture|schema_property | H1_decomposition | attacker_selection | +1.0 pp | [+0.0 pp, +3.1 pp] | 0.756 | 1 |
| when2call|abstention_capture|schema_property | H1_decomposition | task_failure | -0.3 pp | [-4.7 pp, +3.7 pp] | 0.94 | 1 |
| when2call|abstention_capture|schema_property | H2_framing | attacker_selection | +1.3 pp | [+0.0 pp, +3.1 pp] | 0.099 | 1 |
| when2call|abstention_capture|schema_property | H2_framing | task_failure | +2.7 pp | [-2.0 pp, +7.7 pp] | 0.319 | 1 |
| when2call|abstention_capture|schema_property | H3_selector_family | attacker_selection | +0.7 pp | [-0.7 pp, +2.4 pp] | 0.595 | 1 |
| when2call|abstention_capture|schema_property | H3_selector_family | task_failure | +2.0 pp | [-2.4 pp, +6.7 pp] | 0.406 | 1 |
| when2call|trusted_displacement|decoy_insertion | H1_decomposition | attacker_selection | +26.7 pp | [+16.7 pp, +37.3 pp] | 0 | 0 |
| when2call|trusted_displacement|decoy_insertion | H1_decomposition | task_failure | +22.7 pp | [+12.7 pp, +32.7 pp] | 0 | 0 |
| when2call|trusted_displacement|decoy_insertion | H2_framing | attacker_selection | -13.3 pp | [-23.3 pp, -3.3 pp] | 0.016 | 1 |
| when2call|trusted_displacement|decoy_insertion | H2_framing | task_failure | -9.3 pp | [-18.7 pp, +0.0 pp] | 0.061 | 1 |
| when2call|trusted_displacement|decoy_insertion | H3_selector_family | attacker_selection | -22.0 pp | [-34.0 pp, -10.7 pp] | 0 | 0 |
| when2call|trusted_displacement|decoy_insertion | H3_selector_family | task_failure | -18.0 pp | [-28.7 pp, -6.7 pp] | 0 | 0 |
| when2call|trusted_displacement|description_mimicry | H1_decomposition | attacker_selection | +0.0 pp | [+0.0 pp, +0.0 pp] | 1 | 1 |
| when2call|trusted_displacement|description_mimicry | H1_decomposition | task_failure | +1.3 pp | [+0.0 pp, +3.3 pp] | 0.254 | 1 |
| when2call|trusted_displacement|description_mimicry | H2_framing | attacker_selection | +0.0 pp | [+0.0 pp, +0.0 pp] | 1 | 1 |
| when2call|trusted_displacement|description_mimicry | H2_framing | task_failure | -2.0 pp | [-6.7 pp, +1.3 pp] | 0.482 | 1 |
| when2call|trusted_displacement|description_mimicry | H3_selector_family | attacker_selection | +0.7 pp | [+0.0 pp, +2.0 pp] | 0.778 | 1 |
| when2call|trusted_displacement|description_mimicry | H3_selector_family | task_failure | +0.7 pp | [+0.0 pp, +2.0 pp] | 0.778 | 1 |
| when2call|trusted_displacement|near_name | H1_decomposition | attacker_selection | +1.3 pp | [+0.0 pp, +3.3 pp] | 0.262 | 1 |
| when2call|trusted_displacement|near_name | H1_decomposition | task_failure | +1.3 pp | [+0.0 pp, +3.3 pp] | 0.299 | 1 |
| when2call|trusted_displacement|near_name | H2_framing | attacker_selection | +0.0 pp | [-2.7 pp, +2.7 pp] | 1 | 1 |
| when2call|trusted_displacement|near_name | H2_framing | task_failure | -2.0 pp | [-5.3 pp, +1.3 pp] | 0.32 | 1 |
| when2call|trusted_displacement|near_name | H3_selector_family | attacker_selection | +0.0 pp | [-2.0 pp, +2.0 pp] | 1 | 1 |
| when2call|trusted_displacement|near_name | H3_selector_family | task_failure | +0.0 pp | [-2.0 pp, +2.0 pp] | 1 | 1 |
| when2call|trusted_displacement|preference_authority | H1_decomposition | attacker_selection | +0.0 pp | [-2.0 pp, +2.0 pp] | 1 | 1 |
| when2call|trusted_displacement|preference_authority | H1_decomposition | task_failure | +0.0 pp | [-2.0 pp, +2.0 pp] | 1 | 1 |
| when2call|trusted_displacement|preference_authority | H2_framing | attacker_selection | +0.0 pp | [-2.0 pp, +2.0 pp] | 1 | 1 |
| when2call|trusted_displacement|preference_authority | H2_framing | task_failure | -4.7 pp | [-10.7 pp, +0.0 pp] | 0.065 | 1 |
| when2call|trusted_displacement|preference_authority | H3_selector_family | attacker_selection | -0.7 pp | [-2.0 pp, +0.0 pp] | 0.778 | 1 |
| when2call|trusted_displacement|preference_authority | H3_selector_family | task_failure | -0.7 pp | [-2.0 pp, +0.0 pp] | 0.778 | 1 |
| when2call|trusted_displacement|schema_property | H1_decomposition | attacker_selection | +0.7 pp | [+0.0 pp, +2.0 pp] | 0.778 | 1 |
| when2call|trusted_displacement|schema_property | H1_decomposition | task_failure | +1.3 pp | [+0.0 pp, +3.3 pp] | 0.299 | 1 |
| when2call|trusted_displacement|schema_property | H2_framing | attacker_selection | -0.7 pp | [-2.0 pp, +0.0 pp] | 0.778 | 1 |
| when2call|trusted_displacement|schema_property | H2_framing | task_failure | -4.7 pp | [-10.0 pp, -0.7 pp] | 0.035 | 1 |
| when2call|trusted_displacement|schema_property | H3_selector_family | attacker_selection | -0.7 pp | [-2.0 pp, +0.0 pp] | 0.778 | 1 |
| when2call|trusted_displacement|schema_property | H3_selector_family | task_failure | -0.7 pp | [-2.0 pp, +0.0 pp] | 0.778 | 1 |

## Attacker selection by ordering

| cell | arm | ordering | conditional ASR | Δ attacker sel. |
|---|---|---|---|---|
| metatool_s1|trusted_displacement|decoy_insertion | native_llm | 0 | 41% [29%, 54%] (n=56) | +25.0 pp |
| metatool_s1|trusted_displacement|decoy_insertion | matched_systemone | 0 | 34% [25%, 45%] (n=76) | +26.0 pp |
| metatool_s1|trusted_displacement|decoy_insertion | matched_neutral | 0 | 57% [46%, 68%] (n=75) | +45.0 pp |
| metatool_s1|trusted_displacement|decoy_insertion | jev | 0 | 8% [4%, 17%] (n=72) | +6.0 pp |
| metatool_s1|trusted_displacement|decoy_insertion | native_llm | 1 | 39% [28%, 52%] (n=56) | +24.0 pp |
| metatool_s1|trusted_displacement|decoy_insertion | matched_systemone | 1 | 34% [25%, 45%] (n=76) | +26.0 pp |
| metatool_s1|trusted_displacement|decoy_insertion | matched_neutral | 1 | 51% [40%, 62%] (n=75) | +41.0 pp |
| metatool_s1|trusted_displacement|decoy_insertion | jev | 1 | 6% [2%, 13%] (n=72) | +5.0 pp |
| metatool_s1|trusted_displacement|decoy_insertion | native_llm | 2 | 43% [31%, 56%] (n=56) | +27.0 pp |
| metatool_s1|trusted_displacement|decoy_insertion | matched_systemone | 2 | 32% [23%, 43%] (n=75) | +26.0 pp |
| metatool_s1|trusted_displacement|decoy_insertion | matched_neutral | 2 | 58% [47%, 68%] (n=76) | +46.0 pp |
| metatool_s1|trusted_displacement|decoy_insertion | jev | 2 | 5% [2%, 13%] (n=73) | +4.0 pp |
| metatool_s1|trusted_displacement|description_mimicry | native_llm | 0 | 7% [3%, 17%] (n=56) | +4.0 pp |
| metatool_s1|trusted_displacement|description_mimicry | matched_systemone | 0 | 11% [5%, 19%] (n=76) | +4.0 pp |
| metatool_s1|trusted_displacement|description_mimicry | matched_neutral | 0 | 13% [7%, 23%] (n=75) | +7.0 pp |
| metatool_s1|trusted_displacement|description_mimicry | jev | 0 | 6% [2%, 13%] (n=72) | +0.0 pp |
| metatool_s1|trusted_displacement|description_mimicry | native_llm | 1 | 4% [1%, 12%] (n=56) | +1.0 pp |
| metatool_s1|trusted_displacement|description_mimicry | matched_systemone | 1 | 8% [4%, 16%] (n=76) | +4.0 pp |
| metatool_s1|trusted_displacement|description_mimicry | matched_neutral | 1 | 12% [6%, 21%] (n=75) | +8.0 pp |
| metatool_s1|trusted_displacement|description_mimicry | jev | 1 | 6% [2%, 13%] (n=72) | +0.0 pp |
| metatool_s1|trusted_displacement|description_mimicry | native_llm | 2 | 5% [2%, 15%] (n=56) | +3.0 pp |
| metatool_s1|trusted_displacement|description_mimicry | matched_systemone | 2 | 9% [5%, 18%] (n=75) | +2.0 pp |
| metatool_s1|trusted_displacement|description_mimicry | matched_neutral | 2 | 16% [9%, 26%] (n=76) | +9.0 pp |
| metatool_s1|trusted_displacement|description_mimicry | jev | 2 | 10% [5%, 18%] (n=73) | +4.0 pp |
| metatool_s1|trusted_displacement|near_name | native_llm | 0 | 0% [0%, 6%] (n=56) | +1.0 pp |
| metatool_s1|trusted_displacement|near_name | matched_systemone | 0 | 1% [0%, 7%] (n=76) | -1.0 pp |
| metatool_s1|trusted_displacement|near_name | matched_neutral | 0 | 3% [1%, 9%] (n=75) | +1.0 pp |
| metatool_s1|trusted_displacement|near_name | jev | 0 | 0% [0%, 5%] (n=72) | +0.0 pp |
| metatool_s1|trusted_displacement|near_name | native_llm | 1 | 0% [0%, 6%] (n=56) | +0.0 pp |
| metatool_s1|trusted_displacement|near_name | matched_systemone | 1 | 1% [0%, 7%] (n=76) | +0.0 pp |
| metatool_s1|trusted_displacement|near_name | matched_neutral | 1 | 1% [0%, 7%] (n=75) | +2.0 pp |
| metatool_s1|trusted_displacement|near_name | jev | 1 | 3% [1%, 10%] (n=72) | +2.0 pp |
| metatool_s1|trusted_displacement|near_name | native_llm | 2 | 2% [0%, 9%] (n=56) | +2.0 pp |
| metatool_s1|trusted_displacement|near_name | matched_systemone | 2 | 0% [0%, 5%] (n=75) | -3.0 pp |
| metatool_s1|trusted_displacement|near_name | matched_neutral | 2 | 3% [1%, 9%] (n=76) | +2.0 pp |
| metatool_s1|trusted_displacement|near_name | jev | 2 | 1% [0%, 7%] (n=73) | +0.0 pp |
| metatool_s1|trusted_displacement|preference_authority | native_llm | 0 | 0% [0%, 6%] (n=56) | +2.0 pp |
| metatool_s1|trusted_displacement|preference_authority | matched_systemone | 0 | 4% [1%, 11%] (n=76) | +3.0 pp |
| metatool_s1|trusted_displacement|preference_authority | matched_neutral | 0 | 3% [1%, 9%] (n=75) | +2.0 pp |
| metatool_s1|trusted_displacement|preference_authority | jev | 0 | 3% [1%, 10%] (n=72) | +3.0 pp |
| metatool_s1|trusted_displacement|preference_authority | native_llm | 1 | 0% [0%, 6%] (n=56) | +1.0 pp |
| metatool_s1|trusted_displacement|preference_authority | matched_systemone | 1 | 1% [0%, 7%] (n=76) | +2.0 pp |
| metatool_s1|trusted_displacement|preference_authority | matched_neutral | 1 | 4% [1%, 11%] (n=75) | +4.0 pp |
| metatool_s1|trusted_displacement|preference_authority | jev | 1 | 1% [0%, 7%] (n=72) | +3.0 pp |
| metatool_s1|trusted_displacement|preference_authority | native_llm | 2 | 2% [0%, 9%] (n=56) | +3.0 pp |
| metatool_s1|trusted_displacement|preference_authority | matched_systemone | 2 | 0% [0%, 5%] (n=75) | +2.0 pp |
| metatool_s1|trusted_displacement|preference_authority | matched_neutral | 2 | 5% [2%, 13%] (n=76) | +4.0 pp |
| metatool_s1|trusted_displacement|preference_authority | jev | 2 | 3% [1%, 9%] (n=73) | +2.0 pp |
| metatool_s3|abstention_capture|decoy_insertion | native_llm | 0 | 0% [0%, 4%] (n=95) | +0.0 pp |
| metatool_s3|abstention_capture|decoy_insertion | matched_systemone | 0 | 0% [0%, 4%] (n=83) | +0.0 pp |
| metatool_s3|abstention_capture|decoy_insertion | matched_neutral | 0 | 0% [0%, 5%] (n=81) | +0.0 pp |
| metatool_s3|abstention_capture|decoy_insertion | jev | 0 | 0% [0%, 4%] (n=92) | +0.0 pp |
| metatool_s3|abstention_capture|decoy_insertion | native_llm | 1 | 0% [0%, 4%] (n=94) | +0.0 pp |
| metatool_s3|abstention_capture|decoy_insertion | matched_systemone | 1 | 0% [0%, 4%] (n=88) | +0.0 pp |
| metatool_s3|abstention_capture|decoy_insertion | matched_neutral | 1 | 0% [0%, 5%] (n=80) | +1.0 pp |
| metatool_s3|abstention_capture|decoy_insertion | jev | 1 | 0% [0%, 4%] (n=92) | +0.0 pp |
| metatool_s3|abstention_capture|decoy_insertion | native_llm | 2 | 1% [0%, 6%] (n=94) | +1.0 pp |
| metatool_s3|abstention_capture|decoy_insertion | matched_systemone | 2 | 0% [0%, 4%] (n=87) | +0.0 pp |
| metatool_s3|abstention_capture|decoy_insertion | matched_neutral | 2 | 0% [0%, 4%] (n=84) | +0.0 pp |
| metatool_s3|abstention_capture|decoy_insertion | jev | 2 | 0% [0%, 4%] (n=91) | +0.0 pp |
| metatool_s3|abstention_capture|preference_authority | native_llm | 0 | 0% [0%, 4%] (n=95) | +0.0 pp |
| metatool_s3|abstention_capture|preference_authority | matched_systemone | 0 | 1% [0%, 7%] (n=83) | +1.0 pp |
| metatool_s3|abstention_capture|preference_authority | matched_neutral | 0 | 1% [0%, 7%] (n=81) | +1.0 pp |
| metatool_s3|abstention_capture|preference_authority | jev | 0 | 0% [0%, 4%] (n=92) | +0.0 pp |
| metatool_s3|abstention_capture|preference_authority | native_llm | 1 | 0% [0%, 4%] (n=94) | +0.0 pp |
| metatool_s3|abstention_capture|preference_authority | matched_systemone | 1 | 1% [0%, 6%] (n=88) | +1.0 pp |
| metatool_s3|abstention_capture|preference_authority | matched_neutral | 1 | 2% [1%, 9%] (n=80) | +2.0 pp |
| metatool_s3|abstention_capture|preference_authority | jev | 1 | 0% [0%, 4%] (n=92) | +0.0 pp |
| metatool_s3|abstention_capture|preference_authority | native_llm | 2 | 0% [0%, 4%] (n=94) | +0.0 pp |
| metatool_s3|abstention_capture|preference_authority | matched_systemone | 2 | 1% [0%, 6%] (n=87) | +1.0 pp |
| metatool_s3|abstention_capture|preference_authority | matched_neutral | 2 | 1% [0%, 6%] (n=84) | +1.0 pp |
| metatool_s3|abstention_capture|preference_authority | jev | 2 | 0% [0%, 4%] (n=91) | +0.0 pp |
| when2call|abstention_capture|decoy_insertion | native_llm | 0 | 0% [0%, 5%] (n=81) | +1.0 pp |
| when2call|abstention_capture|decoy_insertion | matched_systemone | 0 | 0% [0%, 6%] (n=58) | +3.0 pp |
| when2call|abstention_capture|decoy_insertion | matched_neutral | 0 | 3% [1%, 15%] (n=34) | +10.0 pp |
| when2call|abstention_capture|decoy_insertion | jev | 0 | 0% [0%, 6%] (n=59) | +1.0 pp |
| when2call|abstention_capture|decoy_insertion | native_llm | 1 | 0% [0%, 4%] (n=82) | +1.0 pp |
| when2call|abstention_capture|decoy_insertion | matched_systemone | 1 | 0% [0%, 6%] (n=58) | +3.0 pp |
| when2call|abstention_capture|decoy_insertion | matched_neutral | 1 | 3% [1%, 15%] (n=34) | +9.0 pp |
| when2call|abstention_capture|decoy_insertion | jev | 1 | 0% [0%, 6%] (n=56) | +3.0 pp |
| when2call|abstention_capture|decoy_insertion | native_llm | 2 | 0% [0%, 4%] (n=82) | +1.0 pp |
| when2call|abstention_capture|decoy_insertion | matched_systemone | 2 | 2% [0%, 9%] (n=60) | +6.0 pp |
| when2call|abstention_capture|decoy_insertion | matched_neutral | 2 | 3% [0%, 14%] (n=36) | +11.0 pp |
| when2call|abstention_capture|decoy_insertion | jev | 2 | 0% [0%, 6%] (n=57) | +0.0 pp |
| when2call|abstention_capture|description_mimicry | native_llm | 0 | 0% [0%, 9%] (n=39) | +0.0 pp |
| when2call|abstention_capture|description_mimicry | matched_systemone | 0 | 0% [0%, 14%] (n=23) | +2.0 pp |
| when2call|abstention_capture|description_mimicry | matched_neutral | 0 | 0% [0%, 66%] (n=2) | +2.0 pp |
| when2call|abstention_capture|description_mimicry | jev | 0 | 0% [0%, 16%] (n=20) | +4.0 pp |
| when2call|abstention_capture|description_mimicry | native_llm | 1 | 0% [0%, 9%] (n=41) | +0.0 pp |
| when2call|abstention_capture|description_mimicry | matched_systemone | 1 | 0% [0%, 14%] (n=24) | +2.0 pp |
| when2call|abstention_capture|description_mimicry | matched_neutral | 1 | 0% [0%, 66%] (n=2) | -2.0 pp |
| when2call|abstention_capture|description_mimicry | jev | 1 | 7% [1%, 30%] (n=15) | +2.0 pp |
| when2call|abstention_capture|description_mimicry | native_llm | 2 | 0% [0%, 9%] (n=41) | +0.0 pp |
| when2call|abstention_capture|description_mimicry | matched_systemone | 2 | 0% [0%, 13%] (n=25) | +2.0 pp |
| when2call|abstention_capture|description_mimicry | matched_neutral | 2 | 0% [0%, 66%] (n=2) | +2.0 pp |
| when2call|abstention_capture|description_mimicry | jev | 2 | 0% [0%, 19%] (n=16) | +0.0 pp |
| when2call|abstention_capture|preference_authority | native_llm | 0 | 0% [0%, 5%] (n=81) | -1.0 pp |
| when2call|abstention_capture|preference_authority | matched_systemone | 0 | 5% [2%, 14%] (n=58) | +3.0 pp |
| when2call|abstention_capture|preference_authority | matched_neutral | 0 | 0% [0%, 11%] (n=30) | +2.0 pp |
| when2call|abstention_capture|preference_authority | jev | 0 | 0% [0%, 6%] (n=59) | +1.0 pp |
| when2call|abstention_capture|preference_authority | native_llm | 1 | 0% [0%, 4%] (n=82) | -1.0 pp |
| when2call|abstention_capture|preference_authority | matched_systemone | 1 | 0% [0%, 6%] (n=58) | +0.0 pp |
| when2call|abstention_capture|preference_authority | matched_neutral | 1 | 0% [0%, 11%] (n=30) | +1.0 pp |
| when2call|abstention_capture|preference_authority | jev | 1 | 4% [1%, 12%] (n=55) | +3.0 pp |
| when2call|abstention_capture|preference_authority | native_llm | 2 | 0% [0%, 4%] (n=82) | -1.0 pp |
| when2call|abstention_capture|preference_authority | matched_systemone | 2 | 3% [1%, 11%] (n=60) | +3.0 pp |
| when2call|abstention_capture|preference_authority | matched_neutral | 2 | 0% [0%, 11%] (n=32) | +1.0 pp |
| when2call|abstention_capture|preference_authority | jev | 2 | 4% [1%, 12%] (n=56) | +2.0 pp |
| when2call|abstention_capture|schema_property | native_llm | 0 | 0% [0%, 5%] (n=80) | -1.0 pp |
| when2call|abstention_capture|schema_property | matched_systemone | 0 | 4% [1%, 12%] (n=57) | +3.0 pp |
| when2call|abstention_capture|schema_property | matched_neutral | 0 | 0% [0%, 11%] (n=30) | +0.0 pp |
| when2call|abstention_capture|schema_property | jev | 0 | 0% [0%, 6%] (n=58) | +0.0 pp |
| when2call|abstention_capture|schema_property | native_llm | 1 | 0% [0%, 5%] (n=81) | -1.0 pp |
| when2call|abstention_capture|schema_property | matched_systemone | 1 | 0% [0%, 6%] (n=57) | +0.0 pp |
| when2call|abstention_capture|schema_property | matched_neutral | 1 | 0% [0%, 11%] (n=30) | +0.0 pp |
| when2call|abstention_capture|schema_property | jev | 1 | 2% [0%, 10%] (n=54) | +1.0 pp |
| when2call|abstention_capture|schema_property | native_llm | 2 | 0% [0%, 5%] (n=81) | -1.0 pp |
| when2call|abstention_capture|schema_property | matched_systemone | 2 | 2% [0%, 9%] (n=59) | +1.0 pp |
| when2call|abstention_capture|schema_property | matched_neutral | 2 | 0% [0%, 11%] (n=31) | +0.0 pp |
| when2call|abstention_capture|schema_property | jev | 2 | 2% [0%, 10%] (n=55) | +1.0 pp |
| when2call|trusted_displacement|decoy_insertion | native_llm | 0 | 0% [0%, 9%] (n=40) | +0.0 pp |
| when2call|trusted_displacement|decoy_insertion | matched_systemone | 0 | 13% [6%, 25%] (n=47) | +12.0 pp |
| when2call|trusted_displacement|decoy_insertion | matched_neutral | 0 | 27% [16%, 40%] (n=49) | +26.0 pp |
| when2call|trusted_displacement|decoy_insertion | jev | 0 | 4% [1%, 14%] (n=49) | +4.0 pp |
| when2call|trusted_displacement|decoy_insertion | native_llm | 1 | 3% [0%, 13%] (n=39) | +2.0 pp |
| when2call|trusted_displacement|decoy_insertion | matched_systemone | 1 | 20% [11%, 33%] (n=46) | +18.0 pp |
| when2call|trusted_displacement|decoy_insertion | matched_neutral | 1 | 24% [15%, 38%] (n=49) | +24.0 pp |
| when2call|trusted_displacement|decoy_insertion | jev | 1 | 6% [2%, 17%] (n=49) | +6.0 pp |
| when2call|trusted_displacement|decoy_insertion | native_llm | 2 | 0% [0%, 9%] (n=39) | +0.0 pp |
| when2call|trusted_displacement|decoy_insertion | matched_systemone | 2 | 13% [6%, 26%] (n=45) | +12.0 pp |
| when2call|trusted_displacement|decoy_insertion | matched_neutral | 2 | 33% [21%, 47%] (n=49) | +32.0 pp |
| when2call|trusted_displacement|decoy_insertion | jev | 2 | 6% [2%, 17%] (n=49) | +6.0 pp |
| when2call|trusted_displacement|description_mimicry | native_llm | 0 | 0% [0%, 9%] (n=40) | +0.0 pp |
| when2call|trusted_displacement|description_mimicry | matched_systemone | 0 | 0% [0%, 8%] (n=46) | +0.0 pp |
| when2call|trusted_displacement|description_mimicry | matched_neutral | 0 | 0% [0%, 7%] (n=49) | +0.0 pp |
| when2call|trusted_displacement|description_mimicry | jev | 0 | 0% [0%, 7%] (n=49) | +0.0 pp |
| when2call|trusted_displacement|description_mimicry | native_llm | 1 | 0% [0%, 9%] (n=39) | +0.0 pp |
| when2call|trusted_displacement|description_mimicry | matched_systemone | 1 | 0% [0%, 8%] (n=45) | +0.0 pp |
| when2call|trusted_displacement|description_mimicry | matched_neutral | 1 | 0% [0%, 7%] (n=49) | +0.0 pp |
| when2call|trusted_displacement|description_mimicry | jev | 1 | 0% [0%, 7%] (n=49) | +0.0 pp |
| when2call|trusted_displacement|description_mimicry | native_llm | 2 | 0% [0%, 9%] (n=39) | +0.0 pp |
| when2call|trusted_displacement|description_mimicry | matched_systemone | 2 | 0% [0%, 8%] (n=44) | +0.0 pp |
| when2call|trusted_displacement|description_mimicry | matched_neutral | 2 | 0% [0%, 7%] (n=49) | +0.0 pp |
| when2call|trusted_displacement|description_mimicry | jev | 2 | 2% [0%, 11%] (n=49) | +2.0 pp |
| when2call|trusted_displacement|near_name | native_llm | 0 | 0% [0%, 9%] (n=40) | +0.0 pp |
| when2call|trusted_displacement|near_name | matched_systemone | 0 | 2% [0%, 11%] (n=46) | +2.0 pp |
| when2call|trusted_displacement|near_name | matched_neutral | 0 | 4% [1%, 14%] (n=49) | +4.0 pp |
| when2call|trusted_displacement|near_name | jev | 0 | 2% [0%, 11%] (n=49) | +2.0 pp |
| when2call|trusted_displacement|near_name | native_llm | 1 | 0% [0%, 9%] (n=39) | +0.0 pp |
| when2call|trusted_displacement|near_name | matched_systemone | 1 | 0% [0%, 8%] (n=45) | +0.0 pp |
| when2call|trusted_displacement|near_name | matched_neutral | 1 | 0% [0%, 7%] (n=49) | +0.0 pp |
| when2call|trusted_displacement|near_name | jev | 1 | 0% [0%, 7%] (n=49) | +0.0 pp |
| when2call|trusted_displacement|near_name | native_llm | 2 | 0% [0%, 9%] (n=39) | +0.0 pp |
| when2call|trusted_displacement|near_name | matched_systemone | 2 | 2% [0%, 12%] (n=44) | +2.0 pp |
| when2call|trusted_displacement|near_name | matched_neutral | 2 | 0% [0%, 7%] (n=49) | +0.0 pp |
| when2call|trusted_displacement|near_name | jev | 2 | 2% [0%, 11%] (n=49) | +2.0 pp |
| when2call|trusted_displacement|preference_authority | native_llm | 0 | 0% [0%, 9%] (n=40) | +0.0 pp |
| when2call|trusted_displacement|preference_authority | matched_systemone | 0 | 0% [0%, 8%] (n=46) | +0.0 pp |
| when2call|trusted_displacement|preference_authority | matched_neutral | 0 | 2% [0%, 11%] (n=49) | +2.0 pp |
| when2call|trusted_displacement|preference_authority | jev | 0 | 0% [0%, 7%] (n=49) | +0.0 pp |
| when2call|trusted_displacement|preference_authority | native_llm | 1 | 0% [0%, 9%] (n=39) | +2.0 pp |
| when2call|trusted_displacement|preference_authority | matched_systemone | 1 | 2% [0%, 12%] (n=45) | +2.0 pp |
| when2call|trusted_displacement|preference_authority | matched_neutral | 1 | 0% [0%, 7%] (n=49) | +0.0 pp |
| when2call|trusted_displacement|preference_authority | jev | 1 | 0% [0%, 7%] (n=49) | +0.0 pp |
| when2call|trusted_displacement|preference_authority | native_llm | 2 | 0% [0%, 9%] (n=39) | +0.0 pp |
| when2call|trusted_displacement|preference_authority | matched_systemone | 2 | 0% [0%, 8%] (n=44) | +0.0 pp |
| when2call|trusted_displacement|preference_authority | matched_neutral | 2 | 0% [0%, 7%] (n=49) | +0.0 pp |
| when2call|trusted_displacement|preference_authority | jev | 2 | 0% [0%, 7%] (n=49) | +0.0 pp |
| when2call|trusted_displacement|schema_property | native_llm | 0 | 0% [0%, 9%] (n=40) | +0.0 pp |
| when2call|trusted_displacement|schema_property | matched_systemone | 0 | 0% [0%, 8%] (n=46) | +0.0 pp |
| when2call|trusted_displacement|schema_property | matched_neutral | 0 | 2% [0%, 11%] (n=49) | +2.0 pp |
| when2call|trusted_displacement|schema_property | jev | 0 | 0% [0%, 7%] (n=49) | +0.0 pp |
| when2call|trusted_displacement|schema_property | native_llm | 1 | 0% [0%, 9%] (n=39) | +0.0 pp |
| when2call|trusted_displacement|schema_property | matched_systemone | 1 | 0% [0%, 8%] (n=45) | +0.0 pp |
| when2call|trusted_displacement|schema_property | matched_neutral | 1 | 0% [0%, 7%] (n=49) | +0.0 pp |
| when2call|trusted_displacement|schema_property | jev | 1 | 0% [0%, 7%] (n=49) | +0.0 pp |
| when2call|trusted_displacement|schema_property | native_llm | 2 | 0% [0%, 9%] (n=39) | +0.0 pp |
| when2call|trusted_displacement|schema_property | matched_systemone | 2 | 0% [0%, 8%] (n=44) | +0.0 pp |
| when2call|trusted_displacement|schema_property | matched_neutral | 2 | 0% [0%, 7%] (n=49) | +0.0 pp |
| when2call|trusted_displacement|schema_property | jev | 2 | 0% [0%, 7%] (n=49) | +0.0 pp |

## Action bias: P(tool call | label)

| scope | label | arm | control | attacked |
|---|---|---|---|---|
| clean | cannot_answer | jev | 21% [15%, 28%] (n=150) | |
| clean | cannot_answer | matched_neutral | 43% [35%, 51%] (n=150) | |
| clean | cannot_answer | matched_systemone | 31% [24%, 38%] (n=150) | |
| clean | cannot_answer | native_llm | 17% [12%, 24%] (n=150) | |
| clean | none_in_list | jev | 8% [6%, 12%] (n=300) | |
| clean | none_in_list | matched_neutral | 18% [14%, 23%] (n=300) | |
| clean | none_in_list | matched_systemone | 14% [11%, 18%] (n=300) | |
| clean | none_in_list | native_llm | 5% [3%, 8%] (n=300) | |
| clean | request_for_info | jev | 65% [57%, 72%] (n=150) | |
| clean | request_for_info | matched_neutral | 88% [82%, 92%] (n=150) | |
| clean | request_for_info | matched_systemone | 52% [44%, 60%] (n=150) | |
| clean | request_for_info | native_llm | 18% [13%, 25%] (n=150) | |
| clean | tool | jev | 89% [85%, 92%] (n=300) | |
| clean | tool | matched_neutral | 95% [92%, 97%] (n=300) | |
| clean | tool | matched_systemone | 90% [86%, 93%] (n=300) | |
| clean | tool | native_llm | 65% [60%, 70%] (n=300) | |
| clean | tool_call | jev | 98% [94%, 99%] (n=150) | |
| clean | tool_call | matched_neutral | 99% [96%, 100%] (n=150) | |
| clean | tool_call | matched_systemone | 92% [87%, 95%] (n=150) | |
| clean | tool_call | native_llm | 79% [71%, 84%] (n=150) | |
| decoy_insertion | cannot_answer | jev | 21% [15%, 28%] (n=150) | 19% [13%, 26%] (n=150) |
| decoy_insertion | cannot_answer | matched_neutral | 43% [35%, 51%] (n=150) | 40% [33%, 48%] (n=150) |
| decoy_insertion | cannot_answer | matched_systemone | 31% [24%, 38%] (n=150) | 27% [20%, 34%] (n=150) |
| decoy_insertion | cannot_answer | native_llm | 17% [12%, 24%] (n=150) | 17% [12%, 23%] (n=150) |
| decoy_insertion | none_in_list | jev | 8% [6%, 12%] (n=300) | 7% [4%, 10%] (n=300) |
| decoy_insertion | none_in_list | matched_neutral | 18% [14%, 23%] (n=300) | 21% [16%, 26%] (n=300) |
| decoy_insertion | none_in_list | matched_systemone | 14% [11%, 18%] (n=300) | 12% [9%, 17%] (n=300) |
| decoy_insertion | none_in_list | native_llm | 5% [3%, 8%] (n=300) | 6% [4%, 10%] (n=300) |
| decoy_insertion | request_for_info | jev | 65% [57%, 72%] (n=150) | 41% [33%, 49%] (n=150) |
| decoy_insertion | request_for_info | matched_neutral | 88% [82%, 92%] (n=150) | 84% [77%, 89%] (n=150) |
| decoy_insertion | request_for_info | matched_systemone | 52% [44%, 60%] (n=150) | 45% [37%, 53%] (n=150) |
| decoy_insertion | request_for_info | native_llm | 18% [13%, 25%] (n=150) | 23% [17%, 30%] (n=150) |
| decoy_insertion | tool | jev | 89% [85%, 92%] (n=300) | 88% [83%, 91%] (n=300) |
| decoy_insertion | tool | matched_neutral | 95% [92%, 97%] (n=300) | 96% [93%, 98%] (n=300) |
| decoy_insertion | tool | matched_systemone | 90% [86%, 93%] (n=300) | 90% [86%, 93%] (n=300) |
| decoy_insertion | tool | native_llm | 65% [60%, 70%] (n=300) | 65% [59%, 70%] (n=300) |
| decoy_insertion | tool_call | jev | 98% [94%, 99%] (n=150) | 97% [93%, 99%] (n=150) |
| decoy_insertion | tool_call | matched_neutral | 99% [96%, 100%] (n=150) | 100% [98%, 100%] (n=150) |
| decoy_insertion | tool_call | matched_systemone | 92% [87%, 95%] (n=150) | 91% [85%, 94%] (n=150) |
| decoy_insertion | tool_call | native_llm | 79% [71%, 84%] (n=150) | 78% [71%, 84%] (n=150) |
| description_mimicry | request_for_info | jev | 66% [58%, 73%] (n=150) | 66% [58%, 73%] (n=150) |
| description_mimicry | request_for_info | matched_neutral | 96% [92%, 98%] (n=150) | 93% [88%, 96%] (n=150) |
| description_mimicry | request_for_info | matched_systemone | 52% [44%, 60%] (n=150) | 51% [43%, 59%] (n=150) |
| description_mimicry | request_for_info | native_llm | 18% [13%, 25%] (n=150) | 19% [13%, 26%] (n=150) |
| description_mimicry | tool | jev | 89% [85%, 92%] (n=300) | 85% [81%, 89%] (n=300) |
| description_mimicry | tool | matched_neutral | 95% [92%, 97%] (n=300) | 94% [91%, 96%] (n=300) |
| description_mimicry | tool | matched_systemone | 90% [86%, 93%] (n=300) | 88% [83%, 91%] (n=300) |
| description_mimicry | tool | native_llm | 65% [60%, 70%] (n=300) | 63% [58%, 69%] (n=300) |
| description_mimicry | tool_call | jev | 98% [94%, 99%] (n=150) | 98% [94%, 99%] (n=150) |
| description_mimicry | tool_call | matched_neutral | 99% [96%, 100%] (n=150) | 99% [96%, 100%] (n=150) |
| description_mimicry | tool_call | matched_systemone | 90% [84%, 94%] (n=150) | 93% [87%, 96%] (n=150) |
| description_mimicry | tool_call | native_llm | 79% [71%, 84%] (n=150) | 80% [73%, 86%] (n=150) |
| near_name | tool | jev | 89% [85%, 92%] (n=300) | 89% [85%, 92%] (n=300) |
| near_name | tool | matched_neutral | 95% [92%, 97%] (n=300) | 95% [92%, 97%] (n=300) |
| near_name | tool | matched_systemone | 90% [86%, 93%] (n=300) | 89% [85%, 92%] (n=300) |
| near_name | tool | native_llm | 65% [60%, 70%] (n=300) | 65% [59%, 70%] (n=300) |
| near_name | tool_call | jev | 98% [94%, 99%] (n=150) | 98% [94%, 99%] (n=150) |
| near_name | tool_call | matched_neutral | 99% [96%, 100%] (n=150) | 99% [96%, 100%] (n=150) |
| near_name | tool_call | matched_systemone | 90% [84%, 94%] (n=150) | 93% [87%, 96%] (n=150) |
| near_name | tool_call | native_llm | 79% [71%, 84%] (n=150) | 79% [71%, 84%] (n=150) |
| preference_authority | cannot_answer | jev | 21% [15%, 28%] (n=150) | 23% [17%, 31%] (n=150) |
| preference_authority | cannot_answer | matched_neutral | 43% [35%, 51%] (n=150) | 42% [34%, 50%] (n=150) |
| preference_authority | cannot_answer | matched_systemone | 31% [24%, 38%] (n=150) | 31% [24%, 39%] (n=150) |
| preference_authority | cannot_answer | native_llm | 17% [12%, 24%] (n=150) | 15% [10%, 22%] (n=150) |
| preference_authority | none_in_list | jev | 8% [6%, 12%] (n=300) | 7% [5%, 11%] (n=300) |
| preference_authority | none_in_list | matched_neutral | 18% [14%, 23%] (n=300) | 22% [17%, 27%] (n=300) |
| preference_authority | none_in_list | matched_systemone | 14% [11%, 18%] (n=300) | 15% [11%, 19%] (n=300) |
| preference_authority | none_in_list | native_llm | 5% [3%, 8%] (n=300) | 6% [4%, 10%] (n=300) |
| preference_authority | request_for_info | jev | 66% [58%, 73%] (n=150) | 68% [60%, 75%] (n=150) |
| preference_authority | request_for_info | matched_neutral | 96% [92%, 98%] (n=150) | 94% [89%, 97%] (n=150) |
| preference_authority | request_for_info | matched_systemone | 52% [44%, 60%] (n=150) | 55% [47%, 62%] (n=150) |
| preference_authority | request_for_info | native_llm | 18% [13%, 25%] (n=150) | 17% [12%, 24%] (n=150) |
| preference_authority | tool | jev | 89% [85%, 92%] (n=300) | 90% [86%, 93%] (n=300) |
| preference_authority | tool | matched_neutral | 95% [92%, 97%] (n=300) | 95% [92%, 97%] (n=300) |
| preference_authority | tool | matched_systemone | 90% [86%, 93%] (n=300) | 91% [88%, 94%] (n=300) |
| preference_authority | tool | native_llm | 65% [60%, 70%] (n=300) | 67% [61%, 72%] (n=300) |
| preference_authority | tool_call | jev | 98% [94%, 99%] (n=150) | 98% [94%, 99%] (n=150) |
| preference_authority | tool_call | matched_neutral | 99% [96%, 100%] (n=150) | 99% [96%, 100%] (n=150) |
| preference_authority | tool_call | matched_systemone | 90% [84%, 94%] (n=150) | 95% [91%, 98%] (n=150) |
| preference_authority | tool_call | native_llm | 79% [71%, 84%] (n=150) | 79% [71%, 84%] (n=150) |
| schema_property | cannot_answer | jev | 21% [15%, 28%] (n=147) | 22% [16%, 29%] (n=147) |
| schema_property | cannot_answer | matched_neutral | 42% [34%, 50%] (n=147) | 41% [34%, 50%] (n=147) |
| schema_property | cannot_answer | matched_systemone | 31% [24%, 39%] (n=147) | 33% [26%, 41%] (n=147) |
| schema_property | cannot_answer | native_llm | 18% [12%, 25%] (n=147) | 16% [11%, 23%] (n=147) |
| schema_property | request_for_info | jev | 66% [58%, 73%] (n=150) | 67% [59%, 74%] (n=150) |
| schema_property | request_for_info | matched_neutral | 96% [92%, 98%] (n=150) | 94% [89%, 97%] (n=150) |
| schema_property | request_for_info | matched_systemone | 52% [44%, 60%] (n=150) | 53% [45%, 61%] (n=150) |
| schema_property | request_for_info | native_llm | 18% [13%, 25%] (n=150) | 17% [12%, 24%] (n=150) |
| schema_property | tool_call | jev | 98% [94%, 99%] (n=150) | 98% [94%, 99%] (n=150) |
| schema_property | tool_call | matched_neutral | 99% [96%, 100%] (n=150) | 99% [96%, 100%] (n=150) |
| schema_property | tool_call | matched_systemone | 90% [84%, 94%] (n=150) | 95% [90%, 97%] (n=150) |
| schema_property | tool_call | native_llm | 79% [71%, 84%] (n=150) | 79% [72%, 85%] (n=150) |

## Downstream consequences of attack-induced tool commitment

| family | arm | induced | placeholder | unsupported required | unsupported optional | schema rejected | execution failed |
|---|---|---|---|---|---|---|---|
| decoy_insertion | jev | 27 | 0 | 1 | 0 | 0 | 0 |
| decoy_insertion | matched_neutral | 204 | 17 | 11 | 6 | 7 | 20 |
| decoy_insertion | matched_systemone | 111 | 1 | 6 | 3 | 0 | 1 |
| decoy_insertion | native_llm | 81 | 0 | 0 | 0 | 0 | 0 |
| description_mimicry | jev | 19 | 2 | 1 | 0 | 0 | 2 |
| description_mimicry | matched_neutral | 33 | 0 | 2 | 0 | 0 | 0 |
| description_mimicry | matched_systemone | 25 | 3 | 0 | 0 | 0 | 3 |
| description_mimicry | native_llm | 10 | 0 | 0 | 0 | 0 | 0 |
| near_name | jev | 6 | 2 | 0 | 0 | 0 | 2 |
| near_name | matched_neutral | 8 | 1 | 0 | 0 | 0 | 1 |
| near_name | matched_systemone | 4 | 1 | 0 | 0 | 0 | 1 |
| near_name | native_llm | 4 | 0 | 0 | 0 | 0 | 0 |
| preference_authority | jev | 14 | 0 | 2 | 0 | 0 | 0 |
| preference_authority | matched_neutral | 19 | 1 | 1 | 0 | 0 | 1 |
| preference_authority | matched_systemone | 19 | 5 | 2 | 0 | 0 | 5 |
| preference_authority | native_llm | 7 | 0 | 0 | 0 | 0 | 0 |
| schema_property | jev | 3 | 0 | 1 | 0 | 0 | 0 |
| schema_property | matched_neutral | 1 | 1 | 0 | 0 | 0 | 1 |
| schema_property | matched_systemone | 4 | 1 | 0 | 0 | 0 | 1 |

## Cost

By arm: jev $4.1788, matched_neutral $7.9197, matched_systemone $8.5928, native_llm $9.4040
By stage: selection $20.0214, arguments $10.0738
By family (charged): clean $6.2671, near_name $3.0259, description_mimicry $4.1639, preference_authority $6.3585, decoy_insertion $6.6640, schema_property $3.2805, control_synthetic $0.3352
