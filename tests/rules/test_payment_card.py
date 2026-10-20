"""Unit tests for the payment-card validator and detector (PII-1-e).

All card numbers are public test values or synthetic examples.
Real card numbers are never used.

Acceptance criteria covered:
  UC-24, UC-25, UC-27.
"""

from __future__ import annotations

import pytest

import piitier
from piitier.labels import Label
from piitier.rules.payment_card import _luhn_check, _strip_separators, find, is_valid

# Verified test cards (public, well-known test values)
VISA_VALID = "4111111111111111"
MASTERCARD_VALID = "5555555555554444"
AMEX_VALID = "378282246310005"
DISCOVER_VALID = "6011111111111117"
DINERS_VALID = "30569309025904"

# Valid 16-digit card with wrong check digit
VISA_WRONG_CHECK = "4111111111111112"


# ---------------------------------------------------------------------------
# _luhn_check() — unit
# ---------------------------------------------------------------------------


def test_luhn_check_visa_valid() -> None:
    """_luhn_check returns True for Visa test card."""
    assert _luhn_check(VISA_VALID) is True


def test_luhn_check_mastercard_valid() -> None:
    """_luhn_check returns True for MasterCard test card."""
    assert _luhn_check(MASTERCARD_VALID) is True


def test_luhn_check_amex_valid() -> None:
    """_luhn_check returns True for Amex test card."""
    assert _luhn_check(AMEX_VALID) is True


def test_luhn_check_discover_valid() -> None:
    """_luhn_check returns True for Discover test card."""
    assert _luhn_check(DISCOVER_VALID) is True


def test_luhn_check_diners_valid() -> None:
    """_luhn_check returns True for Diners test card."""
    assert _luhn_check(DINERS_VALID) is True


def test_luhn_check_wrong_check() -> None:
    """_luhn_check returns False for a card with wrong check digit."""
    assert _luhn_check(VISA_WRONG_CHECK) is False


# ---------------------------------------------------------------------------
# _strip_separators() — unit
# ---------------------------------------------------------------------------


def test_strip_separators_spaces() -> None:
    """_strip_separators removes spaces."""
    assert _strip_separators("4111 1111 1111 1111") == "4111111111111111"


def test_strip_separators_dashes() -> None:
    """_strip_separators removes dashes."""
    assert _strip_separators("4111-1111-1111-1111") == "4111111111111111"


def test_strip_separators_no_change() -> None:
    """_strip_separators returns unchanged when no separators."""
    assert _strip_separators("4111111111111111") == "4111111111111111"


# ---------------------------------------------------------------------------
# is_valid() — unit
# ---------------------------------------------------------------------------


def test_is_valid_16_digit_visa() -> None:
    """is_valid returns True for valid Visa."""
    assert is_valid(VISA_VALID) is True


def test_is_valid_16_digit_mastercard() -> None:
    """is_valid returns True for valid MasterCard."""
    assert is_valid(MASTERCARD_VALID) is True


def test_is_valid_15_digit_amex() -> None:
    """is_valid returns True for valid Amex (15 digits)."""
    assert is_valid(AMEX_VALID) is True


def test_is_valid_14_digit_diners() -> None:
    """is_valid returns True for valid Diners (14 digits)."""
    assert is_valid(DINERS_VALID) is True


def test_is_valid_wrong_checksum() -> None:
    """is_valid returns False for wrong check digit."""
    assert is_valid(VISA_WRONG_CHECK) is False


def test_is_valid_too_short() -> None:
    """is_valid returns False for < 13 digits."""
    assert is_valid("411111111111") is False


def test_is_valid_too_long() -> None:
    """is_valid returns False for > 19 digits."""
    assert is_valid("41111111111111111111") is False


def test_is_valid_with_spaces() -> None:
    """is_valid accepts card with spaces."""
    assert is_valid("4111 1111 1111 1111") is True


def test_is_valid_with_dashes() -> None:
    """is_valid accepts card with dashes."""
    assert is_valid("4111-1111-1111-1111") is True


# ---------------------------------------------------------------------------
# UC-24: Valid 16-digit payment cards in 3 format variants
# ---------------------------------------------------------------------------


def test_uc24_contiguous_16_digit() -> None:
    """UC-24: detect on 4111111111111111 (16 contiguous) → [NR_KARTY], status='valid'."""
    spans = find(VISA_VALID)
    assert len(spans) == 1
    assert spans[0].label is Label.NR_KARTY
    assert spans[0].status == "valid"


def test_uc24_spaced_format() -> None:
    """UC-24: detect on '4111 1111 1111 1111' (space-separated) → [NR_KARTY], status='valid'."""
    text = "4111 1111 1111 1111"
    spans = find(text)
    assert len(spans) == 1
    assert spans[0].label is Label.NR_KARTY
    assert spans[0].status == "valid"


