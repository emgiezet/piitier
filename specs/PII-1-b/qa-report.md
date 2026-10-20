---
verdict: PASS
ticket: PII-1-b
date: 2026-10-20
---

# PASS — PII-1-b

verification map: none

---

## UC × test matrix

| UC | Requirement (summary) | Test(s) | Status |
|----|-----------------------|---------|--------|
| UC-7 | `mask("PESEL: 90051512340, tel.")` → `"PESEL: [PESEL], tel."` | `test_uc7_mask_replaces_valid_pesel` (tests/test_api.py:20) | ✅ PASS |
| UC-8 | one span: `start=7, end=18, label=Label.PESEL, source="rule", score=1.0, status="valid"` | `test_uc8_detect_returns_one_span` (tests/test_api.py:31), fields individually asserted | ✅ PASS |
| UC-9 | `90051512341` → `[PESEL]`; span `status="suspect"` | `test_uc9_*` × 3 (tests/test_api.py:57, :63, :71) | ✅ PASS |
| UC-10 | `90131512341` (month 13) → one span, `status="suspect"` | `test_uc10_invalid_month_returns_suspect` (tests/rules/test_pesel.py:241), `test_uc10_suspect_span_never_dropped` (:249) | ✅ PASS |
| UC-11 | `05250112343` (+20 century) → one span, `status="valid"` | `test_uc11_2000s_encoding_valid` (tests/rules/test_pesel.py:260), `test_uc11_span_offsets_correct` (:269) | ✅ PASS |
| UC-12 | 10-digit → no span; 12-digit → no span; `x…y` → one span on 11 digits | `test_uc12_*` × 5 (tests/rules/test_pesel.py:282–314) | ✅ PASS (see Finding 1) |
| UC-13 | fidelity property; no-detection → unchanged; `""` → `""` | `test_uc13_*` × 4 (tests/test_render.py:181–205, 150 hypothesis examples) | ✅ PASS |
| UC-36 | `mask` on 3 separated formats → `[PESEL]`; span covers separators; `status="valid"` | `test_uc36_*` × 4 (tests/rules/test_pesel.py:328–377) + `test_uc36_mask_separated_format_returns_placeholder` (tests/test_api.py:129, 3 parametrized cases) | ✅ PASS |
| UC-37 | `+48 501 234 567` and `+48501234567` → no PESEL span | `test_uc37_plus48_space_not_pesel` (tests/rules/test_pesel.py:385), `test_uc37_plus48_compact_not_pesel` (:392) | ✅ PASS |

**9/9 UCs fully automated — 0 manual-only, 0 gaps**

---

## Suite output

```
$ uv run pytest -q -m "not integration"
......................................................................  [ 61%]
.............................................                            [100%]
117 passed, 1 deselected in 1.08s
```

_(1 deselected = integration-marked tests excluded. No skips, xfails, or `.only` anywhere in the diff.)_

```
$ uv run ruff format --check . && uv run ruff check .
46 files already formatted
All checks passed!

$ uv run mypy src
Success: no issues found in 6 source files
```

---

## Findings

### 1. [minor, non-blocking] UC-12 test names and docstrings swapped — `tests/rules/test_pesel.py:302–314`

- `test_uc12_digit_adjacent_blocks_match` (line 302): name/docstring describe *"digit after"* but code tests `find("1" + PESEL_VALID_1)` — digit is **before**.
- `test_uc12_digit_before_blocks_match` (line 309): name/docstring describe *"digit before"* but code tests `find(PESEL_VALID_1 + "1")` — digit is **after**.

Both `assert spans == []` assertions are functionally correct and the UC is satisfied. Only names and docstrings are transposed.

**Not blocking** — the behaviour tested is correct; the mislabelling is cosmetic.

---

## Gap closed in Phase 2

**UC-36 `mask()` output** was not directly asserted before QA. The existing four `test_uc36_*` tests called only `find()`, leaving the first observable result of the UC ("`each becomes exactly [PESEL]`") unautomated. Added `test_uc36_mask_separated_format_returns_placeholder` (3 parametrised cases) in `tests/test_api.py`; all three pass.

---

## Not verified

- **No logging/printing/exception-leakage** (non-functional): verified by code inspection of `src/piitier/__init__.py`, `src/piitier/render.py`, `src/piitier/rules/__init__.py`, `src/piitier/rules/pesel.py`. No `print`, `logging`, or exception message containing matched text found. No automated test enforces this invariant.
- **Validators are pure functions** (non-functional): `is_valid`, `_checksum_ok`, `_decode_birth_date`, `_valid_calendar_date` are all pure by inspection. No automated purity guard.
- **Integration-marker gap**: `tests/test_api.py` carries no `@pytest.mark.integration` decorator; UC-7/8/9 are marked `integration` in the spec but ran under the non-integration suite. All three pass either way; no UC is dropped.
