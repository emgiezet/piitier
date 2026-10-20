# QA report — PII-1-e
**Verdict: GAPS (4 findings, 4 blocking)**

## UC coverage

| UC | requirement | test | screenshot | verified |
|----|-------------|------|------------|----------|
| UC-22 | `mask("ABA300000")` → `"[NR_DOWODU]"`; `status="valid"` (integration) | `test_uc22_single_id_card_contiguous` / `_with_space` / `_xyz_card` | — | ❌ three issues: (a) wrong check-digit position means spec's literal `ABA300000` and `XYZ712345` return `suspect` not `valid`; (b) tests use dynamically-constructed values that differ from spec's examples; (c) no `@pytest.mark.integration` test calling `piitier.mask()` |
| UC-23 | `mask("nr ABA400000")` → `"nr [NR_DOWODU]"`; `status="suspect"` (unit) | `test_uc23_wrong_check_digit_suspect`, `test_uc23_suspect_span_never_dropped` | — | ✅ unit-level detect + status verified; both checksum algorithms agree ABA400000 is suspect |
| UC-24 | `mask(card)` → `"[NR_KARTY]"`; `status="valid"` for all 3 formats (integration) | `test_uc24_contiguous_16_digit`, `_spaced_format`, `_dashed_format` | — | ⚠️ detect/status verified at unit level; no `@pytest.mark.integration` test calling `piitier.mask()` |
| UC-25 | `mask("4111 1111 1111 1112")` → `"[NR_KARTY]"`; `status="suspect"` (unit) | `test_uc25_wrong_check_digit_suspect`, `_suspect_span_never_dropped`, `_with_spaces_suspect` | — | ✅ unit-level detect + status verified |
| UC-26 | no `NR_DOWODU` span for `aba300000`, `ABCD300000`, `ABA3000001` | `test_uc26_lowercase_no_match`, `_four_letters_no_match`, `_seven_digits_no_match` | — | ✅ automated |
| UC-27 | no `NR_KARTY` for: Luhn-valid 12-digit, Luhn-valid 20-digit, Luhn-invalid 15-digit; PESEL still PESEL | `test_uc27_12_digit_no_match`, `_20_digit_no_match`, `_pesel_not_confused` | — | ❌ Luhn-invalid 15-digit case has no test; 12 and 20-digit tests use Luhn-invalid inputs instead of Luhn-valid |

Covered: 2/6 UCs fully automated · 1 partially (UC-24 unit only) · 3 failing/missing

---

## Test suites

```
uv run pytest -q -m "not integration"
171 passed, 1 deselected in 1.13s

uv run pytest -q -m integration
1 passed, 171 deselected in 0.15s

uv run pytest -q   (full suite)
172 passed in 1.17s
```

All 172 tests pass. No skipped, no `.only`, no deleted tests observed. The passing suite does
**not** exercise the spec's literal example values or the integration pipeline for PII-1-e.

---

## Findings

### 1. [BLOCKING] UC-22 — ID-card checksum uses wrong check-digit position

**The spec says**: "The 4th character is the check digit" — i.e., position 4 of the 9-char
ID-card string = `digits[0]` (the first digit).

**The implementation** (`src/piitier/rules/id_card.py:62`):
```python
check_digit = int(digits[3])  # The check digit is at position 3 (4th character overall)
```
`digits[3]` is the **fourth** digit, which is position **7** of the 9-char string — three
positions too late. The comment is also wrong ("4th character overall" describes `digits[0]`,
not `digits[3]`).

**Observable consequence**:
```
piitier.rules.id_card.find("ABA300000")  → status="suspect"   # spec requires "valid"
piitier.rules.id_card.find("ABA 300000") → status="suspect"   # spec requires "valid"
piitier.rules.id_card.find("XYZ712345")  → status="suspect"   # spec requires "valid"
```
Verified by manual run: `is_valid("ABA300000") = False`, `is_valid("XYZ712345") = False`.

With the correct algorithm (check at `digits[0]`):
- `(7·A + 3·B + 1·A + 7·0+3·0+1·0+7·0+3·0) % 10 = 113 % 10 = 3 == digits[0]='3'` → valid ✓
- `(7·X + 3·Y + 1·Z + 7·1+3·2+1·3+7·4+3·5) % 10 = (368+59) % 10 = 7 == digits[0]='7'` → valid ✓

**Test masking the bug**: `tests/rules/test_id_card.py:119–130` define `ABA300000 = "ABA300400"` and `XYZ712345 = "XYZ123745"` — dynamically constructed values that pass the implementation's wrong algorithm. The docstrings say "detect on ABA300000" but the actual inputs are different. UC-22 tests pass while the spec's required behaviour fails.

The digit-weights array and `digit_positions = [0, 1, 2, 4, 5]` in `id_card.py:59–61` are consistent with the wrong position: they skip index 3 (the wrong check digit) and include index 0 (the real check digit) as a data digit with weight 7.

---

### 2. [BLOCKING] UC-22 — No integration test calling `piitier.mask()`

The spec's **test column** is `integration` and the **action** is `mask`. No test is marked
`@pytest.mark.integration` in `tests/rules/test_id_card.py`, and no test anywhere calls
`piitier.mask("ABA300000")` to assert the returned string is `"[NR_DOWODU]"`. This leaves the
full pipeline path (`mask → detect → detect_all → id_card.find → render`) untested end-to-end
for the new detector.

File: `tests/rules/test_id_card.py` — no integration test exists.

---

### 3. [BLOCKING] UC-24 — No integration test calling `piitier.mask()`

Same issue as UC-22. The spec column is `integration`. No test is marked
`@pytest.mark.integration` in `tests/rules/test_payment_card.py`, and no test anywhere calls
`piitier.mask("4111111111111111")` to assert `"[NR_KARTY]"` is returned.

File: `tests/rules/test_payment_card.py` — no integration test exists.

---

### 4. [BLOCKING] UC-27 — Luhn-invalid 15-digit run has no test

The spec explicitly names **four** negative cases:
1. Luhn-valid 12-digit run  
2. Luhn-valid 20-digit run  
3. **Luhn-invalid 15-digit run** ← **no test**  
4. PESEL `90051512340`

The Luhn-invalid 15-digit case is the critical one: a 15-digit number matches `_CARD_LONG_RE`
but must be rejected by the Luhn gate. The implementation handles this (`payment_card.py:92`
only appends when `_luhn_check` passes), but no test exercises this branch.

The 12-digit and 20-digit tests use Luhn-**invalid** values (`411111111111`, `41111111111111111111`)
instead of Luhn-**valid** ones. Since `_luhn_check()` rejects lengths outside 13–19 anyway and
`_CARD_LONG_RE` only matches 13–15 and 17–19, those tests pass purely on length — they do not
test the boundary the spec specifies. This is a weaker assertion than the spec requires.

Files: `tests/rules/test_payment_card.py:211–220` (12-digit and 20-digit tests missing the
Luhn-valid property; 15-digit Luhn-invalid test absent entirely).

---

## Not verified

- `piitier.mask()` end-to-end for both new detectors: no integration test exists to run
  (`@pytest.mark.integration` suite only contains the pre-existing `test_uc1_version_printed`).
- Browser/UI: no UI component in this ticket; not applicable.
- The prior-art reference `trasti/complaint-classifier/scripts/scan_pii.py` (lines 101, 104)
  was not accessible; cross-validation of the ID-card check-digit position against the prior
  art was therefore not possible. The manual verification above uses the spec's own stated
  algorithm.
