# QA Report — PII-4-a

## Verdict: PASS

Every UC has a passing test carrying its id. Suite passed.

## UC Coverage Map

| UC | actor | use case | automated test | status |
|----|-------|----------|----------------|--------|
| UC-67 | model runner | `bio_tag_names()` returns 79 BIO tags | `test_uc67_bio_tag_names` | pass |
| UC-68 | model runner | `decode_spans` decodes token probability distributions | `test_uc68_decode_spans` | pass |
| UC-69 | model runner | `threshold` filters low-score spans | `test_uc69_threshold` | pass |
| UC-70 | model runner | `merge_windows` merges overlapping same-label spans | `test_uc70_merge_windows`, `test_uc70_merge_windows_touching_vs_overlapping` | pass |
| UC-71 | model runner | `NerPredictor` integration test with tiny random model | `test_uc71_predictor_integration` | pass |

All UCs present: 5/5 automated. All passing.
