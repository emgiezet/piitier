"""Unit and integration tests for the NIP validator and detector (PII-1-c).

All NIP numbers are synthetic, computed for this spec.
Real numbers are never used.

Acceptance criteria covered:
  UC-14, UC-15, UC-18.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from piitier.labels import Label
from piitier.rules.nip import find, is_valid


# ---------------------------------------------------------------------------
# Helpers & hypothesis strategies
# ---------------------------------------------------------------------------

_WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)


def _compute_check_digit(base9: str) -> str:
    """Compute the NIP check digit for a 9-digit base string."""
    total = sum(w * int(d) for w, d in zip(_WEIGHTS, base9))
    check = total % 11
    # A result of 10 is never valid — the NIP is rejected
    if check == 10:
        # This should not happen with valid weights/input, but return '0' as fallback
        return "0"
    return str(check)


def _make_nip(base9: str) -> str:
    """Construct a synthetic valid NIP string (10 digits)."""
    return base9 + _compute_check_digit(base9)


# ---------------------------------------------------------------------------
# Known synthetic examples — anchors for UC tests
# ---------------------------------------------------------------------------

# Example from spec UC-14: 526000124 + check digit 6 = 5260001246
NIP_VALID_1 = "5260001246"
# Example from spec UC-15: 526000124 + wrong digit 7 = 5260001247 (bad check)
NIP_BAD_CHECK = "5260001247"


# ---------------------------------------------------------------------------
# UC-14: Mask NIP with multiple formats
# ---------------------------------------------------------------------------


def test_uc14_mask_nip_contiguous_digits() -> None:
    """mask on 5260001246 becomes [NIP]; span status='valid'."""
    text = "nr faktury 5260001246 wystawiona"
    spans = find(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.label == Label.NIP
    assert span.status == "valid"
    assert text[span.start : span.end] == "5260001246"


def test_uc14_mask_nip_with_dashes() -> None:
    """mask on 526-000-12-46 becomes [NIP]; span covers dashes."""
    text = "nr faktury 526-000-12-46 wystawiona"
    spans = find(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.label == Label.NIP
    assert span.status == "valid"
    assert text[span.start : span.end] == "526-000-12-46"


def test_uc14_mask_nip_with_alternate_dashes() -> None:
    """mask on 526-00-01-246 becomes [NIP]; span covers dashes."""
    text = "numer VAT 526-00-01-246 na fakturze"
    spans = find(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.label == Label.NIP
    assert span.status == "valid"
    assert text[span.start : span.end] == "526-00-01-246"


def test_uc14_mask_nip_with_pl_prefix() -> None:
    """mask on PL5260001246 becomes [NIP]; span covers prefix."""
    text = "numer VAT: PL5260001246 na dokumencie"
    spans = find(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.label == Label.NIP
    assert span.status == "valid"
    assert text[span.start : span.end] == "PL5260001246"


def test_uc14_mask_nip_keyword_with_spaces() -> None:
    """mask on 'NIP: 526 000 12 46' becomes [NIP]; 'NIP: ' stays, span covers prefix/separators."""
    text = "dokument z NIP: 526 000 12 46 dla rachunkowości"
    spans = find(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.label == Label.NIP
    assert span.status == "valid"
    # The span should be just the number part, not the keyword
    assert text[span.start : span.end] == "526 000 12 46"
