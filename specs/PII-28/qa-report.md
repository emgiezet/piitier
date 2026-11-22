# PII-28 QA Report — `.xlsx` workbooks (PR #35)

Verdict: PASS

## Summary

- **Full non-integration suite:** `1118 passed, 51 deselected, 1 warning in 56.95s`
- **Targeted xlsx/CLI/TUI/README files:** `145 passed, 4 deselected in 28.59s`
- **Spec UCs covered:** 34 / 34 (UC-190…217 and UC-260…266)
- **Findings:** 1 non-blocking observation

## UC coverage table

| UC | Test function(s) / verification | Status |
|----|-----------------------------------|--------|
| UC-190 | `tests/test_cli_xlsx.py::test_uc190_mask_xlsx_prints_every_sheet_masked` + hand-run artifact | pass |
| UC-191 | `tests/test_xlsx.py::test_uc191_masked_workbook_keeps_types_formulas_and_source` + hand-run artifact | pass |
| UC-192 | `tests/test_cli_xlsx.py::test_uc192_skip_columns_keep_original_cells` + hand-run artifact | pass |
| UC-193 | `tests/test_cli_xlsx.py::test_uc193_unknown_column_warns_and_masks` + hand-run artifact | pass |
| UC-194 | `tests/test_cli_xlsx.py::test_uc194_unknown_column_warns_for_text_output` + hand-run artifact | pass |
| UC-195 | `tests/test_cli_xlsx.py::test_uc195_delimiter_rejected_for_xlsx` + hand-run artifact | pass |
| UC-196 | `tests/test_cli_xlsx.py::test_uc196_corrupt_xlsx_exits_2` + hand-run artifact | pass |
| UC-197 | `tests/test_cli_xlsx.py::test_uc197_text_output_for_non_xlsx_target` + hand-run artifact | pass |
| UC-198 | `tests/test_xlsx.py::test_uc198_detection_across_two_cells_masks_both` + hand-run | pass |
| UC-199 | `tests/test_tui.py::test_uc199_xlsx_columns_selected_in_tui_and_exported` | pass |
| UC-200 | `tests/test_tui.py::test_uc200_xlsx_export_refuses_existing_file` | pass |
| UC-201 | `tests/test_readme_install.py::test_uc201_readme_documents_installation_per_platform` | pass |
| UC-202 | `tests/test_xlsx.py::test_uc202_cells_without_detection_are_identical` + hand-run | pass |
| UC-203 | `tests/test_xlsx.py::test_uc203_formula_detection_reports_plain_text` + hand-run | pass |
| UC-204 | `tests/test_xlsx.py::test_uc204_comments_are_dropped` + hand-run | pass |
| UC-205 | `tests/test_xlsx.py::test_uc205_hyperlink_targets_are_dropped` + hand-run | pass |
| UC-206 | `tests/test_xlsx.py::test_uc206_document_properties_are_neutral` + hand-run | pass |
| UC-207 | `tests/test_xlsx.py::test_uc207_sheet_names_are_sanitized` + hand-run | pass |
| UC-208 | `tests/test_xlsx.py::test_uc208_headers_and_footers_are_dropped` + hand-run | pass |
| UC-209 | `tests/test_xlsx.py::test_uc209_defined_names_are_dropped` + hand-run | pass |
| UC-210 | `tests/test_xlsx.py::test_uc210_multiple_formulas_have_exact_conversion_count` + hand-run | pass |
| UC-211 | `tests/test_xlsx.py::test_uc211_integer_pesel_is_masked` + hand-run | pass |
| UC-212 | `tests/test_xlsx.py::test_uc212_float_pesel_is_masked` + hand-run | pass |
| UC-213 | `tests/test_xlsx.py::test_uc213_overlapping_detections_cross_separator` + hand-run | pass |
| UC-214 | `tests/test_xlsx.py::test_uc214_output_zip_contains_no_original_identifier` + hand-run artifact | pass |
| UC-215 | `tests/test_xlsx.py::test_uc215_masks_five_thousand_cells_under_five_seconds` + hand-run artifact | pass |
| UC-216 | `tests/test_cli_xlsx.py::test_uc216_converted_formulas_warn_on_stderr` + hand-run artifact | pass |
| UC-217 | `tests/test_tui.py::test_uc217_xlsx_export_shows_converted_formula_count` | pass |
| UC-260 | `tests/test_xlsx.py::test_uc260_sheet_title_offsets_cannot_match_cell_text` + hand-run | pass |
| UC-261 | `tests/test_xlsx.py::test_uc261_free_text_styles_are_removed` + hand-run | pass |
| UC-262 | `tests/test_xlsx.py::test_uc262_safe_styles_remain_supported` + hand-run | pass |
| UC-263 | `tests/test_xlsx.py::test_uc263_chartsheet_only_is_a_content_free_error`, `tests/test_cli_xlsx.py::test_uc263_chartsheet_only_exits_2_without_touching_target` + hand-run artifact | pass |
| UC-264 | `tests/test_xlsx.py::test_uc264_numbering_uses_original_span_offsets_across_cells` + hand-run | pass |
| UC-265 | `tests/test_tui.py::test_uc265_xlsx_tui_export_matches_numbered_model_diff` | pass |
| UC-266 | `tests/test_xlsx.py::test_uc266_numbering_survives_overlapping_span_union` + hand-run | pass |

