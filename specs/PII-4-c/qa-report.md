# QA Report — PII-4-c

## Verdict: PASS

Every UC has a passing test carrying its id. Suite passed.

## UC Coverage Map

| UC | actor | use case | automated test | status |
|----|-------|----------|----------------|--------|
| UC-75 | calibrator | `calibrate_threshold` recall-first sweep target met | `test_uc75_calibrate_threshold_target_met` | pass |
| UC-76 | calibrator | `calibrate_threshold` target not met handling | `test_uc76_calibrate_threshold_target_not_met`, `test_write_threshold` | pass |
| UC-77 | exporter | `export_onnx` produces non-empty onnx/model.onnx | `test_uc77_export_onnx` | pass |
| UC-78 | exporter | Full export, quantize_int8, export_report.json, tolerance gate | `test_uc78_export_quantize_and_main` | pass |

All UCs present: 4/4 automated. All passing.
