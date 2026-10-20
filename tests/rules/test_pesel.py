"""Unit and property-based tests for the PESEL validator and detector (PII-1-b).

All PESEL numbers are synthetic, computed for this spec.
Real person numbers are never used.

Acceptance criteria covered:
  UC-10, UC-11, UC-12, UC-36, UC-37.
Property tests cover is_valid() and find() with hypothesis-generated values.
"""

from __future__ import annotations

import calendar

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from piitier.labels import Label
from piitier.rules.pesel import _checksum_ok, _decode_birth_date, _strip_separators, find, is_valid

# ---------------------------------------------------------------------------
# Helpers & hypothesis strategies
# ---------------------------------------------------------------------------

_WEIGHTS = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)


def _compute_check_digit(base10: str) -> str:
    """Compute the PESEL check digit for a 10-digit base string."""
    total = sum(w * int(d) for w, d in zip(_WEIGHTS, base10))
    return str((10 - total % 10) % 10)


def _make_pesel(
    century_base: int,
    month_offset: int,
    yy: int,
    month: int,
    day: int,
    serial: int,
) -> str:
    """Construct a synthetic valid PESEL string."""
    encoded_month = month + month_offset
    base = f"{yy:02d}{encoded_month:02d}{day:02d}{serial:04d}"
    return base + _compute_check_digit(base)


@st.composite
def valid_pesel_digits(draw: st.DrawFn) -> str:
    """Strategy: generate a syntactically and semantically valid PESEL (11 digits)."""
    century_base, month_offset = draw(
        st.sampled_from(
            [
                (1900, 0),
                (2000, 20),
                (2100, 40),
                (2200, 60),
                (1800, 80),
            ]
        )
    )
    # Exclude yy=0: PESELs with year-digits "00" start with "00" and are
    # dropped by the phone-prefix exclusion rule (spec § phone-number exclusion).
    yy = draw(st.integers(min_value=1, max_value=99))
    actual_year = century_base + yy
    month = draw(st.integers(min_value=1, max_value=12))
    _, max_day = calendar.monthrange(actual_year, month)
    day = draw(st.integers(min_value=1, max_value=max_day))
    serial = draw(st.integers(min_value=0, max_value=9999))
    return _make_pesel(century_base, month_offset, yy, month, day, serial)


# ---------------------------------------------------------------------------
# Known synthetic examples — anchors for UC tests
# ---------------------------------------------------------------------------

# 1990-05-15, 1900s encoding, checksum 0
PESEL_VALID_1 = "90051512340"
# 2005-05-01, 2000s encoding (+20), checksum 3
PESEL_2005_MAY = "05250112343"
# Same base as PESEL_VALID_1 but check digit replaced with 1 → wrong
PESEL_BAD_CHECK = "90051512341"
# Month=13 (invalid encoding), checksum correct = 1
PESEL_BAD_MONTH = "90131512341"
# 1800s: 1889-12-15
PESEL_1800S = "89921500015"
# 2100s: 2100-06-15
PESEL_2100S = "00461500019"


# ---------------------------------------------------------------------------
# is_valid() — happy path and rejection
# ---------------------------------------------------------------------------


def test_is_valid_happy_path_1900s() -> None:
    """is_valid returns True for a well-formed 1900s PESEL."""
    assert is_valid(PESEL_VALID_1) is True


def test_is_valid_happy_path_2000s() -> None:
    """is_valid returns True for a well-formed 2000s PESEL (UC-11 related)."""
    assert is_valid(PESEL_2005_MAY) is True


def test_is_valid_happy_path_1800s() -> None:
    """is_valid returns True for a well-formed 1800s PESEL."""
    assert is_valid(PESEL_1800S) is True


def test_is_valid_happy_path_2100s() -> None:
    """is_valid returns True for a well-formed 2100s PESEL."""
    assert is_valid(PESEL_2100S) is True


def test_is_valid_wrong_check_digit() -> None:
    """is_valid returns False when the check digit is wrong."""
    assert is_valid(PESEL_BAD_CHECK) is False


def test_is_valid_invalid_month() -> None:
    """is_valid returns False when encoded month is not in any century range."""
    assert is_valid(PESEL_BAD_MONTH) is False


def test_is_valid_ten_digits() -> None:
    """is_valid rejects a 10-digit string."""
    assert is_valid(PESEL_VALID_1[:10]) is False


def test_is_valid_twelve_digits() -> None:
    """is_valid rejects a 12-digit string."""
    assert is_valid(PESEL_VALID_1 + "0") is False


