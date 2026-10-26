"""Tests for span fusion (piitier.fusion) — PII-6-a.

Covers UC-102 to UC-105: overlap shapes, precedence rules, threshold filtering,
and the GROUP_WEIGHTS sync assertion against docs/TAXONOMY.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from piitier.fusion import GROUP_WEIGHTS, fuse, label_weight
from piitier.labels import Label
from piitier.spans import Span

TAXONOMY_PATH = Path(__file__).parent.parent / "docs" / "TAXONOMY.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rule_span(
    start: int,
    end: int,
    label: Label,
    *,
    status: str = "valid",
    source: str | None = None,
    score: float = 1.0,
) -> Span:
    src = source or f"rule:{label.name.lower()}"
    return Span(start, end, label, src, score, status)


def _ner_span(
    start: int,
    end: int,
    label: Label,
    *,
    score: float = 0.9,
) -> Span:
    return Span(start, end, label, "model:ner", score, "valid")


def _covered(spans: list[Span]) -> set[int]:
    """Return the set of character positions covered by *spans*."""
    positions: set[int] = set()
    for s in spans:
        positions.update(range(s.start, s.end))
    return positions


def _non_overlapping(spans: list[Span]) -> bool:
    """Return True iff no two spans in *spans* overlap."""
    sorted_spans = sorted(spans, key=lambda s: s.start)
    for i in range(len(sorted_spans) - 1):
        if sorted_spans[i].end > sorted_spans[i + 1].start:
            return False
    return True


# ---------------------------------------------------------------------------
# Weights sync test (pattern: tests/eval/test_metrics.py UC-80)
# ---------------------------------------------------------------------------


def test_weights_match_taxonomy() -> None:
    """GROUP_WEIGHTS in fusion.py equals the Wagi ryzyka table in docs/TAXONOMY.md."""
    content = TAXONOMY_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"## Wagi ryzyka.*?\n\n(\|.*?\n\|[-| ]+\n(?:\|.*?\n)+)",
        content,
        re.DOTALL,
    )
    assert match, "Wagi ryzyka section or table not found in docs/TAXONOMY.md"

    table_text = match.group(1)
    parsed: dict[str, float] = {}
    for line in table_text.strip().split("\n"):
        if "|" in line and "---" not in line and "Grupa" not in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) == 2:
                parsed[parts[0]] = float(parts[1])

    assert parsed == GROUP_WEIGHTS, (
        f"fusion.GROUP_WEIGHTS diverges from TAXONOMY.md.\n"
        f"  taxonomy: {parsed}\n"
        f"  fusion:   {GROUP_WEIGHTS}"
    )


def test_label_weight_returns_group_weight() -> None:
    """label_weight() returns the correct group weight for representative labels."""
    assert label_weight(Label.PESEL) == 1.0  # Identyfikatory państwowe
    assert label_weight(Label.IBAN) == 1.0  # Finanse
    assert label_weight(Label.NR_POLISY) == pytest.approx(0.9)  # Ubezpieczenia
    assert label_weight(Label.ADRES) == pytest.approx(0.8)  # Kontakt i lokalizacja
    assert label_weight(Label.DANE_ZDROWOTNE) == pytest.approx(0.8)  # Zdrowie
    assert label_weight(Label.OSOBA) == pytest.approx(0.6)  # Identyfikacja osoby


# ---------------------------------------------------------------------------
# UC-102: valid rule span inside NER span
# ---------------------------------------------------------------------------


def test_uc102_valid_rule_inside_ner_span() -> None:
    """UC-102: rule valid PESEL [5,16) inside NER ADRES [0,25).

    Expected output:
      - ADRES [0,5)  source=model:ner
      - PESEL [5,16) source=rule:pesel
      - ADRES [16,25) source=model:ner
    Result is non-overlapping; coverage equals union of inputs.
    """
    pesel = _rule_span(5, 16, Label.PESEL, status="valid", source="rule:pesel")
    adres = _ner_span(0, 25, Label.ADRES)

    result = fuse([pesel], [adres])

    assert len(result) == 3
    assert result[0] == Span(0, 5, Label.ADRES, "model:ner", 0.9, "valid")
    assert result[1] == Span(5, 16, Label.PESEL, "rule:pesel", 1.0, "valid")
    assert result[2] == Span(16, 25, Label.ADRES, "model:ner", 0.9, "valid")

    # Structural checks
    assert _non_overlapping(result)
    assert _covered(result) == _covered([pesel, adres])
    for span in result:
        assert span.source in {"rule:pesel", "model:ner"}


def test_uc102_pesel_range_exactly_matches_rule() -> None:
    """UC-102: the PESEL span in the output has exactly the rule's offsets."""
    pesel = _rule_span(5, 16, Label.PESEL)
    adres = _ner_span(0, 25, Label.ADRES)
    result = fuse([pesel], [adres])
    pesel_out = next(s for s in result if s.label is Label.PESEL)
    assert (pesel_out.start, pesel_out.end) == (5, 16)
    assert pesel_out.source == "rule:pesel"


