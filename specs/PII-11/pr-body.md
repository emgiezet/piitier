## PII-11 — feat(eval): gold-set tooling — labelling guidelines, schema v2, twins, annotator agreement

Adopted from pawelkiszczak/warda (see FINDINGS.md, last section). Spec: `specs/PII-11/spec.md`.

- `docs/labelling/GUIDELINES.md` (Polish): every group with positive and negative fictional examples; boundary rules aligned with the training corpus (`dr`/`lek. med.` inside LEKARZ, full name = one OSOBA, currency inside KWOTA/DOCHOD, date only in DATA_URODZENIA).
- `python -m eval.bench_schema`: schema v2 (≥ 2 annotators, adjudication, `twin_of`), overlap, twin and 30% mix rules; errors carry line numbers and rule names, never file content.
- `python -m eval.agreement`: span F1 (strict/partial) and character-level Cohen's kappa pooled over documents, 0.7 floor.
- Writing and double-labelling the 300+ documents still needs human annotators.
- Found: 23 template occurrences annotate full names as IMIE + NAZWISKO, inconsistent with bench/v1 (OSOBA) — separate ticket.

### Verification
- `uv run pre-commit run --all-files`: all hooks pass; `uv run pytest -q -m "not integration"`: green on the branch; CI on this PR.
- Independent review: CHANGES_REQUESTED → all findings fixed; the new tests kill the reviewer's mutations.

Waived: over budget: 1748 added lines > 800 (400 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing) — standing approval by @local-user (2026-10-20); hard ceiling 5000 not exceeded; most added lines are tests from the review round.
