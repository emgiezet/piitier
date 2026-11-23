# QA Report — PII-33

## Verdict: PASS

All spec UCs are exercised by named automated tests in `tests/test_overlap_fidelity.py`, the non-integration suite passes with zero failures, and manual verification of the unautomated integration UCs matches the expected observable behavior.

## UC Coverage Map

| UC | actor | use case | automated test(s) | status |
|----|-------|----------|-------------------|--------|
| UC-250 | library caller | Rules-only `mask` / `mask_csv` preserves text around a REGON-14 vs NR_KARTY collision | `test_uc250_public_mask_preserves_collision_suffix` | PASS |
| UC-251 | CLI caller | `piitier mask` on the reported sentence returns exact stdout | `test_uc251_cli_preserves_collision_suffix` | PASS |
| UC-252 | CSV caller | CSV collision row preserves surrounding cells under skip-column variants | `test_uc252_csv_preserves_collision_cells` | PASS |
| UC-253 | library caller | Digit runs 8–26 embedded in Unicode text change zero bytes outside detected spans | `test_uc253_random_digit_runs_preserve_outside_bytes` | PASS |
| UC-254 | renderer caller | Identical-range rule spans use existing fusion precedence | `test_uc254_identical_ranges_use_fusion_priority` | PASS |
| UC-255 | renderer caller | Partial, nested, adjacent and disjoint spans mask union correctly | `test_uc255_overlap_shapes_preserve_union_and_surroundings` | PASS |
| UC-256 | batch caller | Rules-only `mask-batch` on collision text and CSV files preserves suffixes/delimiters | `test_uc256_batch_preserves_collision_suffixes` | PASS |
| UC-257 | TUI caller | CSV selection/export with rules-only detector callback preserves cells and trailing CRLFs | `test_uc257_rules_only_tui_export_preserves_collision_suffix` | PASS |
| UC-258 | renderer caller | Overlapping numbered spans use exact-range index or template fallback | `test_uc258_numbered_fragments_use_exact_range_or_template` | PASS |
| UC-259 | renderer caller | Equal-priority same-range spans break ties by input order, never object identity | `test_uc259_exact_priority_tie_goes_to_the_first_input_span` | PASS |

All UCs present: 10/10 automated.

## Suite output

### Full non-integration gate

```
$ uv run pytest -q -m "not integration"
1084 passed, 51 deselected, 1 warning in 64.37s
```

- Deselected: 51 tests carrying `@pytest.mark.integration`.
- Warning: single `UndefinedMetricWarning` from `tests/training/test_training_fixes.py::test_finding4_seqeval_strict_mode`, unrelated to this ticket.

### Feature tests only

```
$ uv run pytest -q -m "not integration" tests/test_overlap_fidelity.py
25 passed in 1.47s
```

## Findings

None. All tests pass, no implementation changes were required for QA, and no new tests failed.

## Not verified

| Item | Why | Notes |
|------|-----|-------|
| Shipped TUI `compare` command | Integration test requiring a loaded model (excluded by `-m "not integration"`) | Spec declares it out-of-reach for this ticket; the equivalent `AnonymizationDiffApp` CSV export path with `detector=piitier.detect` is covered by `test_uc257`. |
| Manual CLI / installed CLI end-to-end | UC-251 and UC-256 cover the same executable via `python -m piitier.cli`; no installed-wheel gap was observed. | — |
| Browser-based verification | Spec explicitly states `browser: none`; all TUI coverage uses Textual's headless `run_test`. | — |

## Verification map

- `Verification map: none` — every acceptance-criteria UC has an automated test; no ad-hoc verification map is needed.
- `browser: none` — no browser-based verification was required or performed.
