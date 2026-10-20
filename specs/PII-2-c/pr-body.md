## PII-2-c — Inflect names into the grammatical case the template asks for (Morfeusz 2)

**QA verdict: PASS** · **Code Review: `InflectionReview` APPROVED (zero unwaived findings)** · UC coverage: 7/7 automated · Tests: 377 → 421 (+44) · Skipped: 0

### What this PR adds

Support for inflected names via `{{LABEL#k:case}}` syntax for `OSOBA`, `IMIE`, and `NAZWISKO` placeholders, supporting cases `nom`, `gen`, `dat`, `acc`, `inst`, `loc`, and `voc`. Inflection is powered by `morfeusz2==1.99.15` generation, agreeing with the person's sex from PII-2-b (`OSOBA` inflects first name and surname independently). When Morfeusz has no form for a name, the nominative fallback is used and `doc.inflection_fallbacks` tracks the count. Renderer and build pipeline are wired with case-aware caching, document counter, and manifest aggregation (`build.py`).

### Verification results

- `uv sync --frozen` — PASS
- `uv run ruff format --check . && uv run ruff check .` — PASS
- `uv run mypy src` — PASS
- `uv run pytest -q -m "not integration"` — 392 passed, 29 deselected (3.12s)
- `uv run pytest -q -m integration` — 29 passed, 392 deselected (2.16s)
- Runtime verification: 100 docs / 2100 spans PASS (all 7 cases exact literal/CRLF/entity/seed/global RNG, CLI build/check 100 docs PASS, manifest fallback sum 42, repeated unknown surname 2 slots count 2).

### UC evidence summary

| UC | test(s) |
|----|---------|
| UC-15 — genitive case for surname | `test_uc15_inflect_surname_gen` |
| UC-16 — dative and instrumental cases for first name | `test_uc16_inflect_firstname_dat_inst` |
| UC-17 — OSOBA instrumental case and shared entity | `test_uc17_render_osoba_inst_second_span` |
| UC-18 — TemplateError naming unknown case | `test_uc18_invalid_case_error_names_the_case` |
| UC-19 — TemplateError on disallowed case for PESEL / ADRES | `test_uc19_case_not_allowed_for_pesel`, `test_uc19_case_not_allowed_for_adres` |
| UC-20 — Inflection fallback count and surface form | `test_uc20_render_fallback_span_and_counter` |
| UC-21 — Offset integrity test with case suffixes | `test_uc21_offset_integrity_with_case_suffixes` |

### How to verify

```bash
uv sync --frozen
uv run pytest -q -m "not integration"                  # 392 passed
uv run pytest -q -m integration                       # 29 passed
uv run ruff format --check . && uv run ruff check .  # no issues
uv run mypy src                                      # no issues
```

### Scope, sizing and constraints

- Native scope: 621 added lines, 8 native files, 3 modules (`pyproject.toml`, `src/piitier`, `tests/datagen`), excluding `uv.lock` (9th changed file, lock-only).
- Profile limit: 280 added lines, 4 files, 3 modules with 100% tolerance (560 lines, 8 files, 6 modules), hard ceiling 5000.
- File and module counts within 100% tolerance (8 files ≤ 8, 3 modules ≤ 6); no separate file/module waivers required.
Waived: over budget: 621 added lines > 560 (280 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing) — standing approval by @local-user (2026-10-20), activated; `InflectionReview` APPROVED (zero unwaived findings).

### Limitations and dependencies

- **Morfeusz 1.99.15 (BSD 2-Clause license, primary https://morfeusz.sgjp.pl/doc/license/):** all inflection performed via Morfeusz 2 Python bindings.
- **No corpus publication / model training / GPU claims:** this slice provides template name inflection for data generation only.
