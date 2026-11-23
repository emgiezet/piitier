"""Tests for the placeholder renderer (piitier.render) — PII-1-b.

Covers:
  UC-13: fidelity property test — characters outside spans are unchanged.

All PESEL numbers are synthetic, computed for this spec.
"""

from __future__ import annotations

import calendar

from hypothesis import given, settings
from hypothesis import strategies as st

import piitier
from piitier.labels import Label
from piitier.render import mask as render_mask
from piitier.spans import Span

# ---------------------------------------------------------------------------
# Shared strategy (duplicated from tests/rules/test_pesel.py to avoid
# coupling between test modules)
# ---------------------------------------------------------------------------

_WEIGHTS = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)


def _compute_check_digit(base10: str) -> str:
    total = sum(w * int(d) for w, d in zip(_WEIGHTS, base10))
    return str((10 - total % 10) % 10)


@st.composite
def valid_pesel_digits(draw: st.DrawFn) -> str:
    """Generate a syntactically and semantically valid 11-digit PESEL string."""
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
    # Exclude yy=0: those PESELs start with "00" and are filtered by the
    # phone-prefix exclusion rule (spec § phone-number exclusion).
    yy = draw(st.integers(min_value=1, max_value=99))
    actual_year = century_base + yy
    month = draw(st.integers(min_value=1, max_value=12))
    _, max_day = calendar.monthrange(actual_year, month)
    day = draw(st.integers(min_value=1, max_value=max_day))
    serial = draw(st.integers(min_value=0, max_value=9999))
    encoded_month = month + month_offset
    base = f"{yy:02d}{encoded_month:02d}{day:02d}{serial:04d}"
    return base + _compute_check_digit(base)


# ---------------------------------------------------------------------------
# Fidelity helper
# ---------------------------------------------------------------------------


def _outside_chars_match(original: str, result: str, spans: list[Span]) -> bool:
    """Return True iff every character outside spans in *original* is byte-identical
    in *result* at the corresponding position (after accounting for placeholder lengths)."""
    sorted_spans = sorted(spans, key=lambda s: s.start)
    orig_pos = 0
    res_pos = 0
    for span in sorted_spans:
        gap = span.start - orig_pos
        if original[orig_pos : span.start] != result[res_pos : res_pos + gap]:
            return False
        orig_pos = span.end
        res_pos += gap + len(span.label.placeholder)
    # Tail after the last span
    return original[orig_pos:] == result[res_pos:]


# ---------------------------------------------------------------------------
# render.mask() — unit tests
# ---------------------------------------------------------------------------


def test_render_mask_empty_text() -> None:
    """render_mask with empty text and no spans returns empty string."""
    assert render_mask("", []) == ""


def test_render_mask_no_spans_unchanged() -> None:
    """render_mask with no spans returns the original string unchanged."""
    text = "Brak PII w tym zdaniu."
    assert render_mask(text, []) == text


def test_render_mask_single_span_replaced() -> None:
    """render_mask replaces a single span with its label's placeholder."""
    text = "id: 90051512340 end"
    span = Span(start=4, end=15, label=Label.PESEL, source="rule", score=1.0, status="valid")
    result = render_mask(text, [span])
    assert result == "id: [PESEL] end"


def test_render_mask_two_spans_right_to_left() -> None:
    """render_mask processes multiple spans; ordering must be right-to-left internally."""
    text = "A: 90051512340 B: 05250112343 C"
    span1 = Span(start=3, end=14, label=Label.PESEL, source="rule", score=1.0, status="valid")
    span2 = Span(start=18, end=29, label=Label.PESEL, source="rule", score=1.0, status="valid")
    # Supply in forward order; render_mask must sort internally
    result = render_mask(text, [span1, span2])
    assert result == "A: [PESEL] B: [PESEL] C"


def test_render_mask_unsorted_spans_handled() -> None:
    """render_mask works even when spans are supplied in reverse order."""
    text = "A: 90051512340 B: 05250112343 C"
    span1 = Span(start=3, end=14, label=Label.PESEL, source="rule", score=1.0, status="valid")
    span2 = Span(start=18, end=29, label=Label.PESEL, source="rule", score=1.0, status="valid")
    result = render_mask(text, [span2, span1])  # reversed
    assert result == "A: [PESEL] B: [PESEL] C"


def test_render_mask_span_at_start() -> None:
    """render_mask handles a span that starts at position 0."""
    text = "90051512340 koniec"
    span = Span(start=0, end=11, label=Label.PESEL, source="rule", score=1.0, status="valid")
    assert render_mask(text, [span]) == "[PESEL] koniec"


