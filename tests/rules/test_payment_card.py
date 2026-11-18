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


# ---------------------------------------------------------------------------
# Context-boundary: false-positive suppression (FP-1, FP-2, FP-3, FP-4)
# ---------------------------------------------------------------------------


def test_fp1_decimal_16digit_not_detected() -> None:
    """FP-1: Luhn-valid 16-digit run inside a float literal is not detected.

    '0.8888888888888888' contains 16 consecutive 8s that are Luhn-valid; the run
    is directly preceded by digit + '.' so the context-boundary guard rejects it.
    """
    # 8888888888888888 passes Luhn, but is inside a float
    spans = [s for s in find("0.8888888888888888") if s.label is Label.NR_KARTY]
    assert len(spans) == 0


def test_fp2_decimal_17digit_not_detected() -> None:
    """FP-2: Luhn-valid 17-digit run inside a float literal is not detected.

    '0.28571428571428575' (a benchmark F1 score) contains a 17-digit run preceded
    by digit + '.'; context boundary rejects it.
    """
    spans = [s for s in find("0.28571428571428575") if s.label is Label.NR_KARTY]
    assert len(spans) == 0


def test_fp3_float_in_json_context_not_detected() -> None:
    """FP-3: Float metric embedded in JSON is not detected."""
    spans = [s for s in find('  "f1": 0.28571428571428575,') if s.label is Label.NR_KARTY]
    assert len(spans) == 0


def test_fp4_hex_token_adjacent_not_detected() -> None:
    """FP-4: Luhn-valid digit run surrounded by hex letters is not detected.

    'cc4111111111111111ff' embeds the known Visa test card between hex letters; the
    letter-adjacency guard on both sides rejects it.
    """
    spans = [s for s in find("cc4111111111111111ff") if s.label is Label.NR_KARTY]
    assert len(spans) == 0


def test_fp4b_hex_token_left_adjacent_not_detected() -> None:
    """FP-4b: Digit run preceded by a letter (only) is not detected."""
    spans = [s for s in find("abc4111111111111111") if s.label is Label.NR_KARTY]
    assert len(spans) == 0


def test_fp4c_hex_token_right_adjacent_not_detected() -> None:
    """FP-4c: Digit run followed only by hex letters is not detected."""
    spans = [s for s in find("4111111111111111ff") if s.label is Label.NR_KARTY]
    assert len(spans) == 0


def test_card_followed_by_sentence_period_detected() -> None:
    """Context-boundary: card at end of sentence ('4111111111111111.') is still detected.

    A trailing '.' not followed by a digit is a sentence period, not a decimal; the
    right-side guard '(?![.,]\\d)' does not fire.
    """
    spans = find("Karta: 4111111111111111.")
    nr_karty = [s for s in spans if s.label is Label.NR_KARTY]
    assert len(nr_karty) == 1
    assert nr_karty[0].status == "valid"


def test_spaced_card_still_detected_after_boundary_fix() -> None:
    """Context-boundary: space-separated format '4111 1111 1111 1111' is still detected."""
    spans = find("4111 1111 1111 1111")
    nr_karty = [s for s in spans if s.label is Label.NR_KARTY]
    assert len(nr_karty) == 1
    assert nr_karty[0].status == "valid"


def test_dashed_card_still_detected_after_boundary_fix() -> None:
    """Context-boundary: dash-separated format '4111-1111-1111-1111' is still detected."""
    spans = find("4111-1111-1111-1111")
    nr_karty = [s for s in spans if s.label is Label.NR_KARTY]
    assert len(nr_karty) == 1
    assert nr_karty[0].status == "valid"


def test_suspect_in_normal_context_not_dropped_after_boundary_fix() -> None:
    """Context-boundary: Luhn-invalid 16-digit run in plain text is still reported as suspect.

    The context-boundary guards do not suppress suspect spans; the invariant that a
    checksum-invalid candidate in a 'card-shaped' context is never silently dropped holds.
    """
    spans = find(f"numer: {VISA_WRONG_CHECK} koniec")
    nr_karty = [s for s in spans if s.label is Label.NR_KARTY]
    assert len(nr_karty) == 1
    assert nr_karty[0].status == "suspect"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Jan,4111111111111111,100", "Jan,[NR_KARTY],100"),
        ("100,4111111111111111", "100,[NR_KARTY]"),
        ("4111111111111111,100", "[NR_KARTY],100"),
        ("Jan;4111111111111111;100", "Jan;[NR_KARTY];100"),
        ("karta 4111111111111111", "karta [NR_KARTY]"),
    ],
)
def test_uc218_mask_preserves_delimiter_fields(text: str, expected: str) -> None:
    assert piitier.mask(text) == expected


def test_uc219_invalid_comma_card_is_suspect_and_masked() -> None:
    text = "100,4111111111111112,200"
    spans = find(text)
    assert len(spans) == 1
    assert (spans[0].start, spans[0].end, spans[0].label, spans[0].status) == (
        4,
        20,
        Label.NR_KARTY,
        "suspect",
    )
    assert piitier.mask(text) == "100,[NR_KARTY],200"