# ---------------------------------------------------------------------------
# UC-103: suspect rule span partially overlapping NER span — type-priority
# ---------------------------------------------------------------------------


def test_uc103_suspect_rule_higher_weight_wins() -> None:
    """UC-103: suspect PESEL (w=1.0) partially overlaps NER OSOBA (w=0.6).

    PESEL wins the overlap because its group weight (1.0) > OSOBA weight (0.6).
    OSOBA retains its fragment after the PESEL span.
    """
    pesel = _rule_span(5, 16, Label.PESEL, status="suspect", source="rule:pesel")
    osoba = _ner_span(10, 22, Label.OSOBA)

    result = fuse([pesel], [osoba])

    # PESEL [5,16) should be whole; OSOBA [16,22) is its fragment
    pesel_out = [s for s in result if s.label is Label.PESEL]
    osoba_out = [s for s in result if s.label is Label.OSOBA]

    assert len(pesel_out) == 1
    assert (pesel_out[0].start, pesel_out[0].end) == (5, 16)
    assert pesel_out[0].status == "suspect"

    assert len(osoba_out) == 1
    assert (osoba_out[0].start, osoba_out[0].end) == (16, 22)

    assert _non_overlapping(result)
    assert _covered(result) == _covered([pesel, osoba])


def test_uc103_equal_weight_longer_span_wins() -> None:
    """UC-103: equal weights → longer span wins (PESEL 11 chars vs NIP 6 chars)."""
    # PESEL weight=1.0, NIP weight=1.0 → tie → longer wins
    pesel = _rule_span(0, 11, Label.PESEL, status="suspect", source="rule:pesel")
    nip = _ner_span(8, 14, Label.NIP, score=0.9)  # overlap at [8,11)

    result = fuse([pesel], [nip])

    pesel_out = [s for s in result if s.label is Label.PESEL]
    nip_out = [s for s in result if s.label is Label.NIP]

    # PESEL (11 chars) > NIP fragment in overlap zone (6 chars → but at overlap: 3 chars)
    # PESEL is longer overall → wins the overlap region [8,11)
    assert any(s.start == 0 and s.end == 11 for s in pesel_out)
    # NIP keeps [11,14)
    assert any(s.start == 11 and s.end == 14 for s in nip_out)

    assert _non_overlapping(result)
    assert _covered(result) == _covered([pesel, nip])


def test_uc103_equal_weight_equal_length_earlier_start_wins() -> None:
    """UC-103: equal weight, equal length → earlier start wins."""
    # Two NER spans same label group (Finanse, w=1.0), same length, different start
    iban = _ner_span(0, 10, Label.IBAN, score=0.8)  # starts at 0
    nr_karty = _ner_span(5, 15, Label.NR_KARTY, score=0.8)  # starts at 5, same length 10

    result = fuse([], [iban, nr_karty])

    # IBAN starts earlier → wins overlap [5,10)
    iban_out = [s for s in result if s.label is Label.IBAN]
    nr_karty_out = [s for s in result if s.label is Label.NR_KARTY]

    assert any(s.start == 0 and s.end == 10 for s in iban_out)
    assert any(s.start == 10 and s.end == 15 for s in nr_karty_out)

    assert _non_overlapping(result)
    assert _covered(result) == _covered([iban, nr_karty])


# ---------------------------------------------------------------------------
# UC-104: threshold filtering
# ---------------------------------------------------------------------------


def test_uc104_ner_below_threshold_dropped() -> None:
    """UC-104: NER span with score < threshold is absent from output."""
    low = _ner_span(0, 5, Label.OSOBA, score=0.3)
    result = fuse([], [low], threshold=0.5)
    assert result == []


def test_uc104_ner_equal_threshold_kept() -> None:
    """UC-104: NER span with score == threshold is kept (>= semantics)."""
    equal = _ner_span(0, 5, Label.OSOBA, score=0.5)
    result = fuse([], [equal], threshold=0.5)
    assert len(result) == 1
    assert result[0].start == 0 and result[0].end == 5


