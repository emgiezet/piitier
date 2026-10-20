"""Unit and integration tests for the REGON validator and detector (PII-1-c).

All REGON numbers are synthetic, computed for this spec.
Real numbers are never used.

Acceptance criteria covered:
  UC-16, UC-17, UC-18.
"""

from __future__ import annotations

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
    return str(total % 11)


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
