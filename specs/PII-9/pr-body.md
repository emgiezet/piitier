## PII-9 — feat(eval): evaluation protocol — counts, undefined denominators, control systems, provenance

Adopted from pawelkiszczak/warda (see FINDINGS.md, last section). Spec: `specs/PII-9/spec.md`.

- `EntityPRF` carries TP/FP/FN; reports render a zero denominator as `undefined (0/0)` (markdown) / `null` (JSON), never 0.0; `eval.compare` skips regressions on undefined values.
- Control systems `none` and `mask-all` (negative controls: recall 0 / value leak 1.0, and value leak 0 / precision ~0).
- Report provenance: git commit (or `unknown`), SHA-256 of every bench file, doc count, split, threshold.
- `docs/bench/PROTOCOL.md`: metric formulas, split roles, gates with thresholds, reporting rules. Fidelity is now measured against predicted spans (CLAUDE.md invariant 4); reports before PII-9 used gold spans and are not comparable.

### Verification
- `uv run pre-commit run --all-files`: all hooks pass; `uv run pytest -q -m "not integration"`: green on the branch; CI on this PR.
- Independent review: CHANGES_REQUESTED → all findings fixed; the new tests kill the reviewer's mutations.

Waived: over budget: 1350 added lines > 800 (400 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing) — standing approval by @local-user (2026-10-20); hard ceiling 5000 not exceeded; most added lines are tests from the review round.