def test_uc104_rule_spans_never_threshold_filtered() -> None:
    """UC-104: rule spans are kept regardless of threshold."""
    rule = _rule_span(0, 11, Label.PESEL, score=0.0)  # score would be filtered if NER
    result = fuse([rule], [], threshold=0.9)
    assert len(result) == 1
    assert result[0].label is Label.PESEL


def test_uc104_mixed_threshold_applied_only_to_ner() -> None:
    """UC-104: high threshold filters NER but rule spans survive."""
    rule = _rule_span(20, 31, Label.PESEL)
    dropped_ner = _ner_span(0, 10, Label.OSOBA, score=0.3)
    kept_ner = _ner_span(40, 50, Label.OSOBA, score=0.7)

    result = fuse([rule], [dropped_ner, kept_ner], threshold=0.5)

    labels = [s.label for s in result]
    assert Label.PESEL in labels
    assert Label.OSOBA in labels
    assert len([s for s in result if s.label is Label.OSOBA]) == 1
    assert result[0].start == 20  # PESEL span
    assert result[-1].start == 40  # kept OSOBA span


# ---------------------------------------------------------------------------
# UC-105: overlap shapes — nested, partial, adjacent, identical
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "desc,rule_spans,ner_spans",
    [
        (
            "nested_outer_higher",
            [_rule_span(0, 20, Label.PESEL)],  # outer wins (valid rule)
            [_ner_span(5, 15, Label.OSOBA)],  # inner, lower priority
        ),
        (
            "nested_inner_higher",
            [],
            [
                _ner_span(0, 20, Label.OSOBA, score=0.5),  # outer, lower weight
                _ner_span(5, 15, Label.PESEL, score=0.9),  # inner, higher weight
            ],
        ),
        (
            "partial_overlap",
            [_rule_span(0, 12, Label.PESEL)],
            [_ner_span(8, 20, Label.ADRES)],
        ),
        (
            "adjacent_no_gap",
            [_rule_span(0, 5, Label.PESEL)],
            [_ner_span(5, 10, Label.ADRES)],  # starts exactly where PESEL ends
        ),
        (
            "identical_range",
            [_rule_span(0, 10, Label.PESEL)],
            [_ner_span(0, 10, Label.OSOBA)],
        ),
    ],
)
def test_uc105_overlap_shapes(
    desc: str,
    rule_spans: list[Span],
    ner_spans: list[Span],
) -> None:
    """UC-105: all overlap shapes produce non-overlapping, sorted, coverage-preserving output."""
    result = fuse(rule_spans, ner_spans)

    # Non-overlapping
    assert _non_overlapping(result), f"{desc}: result has overlapping spans"

    # Sorted by start
    starts = [s.start for s in result]
    assert starts == sorted(starts), f"{desc}: result not sorted by start"

    # Coverage equals union of inputs
    all_inputs = rule_spans + ner_spans
    assert _covered(result) == _covered(all_inputs), (
        f"{desc}: coverage mismatch: result={_covered(result)} input={_covered(all_inputs)}"
    )

    # Every span retains its source
    valid_sources = {"model:ner"} | {s.source for s in rule_spans}
    for span in result:
        assert span.source in valid_sources, (
            f"{desc}: span.source={span.source!r} not in {valid_sources}"
        )


def test_uc105_adjacent_spans_not_merged() -> None:
    """UC-105: two adjacent non-overlapping spans are NOT merged even if same label."""
    s1 = _ner_span(0, 5, Label.OSOBA, score=0.9)
    s2 = _ner_span(5, 10, Label.OSOBA, score=0.9)

    result = fuse([], [s1, s2])

    # Two separate spans, not one merged span
    assert len(result) == 2
    assert result[0].start == 0 and result[0].end == 5
    assert result[1].start == 5 and result[1].end == 10


def test_uc105_empty_inputs() -> None:
    """UC-105: fuse with no spans returns empty list."""
    assert fuse([], []) == []
    assert fuse([], [], threshold=0.5) == []


def test_uc105_no_ner_returns_rule_spans() -> None:
    """UC-105: fuse with no NER spans returns rule spans as-is."""
    pesel = _rule_span(5, 16, Label.PESEL)
    result = fuse([pesel], [])
    assert result == [Span(5, 16, Label.PESEL, "rule:pesel", 1.0, "valid")]


def test_uc105_no_rule_returns_ner_spans() -> None:
    """UC-105: fuse with no rule spans (and no overlap) returns NER spans."""
    osoba = _ner_span(0, 5, Label.OSOBA, score=0.9)
    result = fuse([], [osoba])
    assert result == [Span(0, 5, Label.OSOBA, "model:ner", 0.9, "valid")]