def test_render_mask_span_at_end() -> None:
    """render_mask handles a span that ends at the last character."""
    text = "poczatek 90051512340"
    span = Span(start=9, end=20, label=Label.PESEL, source="rule", score=1.0, status="valid")
    assert render_mask(text, [span]) == "poczatek [PESEL]"


def test_render_mask_whole_string_is_span() -> None:
    """render_mask replaces the entire string when the span covers it all."""
    text = "90051512340"
    span = Span(start=0, end=11, label=Label.PESEL, source="rule", score=1.0, status="valid")
    assert render_mask(text, [span]) == "[PESEL]"


# ---------------------------------------------------------------------------
# UC-13: fidelity property test
# ---------------------------------------------------------------------------


@st.composite
def _text_with_pesels(draw: st.DrawFn) -> str:
    """Build text from letter-only segments interleaved with 0–5 valid PESELs.

    Segments between PESELs always contain at least one non-digit letter so that
    adjacent PESELs cannot merge into a longer digit run.
    """
    n_pesels = draw(st.integers(min_value=0, max_value=5))
    # Non-digit text segments (letters + spaces only)
    edge_seg = st.text(
        alphabet="aąbcćdeęfghijklłmnńoóprsśtuwyzźżABCDEFGHIJKLMNOPRSTUWYZ ",
        min_size=0,
        max_size=50,
    )
    between_seg = st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz ",
        min_size=1,
        max_size=20,
    )
    parts: list[str] = [draw(edge_seg)]
    for i in range(n_pesels):
        parts.append(draw(valid_pesel_digits()))
        sep = draw(between_seg) if i < n_pesels - 1 else draw(edge_seg)
        parts.append(sep)
    return "".join(parts)


@given(text=_text_with_pesels())
@settings(max_examples=150)
def test_uc13_fidelity_mask_outside_spans_unchanged(text: str) -> None:
    """UC-13: every character outside detected spans is identical, in order, to the input."""
    result = piitier.mask(text)
    spans = piitier.detect(text)
    assert _outside_chars_match(text, result, spans), (
        f"Characters outside spans were modified.\nInput:  {text!r}\nOutput: {result!r}"
    )


@given(text=_text_with_pesels())
@settings(max_examples=150)
def test_uc13_no_detections_unchanged(text: str) -> None:
    """UC-13: text with no detections is returned unchanged."""
    result = piitier.mask(text)
    spans = piitier.detect(text)
    if not spans:
        assert result == text


def test_uc13_empty_string_returns_empty() -> None:
    """UC-13: mask('') returns ''."""
    assert piitier.mask("") == ""


def test_uc13_fidelity_zero_pesels_returns_input() -> None:
    """UC-13: text with no PESELs is returned byte-for-byte identical."""
    text = "Wniosek o odszkodowanie nr AV-2024-001. Kwota: 1500 PLN."
    assert piitier.mask(text) == text


# ---------------------------------------------------------------------------
# Numbering parameter tests (PII-6-b)
# ---------------------------------------------------------------------------


def test_render_mask_numbering_replaces_n_suffix() -> None:
    """mask() with numbering replaces _n suffix in numbered-label placeholder."""
    text = "Jan Kowalski szkodę"
    span = Span(0, 12, Label.OSOBA, "model:ner", 1.0, "valid")
    result = render_mask(text, [span], numbering={(0, 12): 1})
    assert result == "[OSOBA_1] szkodę"


def test_render_mask_numbering_distinct_indices() -> None:
    """mask() with numbering assigns different indices to different entities."""
    text = "Jan Kowalski Anna Nowak"
    s1 = Span(0, 12, Label.OSOBA, "model:ner", 1.0, "valid")
    s2 = Span(13, 23, Label.OSOBA, "model:ner", 1.0, "valid")
    result = render_mask(text, [s1, s2], numbering={(0, 12): 1, (13, 23): 2})
    assert result == "[OSOBA_1] [OSOBA_2]"


def test_render_mask_numbering_none_unchanged() -> None:
    """mask() without numbering still emits template placeholder (no _n replacement)."""
    text = "Jan Kowalski"
    span = Span(0, 12, Label.OSOBA, "model:ner", 1.0, "valid")
    result = render_mask(text, [span])
    assert result == "[OSOBA_n]"


def test_render_mask_numbering_unnumbered_label_unaffected() -> None:
    """mask() with numbering leaves non-numbered labels (PESEL) without an index."""
    text = "PESEL 90051512340"
    span = Span(6, 17, Label.PESEL, "rule", 1.0, "valid")
    # numbering contains an entry but PESEL is not numbered → template placeholder
    result = render_mask(text, [span], numbering={(6, 17): 1})
    assert result == "PESEL [PESEL]"
