## Ticket and spec

- Ticket: PII-<n>
- Spec: `specs/PII-<n>/spec.md` (status: approved)

## UC coverage

| UC | Test |
|---|---|
| UC-<n> | `test_uc<n>_...` |

## Verification

- [ ] `uv run pre-commit run --all-files` passes
- [ ] `uv run pytest -q -m "not integration"`: <n> passed
- [ ] `uv run pytest -q -m integration` run if model loading, training or export changed
- [ ] For a bug fix: the new tests fail on the code before the fix (paste the failing run)
- [ ] Independent review done; findings fixed or listed below

## Privacy and data

- [ ] Only synthetic data added; no employer or client documents, nothing derived from `raw_data/`
- [ ] New checksum-valid identifiers are synthetic and allowlisted in `.pii-allowlist`
- [ ] No document text or PII values in logs, errors or reports
- [ ] `bench/**/test/` untouched and not used for training or calibration

## Model and benchmark impact

<!-- Metric changes with numbers and the report path, or "none". -->

## Notes

<!-- Deviations from the spec, follow-ups, findings for FINDINGS.md. -->