def test_is_valid_empty_string() -> None:
    """is_valid rejects empty string."""
    assert is_valid("") is False


def test_is_valid_non_digits() -> None:
    """is_valid rejects strings that contain non-digit characters."""
    assert is_valid("9005151234X") is False


def test_is_valid_invalid_date_day_32() -> None:
    """is_valid rejects an otherwise-correct PESEL with day=32."""
    # month=01 (January), day=32 doesn't exist
    base = "90013200001"
    pesel = base[:10] + _compute_check_digit(base[:10])
    assert is_valid(pesel) is False


def test_is_valid_invalid_date_feb_30() -> None:
    """is_valid rejects February 30 which never exists."""
    # year=00 (1900), month=02, day=30
    base = "90023000001"
    pesel = base[:10] + _compute_check_digit(base[:10])
    assert is_valid(pesel) is False


# ---------------------------------------------------------------------------
# _checksum_ok() — unit
# ---------------------------------------------------------------------------


def test_checksum_ok_correct() -> None:
    """_checksum_ok returns True for a PESEL with correct check digit."""
    assert _checksum_ok(PESEL_VALID_1) is True


def test_checksum_ok_wrong() -> None:
    """_checksum_ok returns False for a PESEL with wrong check digit."""
    assert _checksum_ok(PESEL_BAD_CHECK) is False


def test_checksum_ok_bad_month_still_true() -> None:
    """_checksum_ok is True even when the month is invalid (checksum is independent)."""
    assert _checksum_ok(PESEL_BAD_MONTH) is True


# ---------------------------------------------------------------------------
# _decode_birth_date() — unit
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "digits, expected",
    [
        (PESEL_VALID_1, (1990, 5, 15)),  # 1900s
        (PESEL_2005_MAY, (2005, 5, 1)),  # 2000s (+20)
        (PESEL_1800S, (1889, 12, 15)),  # 1800s (+80)
        (PESEL_2100S, (2100, 6, 15)),  # 2100s (+40)
    ],
)
def test_decode_birth_date_valid(digits: str, expected: tuple[int, int, int]) -> None:
    """_decode_birth_date returns correct (year, month, day) for known PESELs."""
    assert _decode_birth_date(digits) == expected


def test_decode_birth_date_invalid_month_13() -> None:
    """_decode_birth_date returns None for encoded month 13 (not in any range)."""
    # PESEL_BAD_MONTH has encoded month 13
    assert _decode_birth_date(PESEL_BAD_MONTH) is None


def test_decode_birth_date_invalid_month_93() -> None:
    """_decode_birth_date returns None for encoded month 93 (> 92)."""
    base = "00930100001"
    assert _decode_birth_date(base) is None


# ---------------------------------------------------------------------------
# _strip_separators() — unit
# ---------------------------------------------------------------------------


def test_strip_separators_spaces() -> None:
    assert _strip_separators("900 515 123 40") == "90051512340"


def test_strip_separators_dashes() -> None:
    assert _strip_separators("9005-1512-340") == "90051512340"


def test_strip_separators_mixed() -> None:
    assert _strip_separators("9005 1512-340") == "90051512340"


def test_strip_separators_no_change() -> None:
    assert _strip_separators("90051512340") == "90051512340"


# ---------------------------------------------------------------------------
# UC-10: month-13 PESEL → suspect (checksum valid, date invalid)
# ---------------------------------------------------------------------------


def test_uc10_invalid_month_returns_suspect() -> None:
    """UC-10: detect on 90131512341 (checksum OK, month 13 invalid) → status='suspect'."""
    spans = find("90131512341")
    assert len(spans) == 1
    assert spans[0].status == "suspect"
    assert spans[0].label is Label.PESEL


def test_uc10_suspect_span_never_dropped() -> None:
    """UC-10 / invariant-6: bad date PESEL is not dropped, only marked suspect."""
    spans = find("ref: 90131512341 end")
    assert len(spans) == 1


# ---------------------------------------------------------------------------
# UC-11: 2000s century encoding → valid
# ---------------------------------------------------------------------------


def test_uc11_2000s_encoding_valid() -> None:
    """UC-11: detect on 05250112343 (born 2005-05-01, +20 encoding) → status='valid'."""
    spans = find("05250112343")
    assert len(spans) == 1
    span = spans[0]
    assert span.status == "valid"
    assert span.label is Label.PESEL


def test_uc11_span_offsets_correct() -> None:
    """UC-11: offsets are correct when PESEL is embedded in text."""
    text = "id: 05250112343 koniec"
    spans = find(text)
    assert len(spans) == 1
    assert text[spans[0].start : spans[0].end] == "05250112343"


