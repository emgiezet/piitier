# QA Report — PII-1-a

**Verdict: PASS**

## Use Case Coverage

| UC | Actor | Action | Expected Result | Test | Status |
|----|-------|--------|-----------------|------|--------|
| UC-1 | developer | `uv sync`, then `uv run python -c "import piitier; print(piitier.__version__)"` | prints `0.1.0`; exit 0 | `test_uc1_package_import_and_version`, `test_uc1_import_via_cli` | ✅ |
| UC-2 | maintainer | runs the test suite with `docs/TAXONOMY.md` and `Label` in agreement | the sync test passes; 39 entries match | `test_uc2_taxonomy_label_sync` | ✅ |
| UC-3 | maintainer | adds a row to `docs/TAXONOMY.md` without adding `Label` member (simulated) | the sync test fails, naming the missing placeholder | `test_uc3_sync_test_fails_on_mismatch` | ✅ |
| UC-4 | developer | reads `Label.<member>.placeholder` for every member | equals taxonomy verbatim with diacritics; numbered types have `[ENTITYNAME_n]` | `test_uc4_label_placeholder_property`, `test_uc4_specific_placeholders` | ✅ |
| UC-5 | developer | constructs `Span(start=5, end=3)`, `Span(start=-1, end=2)`, `Span(start=3, end=3)` | each raises `ValueError` with offsets only, never text | `test_uc5_span_offset_validation_start_greater_than_end`, `test_uc5_span_offset_validation_negative_start`, `test_uc5_span_offset_validation_equal_offsets` | ✅ |
| UC-6 | developer | constructs `Span` with `status` other than `"valid"` or `"suspect"` | raises `ValueError` | `test_uc6_span_status_validation_invalid_status` | ✅ |

**Coverage: 6/6 UCs automated**

## Test Suite Results

### Unit tests (`uv run pytest -q -m "not integration"`)
```
.............                                                            [100%]
13 passed, 1 deselected in 0.09s
```

### Integration tests (`uv run pytest -q -m "integration"`)
```
.                                                                        [100%]
1 passed, 13 deselected in 0.11s
```

**Total: 14 tests passing, 0 skipped, 0 failures**

## Code Quality

| Check | Command | Result |
|-------|---------|--------|
| Type checking | `uv run mypy src` | ✅ Success: no issues found in 3 source files |
| Format check | `uv run ruff format --check .` | ✅ 5 files already formatted |
| Linting | `uv run ruff check .` | ✅ All checks passed |

## Findings

None. All acceptance criteria are satisfied by passing tests. No blockers, no gaps.

## Not Verified

None. All UCs have automated test coverage.

---

**Test baseline:** 0 → 14 tests
**Verification map:** none (no runnable app yet; UC-1 verified via integration test calling `subprocess`)
