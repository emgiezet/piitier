## PII-2-a — Render a labelled synthetic document from a placeholder template
**QA verdict: PASS** · **Code Review: DatagenFinalReview APPROVED** · UC coverage: 8/8 automated · Tests: 295 → 336 · Skipped: 0

### What the spec asked for

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-1 | data author | `render` of `"Klient PESEL {{PESEL}}."` with seed 7 | `doc.text` starts `"Klient PESEL "` and ends `"."`; one span, `label=PESEL`; `doc.text[start:end]` passes the PESEL validator | unit (`test_uc1_render_pesel_complete`) |
| UC-2 | data author | `render` of the same template twice with seed 7, then once with seed 8 | seeds 7 and 7 give identical `Document`s; seed 8 gives a different PESEL | unit (`test_uc2_seed_identity_and_difference`) |
| UC-3 | data author | `render` of `"{{IBAN#1}} oraz {{IBAN#1}}, inny {{IBAN#2}}"` | the two `#1` spans have identical text and `entity="1"`; the `#2` value differs from it | unit (`test_uc3_numbered_entity_caching`) |
| UC-4 | data author | `render`, over 50 seeds, of a template with one placeholder of each of the 6 labels, then `piitier.detect(doc.text)` | for every rendered span, `detect` returns a span with the same offsets, the same label and `status="valid"` | integration (`test_uc4_all_seeds_detectability_and_validity`) |
| UC-5 | data author | `render` of `"{{FOO}}"` | `TemplateError` naming the template id and offset 0; no `Document` returned | unit (`test_uc5_unknown_label_error`) |
| UC-6 | data author | `render` of `"{{LEK}}"` (a `Label` with no generator yet) | `TemplateError` with `no generator for LEK` | unit (`test_uc6_no_generator_error`) |
| UC-7 | data author | `render` of `"{{PESEL"`, `"{{PESEL#x}}"` and `"{{PESEL#1:gen}}"` | `TemplateError` each time: unclosed, bad entity id, case not supported yet | unit (`test_uc7_malformed_errors`) |
| UC-8 | data author | hypothesis-generated templates mixing Polish literal text and the 6 placeholders | for every span, `doc.text[start:end]` is the injected value; literal text appears verbatim and in order; spans sorted and non-overlapping | unit (`test_uc8_properties_consolidated`) |

### How to verify
```bash
uv run pytest -q                                    # 336 passed
uv run ruff format --check . && uv run ruff check . # no lint issues
uv run mypy src                                     # no type issues
```

Parent observed checks (manual execution): 336 tests passed, Ruff format/check PASS, mypy (17 src files) PASS, 100 documents / 700 spans runtime verification PASS.

### Review here first
- `src/piitier/datagen/template.py`: Template parser for `{{LABEL}}`, `{{LABEL#k}}` and `{{LABEL#k:case}}`.
- `src/piitier/datagen/values.py`: Value generators for `PESEL`, `NIP`, `REGON`, `IBAN`, `NR_DOWODU`, `NR_KARTY`.
- `src/piitier/datagen/render.py`: `render(template: Template, seed: int) -> Document`.
- `src/piitier/datagen/__init__.py`: Package exports.
- `tests/datagen/`: Unit and integration test suite (`test_template.py`, `test_render.py`).

### Scope, Sizing & Constraints
- Files changed: 7 (`src/piitier/datagen/__init__.py`, `src/piitier/datagen/template.py`, `src/piitier/datagen/values.py`, `src/piitier/datagen/render.py`, `tests/datagen/__init__.py`, `tests/datagen/test_template.py`, `tests/datagen/test_render.py`).
- Native modules (first 2 path segments): 2 (`src/piitier`, `tests/datagen`).
- Added lines: 998 added excluding docs.
- Size finding: `over budget: 998 added lines > 700 (350 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)`.
- `Waived: over budget: 998 added lines > 700 (350 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)` activated under standing approval by @local-user (2026-10-20) following `DatagenFinalReview` APPROVED (zero unwaived findings).
- Limitations: no LLM, training, export, person, or inflection.