def test_uc24_dashed_format() -> None:
    """UC-24: detect on '4111-1111-1111-1111' (dash-separated) → [NR_KARTY], status='valid'."""
    text = "4111-1111-1111-1111"
    spans = find(text)
    assert len(spans) == 1
    assert spans[0].label is Label.NR_KARTY
    assert spans[0].status == "valid"


def test_uc24_span_offsets_correct() -> None:
    """UC-24: offsets are correct when card is embedded in text."""
    text = f"card: {VISA_VALID} end"
    spans = find(text)
    assert len(spans) == 1
    assert text[spans[0].start : spans[0].end] == VISA_VALID


def test_uc24_multiple_cards() -> None:
    """UC-24: multiple cards in text are all detected."""
    text = f"{VISA_VALID} and {MASTERCARD_VALID} here"
    spans = find(text)
    assert len(spans) == 2
    assert all(s.label is Label.NR_KARTY for s in spans)
    assert all(s.status == "valid" for s in spans)


# ---------------------------------------------------------------------------
# UC-25: 16-digit card with wrong check digit → suspect
# ---------------------------------------------------------------------------


def test_uc25_wrong_check_digit_suspect() -> None:
    """UC-25: detect on 4111111111111112 (wrong check, no keyword) → suspect."""
    spans = find("4111111111111112")
    assert len(spans) == 1
    assert spans[0].label is Label.NR_KARTY
    assert spans[0].status == "suspect"


def test_uc25_suspect_span_never_dropped() -> None:
    """UC-25 / invariant-6: bad-checksum card is not dropped, only marked suspect."""
    spans = find("found: 4111111111111112 in text")
    assert len(spans) == 1
    assert spans[0].status == "suspect"


def test_uc25_with_spaces_suspect() -> None:
    """UC-25: wrong-check card with spaces is still suspect."""
    spans = find("4111 1111 1111 1112")
    assert len(spans) == 1
    assert spans[0].status == "suspect"


# ---------------------------------------------------------------------------
# UC-27: Negative cases — lowercase, boundaries, PESEL overlap
# ---------------------------------------------------------------------------


def test_uc27_12_digit_no_match() -> None:
    """UC-27: 12-digit run produces no span."""
    spans = find("411111111111")
    assert len(spans) == 0


def test_uc27_20_digit_no_match() -> None:
    """UC-27: 20-digit run produces no span."""
    spans = find("41111111111111111111")
    assert len(spans) == 0


def test_uc27_pesel_not_confused() -> None:
    """UC-27: PESEL 90051512340 is not detected as card."""
    from piitier.rules.pesel import find as pesel_find

    card_spans = [s for s in find("90051512340") if s.label is Label.NR_KARTY]
    assert len(card_spans) == 0

    # Verify PESEL is still detected correctly
    pesel_spans = pesel_find("90051512340")
    assert len(pesel_spans) == 1


# ---------------------------------------------------------------------------
# Different card lengths and types
# ---------------------------------------------------------------------------


def test_various_valid_cards() -> None:
    """Different card types with different lengths are all detected."""
    cards = [
        (VISA_VALID, 16),  # Visa
        (MASTERCARD_VALID, 16),  # MasterCard
        (AMEX_VALID, 15),  # Amex
        (DISCOVER_VALID, 16),  # Discover
        (DINERS_VALID, 14),  # Diners
    ]
    for card, expected_len in cards:
        spans = find(card)
        assert len(spans) == 1, f"Expected 1 span for {card}"
        assert spans[0].label is Label.NR_KARTY
        assert spans[0].status == "valid"
        assert spans[0].end - spans[0].start == expected_len


# ---------------------------------------------------------------------------
# UC-24: Integration test — mask() replaces payment cards with placeholder
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_uc24_mask_contiguous_16() -> None:
    """UC-24 integration: mask("4111111111111111") → "[NR_KARTY]", status="valid"."""
    result = piitier.mask(VISA_VALID)
    assert result == "[NR_KARTY]"


@pytest.mark.integration
def test_uc24_mask_spaced_16() -> None:
    """UC-24 integration: mask("4111 1111 1111 1111") → "[NR_KARTY]", status="valid"."""
    text = "4111 1111 1111 1111"
    result = piitier.mask(text)
    assert result == "[NR_KARTY]"


@pytest.mark.integration
def test_uc24_mask_dashed_16() -> None:
    """UC-24 integration: mask("4111-1111-1111-1111") → "[NR_KARTY]", status="valid"."""
    text = "4111-1111-1111-1111"
    result = piitier.mask(text)
    assert result == "[NR_KARTY]"


# ---------------------------------------------------------------------------
# UC-27: Edge case — Luhn-invalid 15-digit run should not match
# ---------------------------------------------------------------------------


def test_uc27_luhn_invalid_15_digit_no_match() -> None:
    """UC-27: detect on Luhn-invalid 15-digit run → no [NR_KARTY] span."""
    # Use a 15-digit number that fails Luhn check
    # 15 consecutive 1s fails Luhn
    spans = find("111111111111111")
    # Should not find any payment card (fails Luhn)
    assert not any(s.label is Label.NR_KARTY for s in spans)