# ---------------------------------------------------------------------------
# UC-12: length boundaries — 10 and 12 digit runs, letter-adjacent match
# ---------------------------------------------------------------------------


def test_uc12_ten_digit_run_no_match() -> None:
    """UC-12: 10-digit run produces no span."""
    spans = find("9005151234")
    assert spans == []


def test_uc12_twelve_digit_run_no_match() -> None:
    """UC-12: 12-digit run produces no span."""
    spans = find("900515123401")
    assert spans == []


def test_uc12_letter_adjacent_matches() -> None:
    """UC-12: letters do not block a match; x90051512340y yields one span."""
    text = "x90051512340y"
    spans = find(text)
    assert len(spans) == 1
    assert text[spans[0].start : spans[0].end] == "90051512340"


def test_uc12_digit_adjacent_blocks_match() -> None:
    """UC-12: a digit immediately after 11 digits blocks the match (12-digit run)."""
    # Appending a digit makes it a 12-digit run → no PESEL
    spans = find("1" + PESEL_VALID_1)
    assert spans == []


def test_uc12_digit_before_blocks_match() -> None:
    """UC-12: a digit immediately before 11 digits blocks the match."""
    spans = find(PESEL_VALID_1 + "1")
    assert spans == []


# ---------------------------------------------------------------------------
# UC-36: format variants with separators
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "900 515 123 40",
        "9005-1512-340",
        "90051 512340",
    ],
)
def test_uc36_separated_formats_matched(text: str) -> None:
    """UC-36: PESEL digits separated by spaces or dashes are detected."""
    spans = find(text)
    assert len(spans) == 1, f"expected 1 span for {text!r}, got {len(spans)}"


@pytest.mark.parametrize(
    "text",
    [
        "900 515 123 40",
        "9005-1512-340",
        "90051 512340",
    ],
)
def test_uc36_separated_formats_status_valid(text: str) -> None:
    """UC-36: separated-format PESELs resolve to the same valid number."""
    spans = find(text)
    assert len(spans) == 1
    assert spans[0].status == "valid"


@pytest.mark.parametrize(
    "text",
    [
        "900 515 123 40",
        "9005-1512-340",
        "90051 512340",
    ],
)
def test_uc36_span_covers_separators(text: str) -> None:
    """UC-36: the span's start/end cover the full matched region including separators."""
    spans = find(text)
    assert len(spans) == 1
    # The slice should include the separators
    assert text[spans[0].start : spans[0].end] == text.strip()


@pytest.mark.parametrize(
    "text",
    [
        "900 515 123 40",
        "9005-1512-340",
        "90051 512340",
    ],
)
def test_uc36_stripped_digits_equal_canonical(text: str) -> None:
    """UC-36: stripping separators from matched text recovers the canonical digits."""
    spans = find(text)
    assert len(spans) == 1
    matched = text[spans[0].start : spans[0].end]
    assert _strip_separators(matched) == PESEL_VALID_1


# ---------------------------------------------------------------------------
# UC-37: phone-prefix exclusion
# ---------------------------------------------------------------------------


def test_uc37_plus48_space_not_pesel() -> None:
    """UC-37: +48 501 234 567 must not produce a PESEL span."""
    spans = find("Telefon: +48 501 234 567")
    pesel_spans = [s for s in spans if s.label is Label.PESEL]
    assert pesel_spans == []


def test_uc37_plus48_compact_not_pesel() -> None:
    """UC-37: +48501234567 must not produce a PESEL span."""
    spans = find("tel. +48501234567")
    pesel_spans = [s for s in spans if s.label is Label.PESEL]
    assert pesel_spans == []


def test_uc37_00_prefix_not_pesel() -> None:
    """UC-37: a sequence whose raw digits start with 00 is excluded (phone prefix)."""
    # 0048501234567 — international dialing prefix 00 + country code 48
    spans = find("0048501234567")
    assert spans == []


def test_uc37_plain_number_without_plus_can_be_pesel() -> None:
    """UC-37: a PESEL without any phone prefix is still detected."""
    spans = find(PESEL_VALID_1)
    assert len(spans) == 1


def test_uc37_00_prefix_11digits_not_pesel() -> None:
    """UC-37: an 11-digit sequence starting with 00 is excluded by the phone rule.

    Regression: hypothesis shrunk to '00010100008' (year-digits 00, valid date
    1900-01-10, valid checksum) — excluded because raw digits start with '00'.
    """
    assert find("00010100008") == []