## Test suite output

```text
$ uv run pytest -q -m "not integration" --no-header
........................................................................ [  6%]
........................................................................ [ 12%]
........................................................................ [ 19%]
........................................................................ [ 25%]
........................................................................ [ 32%]
........................................................................ [ 38%]
........................................................................ [ 45%]
........................................................................ [ 51%]
........................................................................ [ 57%]
........................................................................ [ 64%]
........................................................................ [ 70%]
........................................................................ [ 77%]
........................................................................ [ 83%]
........................................................................ [ 90%]
........................................................................ [ 96%]
......................................                                   [100%]
=============================== warnings summary ===============================
tests/training/test_training_fixes.py::test_finding4_seqeval_strict_mode
  <venv>/site-packages/seqeval/metrics/v1.py:57: UndefinedMetricWarning: Precision is ill-defined and being set to 0.0 due to no predicted samples. Use the `zero_division` parameter to control this behavior.
    _warn_prf(average, modifier, msg_start, len(result))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1118 passed, 51 deselected, 1 warning in 56.95s (0:00:56)
```

Targeted files:

```text
$ uv run pytest -q -m 'not integration' --no-header tests/test_xlsx.py tests/test_cli_xlsx.py tests/test_tui.py tests/test_cli.py tests/test_readme_install.py
........................................................................ [ 49%]
........................................................................ [ 99%]
.                                                                        [100%]
145 passed, 4 deselected in 28.59s
```

## Tests added

No new tests were added. The existing suite already carries the id of every listed UC. A potential new test was considered for the observation in Findings, but it would not fail against the spec and was therefore not committed.

## Findings

### 1. CLI `-o` overwrites existing output files for every format (non-blocking observation)

- **Files:line**: `src/piitier/cli.py:223` (`output_path.write_text`) and `src/piitier/cli.py:240` (`_mask_workbook_file` → `mask_workbook` at `src/piitier/xlsx.py:263`).
- **Observation**: `piitier mask a.txt -o o.txt` and `piitier mask a.xlsx -o o.xlsx` both return 0 and replace an existing `o.*`. The spec requires the TUI export to refuse existing files (UC-200) and requires failed loads to leave an existing destination untouched (UC-263), but it does not require the CLI `mask -o` path to refuse existing targets. This behaviour is consistent with the existing CLI contract on `release/0.1.0`.
- **Impact**: A user can accidentally destroy an existing output file. Refusing would be a CLI-wide behaviour change for the owner to decide; it is not a PII-28 spec violation.

## Hand-verified CLI UCs

Artifacts stored in `specs/PII-28/qa/`:

| UC | Command | Result |
|----|---------|--------|
| UC-190 | `piitier mask <tmp>/qa_pii28.xlsx` | exit 0, both sheets rendered, `[PESEL]` in int and text cells, numeric/date/formula visible in text. |
| UC-191 | `piitier mask <tmp>/uc190_pii28.xlsx -o <tmp>/uc190_pii28_out.xlsx` | exit 0, output opens with openpyxl, types/formulas preserved, source unchanged. |
| UC-192 | `… -o out.xlsx --skip-columns "Nr polisy"` | exit 0, skipped column unchanged, others masked. |
| UC-193 | `… -o out.xlsx --skip-columns "Brak"` | exit 0, stderr `warning: unknown column: Brak`. |
| UC-194 | `… --skip-columns "Brak"` (text output) | exit 0, stderr `warning: unknown column: Brak`. |
| UC-195 | `… --delimiter ";"` | exit 2, stderr `--delimiter is only supported for .csv files: <tmp>/qa_pii28.xlsx`. |
| UC-196 | `piitier mask <tmp>/corrupt_pii28.xlsx` | exit 2, stderr `unsupported or corrupt xlsx: <tmp>/corrupt_pii28.xlsx`, stdout empty. |
| UC-197 | `… -o <tmp>/qa_pii28_out.txt` | exit 0, text file rendered starting with `# Raport`, no xlsx written. |
| UC-214 | full ZIP leak scan on a workbook with PESEL in cell, sheet title and core properties | no output ZIP member contained `90051512340`. |
| UC-215 | `time uv run piitier mask <tmp>/uc215_perf_pii28.xlsx -o <tmp>/uc215_perf_pii28_out.xlsx` | real ~1.0 s, all 5000 cells masked. |
| UC-216 | `… -o out.xlsx` on workbook with two detected formulas and one safe formula | exit 0, stdout empty, one warning per converted formula, safe formula unchanged. |
| UC-263 | `piitier mask <tmp>/uc263_charts.xlsx -o <tmp>/uc263_out.xlsx` | exit 2, stderr `unsupported or corrupt xlsx: <tmp>/uc263_charts.xlsx`, pre-existing target bytes preserved. |

## Not verified

- **Live TUI export with a real terminal (UC-199/200/217/265):** the Textual app cannot be interactively driven in a headless session beyond the existing unit tests, which already exercise the widget flow and export assertions.
- **Windows PowerShell installation steps (UC-201):** not executed on Windows; covered by `README.md` review and `test_uc201_readme_documents_installation_per_platform`.
- **Contrived same-index overlapping spans for UC-266:** not reachable with normal detector output; already unit-tested.

## Deliverables

- `specs/PII-28/qa-report.md`
- `specs/PII-28/qa/uc*.txt` CLI artifact files
