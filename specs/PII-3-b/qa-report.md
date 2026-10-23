# QA Report — PII-3-b

## Verdict: PASS

Every UC has a passing test carrying its id. PII-3-b slice tests pass successfully.
Code Review: Independent review findings addressed in commit `5c37ab2`.

## UC Coverage Map

| UC | actor | use case | automated test function | status |
|----|-------|----------|-------------------------|--------|
| UC-46 | data author | 100 draws per generator at Random(42) pass validators, deterministic | `test_uc46_medical_generators_and_validators_100_draws` | PASS |
| UC-47 | data author | ICD10 list has >= 25 codes, both dotted and undotted pass validator | `test_uc47_icd10_dotted_undotted_and_list_size` | PASS |
| UC-48 | data author | NPWZ 100 draws valid, first digit is 1, evidence comment exists in source | `test_uc48_npwz_format_and_evidence` | PASS |
| UC-49 | data author | LEK list length is exactly 40 names, all unique | `test_uc49_lek_list_length_40` | PASS |
| UC-50 | data author | render() with all 6 medical labels returns valid spans and exact text slicing | `test_uc50_render_template_with_six_medical_labels` | PASS |
| UC-51 | data author | LEKARZ#1:gen inflection works and fallback is counted like OSOBA | `test_uc51_lekarz_inflection_and_fallback` | PASS |
| UC-52 | data author | build passes, check returns 0, span_counts include medical labels | `test_uc52_build_check_manifest_medical_templates` | PASS |
| UC-53 | data author | prompt for each doc_type lists all 27 labels from _SUPPORTED_LABELS | `test_uc53_prompt_label_list_27_labels` | PASS |

All UCs present: 8/8 automated. All passing.

## Suite output

**Unit & Integration Tests:**
```
uv run pytest -q (tests/datagen/test_values_medical.py): passed
```

- Ruff format/check, mypy (24 src files) PASS.
- Runtime verification: medical generators & validators (ICD10, LEK, ROZPOZNANIE, PLACOWKA, LEKARZ, NPWZ), inflection, prompts, and build manifest.