# ---------------------------------------------------------------------------
# Property tests — is_valid()
# ---------------------------------------------------------------------------


@given(pesel=valid_pesel_digits())
def test_prop_is_valid_generated_valid(pesel: str) -> None:
    """Property: every hypothesis-generated valid PESEL passes is_valid."""
    assert is_valid(pesel) is True


@given(pesel=valid_pesel_digits())
def test_prop_is_valid_altered_check_fails(pesel: str) -> None:
    """Property: altering the check digit of a valid PESEL makes is_valid return False."""
    original_check = int(pesel[10])
    # Replace with a different digit (wrap around)
    bad_check = str((original_check + 1) % 10)
    bad_pesel = pesel[:10] + bad_check
    assert is_valid(bad_pesel) is False


# ---------------------------------------------------------------------------
# Property tests — find()
# ---------------------------------------------------------------------------


@given(
    pesel=valid_pesel_digits(),
    prefix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", max_size=20),
    suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", max_size=20),
)
@settings(max_examples=120)
def test_prop_find_detects_embedded_valid_pesel(pesel: str, prefix: str, suffix: str) -> None:
    """Property: find() detects every valid PESEL embedded in letter/space filler text."""
    text = prefix + pesel + suffix
    spans = find(text)
    pesel_spans = [s for s in spans if s.label is Label.PESEL]
    assert len(pesel_spans) >= 1
    # The slice must reproduce the embedded PESEL
    found_texts = {text[s.start : s.end] for s in pesel_spans}
    assert pesel in found_texts


@given(
    pesel=valid_pesel_digits(),
    prefix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", max_size=20),
    suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", max_size=20),
)
@settings(max_examples=120)
def test_prop_find_slice_equals_embedded(pesel: str, prefix: str, suffix: str) -> None:
    """Property: text[span.start:span.end] equals the embedded PESEL for every found span."""
    text = prefix + pesel + suffix
    spans = find(text)
    for span in spans:
        assert text[span.start : span.end] is not None
        raw = text[span.start : span.end]
        assert _strip_separators(raw) == pesel


@given(pesel=valid_pesel_digits())
def test_prop_find_valid_pesel_status_valid(pesel: str) -> None:
    """Property: every generated valid PESEL produces a span with status='valid'."""
    spans = find(pesel)
    assert len(spans) == 1
    assert spans[0].status == "valid"


@given(pesel=valid_pesel_digits())
def test_prop_find_score_is_one(pesel: str) -> None:
    """Property: rule-based detector always assigns score=1.0."""
    spans = find(pesel)
    assert len(spans) == 1
    assert spans[0].score == 1.0


@given(pesel=valid_pesel_digits())
def test_prop_find_source_is_rule(pesel: str) -> None:
    """Property: rule-based detector source is 'rule'."""
    spans = find(pesel)
    assert len(spans) == 1
    assert spans[0].source == "rule"


@given(pesel=valid_pesel_digits())
def test_prop_altered_check_digit_returns_suspect(pesel: str) -> None:
    """Property: wrong check digit → find returns one span with status='suspect'."""
    original_check = int(pesel[10])
    bad_check = str((original_check + 1) % 10)
    bad_pesel = pesel[:10] + bad_check
    spans = find(bad_pesel)
    assert len(spans) == 1
    assert spans[0].status == "suspect"


# ---------------------------------------------------------------------------
# Hard negatives (density grid — error returns)
# ---------------------------------------------------------------------------


def test_hard_negative_ten_digits_no_match() -> None:
    """A 10-digit run never produces a PESEL span."""
    spans = find("1234567890")
    assert spans == []


def test_hard_negative_twelve_digits_no_match() -> None:
    """A 12-digit run never produces a PESEL span (too long)."""
    spans = find("123456789012")
    assert spans == []


def test_hard_negative_double_space_separator_no_match() -> None:
    """Two spaces between digits break the separator rule — no match."""
    # "9005  1512340" has a double space, which is not a valid separator
    spans = find("9005  1512340")
    # Should not match as a single PESEL (may match sub-sequences as suspect)
    if spans:
        # Confirm none spans the full "9005  1512340"
        assert all(s.end - s.start < len("9005  1512340") for s in spans)


def test_hard_negative_no_text() -> None:
    """Empty text produces no spans."""
    assert find("") == []


def test_hard_negative_only_letters() -> None:
    """Text without digit runs produces no spans."""
    assert find("Nie ma danych osobowych") == []
