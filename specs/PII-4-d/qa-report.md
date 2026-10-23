# QA Report — PII-4-d

## Verdict: PASS

Every UC has a passing test carrying its id. Suite passed.

## UC Coverage Map

| UC | actor | use case | automated test | status |
|----|-------|----------|----------------|--------|
| UC-79 | evaluator | `entity_metrics` strict and partial, per-label | `test_uc79_entity_metrics` | pass |
| UC-80 | evaluator | `risk_weighted_recall` computation and TAXONOMY sync | `test_uc80_risk_weighted_recall` | pass |
| UC-81 | evaluator | `leak_rate` counting docs/values leaked and direct IDs | `test_uc81_leak_rate` | pass |
| UC-82 | evaluator | `fidelity` checks text outside spans unchanged | `test_uc82_fidelity`, `test_adjacent_spans_fidelity_and_numbering` | pass |
| UC-83 | evaluator | `numbering_consistency` with render/manual placeholders | `test_uc83_numbering_consistency`, `test_numbering_consistency_polisa_scenario`, `test_numbering_consistency_partial_masking_variants` | pass |
| UC-84 | evaluator | `throughput_stats` and `peak_ram_bytes` | `test_uc84_throughput_stats_and_ram`, `test_group_for_label_and_direct_identifiers` | pass |

All UCs present: 6/6 automated. All passing.
