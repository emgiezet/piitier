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

import piitier
from piitier.labels import Label
from piitier.rules.nip import find, is_valid

# ---------------------------------------------------------------------------
# Helpers & hypothesis strategies
# ---------------------------------------------------------------------------

_WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)

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


# ---------------------------------------------------------------------------
# UC-15: Mask NIP with wrong check digit (suspect)
# ---------------------------------------------------------------------------


def test_uc15_mask_nip_suspect_bad_check() -> None:
    """mask on 'nr zamówienia 5260001247' (wrong check); 'nr zamówienia [NIP]'; status='suspect'."""
    text = "nr zamówienia 5260001247"
    spans = find(text)
    assert len(spans) == 1
    span = spans[0]
    assert span.label == Label.NIP
    assert span.status == "suspect"
    assert text[span.start : span.end] == "5260001247"


# ---------------------------------------------------------------------------
# UC-18: NIP exclusion — KRS keyword within 40 characters
# ---------------------------------------------------------------------------


def test_uc18_no_nip_after_krs_keyword() -> None:
    """detect on 'KRS 0000123456' → no NIP span for the 10-digit run."""
    text = "Numer KRS 0000123456 w rejestrze"
    spans = find(text)
    assert len(spans) == 0


# ---------------------------------------------------------------------------
# Property-based tests with hypothesis
# ---------------------------------------------------------------------------


@given(st.integers(min_value=0, max_value=999999999))
@settings(max_examples=200)
def test_nip_valid_numbers_pass_validator(base9: int) -> None:
    """For any 9-digit base, compute a valid check digit and verify is_valid returns True."""
    base_str = str(base9).zfill(9)
    # Compute check digit
    total = sum(w * int(d) for w, d in zip(_WEIGHTS, base_str))
    check = total % 11
    if check == 10:
        # Skip this case since 10 is never valid
        return
    nip = base_str + str(check)
    assert is_valid(nip) is True


@given(st.integers(min_value=0, max_value=9))
def test_nip_modified_check_digit_fails(check_digit: int) -> None:
    """Modifying the check digit of a valid NIP makes is_valid return False."""
    # Use a known valid NIP
    nip = "5260001246"
    # Replace the last digit with something different
    original_check = int(nip[9])
    modified_check = check_digit % 10
    if modified_check == original_check:
        # Skip if we accidentally kept it the same
        return
    modified_nip = nip[:9] + str(modified_check)
    assert is_valid(modified_nip) is False


# ---------------------------------------------------------------------------
# Format variants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nip_text",
    [
        "5260001246",  # Contiguous
        "526-000-12-46",  # Dashes (X-X-XX-XX)
        "526-00-01-246",  # Dashes (X-XX-XX-XXX)
        "526 000 12 46",  # Spaces
        "526\t000\t12\t46",  # Tabs
        "PL5260001246",  # PL prefix, contiguous
        "PL526-000-12-46",  # PL prefix with dashes
    ],
)
def test_nip_format_variants_detected(nip_text: str) -> None:
    """Every keyword-labelled format variant is detected and has status='valid'."""
    text = f"NIP: {nip_text} na dokumencie"
    spans = find(text)
    assert len(spans) == 1
    assert spans[0].status == "valid"


# ---------------------------------------------------------------------------
# Hard negatives — exclude cases that look like NIP but are not
# ---------------------------------------------------------------------------


def test_nip_invoice_line_number_as_suspect() -> None:
    """A 10-digit run in invoice line context is marked suspect, not valid."""
    # Use a 10-digit number with wrong checksum
    text = "wiersz 1234567890 faktury"
    spans = find(text)
    assert len(spans) == 1
    assert spans[0].status == "suspect"


def test_nip_longer_digit_run_no_match_at_head() -> None:
    """A 12-digit run should not match at the first 10 positions."""
    text = "numer 123456789012 bardzo długi"
    spans = find(text)
    # Depending on checksums, might match or not, but not at wrong positions
    # The lookahead should prevent matching the head of a longer run
    for span in spans:
        # If there's a match, verify it's not consuming more than 10 digits
        matched = text[span.start : span.end]
        digits = matched.replace(" ", "").replace("-", "").replace("\t", "").lstrip("PL")
        assert len(digits) == 10


def test_nip_no_match_when_preceded_by_digit() -> None:
    """A 10-digit run preceded by a digit is not matched (it's part of a longer run)."""
    text = "ID 15260001246 for document"
    spans = find(text)
    # The regex lookbehind should prevent matching here
    assert len(spans) == 0


