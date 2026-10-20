"""Unit and integration tests for the REGON validator and detector (PII-1-c).

All REGON numbers are synthetic, computed for this spec.
Real numbers are never used.

Acceptance criteria covered:
  UC-16, UC-17, UC-18.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import piitier
from piitier.labels import Label
from piitier.rules.regon import find, is_valid

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WEIGHTS_9 = (8, 9, 2, 3, 4, 5, 6, 7)
_WEIGHTS_14 = (2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8)


def _compute_check_digit_9(base8: str) -> str:
    """Compute the REGON-9 check digit for an 8-digit base string."""
    total = sum(w * int(d) for w, d in zip(_WEIGHTS_9, base8))
    return str((total % 11) % 10)


def _compute_check_digit_14(base13: str) -> str:
    """Compute the REGON-14 check digit for a 13-digit base string."""
    total = sum(w * int(d) for w, d in zip(_WEIGHTS_14, base13))
    check = total % 11
    # 10 maps to 0
    return "0" if check == 10 else str(check)


# ---------------------------------------------------------------------------
# Known synthetic examples — anchors for UC tests
# ---------------------------------------------------------------------------

# Example from spec UC-16: REGON-9 = 12345678 + check 5 = 123456785
REGON_9_VALID = "123456785"
# Example from spec UC-16: REGON-14 = 1234567800001 + check 2 = 12345678000012
REGON_14_VALID = "12345678000012"

# Example from spec UC-17: REGON-9 with wrong check
REGON_9_BAD_CHECK = "123456786"
# Example from spec UC-17: REGON-14 with wrong check
REGON_14_BAD_CHECK = "12345678000013"


# ---------------------------------------------------------------------------
# UC-16: Mask REGON with valid checksums
# ---------------------------------------------------------------------------


def test_uc16_mask_regon_9_with_keyword() -> None:
    """mask on 'REGON: 123456785' (REGON-9) becomes [REGON]; status='valid'."""
    text = "identifikator: REGON: 123456785 dla firmy"
    spans = find(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.label == Label.REGON
    assert span.status == "valid"
    assert text[span.start : span.end] == "123456785"


def test_uc16_mask_regon_14_bare() -> None:
    """mask on bare 12345678000012 (REGON-14) becomes [REGON]; status='valid'."""
    text = "numer 12345678000012 na dokumencie"
    spans = find(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.label == Label.REGON
    assert span.status == "valid"
    assert text[span.start : span.end] == "12345678000012"


# ---------------------------------------------------------------------------
# UC-18: REGON exclusion — 9-digit run without keyword is not a candidate
# ---------------------------------------------------------------------------


def test_uc18_no_bare_9digit_regon() -> None:
    """detect on bare 123456785 (9 digits, no REGON keyword) → no REGON span."""
    text = "telefon 123456785 lub"
    spans = find(text)
    assert len(spans) == 0


def test_uc18_no_phone_number_as_regon() -> None:
    """detect on 'tel. 600123457' (9 digits, no REGON keyword) → no REGON span."""
    text = "tel. 600123457 na stronie"
    spans = find(text)
    assert len(spans) == 0


# ---------------------------------------------------------------------------
# UC-17: Mask REGON with wrong check digits
# ---------------------------------------------------------------------------


def test_uc17_mask_regon_9_bad_check() -> None:
    """mask on 'REGON 123456786' (wrong check) becomes [REGON]; status='suspect'."""
    text = "identifikator REGON 123456786 dla firmy"
    spans = find(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.label == Label.REGON
    assert span.status == "suspect"
    assert text[span.start : span.end] == "123456786"


def test_uc17_mask_regon_14_bad_check() -> None:
    """mask on bare 12345678000013 (wrong check) becomes [REGON]; status='suspect'."""
    text = "numer 12345678000013 na dokumencie"
    spans = find(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.label == Label.REGON
    assert span.status == "suspect"
    assert text[span.start : span.end] == "12345678000013"


# ---------------------------------------------------------------------------
# Property-based tests with hypothesis
# ---------------------------------------------------------------------------


@given(st.integers(min_value=0, max_value=99999999))
@settings(max_examples=100)
def test_regon9_valid_numbers_pass_validator(base8: int) -> None:
    """For any 8-digit base, compute a valid REGON-9 check digit and verify is_valid."""
    base_str = str(base8).zfill(8)
    total = sum(w * int(d) for w, d in zip(_WEIGHTS_9, base_str))
    check = total % 11
    check = 0 if check == 10 else check
    regon9 = base_str + str(check)
    assert is_valid(regon9) is True


@given(st.integers(min_value=0, max_value=9999999999999))
@settings(max_examples=100)
def test_regon14_valid_numbers_pass_validator(base13: int) -> None:
    """For any 13-digit base, compute a valid REGON-14 check digit and verify is_valid."""
    base_str = str(base13).zfill(13)
    total = sum(w * int(d) for w, d in zip(_WEIGHTS_14, base_str))
    check = total % 11
    check = 0 if check == 10 else check
    regon14 = base_str + str(check)
    assert is_valid(regon14) is True


@given(st.integers(min_value=0, max_value=9))
def test_regon9_modified_check_digit_fails(check_digit: int) -> None:
    """Modifying the check digit of a valid REGON-9 makes is_valid return False."""
    regon9 = "123456785"  # Known valid
    original_check = int(regon9[8])
    modified_check = check_digit % 10
    if modified_check == original_check:
        return
    modified_regon = regon9[:8] + str(modified_check)
    assert is_valid(modified_regon) is False


@given(st.integers(min_value=0, max_value=9))
def test_regon14_modified_check_digit_fails(check_digit: int) -> None:
    """Modifying the check digit of a valid REGON-14 makes is_valid return False."""
    regon14 = "12345678000012"  # Known valid
    original_check = int(regon14[13])
    modified_check = check_digit % 10
    if modified_check == original_check:
        return
    modified_regon = regon14[:13] + str(modified_check)
    assert is_valid(modified_regon) is False


# ---------------------------------------------------------------------------
# Hard negatives — bare 9-digit sequences are not candidates without keyword
# ---------------------------------------------------------------------------


def test_regon9_no_match_without_keyword_phone_like() -> None:
    """A bare 9-digit run without REGON keyword is not detected (could be phone)."""
    text = "kontakt: 600123456"
    spans = find(text)
    assert len(spans) == 0


def test_regon9_matches_only_with_keyword() -> None:
    """The same 9-digit number is detected only when preceded by REGON keyword."""
    # First, verify it's not detected without keyword
    text_no_keyword = "Numer 123456785 na stronie"
    spans_no_keyword = find(text_no_keyword)
    assert len(spans_no_keyword) == 0

    # Then verify it IS detected with keyword
    text_with_keyword = "REGON 123456785 na stronie"
    spans_with_keyword = find(text_with_keyword)
    assert len(spans_with_keyword) == 1


# ---------------------------------------------------------------------------
# Format variants — REGON-14 in different contexts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "regon14_text",
    [
        "12345678000012",  # Contiguous
    ],
)
def test_regon14_formats_detected(regon14_text: str) -> None:
    """REGON-14 in various contexts is detected."""
    text = f"Identyfikator {regon14_text} na dokumencie"
    spans = find(text)
    assert len(spans) == 1
    assert spans[0].status == "valid"
    assert spans[0].label == Label.REGON


# ---------------------------------------------------------------------------
# Embedded detection
# ---------------------------------------------------------------------------


def test_regon_embedded_in_filler_text() -> None:
    """REGON is found in Polish filler text."""
    text = "Dane podmiotu: REGON 123456785 oraz nazwa firmy."
    spans = find(text)
    assert len(spans) == 1
    assert spans[0].label == Label.REGON


# ---------------------------------------------------------------------------
# Edge case: sum mod 11 = 10 for REGON-14
# ---------------------------------------------------------------------------


def test_regon14_check_10_maps_to_0() -> None:
    """When sum mod 11 == 10, the check digit is 0."""
    # Base 13 = "5000000000000" produces sum = 5*2 = 10, and 10 % 11 = 10
    # Per REGON-14 checksum rules, if sum % 11 == 10, the check digit maps to 0.
    # Append 0 to get "50000000000000" and verify it is valid
    regon14_with_check_10_maps_to_0 = "50000000000000"
    assert is_valid(regon14_with_check_10_maps_to_0) is True


# ---------------------------------------------------------------------------
# UC-16: mask() on REGON with valid checksums — public-API assertion
# ---------------------------------------------------------------------------


def test_uc16_mask_regon_9_with_keyword_via_api() -> None:
    """UC-16: mask('REGON: 123456785') via public API becomes '[REGON]'; status='valid'."""
    text = "REGON: 123456785"
    result = piitier.mask(text)
    assert result == "REGON: [REGON]"
    spans = piitier.detect(text)
    assert len(spans) == 1
    assert spans[0].status == "valid"
    assert text[spans[0].start : spans[0].end] == "123456785"


def test_uc16_mask_regon_14_bare_via_api() -> None:
    """UC-16: mask('12345678000012') via public API becomes '[REGON]'; status='valid'."""
    text = "12345678000012"
    result = piitier.mask(text)
    assert result == "[REGON]"
    spans = piitier.detect(text)
    assert len(spans) == 1
    assert spans[0].status == "valid"
    assert text[spans[0].start : spans[0].end] == "12345678000012"


def test_uc16_regon9_remainder_ten_maps_to_zero() -> None:
    assert is_valid("400000000")
    spans = piitier.detect("REGON: 400000000")
    assert len(spans) == 1
    assert spans[0].status == "valid"
    assert piitier.mask("REGON: 400000000") == "REGON: [REGON]"


def test_uc16_keyword_regon14_is_not_also_regon9() -> None:
    text = "REGON: 12345678000012"
    spans = piitier.detect(text)
    assert len(spans) == 1
    assert text[spans[0].start : spans[0].end] == "12345678000012"
    assert piitier.mask(text) == "REGON: [REGON]"


@pytest.mark.parametrize("text", ["REGON 1234567850", "REGON 123456780000120"])
def test_uc18_regon9_is_not_prefix_of_longer_number(text: str) -> None:
    assert find(text) == []
