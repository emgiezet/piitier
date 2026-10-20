# QA Report — PII-2-c

## Verdict: PASS

Every UC has a passing test carrying its id. Suite breakdown: `uv run pytest -q -m "not integration"` (392 passed, 29 deselected in 3.12s); `uv run pytest -q -m integration` (29 passed, 392 deselected in 2.16s). Total suite: 421 tests (baseline 377 + 44 added), zero skipped.
Code Review: `InflectionReview` APPROVED (zero unwaived findings). Line budget finding waived under standing approval.

## UC Coverage Map

| UC | Test | Status |
|----|------|--------|
| UC-15 | `test_uc15_inflect_surname_gen` | pass |
| UC-16 | `test_uc16_inflect_firstname_dat_inst` | pass |
| UC-17 | `test_uc17_render_osoba_inst_second_span` | pass |
| UC-18 | `test_uc18_invalid_case_error_names_the_case` | pass |
| UC-19 | `test_uc19_case_not_allowed_for_pesel`, `test_uc19_case_not_allowed_for_adres` | pass |
| UC-20 | `test_uc20_render_fallback_span_and_counter` | pass |
| UC-21 | `test_uc21_offset_integrity_with_case_suffixes` | pass |

All UCs present: 7/7 automated. All passing.

## Suite output

**Unit & Integration Tests:**
```
uv run pytest -q -m "not integration": 392 passed, 29 deselected (3.12s)
uv run pytest -q -m integration: 29 passed, 392 deselected (2.16s)
```

- Source commit: `018df4b`
- Ruff format/check and mypy PASS.
- Runtime observed: 100 docs, 2100 spans / all 7 cases exact literal/CRLF/entity/seed/global RNG, CLI build/check 100 docs PASS, manifest fallback sum 42; repeated unknown surname 2 slots count 2.
- Morfeusz 1.99.15 real known forms: `Kowalskiego`, `Kowalskiej`, `Annie`, `Janem`, `Anny Marii` (with space).
- License: BSD 2-Clause (primary https://morfeusz.sgjp.pl/doc/license/).

## Regressions and Robustness

Compound-name inflection (such as `Anny Marii`), cache fallback undercount handling, and manifest aggregation via `build.py` have been verified through regression testing. Global RNG stability was confirmed during runtime evaluation.

## Implementation Scope & Sizing

- Files changed: 8 native files (excluding `uv.lock`): `pyproject.toml`, `src/piitier/datagen/inflect.py`, `src/piitier/datagen/template.py`, `src/piitier/datagen/render.py`, `src/piitier/datagen/build.py`, `tests/datagen/test_inflect.py`, `tests/datagen/test_template.py`, `tests/datagen/test_build.py`.
- Native modules (first 2 path segments): 3 (`pyproject.toml`, `src/piitier`, `tests/datagen`).
- Added lines: 621 excluding `uv.lock`.
- Scope verdict: GAPS.
- Line finding:
  `over budget: 621 added lines > 560 (280 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)`
- Waiver: `Waived: over budget: 621 added lines > 560 (280 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)` activated under standing approval by @local-user (2026-10-20); `InflectionReview` APPROVED (zero unwaived findings).

## Not verified

- No corpus publication or model training in this slice.
- No claims regarding GPU acceleration or model evaluation.
