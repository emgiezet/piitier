# QA Report — PII-2-a

## Verdict: PASS

Every UC has a passing test carrying its id. Full suite: 336 passed, zero skipped.
Code Review: `DatagenFinalReview` APPROVED (zero unwaived findings).

## UC Coverage Map

| UC | actor | use case | automated test | status |
|----|-------|----------|----------------|--------|
| UC-1 | data author | `render` of `"Klient PESEL {{PESEL}}."` with seed 7 | `test_uc1_render_pesel_complete` | pass |
| UC-2 | data author | `render` of the same template twice with seed 7, then once with seed 8 | `test_uc2_seed_identity_and_difference` | pass |
| UC-3 | data author | `render` of `"{{IBAN#1}} oraz {{IBAN#1}}, inny {{IBAN#2}}"` | `test_uc3_numbered_entity_caching` | pass |
| UC-4 | data author | `render`, over 50 seeds, of a template with one placeholder of each of the 6 labels, then `piitier.detect(doc.text)` | `test_uc4_all_seeds_detectability_and_validity`, `test_format_diversity_observed` | pass |
| UC-5 | data author | `render` of `"{{FOO}}"` (unknown label) | `test_uc5_unknown_label_error`, `test_uc5_unknown_label_error_contract` | pass |
| UC-6 | data author | `render` of `"{{LEK}}"` (no generator yet) | `test_uc6_no_generator_error`, `test_uc6_lek_parse_succeeds_and_label_stored` | pass |
| UC-7 | data author | `render` of `"{{PESEL"`, `"{{PESEL#x}}"` and `"{{PESEL#1:gen}}"` | `test_uc7_malformed_errors`, `test_uc7_malformed_syntax_raises_template_error` | pass |
| UC-8 | data author | hypothesis-generated templates mixing Polish literal text and the 6 placeholders | `test_uc8_properties_consolidated`, `test_property_placeholder_offsets_point_to_opening_braces` | pass |

All UCs present: 8/8 automated. All passing.

## Suite output

**Unit & Integration Tests:**
```
uv run pytest -q: 336 passed
```

- Baseline: 295 tests (Datagen branch); feature branch: 336 tests (+41 tests added).
- Skipped: 0.
- Ruff format/check, mypy (17 src files) PASS.
- Runtime verification: 100 documents / 700 spans passed (exact literal preservation, validator/detector offset/status agreement, seeded reproducibility, repeated IBAN entity, global RNG unchanged).
- Verification attribution: parent manual execution (not native harness or CI).

## Implementation Scope & Sizing
- Files changed: 7 (`src/piitier/datagen/__init__.py`, `src/piitier/datagen/template.py`, `src/piitier/datagen/values.py`, `src/piitier/datagen/render.py`, `tests/datagen/__init__.py`, `tests/datagen/test_template.py`, `tests/datagen/test_render.py`).
- Native modules (first 2 path segments): 2 (`src/piitier`, `tests/datagen`).
- Added lines: 998 added excluding docs.
- Size finding: `over budget: 998 added lines > 700 (350 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)`.
- Waived: `Waived: over budget: 998 added lines > 700 (350 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)` activated under standing approval by @local-user (2026-10-20) following `DatagenFinalReview` APPROVED (zero unwaived findings).
- Limitations: no LLM, training, export, person, or inflection.
