---
ticket: PII-1-e
title: Mask ID-card numbers and payment-card numbers — QA Report
status: PASS
date: 2026-10-20
---

# QA Report — PII-1-e

**Verdict: PASS**

---

## UC coverage

| UC | requirement | test | verified |
|---|---|---|---|
| UC-22 | `mask("ABA300000")` → `"[NR_DOWODU]"`; `status="valid"` (integration) | `test_uc22_mask_contiguous`, `_mask_with_space`, `_mask_xyz_card` | ✅ |
| UC-23 | `mask("nr ABA400000")` → `"nr [NR_DOWODU]"`; `status="suspect"` (unit) | `test_uc23_wrong_check_digit_suspect`, `_suspect_span_never_dropped` | ✅ |
| UC-24 | `mask(card)` → `"[NR_KARTY]"`; `status="valid"` for 3 formats (integration) | `test_uc24_mask_contiguous_16`, `_mask_spaced_16`, `_mask_dashed_16` | ✅ |
| UC-25 | `mask("4111 1111 1111 1112")` → `"[NR_KARTY]"`; `status="suspect"` (unit) | `test_uc25_wrong_check_digit_suspect`, `_suspect_span_never_dropped`, `_with_spaces_suspect` | ✅ |
| UC-26 | no `NR_DOWODU` for `aba300000`, `ABCD300000`, `ABA3000001` | `test_uc26_lowercase_no_match`, `_four_letters_no_match`, `_seven_digits_no_match` | ✅ |
| UC-27 | no `NR_KARTY` for Luhn-valid 12-digit, 20-digit, Luhn-invalid 15-digit, PESEL | `test_uc27_12_digit_no_match`, `_20_digit_no_match`, `_luhn_invalid_15_digit_no_match`, `_pesel_not_confused` | ✅ |

**Covered: 6/6 fully automated** · **Tests: 54 → 61** · **Skipped: 0**

---

## Test suites

```
uv run pytest -q -m "not integration"
 (54 unit tests)       → 54 passed in 0.19s

uv run pytest -q -m integration
 (7 integration tests) → 7 passed in 0.11s

uv run pytest -q
 (61 total)            → 61 passed in 0.23s
```

All tests pass. No skipped tests. All UC-marked tests exercise the observable result specified in the acceptance criteria.

---

## Findings

### 1. [FIXED] UC-22 — ID-card checksum used wrong digit position

**Status: Fixed in this QA cycle**

**Original bug** (`src/piitier/rules/id_card.py:57-61`):
```python
# Before (buggy)
digit_positions = [0, 1, 2, 4, 5]  # Included check digit position 0
check_digit = int(digits[3])       # Used position 3 instead of 0
```

The spec states: "The 4th character is the check digit" (position 4 in the full card, index 0 in the 6-digit string). The implementation was using index 3, which is position 7 of the full card — 3 positions off.

**Root cause:** Test values were dynamically computed using the same buggy algorithm, masking the error. Test data comments referenced incorrect digit positions.

**Fix applied:**
```python
# After (fixed)
digit_positions = [1, 2, 3, 4, 5]  # Data digits only (skip check at 0)
check_digit = int(digits[0])       # Check digit at position 0 ✓
```

Test data updated:
- `ABA_DIGIT_BASE` changed from `"30000"` to `"00000"` (represents data digits, not including check)
- `_make_id_card()` now constructs: `letters + check + data` (correct order)
- All 24 ID-card tests now pass with correct algorithm

---

### 2. [FIXED] UC-22 — Added missing integration test for mask()

**Status: Fixed in this QA cycle**

Three new integration tests added:
- `test_uc22_mask_contiguous`: Calls `piitier.mask("ABA300000")` → `"[NR_DOWODU]"` ✓
- `test_uc22_mask_with_space`: Calls `piitier.mask("ABA 300000")` → `"[NR_DOWODU]"` ✓
- `test_uc22_mask_xyz_card`: Calls `piitier.mask("XYZ712345")` → `"[NR_DOWODU]"` ✓

Each test marked `@pytest.mark.integration` and exercises the full `mask() → detect() → mask_render()` pipeline on real spec examples.

---

### 3. [FIXED] UC-24 — Added missing integration test for mask()

**Status: Fixed in this QA cycle**

Three new integration tests added:
- `test_uc24_mask_contiguous_16`: Calls `piitier.mask("4111111111111111")` → `"[NR_KARTY]"` ✓
- `test_uc24_mask_spaced_16`: Calls `piitier.mask("4111 1111 1111 1111")` → `"[NR_KARTY]"` ✓
- `test_uc24_mask_dashed_16`: Calls `piitier.mask("4111-1111-1111-1111")` → `"[NR_KARTY]"` ✓

All three format variants from the spec are now tested end-to-end.

---

### 4. [FIXED] UC-27 — Added missing edge case test

**Status: Fixed in this QA cycle**

New test added:
- `test_uc27_luhn_invalid_15_digit_no_match`: Calls `detect("111111111111111")` (15 contiguous 1s, fails Luhn) → no `NR_KARTY` span ✓

This completes the negative test case set: 12-digit, 20-digit, and 15-digit (Luhn-invalid) numbers are all correctly rejected.

---

## Implementation verification

**ID-card checksum (spec example):**
```python
# ABA300000: A=10, B=11, A=10; data digits 0,0,0,0,0
letter_sum = 7*10 + 3*11 + 1*10 = 113 ≡ 3 (mod 10)
digit_sum  = 7*0 + 3*0 + 1*0 + 7*0 + 3*0 = 0
check      = (3 + 0) % 10 = 3 ✓ (matches ABA300000)
```

**Payment-card Luhn check:**
- `4111111111111111` (VISA, 16 digits): passes Luhn, marked `status="valid"` ✓
- `4111 1111 1111 1112` (invalid check): fails Luhn, marked `status="suspect"` ✓
- `111111111111111` (15 ones): fails Luhn, not matched at all ✓

---

## Not verified

- Card brand detection (BIN ranges) — Out of scope (PII-1-e spec line 34)
- Lowercase ID-card numbers — Explicitly rejected by spec (line 35)
- Manual review of rendered output in a browser/UI — No browser descriptor configured

---

## Summary

- **All 6 acceptance criteria automated and passing** ✓
- **61 total tests (54 unit + 7 integration)** ✓
- **4 blocking findings resolved in this cycle** ✓
- **Zero skipped tests, zero test-integrity issues** ✓
- **Implementation now matches spec exactly** ✓

Verdict: **PASS** — Ready for /sdlc:scope-check and /sdlc:ship.
