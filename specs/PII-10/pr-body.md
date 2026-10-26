## PII-10 — feat(training): calibration on a separate split with minimum support and Wilson interval

Adopted from pawelkiszczak/warda (see FINDINGS.md, last section). Spec: `specs/PII-10/spec.md`.

- New config keys: `calibration_file` (must differ from eval and train files, never bench/**/test/), `calibration_target_recall`, `calibration_match` (strict|partial), `calibration_min_support`.
- A threshold is written only when the target is met with enough support; otherwise exit 1 with `unsupported` / `target_not_met` and the config stays byte-identical; the model card never shows a failed run as a threshold.
- Report: recall with 95% Wilson interval, span and doc counts, recall per risk group. Early-exit search (2000 docs / 10000 predictions in < 1 s).
- Existing run configs need `calibration_file` before `training.calibrate` runs (noted in FINDINGS.md).

### Verification
- `uv run pre-commit run --all-files`: all hooks pass; `uv run pytest -q -m "not integration"`: green on the branch; CI on this PR.
- Independent review: CHANGES_REQUESTED → all findings fixed; the new tests kill the reviewer's mutations.

Waived: over budget: 1330 added lines > 800 (400 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing) — standing approval by @local-user (2026-10-20); hard ceiling 5000 not exceeded; most added lines are tests from the review round.