@pytest.mark.parametrize(
    ("prefix", "suffix"),
    [("karta", " wydana"), ("", "xyz"), ("płatność", "zakończona"), ("id_", "_ref")],
)
@pytest.mark.parametrize("card", [VISA_VALID, VISA_WRONG_CHECK])
def test_uc220_nonhex_word_glued_card_is_suspect(prefix: str, suffix: str, card: str) -> None:
    text = prefix + card + suffix
    spans = find(text)
    assert len(spans) == 1
    assert (spans[0].start, spans[0].end, spans[0].status) == (
        len(prefix),
        len(prefix) + len(card),
        "suspect",
    )
    assert piitier.mask(text) == prefix + "[NR_KARTY]" + suffix


@pytest.mark.parametrize("card", ["4111 1111 1111 1111", "4111-1111-1111-1112"])
def test_uc220_grouped_card_is_not_a_hex_fragment(card: str) -> None:
    text = f"abc{card}ff"
    spans = find(text)
    assert len(spans) == 1
    assert (spans[0].start, spans[0].end, spans[0].status) == (3, 3 + len(card), "suspect")
    assert piitier.mask(text) == "abc[NR_KARTY]ff"


@pytest.mark.parametrize("card", [VISA_VALID, VISA_WRONG_CHECK])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_uc221_mask_csv_preserves_neighboring_cells(card: str, newline: str) -> None:
    text = f"imie,karta,kwota{newline}Jan,{card},100{newline}"
    assert piitier.mask_csv(text) == f"imie,karta,kwota{newline}Jan,[NR_KARTY],100{newline}"


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_uc221_14_digit_csv_preserves_surrounding_text(newline: str) -> None:
    text = f"id,kwota{newline}30569309025904,100{newline}"
    assert piitier.mask_csv(text) == f"id,kwota{newline}[REGON],100{newline}"


@pytest.mark.parametrize(
    "card",
    [
        "4111 1111 1111 1111",
        "4111-1111-1111-1111",
        "4111 1111 1111 1112",
        "4111-1111-1111-1112",
    ],
)
def test_uc222_grouped_comma_card_keeps_exact_span(card: str) -> None:
    text = f"100,{card},200"
    spans = find(text)
    assert len(spans) == 1
    assert (spans[0].start, spans[0].end, spans[0].status) == (
        4,
        4 + len(card),
        "suspect",
    )
    assert text[spans[0].start : spans[0].end] == card
    assert piitier.mask(text) == "100,[NR_KARTY],200"


@pytest.mark.parametrize(
    "text",
    [
        "0.9937050359712231",
        "0.8888888888888888",
        '"f1": 0.28571428571428575,',
        "4111111111111111.25",
        "-0.4111111111111112",
    ],
)
def test_uc223_dot_decimal_fragments_stay_undetected(text: str) -> None:
    assert find(text) == []
    assert piitier.mask(text) == text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("4111111111111111.", "[NR_KARTY]."),
        ("100.4111 1111 1111 1111.25", "100.[NR_KARTY].25"),
        ("100.4111-1111-1111-1111.25", "100.[NR_KARTY].25"),
    ],
)
def test_uc223_nondecimal_card_punctuation_is_not_suppressed(text: str, expected: str) -> None:
    assert len(find(text)) == 1
    assert piitier.mask(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "cc4111111111111111ff",
        "abc4111111111111111",
        "4111111111111111ff",
        "AB4111111111111111EF",
        "0xabc4111111111111111ff",
    ],
)
def test_uc224_hex_tokens_stay_undetected(text: str) -> None:
    assert find(text) == []
    assert not any(span.label is Label.NR_KARTY for span in piitier.detect(text))


@pytest.mark.parametrize("card", [AMEX_VALID, DINERS_VALID])
@pytest.mark.parametrize(("prefix", "suffix"), [("100,", ",200"), ("karta", " wydana")])
def test_uc225_other_supported_lengths_keep_context_recall(
    card: str, prefix: str, suffix: str
) -> None:
    text = prefix + card + suffix
    spans = find(text)
    assert len(spans) == 1
    assert (spans[0].start, spans[0].end, spans[0].status) == (
        len(prefix),
        len(prefix) + len(card),
        "suspect",
    )


@pytest.mark.parametrize(
    ("card", "prefix", "suffix", "expected"),
    [
        (AMEX_VALID, "100,", ",200", "100,[NR_KARTY],200"),
        (AMEX_VALID, "karta", " wydana", "karta[NR_KARTY] wydana"),
        (DINERS_VALID, "100,", ",200", "100,[REGON],200"),
        (DINERS_VALID, "karta", " wydana", "karta[REGON] wydana"),
    ],
)
def test_uc225_other_supported_lengths_mask_with_fusion(
    card: str, prefix: str, suffix: str, expected: str
) -> None:
    assert piitier.mask(prefix + card + suffix) == expected