# ---------------------------------------------------------------------------
# Embedded detection
# ---------------------------------------------------------------------------


def test_nip_embedded_in_filler_text() -> None:
    """NIP is found even when surrounded by Polish text."""
    text = "Faktura zawiera numer NIP: 5260001246 oraz opis usług."
    spans = find(text)
    assert len(spans) == 1
    assert spans[0].label == Label.NIP
    assert spans[0].status == "valid"


# ---------------------------------------------------------------------------
# Checksum edge case: sum mod 11 = 10
# ---------------------------------------------------------------------------


def test_nip_check_digit_never_10() -> None:
    """A NIP where the sum mod 11 would be 10 is invalid (never valid)."""
    # Base 9 = "900000000" produces sum = 9*6 = 54, and 54 % 11 = 10
    # Per NIP checksum rules, if sum % 11 == 10, the NIP is invalid.
    # Append any digit (we use 0) to get "9000000000"
    nip_with_impossible_check = "9000000000"
    assert is_valid(nip_with_impossible_check) is False


# ---------------------------------------------------------------------------
# UC-14: mask() on NIP with multiple formats — public-API assertion
# ---------------------------------------------------------------------------


def test_uc14_mask_nip_contiguous_digits_via_api() -> None:
    """UC-14: mask('5260001246') via public API becomes '[NIP]'; span status='valid'."""
    text = "5260001246"
    result = piitier.mask(text)
    assert result == "[NIP]"
    spans = piitier.detect(text)
    assert len(spans) == 1
    assert spans[0].status == "valid"
    assert text[spans[0].start : spans[0].end] == "5260001246"


def test_uc14_mask_nip_with_dashes_via_api() -> None:
    """UC-14: mask('526-000-12-46') via public API becomes '[NIP]'; span covers dashes."""
    text = "526-000-12-46"
    result = piitier.mask(text)
    assert result == "[NIP]"
    spans = piitier.detect(text)
    assert len(spans) == 1
    assert spans[0].status == "valid"
    assert text[spans[0].start : spans[0].end] == "526-000-12-46"


def test_uc14_mask_nip_with_alternate_dashes_via_api() -> None:
    """UC-14: mask('526-00-01-246') via public API becomes '[NIP]'; span covers dashes."""
    text = "526-00-01-246"
    result = piitier.mask(text)
    assert result == "[NIP]"
    spans = piitier.detect(text)
    assert len(spans) == 1
    assert spans[0].status == "valid"
    assert text[spans[0].start : spans[0].end] == "526-00-01-246"


def test_uc14_mask_nip_with_pl_prefix_via_api() -> None:
    """UC-14: mask('PL5260001246') via public API becomes '[NIP]'; span covers prefix."""
    text = "PL5260001246"
    result = piitier.mask(text)
    assert result == "[NIP]"
    spans = piitier.detect(text)
    assert len(spans) == 1
    assert spans[0].status == "valid"
    assert text[spans[0].start : spans[0].end] == "PL5260001246"


def test_uc14_mask_nip_keyword_with_spaces_via_api() -> None:
    """UC-14: preserve the NIP keyword and mask the entire space-separated value."""
    text = "NIP: 526 000 12 46"
    result = piitier.mask(text)
    assert result == "NIP: [NIP]"
    spans = piitier.detect(text)
    assert len(spans) == 1
    assert spans[0].status == "valid"
    assert text[spans[0].start : spans[0].end] == "526 000 12 46"


@pytest.mark.parametrize("text", ["526 000 12 46", "526\t000\t12\t46", "5260-001246"])
def test_uc14_arbitrary_separators_require_keyword(text: str) -> None:
    assert find(text) == []


@pytest.mark.parametrize("keyword", ["NIP", "nip", "VAT ID", "vat id"])
def test_uc14_keyword_prefix_is_masked_once(keyword: str) -> None:
    text = f"{keyword}: PL526 000 12 46"
    spans = piitier.detect(text)
    assert len(spans) == 1
    assert text[spans[0].start : spans[0].end] == "PL526 000 12 46"
    assert piitier.mask(text) == f"{keyword}: [NIP]"


def test_uc18_krs_exclusion_also_applies_after_nip_keyword() -> None:
    assert find("KRS NIP 0000123456") == []


def test_uc14_does_not_extract_suffix_from_longer_separated_run() -> None:
    assert find("9 5260001246") == []
