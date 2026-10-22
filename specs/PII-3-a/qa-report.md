# QA Report — PII-3-a

## Verdict: PASS

Every UC has a passing test carrying its id. PII-3-a slice tests pass successfully.
Code Review: Independent review findings addressed in commit `5c37ab2`.

## UC Coverage Map

| UC | actor | use case | automated test function | status |
|----|-------|----------|-------------------------|--------|
| UC-38 | data author | 100 draws per generator with Random(42) pass validators without exceptions | `test_uc38_generators_and_validators_100_draws` | PASS |
| UC-39 | data author | VIN has ZZ prefix, no I/O/Q, 17 chars, valid ISO 3779 check digit | `test_uc39_vin_properties` | PASS |
| UC-40 | data author | same seed gives identical values; different seed gives different values | `test_uc40_determinism` | PASS |
| UC-41 | data author | render() with 6 new labels returns valid spans and exact text slicing | `test_uc41_render_all_six_new_labels` | PASS |
| UC-42 | data author | template with unknown/unsupported label raises TemplateError | `test_uc42_unsupported_label_raises_template_error` | PASS |
| UC-43 | data author | build passes, check returns 0, span_counts include new labels | `test_uc43_build_check_manifest_with_new_templates` | PASS |
| UC-44 | data author | llm.write_templates accepts template using new labels with rejected == {} | `test_uc44_llm_write_templates_accepts_new_labels` | PASS |
| UC-45 | data author | prompt for each doc_type lists all labels from _SUPPORTED_LABELS | `test_uc45_prompt_label_list_matches_supported_labels` | PASS |

All UCs present: 8/8 automated. All passing.

## Suite output

**Unit & Integration Tests:**
```
uv run pytest -q (tests/datagen/test_values_finance.py): passed
```

- Ruff format/check, mypy (24 src files) PASS.
- Runtime verification: finance generators & validators, ISO 3779 VIN check digit, template rendering, LLM prompt label lists, build manifest.
