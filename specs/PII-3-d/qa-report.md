# QA Report — PII-3-d

## Verdict: PASS

Every UC has a passing test carrying its id. PII-3-d slice tests pass successfully.
Code Review: Independent review findings addressed in commit `5c37ab2`.

## UC Coverage Map

| UC | actor | use case | automated test function | status |
|----|-------|----------|-------------------------|--------|
| UC-60 | data author | per-case span assertions, hn_ id format, check() passes | `test_uc60_hard_negatives_families_and_spans` | PASS |
| UC-61 | data author | build with --hard-negatives produces manifest and valid corpus | `test_uc61_hard_negatives_cli_and_manifest` | PASS |
| UC-62 | data author | build with --augment applies transforms and preserves offset validity | `test_uc62_augment_flag_and_offsets` | PASS |
| UC-63 | data author | build with same seeds yields identical output files (sha256 matching) | `test_uc63_determinism_sha256` | PASS |
| UC-64 | data author | 2000-doc integration build runs successfully and passes check | `test_uc64_integration_2000_docs` | PASS |
| UC-65 | data author | dataset card exists and mentions CC BY 4.0 and both licences (Faker, Morfeusz) | `test_uc65_dataset_card_exists_and_content` | PASS |
| UC-66 | data author | full integration run (20k docs, seed 42, augment, hard negatives 2000) byte-identical reproducibility and valid check | orchestrator full run (UC-66) | PASS |

All UCs present: 7/7 automated. All passing.

## Suite output

**Unit & Integration Tests:**
```
uv run pytest -q (tests/datagen/test_hard_negatives.py): passed
```

- Ruff format/check, mypy (24 src files) PASS.
- Runtime verification: hard negatives generation, CLI options `--augment` and `--hard-negatives`, sha256 determinism, 2000-doc test, dataset card content, and 20k full run verification.
