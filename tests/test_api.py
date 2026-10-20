"""Integration tests for the piitier public API — detect() and mask().

Covers the integration-level acceptance criteria from PII-1-b:
  UC-7, UC-8, UC-9, UC-36 (mask on separated formats).

All PESEL numbers are synthetic, computed for this spec.
"""

from __future__ import annotations

import pytest

import piitier
from piitier.labels import Label

# ---------------------------------------------------------------------------
# UC-7: mask() replaces PESEL with [PESEL], leaves surrounding text intact
# ---------------------------------------------------------------------------


def test_uc7_mask_replaces_valid_pesel() -> None:
    """UC-7: piitier.mask('PESEL: 90051512340, tel.') → 'PESEL: [PESEL], tel.'"""
    result = piitier.mask("PESEL: 90051512340, tel.")
    assert result == "PESEL: [PESEL], tel."


# ---------------------------------------------------------------------------
# UC-8: detect() returns exactly one span with expected fields
# ---------------------------------------------------------------------------


def test_uc8_detect_returns_one_span() -> None:
    """UC-8: detect on 90051512340 returns one span with all expected fields."""
    spans = piitier.detect("PESEL: 90051512340, tel.")
    assert len(spans) == 1
    span = spans[0]
    assert span.start == 7
    assert span.end == 18
    assert span.label is Label.PESEL
    assert span.source == "rule"
    assert span.score == 1.0
    assert span.status == "valid"


def test_uc8_detect_span_slice_equals_pesel() -> None:
    """UC-8: text[span.start:span.end] reproduces the matched PESEL digits."""
    text = "PESEL: 90051512340, tel."
    spans = piitier.detect(text)
    assert len(spans) == 1
    assert text[spans[0].start : spans[0].end] == "90051512340"


# ---------------------------------------------------------------------------
# UC-9: wrong check digit → masked, status='suspect'
# ---------------------------------------------------------------------------


def test_uc9_suspect_pesel_is_masked() -> None:
    """UC-9: mask on 90051512341 (wrong check digit) returns [PESEL]."""
    result = piitier.mask("id: 90051512341")
    assert result == "id: [PESEL]"


def test_uc9_suspect_pesel_detect_status() -> None:
    """UC-9: detect on 90051512341 returns one span with status='suspect'."""
    spans = piitier.detect("id: 90051512341")
    assert len(spans) == 1
    assert spans[0].status == "suspect"
    assert spans[0].label is Label.PESEL


def test_uc9_suspect_pesel_is_never_dropped() -> None:
    """UC-9 / invariant-6: a bad check digit never causes the span to be dropped."""
    # 90051512341 — wrong check digit (correct is 0)
    spans = piitier.detect("90051512341")
    assert len(spans) == 1


# ---------------------------------------------------------------------------
# Additional API surface tests (density grid — public symbols)
# ---------------------------------------------------------------------------


def test_mask_empty_string_returns_empty() -> None:
    """mask('') → '' (UC-13 sub-case, exercised here at API level too)."""
    assert piitier.mask("") == ""


def test_detect_empty_string_returns_empty_list() -> None:
    """detect('') → [] — empty input produces no spans."""
    assert piitier.detect("") == []


def test_detect_no_pesel_in_text() -> None:
    """detect on text with no PESEL → empty list."""
    spans = piitier.detect("Brak danych osobowych tutaj.")
    assert spans == []


def test_mask_no_pesel_unchanged() -> None:
    """mask on text with no PESEL → identical string."""
    text = "Nic do zanonimizowania."
    assert piitier.mask(text) == text


def test_detect_sorted_by_start() -> None:
    """detect returns spans in ascending start-offset order."""
    text = "A: 90051512340 B: 05250112343 C"
    spans = piitier.detect(text)
    assert len(spans) == 2
    assert spans[0].start < spans[1].start


def test_mask_multiple_pesels() -> None:
    """mask handles multiple PESEL occurrences in one string."""
    text = "P1=90051512340 P2=05250112343"
    result = piitier.mask(text)
    assert result == "P1=[PESEL] P2=[PESEL]"


# ---------------------------------------------------------------------------
# UC-36: mask() on separated-format PESELs — public-API assertion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "900 515 123 40",
        "9005-1512-340",
        "90051 512340",
    ],
)
def test_uc36_mask_separated_format_returns_placeholder(text: str) -> None:
    """UC-36: mask on each separated format returns exactly '[PESEL]'."""
    assert piitier.mask(text) == "[PESEL]"
