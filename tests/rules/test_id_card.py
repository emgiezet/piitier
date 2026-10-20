"""Unit and property-based tests for the ID-card validator and detector (PII-1-e).

All ID-card numbers are synthetic, computed for this spec.
Real person numbers are never used.

Acceptance criteria covered:
  UC-22, UC-23, UC-26.
Property tests cover is_valid() and find() with hypothesis-generated values.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from piitier.labels import Label
from piitier.rules.id_card import _checksum_ok, _strip_separator, find, is_valid
import piitier

# ---------------------------------------------------------------------------
# Helpers & hypothesis strategies
# ---------------------------------------------------------------------------

_WEIGHTS_LETTERS = (7, 3, 1)
_WEIGHTS_DIGITS = (7, 3, 1, 7, 3)
_LETTER_VALUES = {chr(ord("A") + i): 10 + i for i in range(26)}


def _compute_check_digit(letters: str, digits_without_check: str) -> str:
    """Compute the ID card check digit for given letters and 5-digit data string.

    Args:
        letters: 3 uppercase letters.
        digits_without_check: 5 digits (the data digits at positions 5-9 of the full card).
    """
    letter_sum = sum(w * _LETTER_VALUES[letter] for w, letter in zip(_WEIGHTS_LETTERS, letters))
    # Apply weights [7, 3, 1, 7, 3] to all 5 data digits
    digit_sum = sum(w * int(digits_without_check[i]) for i, w in enumerate(_WEIGHTS_DIGITS))
    total = (letter_sum + digit_sum) % 10
    return str(total)


def _make_id_card(letters: str, digits_without_check: str) -> str:
    """Construct a synthetic valid ID card string.

    Args:
        letters: 3 uppercase letters.
        digits_without_check: 5 digits (positions 5-9 of the full card, the data digits).
    """
    check = _compute_check_digit(letters, digits_without_check)
    # Reconstruct: check digit (position 4 of full card) followed by all 5 data digits
    return f"{letters}{check}{digits_without_check}"


@st.composite
def valid_id_card_digits(draw: st.DrawFn) -> str:
    """Strategy: generate a syntactically and semantically valid ID card (9 chars)."""
    letters = "".join(chr(ord("A") + draw(st.integers(0, 25))) for _ in range(3))
    # Generate 5 digits for positions 0,1,2,4,5 (skipping position 3 which is the check digit)
    digit_base = "".join(str(draw(st.integers(0, 9))) for _ in range(5))
    return _make_id_card(letters, digit_base)


# ---------------------------------------------------------------------------
# Known synthetic examples — anchors for UC tests
# ---------------------------------------------------------------------------

# ABA300000 — synthetic card with correct checksum
# A=10 (weight 7), B=11 (weight 3), A=10 (weight 1)
# letter_sum = 7*10 + 3*11 + 1*10 = 113 ≡ 3 (mod 10)
# data digits: 0,0,0,0,0 (positions 5-9)
# digit_sum = 7*0 + 3*0 + 1*0 + 7*0 + 3*0 = 0
# check = (3 + 0) % 10 = 3 → card = ABA300000 ✓

ABA_LETTERS = "ABA"
ABA_DIGIT_BASE = "00000"  # data digits at positions 5-9
ABA_CHECK = _compute_check_digit(ABA_LETTERS, ABA_DIGIT_BASE)
ABA300000 = _make_id_card(ABA_LETTERS, ABA_DIGIT_BASE)

XYZ_LETTERS = "XYZ"
XYZ_DIGIT_BASE = "12345"  # data digits at positions 5-9
XYZ_CHECK = _compute_check_digit(XYZ_LETTERS, XYZ_DIGIT_BASE)
XYZ712345 = _make_id_card(XYZ_LETTERS, XYZ_DIGIT_BASE)

# ABA400000 has wrong check digit (4 instead of correct digit 3)
ABA400000_WRONG = "ABA400000"

# ---------------------------------------------------------------------------
# is_valid() — unit
# ---------------------------------------------------------------------------


def test_is_valid_correct_checksum() -> None:
    """is_valid returns True for an ID card with correct check digit."""
    assert is_valid(ABA300000) is True
    assert is_valid(XYZ712345) is True


def test_is_valid_wrong_checksum() -> None:
    """is_valid returns False for an ID card with wrong check digit."""
    assert is_valid(ABA400000_WRONG) is False


def test_is_valid_with_space() -> None:
    """is_valid accepts ID card with space between letters and digits."""
    text_with_space = f"{ABA_LETTERS} {ABA_CHECK}{ABA_DIGIT_BASE}"
    assert is_valid(text_with_space) is True


def test_is_valid_too_short() -> None:
    """is_valid returns False for strings shorter than 9 characters."""
    assert is_valid("ABC12345") is False


def test_is_valid_too_long() -> None:
    """is_valid returns False for strings longer than 9 characters."""
    assert is_valid("ABC1234567") is False


def test_is_valid_lowercase_letters() -> None:
    """is_valid returns False for lowercase letters (only uppercase allowed)."""
    assert is_valid("aba300000") is False


def test_is_valid_not_all_digits() -> None:
    """is_valid returns False when digit part is not all digits."""
    assert is_valid("ABCa00000") is False


# ---------------------------------------------------------------------------
# _checksum_ok() — unit
# ---------------------------------------------------------------------------


def test_checksum_ok_correct() -> None:
    """_checksum_ok returns True for correct check digit."""
    assert _checksum_ok(ABA_LETTERS, ABA_CHECK + ABA_DIGIT_BASE) is True


def test_checksum_ok_wrong() -> None:
    """_checksum_ok returns False for wrong check digit."""
    assert _checksum_ok("ABA", "400000") is False


# ---------------------------------------------------------------------------
# _strip_separator() — unit
# ---------------------------------------------------------------------------


def test_strip_separator_space() -> None:
    assert _strip_separator("ABA 300000") == "ABA300000"


def test_strip_separator_no_space() -> None:
    assert _strip_separator("ABA300000") == "ABA300000"


# ---------------------------------------------------------------------------
# UC-22: Valid ID cards are detected
# ---------------------------------------------------------------------------


def test_uc22_single_id_card_contiguous() -> None:
    """UC-22: detect on ABA300000 → [NR_DOWODU], status='valid'."""
    spans = find(ABA300000)
    assert len(spans) == 1
    assert spans[0].label is Label.NR_DOWODU
    assert spans[0].status == "valid"


def test_uc22_single_id_card_with_space() -> None:
    """UC-22: detect on ABA 300000 → [NR_DOWODU], status='valid'."""
    text = f"{ABA_LETTERS} {ABA_CHECK}{ABA_DIGIT_BASE}"
    spans = find(text)
    assert len(spans) == 1
    assert spans[0].label is Label.NR_DOWODU
    assert spans[0].status == "valid"


def test_uc22_xyz_card() -> None:
    """UC-22: detect on XYZ712345 → [NR_DOWODU], status='valid'."""
    spans = find(XYZ712345)
    assert len(spans) == 1
    assert spans[0].label is Label.NR_DOWODU
    assert spans[0].status == "valid"


def test_uc22_span_offsets_correct() -> None:
    """UC-22: offsets are correct when ID card is embedded in text."""
    text = f"id: {ABA300000} koniec"
    spans = find(text)
    assert len(spans) == 1
    assert text[spans[0].start : spans[0].end] == ABA300000


def test_uc22_multiple_cards() -> None:
    """UC-22: multiple ID cards in text are all detected."""
    text = f"{ABA300000} and {XYZ712345} here"
    spans = find(text)
    assert len(spans) == 2
    assert all(s.label is Label.NR_DOWODU for s in spans)
    assert all(s.status == "valid" for s in spans)


# ---------------------------------------------------------------------------
# UC-23: Wrong check digit → suspect (no keyword needed)
# ---------------------------------------------------------------------------


def test_uc23_wrong_check_digit_suspect() -> None:
    """UC-23: detect on 'nr ABA400000' (wrong check digit, no keyword) → suspect."""
    spans = find("nr ABA400000")
    assert len(spans) == 1
    assert spans[0].label is Label.NR_DOWODU
    assert spans[0].status == "suspect"


def test_uc23_suspect_span_never_dropped() -> None:
    """UC-23 / invariant-6: bad-checksum ID card is not dropped, only marked suspect."""
    spans = find("found: ABA400000 in text")
    assert len(spans) == 1
    assert spans[0].status == "suspect"


# ---------------------------------------------------------------------------
# UC-26: Negative cases — lowercase, 4 letters, 7 digits
# ---------------------------------------------------------------------------


def test_uc26_lowercase_no_match() -> None:
    """UC-26: detect on 'aba300000' (lowercase) → no NR_DOWODU span."""
    spans = find("aba300000")
    # Should find nothing or just mark as suspect if it somehow matches, but lowercase letters
    # don't match the regex [A-Z]{3}
    assert len(spans) == 0


def test_uc26_four_letters_no_match() -> None:
    """UC-26: detect on 'ABCD300000' (4 letters, 6 digits) → no NR_DOWODU span."""
    spans = find("ABCD300000")
    assert len(spans) == 0


def test_uc26_seven_digits_no_match() -> None:
    """UC-26: detect on 'ABA3000001' (3 letters, 7 digits) → no NR_DOWODU span."""
    spans = find("ABA3000001")
    assert len(spans) == 0


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------


@given(valid_id_card_digits())
@settings(max_examples=50)
def test_property_valid_cards_pass_validator(card: str) -> None:
    """Property: valid generated cards pass is_valid()."""
    assert is_valid(card) is True


@given(valid_id_card_digits())
@settings(max_examples=50)
def test_property_valid_cards_detected(card: str) -> None:
    """Property: valid generated cards are detected with status='valid'."""
    text = f"card: {card} end"
    spans = find(text)
    assert len(spans) >= 1
    assert any(s.status == "valid" for s in spans)


# Test with separator variants
@given(valid_id_card_digits())
@settings(max_examples=20)
def test_property_cards_with_space_detected(card: str) -> None:
    """Property: valid cards with space separator are detected."""
    letters = card[:3]
    digits = card[3:]
    text_with_space = f"{letters} {digits}"
    spans = find(text_with_space)
    assert len(spans) >= 1
    assert text_with_space[spans[0].start : spans[0].end] == text_with_space.strip()


# ---------------------------------------------------------------------------
# UC-22: Integration test — mask() replaces ID cards with placeholder
# ---------------------------------------------------------------------------

import pytest


@pytest.mark.integration
def test_uc22_mask_contiguous() -> None:
    """UC-22 integration: mask("ABA300000") → "[NR_DOWODU]", status="valid"."""
    result = piitier.mask(ABA300000)
    assert result == "[NR_DOWODU]"


@pytest.mark.integration
def test_uc22_mask_with_space() -> None:
    """UC-22 integration: mask("ABA 300000") → "[NR_DOWODU]", status="valid"."""
    text = f"{ABA_LETTERS} {ABA_CHECK}{ABA_DIGIT_BASE}"
    result = piitier.mask(text)
    assert result == "[NR_DOWODU]"


@pytest.mark.integration
def test_uc22_mask_xyz_card() -> None:
    """UC-22 integration: mask("XYZ712345") → "[NR_DOWODU]", status="valid"."""
    result = piitier.mask(XYZ712345)
    assert result == "[NR_DOWODU]"
