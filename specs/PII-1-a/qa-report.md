# QA report — PII-1-a
**Verdict: PASS**

## UC×test matrix

| UC | requirement | test function(s) | result |
|----|-------------|-----------------|--------|
| UC-1 | `python -c "import piitier; print(piitier.__version__)"` prints `0.1.0`; exit 0 | `test_uc1_version_printed_by_interpreter` (integration) | ✅ pass |
| UC-2 | taxonomy sync passes; exactly 39 entries | `test_uc2_taxonomy_label_sync_passes` | ✅ pass |
| UC-3 | extra taxonomy row → AssertionError naming the missing placeholder | `test_uc3_sync_fails_and_names_the_missing_placeholder` | ✅ pass |
| UC-4 | placeholder/numbered correct on all 39 members; diacritics verbatim (`Label.MIEJSCOWOSC.placeholder == "[MIEJSCOWOŚĆ]"`); numbered types have `_n]` suffix | `test_uc4_numbered_types_have_flag_and_n_suffix`, `test_uc4_diacritics_preserved_in_placeholders`, `test_uc4_all_placeholders_roundtrip_taxonomy` | ✅ pass |
| UC-5 | `Span(start=5,end=3)`, `Span(start=-1,end=2)`, `Span(start=3,end=3)` each raise `ValueError`; message carries offsets only, never text | `test_uc5_start_greater_than_end_raises`, `test_uc5_negative_start_raises`, `test_uc5_equal_offsets_raises`, `test_uc5_error_message_contains_offsets`, **`test_UC_5_error_message_offsets_only_never_text`** (added by QA) | ✅ pass |
| UC-6 | `status` other than `"valid"` or `"suspect"` raises `ValueError` | `test_uc6_invalid_status_uppercase_raises`, `test_uc6_empty_status_raises`, `test_uc6_unknown_status_raises` | ✅ pass |

Covered: 6/6 UCs automated (UC-1 integration, UC-2–6 unit) · 0 manual · 0 failing

## Test suites

### Unit (`-m "not integration"`) — after gap test added

```
============================= test session starts ==============================
platform linux -- Python 3.13.13, pytest-9.1.1, pluggy-1.7.0
rootdir: /home/mgz/workspace/.aisdlc-worktrees/piitier-pii-1-a-20261020-114700-8462
configfile: pyproject.toml
testpaths: tests
plugins: hypothesis-6.170.5
collected 27 items / 1 deselected / 26 selected

tests/test_labels.py .....                                               [ 19%]
tests/test_spans.py .....................                                [100%]

======================= 26 passed, 1 deselected in 0.22s =======================
```

### Integration (`-m integration`)

```
============================= test session starts ==============================
platform linux -- Python 3.13.13, pytest-9.1.1, pluggy-1.7.0
rootdir: /home/mgz/workspace/.aisdlc-worktrees/piitier-pii-1-a-20261020-114700-8462
configfile: pyproject.toml
testpaths: tests
plugins: hypothesis-6.170.5
collected 27 items / 26 deselected / 1 selected

tests/test_labels.py .                                                   [100%]

======================= 1 passed, 26 deselected in 0.11s =======================
```

### mypy (`uv run mypy src`)

```
Success: no issues found in 3 source files
```

### ruff (`uv run ruff check . && uv run ruff format --check .`)

```
All checks passed!
29 files already formatted
```

## Findings

1. **[INFO] UC-5 "never text" requirement had no negative-side test** — `tests/test_spans.py` (original)
   The spec explicitly "(added)" the requirement that "the message carries offsets only, never text". The pre-existing test `test_uc5_error_message_contains_offsets` verified only the positive side (offset values appear in message). No test asserted that other field values (source, score, label) do NOT leak into the error message.
   **Gap closed**: added `test_UC_5_error_message_offsets_only_never_text` at `tests/test_spans.py:83`. The new test passes — the implementation correctly restricts the message to `start`/`end` integers only.

2. **[INFO] `tests/__init__.py` not listed in spec's "New" section** — `tests/__init__.py:1`
   The spec enumerates 9 new files; `tests/__init__.py` (empty, 0 bytes) is a tenth file in the diff. It is a standard Python marker file required for pytest import resolution and carries no logic. Not a correctness concern; recorded for completeness.

## Non-functional verification

- **Frozen dataclass fields**: `Span` is `@dataclass(frozen=True)` with exactly `start: int`, `end: int`, `label: Label`, `source: str`, `score: float`, `status: str` — matches spec. ✅
- **mypy strict with no ignores**: `strict = true` in `pyproject.toml`; `uv run mypy src` → `Success: no issues found in 3 source files`. ✅
- **Exact version pins**: `hypothesis==6.170.5`, `mypy==2.4.0`, `pytest==9.1.1`, `ruff==0.17.1` in `[dependency-groups]`. ✅
- **`integration` marker registered**: present in `[tool.pytest.ini_options].markers`. ✅
- **39 Label members, 6 groups**: confirmed by runtime enumeration. ✅

## Not verified

- Nothing remains unverified. All 6 UCs are covered by automated tests and all pass.
- UC-1 integration test exercises the real subprocess path (`sys.executable -c "import piitier; …"`) rather than mocking, so the package import is genuinely exercised.

verification map: none
