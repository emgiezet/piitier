"""Unit and property-based tests for the IBAN validator and detector (PII-1-d).

Tests cover Polish NRB (26 digits, mod 97 checksum), foreign IBANs (2 letters + 2 digits +
11–30 alphanumerics), format variants (contiguous or space-separated), and checksum failure
handling.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

import piitier
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
    assert spans[0].start == 0
    assert spans[0].end == len(IBAN_PL_VALID_COMPACT)


def test_uc19_nrb_bare_spaced() -> None:
    """UC-19: mask on bare 26-digit NRB spaced → [IBAN], status='valid'."""
    spans = find(IBAN_NRB_VALID_SPACED)
    assert len(spans) == 1
    assert spans[0].label is Label.IBAN
    assert spans[0].status == "valid"
    assert spans[0].start == 0
    assert spans[0].end == len(IBAN_NRB_VALID_SPACED)


def test_uc19_nrb_bare_compact() -> None:
    """UC-19: mask on bare 26-digit NRB compact → [IBAN], status='valid'."""
    spans = find(IBAN_NRB_VALID_COMPACT)
    assert len(spans) == 1
    assert spans[0].label is Label.IBAN
    assert spans[0].status == "valid"
    assert spans[0].start == 0
    assert spans[0].end == len(IBAN_NRB_VALID_COMPACT)


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
    """UC-21: 1 spaced IBAN + 1 contiguous IBAN + 1 PESEL → 3 non-overlapping spans."""
    # Use PESEL that doesn't overlap with IBANs
    pesel = "12345678901"
    text = f"Invoice: {IBAN_PL_VALID_SPACED} or {IBAN_NRB_VALID_COMPACT} person {pesel}"
    spans = piitier.detect(text)
    # Filter to just IBAN and PESEL spans
    iban_spans = [s for s in spans if s.label is Label.IBAN]
    pesel_spans = [s for s in spans if s.label is Label.PESEL]
    assert len(iban_spans) == 2, f"Expected 2 IBANs, got {len(iban_spans)}"
    assert len(pesel_spans) == 1, f"Expected 1 PESEL, got {len(pesel_spans)}"
    # Verify sorted by start
    all_spans = iban_spans + pesel_spans
    assert all_spans == sorted(all_spans, key=lambda s: s.start)
    # Verify no PESEL overlaps with any IBAN
    pesel_span = pesel_spans[0]
    for iban_span in iban_spans:
        assert not (iban_span.start <= pesel_span.start < iban_span.end), "PESEL starts inside IBAN"
        assert not (iban_span.start < pesel_span.end <= iban_span.end), "PESEL ends inside IBAN"


# ---------------------------------------------------------------------------
# UC-21: Regression — no PESEL inside IBAN (overlapping span suppression)
# ---------------------------------------------------------------------------


def test_uc21_regression_pesel_inside_suspect_iban_suppressed() -> None:
    """UC-21 regression (suspect): PESEL inside suspect IBAN is suppressed.

    'AA01010100005AA': foreign IBAN [0,15) status=suspect AND PESEL at [2,13).
    Before the fix detect_all returned both, breaking mask() fidelity.
    """
    spans = piitier.detect("AA01010100005AA")
    assert len(spans) == 1, f"Expected 1 span, got {len(spans)}: {spans}"
    assert spans[0].label is Label.IBAN
    assert spans[0].status == "suspect"
    assert spans[0].start == 0
    assert spans[0].end == 15


def test_uc21_regression_pesel_inside_valid_iban_suppressed() -> None:
    """UC-21 regression (valid): PESEL inside valid IBAN is suppressed.

    'AI01010100005AA': foreign IBAN [0,15) status=valid (mod97=1) AND PESEL at [2,13).
    Suppression must apply to valid IBAN containers, not only suspect ones.
    """
    spans = piitier.detect("AI01010100005AA")
    assert len(spans) == 1, f"Expected 1 span, got {len(spans)}: {spans}"
    assert spans[0].label is Label.IBAN
    assert spans[0].status == "valid"
    assert spans[0].start == 0
    assert spans[0].end == 15


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


def _iban_check_digits(country: str, bban: str) -> str:
    """Independently compute IBAN check digits for *country* + *bban*.

    Algorithm (test-local; does NOT call production _mod97):
      1. Build BBAN + CC_numeric + "00" as a decimal string.
      2. check = (98 - int(rearranged) % 97) % 97, zero-padded to 2 digits.

    Letters map A=10 … Z=35 via ord arithmetic.
    """
    cc_num = "".join(
        str(ord(c.upper()) - ord("A") + 10) if c.isalpha() else c for c in country.upper()
    )
    n = int(bban + cc_num + "00") % 97
    return f"{(98 - n) % 97:02d}"


@given(bban=st.text(alphabet="0123456789", min_size=24, max_size=24))
def test_prop_generated_valid_nrb_detected_as_valid(bban: str) -> None:
    """Property: PL NRB with independently computed check digits → status='valid', mask='[IBAN]'.

    The check-digit helper is a self-contained test fixture that does not
    re-invoke any production function to verify its own output.
    """
    check = _iban_check_digits("PL", bban)
    iban = f"PL{check}{bban}"
    spans = find(iban)
    assert len(spans) == 1, f"Expected 1 span for {iban!r}"
    assert spans[0].status == "valid", f"Expected valid, got {spans[0].status!r}"
    assert spans[0].start == 0
    assert spans[0].end == len(iban)
    assert piitier.mask(iban) == "[IBAN]"


@given(bban=st.text(alphabet="0123456789", min_size=24, max_size=24))
def test_prop_mutated_check_digit_yields_suspect(bban: str) -> None:
    """Property: PL NRB with a single wrong check digit → span status='suspect'.

    wrong_check = (correct + 1) % 100 is always different from the correct
    value (which is 0–96) so the mutated IBAN always fails mod 97.
    """
    check = _iban_check_digits("PL", bban)
    wrong_check = f"{(int(check) + 1) % 100:02d}"
    iban = f"PL{wrong_check}{bban}"
    spans = find(iban)
    assert len(spans) == 1, f"Expected 1 span for {iban!r}"
    assert spans[0].status == "suspect"


# ---------------------------------------------------------------------------
# Regression — contiguous foreign IBAN must not swallow adjacent prose
# ---------------------------------------------------------------------------


def test_regression_contiguous_be68_stops_before_prose() -> None:
    """Regression: 'BE68539007547034 EUR' → span covers only the IBAN; status='valid'.

    Previously the mixed-separator regex grabbed ' EUR' as an optional final group,
    corrupting the checksum and producing status='suspect' on a valid IBAN.
    """
    text = "BE68539007547034 EUR"
    spans = find(text)
    assert len(spans) == 1, f"Expected 1 span, got {spans}"
    matched = text[spans[0].start : spans[0].end]
    assert matched == "BE68539007547034", f"Span swallowed prose: {matched!r}"
    assert spans[0].status == "valid"
    # Integration: detect_all must suppress the REGON span contained inside IBAN[0,16).
    detected = piitier.detect(text)
    assert len(detected) == 1, f"detect_all must yield exactly one span, got {detected}"
    assert detected[0].label is Label.IBAN
    assert detected[0].start == 0
    assert detected[0].end == 16
    assert piitier.mask(text) == "[IBAN] EUR"


def test_regression_contiguous_be69_suspect_suppresses_contained_regon() -> None:
    """Suspect outer IBAN still suppresses non-IBAN spans wholly contained inside it.

    BE69539007547034 fails mod 97, so it is marked 'suspect'.  The REGON detector
    matches the digit body within the IBAN; that contained span must be suppressed
    (UC-21 / integration fix).  Validity is irrelevant for containment suppression.
    """
    text = "BE69539007547034 EUR"
    spans = find(text)
    assert len(spans) == 1, f"Expected 1 IBAN span, got {spans}"
    assert spans[0].start == 0
    assert spans[0].end == 16
    assert spans[0].status == "suspect"
    detected = piitier.detect(text)
    assert len(detected) == 1, f"detect_all must yield exactly one span, got {detected}"
    assert detected[0].label is Label.IBAN
    assert detected[0].start == 0
    assert detected[0].end == 16
    assert piitier.mask(text) == "[IBAN] EUR"


def test_regression_contiguous_at61_stops_before_prose() -> None:
    """Regression: 'AT611904300234573201 payment received' → span covers only the IBAN.

    Previously 'paym' was swallowed as a space-optional group and 'ent' as the
    final partial group, producing status='suspect' on a valid IBAN.
    """
    text = "AT611904300234573201 payment received"
    spans = find(text)
    assert len(spans) == 1, f"Expected 1 span, got {spans}"
    matched = text[spans[0].start : spans[0].end]
    assert matched == "AT611904300234573201", f"Span swallowed prose: {matched!r}"
    assert spans[0].status == "valid"
    assert piitier.mask(text) == "[IBAN] payment received"


# ---------------------------------------------------------------------------
# Boundary — overlong contiguous token must not partially match
# ---------------------------------------------------------------------------


def test_hard_negative_overlong_contiguous_foreign_iban() -> None:
    """A contiguous 35-char foreign-IBAN-like token (> 34 clean chars) → no match.

    The compact pattern enforces [A-Z0-9]{11,30} after CC+NN; combined with the
    (?![A-Z0-9]) lookahead, a 35-char token forces all suffix widths to fail.
    """
    token = "DE89" + "A" * 31  # 4 + 31 = 35 chars, exceeds the 34-char maximum
    assert find(token) == []
