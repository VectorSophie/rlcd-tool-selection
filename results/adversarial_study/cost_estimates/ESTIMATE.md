# Adversarial study cost estimate

Conservative estimator, unchanged from the external pilot (chars/3 tokens, fixed output allowances, x1.25 margin, live OpenRouter prices; argument generation assumed for every decomposed task). Not discounted, although the pilot's actual spend was 0.58x its estimate.

**Status: STOPPED: over the global cap.** The complete primary study is estimated above the cap, so nothing is frozen or run. Reduced designs (not adopted without approval): R1: clean ablation at 3 orderings, attack groups B and C at 2 orderings (orderings 0 and 1), no BFCL holdout: $39.15; R2: 2 orderings for A, B and C, no BFCL holdout: $35.34; with the holdout $42.34; R3: the full design under a raised cap of $53.01 (primary) or $60.01 (with holdout); expected actual spend about 0.58x the estimate if the pilot ratio holds.

| group | dataset | family | estimate $ |
|---|---|---|---|
| A_clean | when2call | clean | 5.5520 |
| A_clean | metatool_s1 | clean | 2.9395 |
| A_clean | metatool_s3 | clean | 2.9215 |
| B_displacement | metatool_s1 | near_name | 2.9405 |
| B_displacement | metatool_s1 | description_mimicry | 2.9751 |
| B_displacement | metatool_s1 | preference_authority | 2.9612 |
| B_displacement | metatool_s1 | decoy_insertion | 3.0245 |
| B_displacement | when2call | near_name | 1.9539 |
| B_displacement | when2call | description_mimicry | 1.9763 |
| B_displacement | when2call | preference_authority | 1.9644 |
| B_displacement | when2call | schema_property | 1.9644 |
| B_displacement | when2call | decoy_insertion | 2.1443 |
| B_displacement | when2call | control_synthetic | 0.2851 |
| C_abstention | metatool_s3 | preference_authority | 2.9437 |
| C_abstention | metatool_s3 | decoy_insertion | 3.0085 |
| C_abstention | when2call | preference_authority | 3.6437 |
| C_abstention | when2call | schema_property | 3.6066 |
| C_abstention | when2call | description_mimicry | 1.9210 |
| C_abstention | when2call | decoy_insertion | 3.9798 |
| C_abstention | when2call | control_synthetic | 0.3077 |
| D_bfcl_holdout | bfcl_simple_python | clean | 0.4314 |
| D_bfcl_holdout | bfcl_simple_python | preference_authority | 0.4499 |
| D_bfcl_holdout | bfcl_simple_python | decoy_insertion | 0.4757 |
| D_bfcl_holdout | bfcl_simple_python | control_synthetic | 0.4470 |
| D_bfcl_holdout | bfcl_live_simple | clean | 0.4707 |
| D_bfcl_holdout | bfcl_live_simple | preference_authority | 0.4892 |
| D_bfcl_holdout | bfcl_live_simple | decoy_insertion | 0.5333 |
| D_bfcl_holdout | bfcl_live_simple | control_synthetic | 0.4863 |
| D_bfcl_holdout | bfcl_irrelevance | clean | 0.4270 |
| D_bfcl_holdout | bfcl_irrelevance | preference_authority | 0.4327 |
| D_bfcl_holdout | bfcl_irrelevance | decoy_insertion | 0.4715 |
| D_bfcl_holdout | bfcl_live_irrelevance | clean | 0.5964 |
| D_bfcl_holdout | bfcl_live_irrelevance | preference_authority | 0.6014 |
| D_bfcl_holdout | bfcl_live_irrelevance | decoy_insertion | 0.6883 |

| group | arm | selection $ | arguments $ |
|---|---|---|---|
| A_clean | native_llm | 2.6264 | 0.0000 |
| A_clean | matched_systemone | 1.8650 | 1.7587 |
| A_clean | matched_neutral | 1.4468 | 1.7587 |
| A_clean | jev | 0.1987 | 1.7587 |
| B_displacement | native_llm | 5.1784 | 0.0000 |
| B_displacement | matched_systemone | 3.6975 | 3.3308 |
| B_displacement | matched_neutral | 2.9088 | 3.3308 |
| B_displacement | jev | 0.4126 | 3.3308 |
| C_abstention | native_llm | 4.3753 | 0.0000 |
| C_abstention | matched_systemone | 3.2868 | 2.9166 |
| C_abstention | matched_neutral | 2.6176 | 2.9166 |
| C_abstention | jev | 0.3815 | 2.9166 |
| D_bfcl_holdout | native_llm | 1.4005 | 0.0000 |
| D_bfcl_holdout | matched_systemone | 1.0635 | 1.2191 |
| D_bfcl_holdout | matched_neutral | 0.7846 | 1.2191 |
| D_bfcl_holdout | jev | 0.0947 | 1.2191 |

| group | orderings | variants | estimate $ | nominal cap $ |
|---|---|---|---|---|
| A_clean | 3 | 350 | 11.4130 | – |
| B_displacement | 3 | 660 | 22.1896 | – |
| C_abstention | 3 | 560 | 19.4111 | – |
| D_bfcl_holdout | 1 | 700 | 7.0007 | – |

Primary groups (A-C): **$53.0137**. All groups: **$60.0145**. Global cap $40.00.
