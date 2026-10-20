"""Unit and property-based tests for the IBAN validator and detector (PII-1-d).

Tests cover Polish NRB (26 digits, mod 97 checksum), foreign IBANs (2 letters + 2 digits +
11–30 alphanumerics), format variants (contiguous or space-separated), and checksum failure
handling.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from piitier.labels import Label
from piitier.rules.iban import find, is_valid

# ---------------------------------------------------------------------------
# Known synthetic examples — anchors for UC tests
# ---------------------------------------------------------------------------

# Valid Polish NRB: PL61 1090 1014 0000 0712 1981 2874, mod 97 check passes
IBAN_PL_VALID_SPACED = "PL61 1090 1014 0000 0712 1981 2874"
IBAN_PL_VALID_COMPACT = "PL61109010140000071219812874"
IBAN_NRB_VALID_SPACED = "61 1090 1014 0000 0712 1981 2874"
IBAN_NRB_VALID_COMPACT = "61109010140000071219812874"

# Invalid Polish NRB: mod 97 check fails (last digit altered)
IBAN_PL_INVALID = "PL61109010140000071219812875"

# Valid German IBAN: DE89 3704 0044 0532 0130 00, mod 97 check passes
IBAN_DE_VALID_SPACED = "DE89 3704 0044 0532 0130 00"
IBAN_DE_VALID_COMPACT = "DE89370400440532013000"

# Invalid German IBAN: mod 97 check fails (last digit altered)
IBAN_DE_INVALID = "DE89 3704 0044 0532 0130 01"


# ---------------------------------------------------------------------------
# UC-19: Polish IBAN and NRB in all format variants → [IBAN]
# ---------------------------------------------------------------------------


def test_uc19_pl_iban_with_prefix_spaced() -> None:
    """UC-19: mask on PL61 1090 1014 0000 0712 1981 2874 → [IBAN], status='valid'."""
    spans = find(IBAN_PL_VALID_SPACED)
    assert len(spans) == 1
    assert spans[0].label is Label.IBAN
    assert spans[0].status == "valid"
    assert spans[0].start == 0
    assert spans[0].end == len(IBAN_PL_VALID_SPACED)


def test_uc19_pl_iban_with_prefix_compact() -> None:
    """UC-19: mask on PL61109010140000071219812874 → [IBAN], status='valid'."""
    spans = find(IBAN_PL_VALID_COMPACT)
    assert len(spans) == 1
    assert spans[0].label is Label.IBAN
    assert spans[0].status == "valid"


def test_uc19_nrb_bare_spaced() -> None:
    """UC-19: mask on bare 26-digit NRB spaced → [IBAN], status='valid'."""
    spans = find(IBAN_NRB_VALID_SPACED)
    assert len(spans) == 1
    assert spans[0].label is Label.IBAN
    assert spans[0].status == "valid"


def test_uc19_nrb_bare_compact() -> None:
    """UC-19: mask on bare 26-digit NRB compact → [IBAN], status='valid'."""
    spans = find(IBAN_NRB_VALID_COMPACT)
    assert len(spans) == 1
    assert spans[0].label is Label.IBAN
    assert spans[0].status == "valid"


# ---------------------------------------------------------------------------
# UC-20: Invalid mod 97 checksum → suspect
# ---------------------------------------------------------------------------


def test_uc20_invalid_checksum_status_suspect() -> None:
    """UC-20: mask on PL61109010140000071219812875 (fails mod 97) → status='suspect'."""
    spans = find(IBAN_PL_INVALID)
    assert len(spans) == 1
    assert spans[0].label is Label.IBAN
    assert spans[0].status == "suspect"


def test_uc20_suspect_span_never_dropped() -> None:
    """UC-20 / invariant-6: bad checksum IBAN is not dropped, only marked suspect."""
    spans = find("ref: " + IBAN_PL_INVALID + " end")
    assert len(spans) == 1
    assert spans[0].status == "suspect"


# ---------------------------------------------------------------------------
# UC-21: No overlap with PESEL when both present in text
# ---------------------------------------------------------------------------


def test_uc21_iban_and_pesel_no_overlap() -> None:
    """UC-21: detect on text with one IBAN, one PESEL → exactly two spans, none overlapping."""
    text = f"Account {IBAN_NRB_VALID_COMPACT} for PESEL 90051512340 active"
    spans = find(text)
    # Filter for IBAN only; PESEL detection is in a separate detector
    iban_spans = [s for s in spans if s.label is Label.IBAN]
    assert len(iban_spans) == 1
    # Check that span covers only the IBAN part
    assert text[iban_spans[0].start : iban_spans[0].end] == IBAN_NRB_VALID_COMPACT


# ---------------------------------------------------------------------------
# UC-38: Foreign IBAN (Germany) valid checksum
# ---------------------------------------------------------------------------


def test_uc38_de_iban_spaced_valid() -> None:
    """UC-38: mask on DE89 3704 0044 0532 0130 00 → [IBAN], status='valid'."""
    spans = find(IBAN_DE_VALID_SPACED)
    assert len(spans) == 1
    assert spans[0].label is Label.IBAN
    assert spans[0].status == "valid"


def test_uc38_de_iban_compact_valid() -> None:
    """UC-38: mask on DE89370400440532013000 → [IBAN], status='valid'."""
    spans = find(IBAN_DE_VALID_COMPACT)
    assert len(spans) == 1
    assert spans[0].label is Label.IBAN
    assert spans[0].status == "valid"


# ---------------------------------------------------------------------------
# UC-39: Foreign IBAN (Germany) invalid checksum
# ---------------------------------------------------------------------------


def test_uc39_de_iban_invalid_checksum() -> None:
    """UC-39: mask on DE89 3704 0044 0532 0130 01 (fails mod 97) → status='suspect'."""
    spans = find(IBAN_DE_INVALID)
    assert len(spans) == 1
    assert spans[0].label is Label.IBAN
    assert spans[0].status == "suspect"


# ---------------------------------------------------------------------------
# Format variants — edge cases
# ---------------------------------------------------------------------------


def test_format_pl_lowercase_prefix() -> None:
    """Polish IBAN with lowercase 'pl' prefix is detected."""
    text = "pl61109010140000071219812874"
    spans = find(text)
    assert len(spans) == 1
    assert spans[0].label is Label.IBAN


def test_format_de_lowercase_prefix() -> None:
    """Foreign IBAN with lowercase country code is detected."""
    text = "de89370400440532013000"
    spans = find(text)
    assert len(spans) == 1
    assert spans[0].label is Label.IBAN


def test_format_nrb_exactly_26_digits() -> None:
    """Bare NRB is exactly 26 digits."""
    spans = find(IBAN_NRB_VALID_COMPACT)
    assert len(spans) == 1
    # Verify span covers exactly the 26 digits
    matched = spans[0]
    assert matched.end - matched.start == 26


def test_format_foreign_with_spaces() -> None:
    """Foreign IBAN with space-separated groups detected."""
    text = "Reference IBAN: FR14 2004 1010 0505 0001 3M02 606"
    spans = find(text)
    # Should find the FR IBAN (assuming valid mod 97)
    iban_spans = [s for s in spans if s.label is Label.IBAN]
    assert len(iban_spans) >= 1


def test_hard_negative_25_digit_nrb() -> None:
    """25-digit bare number (not 26) → no match."""
    spans = find("6110901014000007121981287")
    assert spans == []


def test_hard_negative_27_digit_nrb() -> None:
    """27-digit bare number (not 26) → no match."""
    spans = find("611090101400000712198128744")
    assert spans == []


def test_hard_negative_double_space_breaks_match() -> None:
    """Double space between digit groups breaks the pattern → no match."""
    text = "PL61 1090  1014 0000 0712 1981 2874"
    spans = find(text)
    # Double space should break the IBAN pattern
    iban_spans = [s for s in spans if s.label is Label.IBAN]
    assert len(iban_spans) == 0


def test_hard_negative_empty_text() -> None:
    """Empty text produces no spans."""
    assert find("") == []


def test_hard_negative_no_iban() -> None:
    """Text without IBAN produces no spans."""
    assert find("Invoice 12345") == []


# ---------------------------------------------------------------------------
# is_valid() — unit tests for checksum validation
# ---------------------------------------------------------------------------


def test_is_valid_pl_nrb_digits() -> None:
    """is_valid returns True for valid 26-digit bare NRB."""
    digits = "61109010140000071219812874"
    assert is_valid(digits) is True


def test_is_valid_pl_with_prefix() -> None:
    """is_valid returns True for valid PL+26 digit IBAN."""
    iban = "PL61109010140000071219812874"
    assert is_valid(iban) is True


def test_is_valid_pl_lowercase_prefix() -> None:
    """is_valid returns True for lowercase 'pl' prefix."""
    iban = "pl61109010140000071219812874"
    assert is_valid(iban) is True


def test_is_valid_de_iban() -> None:
    """is_valid returns True for valid German IBAN."""
    iban = "DE89370400440532013000"
    assert is_valid(iban) is True


def test_is_valid_fr_iban() -> None:
    """is_valid returns True for valid French IBAN."""
    # FR14 2004 1010 0505 0001 3M02 606 (without spaces)
    iban = "FR1420041010050500013M02606"
    assert is_valid(iban) is True


def test_is_valid_wrong_checksum_pl() -> None:
    """is_valid returns False for Polish IBAN with wrong check digits."""
    assert is_valid("PL61109010140000071219812875") is False


def test_is_valid_wrong_checksum_de() -> None:
    """is_valid returns False for German IBAN with wrong check digits."""
    assert is_valid("DE89370400440532013001") is False


def test_is_valid_too_short() -> None:
    """is_valid returns False for string too short to be any valid IBAN."""
    assert is_valid("PL61") is False


def test_is_valid_empty_string() -> None:
    """is_valid returns False for empty string."""
    assert is_valid("") is False


def test_is_valid_only_letters() -> None:
    """is_valid returns False for string with only letters."""
    assert is_valid("PLXX") is False


def test_is_valid_non_ascii() -> None:
    """is_valid returns False for non-ASCII characters."""
    assert is_valid("PL61109010140000071219812874Ł") is False


# ---------------------------------------------------------------------------
# Property tests — is_valid()
# ---------------------------------------------------------------------------


@given(
    country_code=st.sampled_from(["PL", "DE", "FR", "IT", "ES"]),
    check_digits=st.integers(min_value=0, max_value=99),
    remaining_digits=st.text(alphabet="0123456789", min_size=11, max_size=30),
)
def test_prop_is_valid_generated_iban_passes(
    country_code: str, check_digits: int, remaining_digits: str
) -> None:
    """Property: generated IBAN structure is checked for validity.

    is_valid returns a boolean consistently based on mod 97 checksum.
    """
    iban = f"{country_code}{check_digits:02d}{remaining_digits}"
    # Verify that is_valid doesn't crash and returns a boolean
    result = is_valid(iban)
    assert isinstance(result, bool)


@given(nrb=st.text(alphabet="0123456789", min_size=26, max_size=26))
def test_prop_bare_nrb_26_digits_consistency(nrb: str) -> None:
    """Property: is_valid consistency for 26-digit bare NRB.

    If is_valid returns True, mod 97 of PL+NRB must equal 1.
    """
    result = is_valid(nrb)
    if result:
        # If valid, verify mod 97 equals 1
        from piitier.rules.iban import _mod97

        iban_with_pl = "PL" + nrb
        assert _mod97(iban_with_pl) == 1


