"""Tests for span fusion (piitier.fusion) — PII-6-a.

Covers UC-102 to UC-105: overlap shapes, precedence rules, threshold filtering,
GROUP_WEIGHTS sync, performance, property-based fidelity, and additional
structural tests required by the review.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from piitier import rules
from piitier.fusion import _LABEL_GROUP, GROUP_WEIGHTS, fuse, label_weight
from piitier.labels import Label
from piitier.render import mask as render_mask
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
    source: str = "rule",
    score: float = 1.0,
) -> Span:
    """Create a synthetic rule span using the real source value ``"rule"``."""
    return Span(start, end, label, source, score, status)


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


def _fidelity_ok(original: str, rendered: str, spans: list[Span]) -> bool:
    """Return True iff every character outside *spans* is byte-identical."""
    sorted_spans = sorted(spans, key=lambda s: s.start)
    orig_pos = 0
    res_pos = 0
    for span in sorted_spans:
        before_len = span.start - orig_pos
        if original[orig_pos : span.start] != rendered[res_pos : res_pos + before_len]:
            return False
        orig_pos = span.end
        res_pos += before_len + len(span.label.placeholder)
    return original[orig_pos:] == rendered[res_pos:]


# ---------------------------------------------------------------------------
# Weights sync test (pattern: tests/eval/test_metrics.py UC-80)
# ---------------------------------------------------------------------------


def test_weights_match_taxonomy() -> None:
    """GROUP_WEIGHTS in fusion.py equals the Risk weights table in docs/TAXONOMY.md."""
    content = TAXONOMY_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"## Risk weights.*?\n\n(\|.*?\n\|[-| ]+\n(?:\|.*?\n)+)",
        content,
        re.DOTALL,
    )
    assert match, "Risk weights section or table not found in docs/TAXONOMY.md"

    table_text = match.group(1)
    parsed: dict[str, float] = {}
    for line in table_text.strip().split("\n"):
        if "|" in line and "---" not in line and "Group" not in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) == 2:
                parsed[parts[0]] = float(parts[1])

    assert parsed == GROUP_WEIGHTS, (
        f"fusion.GROUP_WEIGHTS diverges from TAXONOMY.md.\n"
        f"  taxonomy: {parsed}\n"
        f"  fusion:   {GROUP_WEIGHTS}"
    )


def test_label_group_complete() -> None:
    """Every Label member is mapped in _LABEL_GROUP (no missing entries)."""
    all_labels = set(Label)
    mapped_labels = set(_LABEL_GROUP.keys())
    missing = all_labels - mapped_labels
    extra = mapped_labels - all_labels
    assert not missing, f"Labels missing from _LABEL_GROUP: {missing}"
    assert not extra, f"Extra keys in _LABEL_GROUP: {extra}"
    assert len(_LABEL_GROUP) == len(Label)


def test_label_weight_returns_group_weight() -> None:
    """label_weight() returns the correct group weight for representative labels."""
    assert label_weight(Label.PESEL) == 1.0  # State identifiers
    assert label_weight(Label.IBAN) == 1.0  # Finance
    assert label_weight(Label.NR_POLISY) == pytest.approx(0.9)  # Insurance
    assert label_weight(Label.ADRES) == pytest.approx(0.8)  # Contact and location
    assert label_weight(Label.DANE_ZDROWOTNE) == pytest.approx(0.8)  # Health
    assert label_weight(Label.OSOBA) == pytest.approx(0.6)  # Personal identification


# ---------------------------------------------------------------------------
# UC-102: valid rule span inside NER span
# ---------------------------------------------------------------------------


def test_uc102_valid_rule_inside_ner_span() -> None:
    """UC-102: rule valid PESEL [5,16) inside NER ADRES [0,25).

    Expected output:
      - ADRES [0,5)   source=model:ner
      - PESEL [5,16)  source=rule
      - ADRES [16,25) source=model:ner
    Result is non-overlapping; coverage equals union of inputs.
    """
    pesel = _rule_span(5, 16, Label.PESEL, status="valid")
    adres = _ner_span(0, 25, Label.ADRES)

    result = fuse([pesel], [adres])

    assert len(result) == 3
    assert result[0] == Span(0, 5, Label.ADRES, "model:ner", 0.9, "valid")
    assert result[1] == Span(5, 16, Label.PESEL, "rule", 1.0, "valid")
    assert result[2] == Span(16, 25, Label.ADRES, "model:ner", 0.9, "valid")

    assert _non_overlapping(result)
    assert _covered(result) == _covered([pesel, adres])
    for span in result:
        assert span.source in {"rule", "model:ner"}


def test_uc102_pesel_range_exactly_matches_rule() -> None:
    """UC-102: the PESEL span in the output has exactly the rule's offsets."""
    pesel = _rule_span(5, 16, Label.PESEL)
    adres = _ner_span(0, 25, Label.ADRES)
    result = fuse([pesel], [adres])
    pesel_out = next(s for s in result if s.label is Label.PESEL)
    assert (pesel_out.start, pesel_out.end) == (5, 16)
    assert pesel_out.source == "rule"


def test_uc102_real_detect_all_valid_rule_beats_longer_ner() -> None:
    """UC-102 (real sources): detect_all PESEL (rule, valid) beats a longer NER KWOTA.

    PESEL has group weight 1.0; KWOTA (Finance) also 1.0.  Normally longer span
    wins, but valid rule precedence means PESEL beats KWOTA regardless of length.
    Before the _is_valid_rule fix (source.startswith("rule:")) this failed because
    detect_all emits source="rule", not "rule:pesel".
    """
    text = "PESEL 90051512340 x"
    rule_spans = rules.detect_all(text)
    pesel_spans = [s for s in rule_spans if s.label is Label.PESEL]
    assert pesel_spans, "detect_all must find the PESEL in the test text"
    pesel = pesel_spans[0]
    assert pesel.source == "rule"

    # NER KWOTA covering the whole text (longer than PESEL, same weight group)
    kwota_ner = [Span(0, len(text), Label.KWOTA, "model:ner", 0.9, "valid")]

    result = fuse(rule_spans, kwota_ner)

    pesel_out = [s for s in result if s.label is Label.PESEL]
    assert len(pesel_out) == 1, "PESEL must survive in the fused output"
    assert pesel_out[0].start == pesel.start
    assert pesel_out[0].end == pesel.end
    assert pesel_out[0].source == "rule"


# ---------------------------------------------------------------------------
# UC-103: suspect rule span partially overlapping NER span — type-priority
# ---------------------------------------------------------------------------


def test_uc103_suspect_rule_higher_weight_wins() -> None:
    """UC-103: suspect PESEL (w=1.0) partially overlaps NER OSOBA (w=0.6).

    PESEL wins the overlap because its group weight (1.0) > OSOBA weight (0.6).
    OSOBA retains its fragment after the PESEL span.
    """
    pesel = _rule_span(5, 16, Label.PESEL, status="suspect")
    osoba = _ner_span(10, 22, Label.OSOBA)

    result = fuse([pesel], [osoba])

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
    """UC-103: equal weights → longer span wins (PESEL 11 chars vs NIP 6-char tail)."""
    pesel = _rule_span(0, 11, Label.PESEL, status="suspect")
    nip = _ner_span(8, 14, Label.NIP, score=0.9)  # overlap at [8,11)

    result = fuse([pesel], [nip])

    pesel_out = [s for s in result if s.label is Label.PESEL]
    nip_out = [s for s in result if s.label is Label.NIP]

    assert any(s.start == 0 and s.end == 11 for s in pesel_out)
    assert any(s.start == 11 and s.end == 14 for s in nip_out)

    assert _non_overlapping(result)
    assert _covered(result) == _covered([pesel, nip])


def test_uc103_equal_weight_equal_length_earlier_start_wins() -> None:
    """UC-103: equal weight, equal length → earlier start wins."""
    iban = _ner_span(0, 10, Label.IBAN, score=0.8)
    nr_karty = _ner_span(5, 15, Label.NR_KARTY, score=0.8)  # same length (10), later start

    result = fuse([], [iban, nr_karty])

    iban_out = [s for s in result if s.label is Label.IBAN]
    nr_karty_out = [s for s in result if s.label is Label.NR_KARTY]

    assert any(s.start == 0 and s.end == 10 for s in iban_out)
    assert any(s.start == 10 and s.end == 15 for s in nr_karty_out)

    assert _non_overlapping(result)
    assert _covered(result) == _covered([iban, nr_karty])


def test_uc103_rule_vs_rule_both_valid_length_tiebreak() -> None:
    """Two valid rule spans at equal weight → longer wins overlap; both rule sources kept."""
    pesel = _rule_span(0, 11, Label.PESEL)  # valid, weight=1.0, length=11
    nip = _rule_span(5, 19, Label.NIP)  # valid, weight=1.0, length=14 → longer

    result = fuse([pesel, nip], [])

    nip_out = [s for s in result if s.label is Label.NIP]
    pesel_out = [s for s in result if s.label is Label.PESEL]

    # NIP (length=14) wins the overlap [5,11); PESEL keeps [0,5)
    assert any(s.start == 5 and s.end == 19 for s in nip_out)
    assert any(s.start == 0 and s.end == 5 for s in pesel_out)
    for s in result:
        assert s.source == "rule"
    assert _non_overlapping(result)
    assert _covered(result) == _covered([pesel, nip])


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
    rule = _rule_span(0, 11, Label.PESEL, score=0.0)
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
    assert result[0].start == 20
    assert result[-1].start == 40


def test_uc104_threshold_nan_raises() -> None:
    """fuse raises ValueError for NaN threshold (fail-closed)."""
    import math

    with pytest.raises(ValueError, match="threshold"):
        fuse([], [], threshold=math.nan)


def test_uc104_threshold_gt1_raises() -> None:
    """fuse raises ValueError for threshold > 1 (fail-closed)."""
    with pytest.raises(ValueError, match="threshold"):
        fuse([], [], threshold=1.5)


def test_uc104_threshold_lt0_raises() -> None:
    """fuse raises ValueError for threshold < 0."""
    with pytest.raises(ValueError, match="threshold"):
        fuse([], [], threshold=-0.1)


# ---------------------------------------------------------------------------
# UC-105: overlap shapes — nested, partial, adjacent, identical
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "desc,rule_spans,ner_spans",
    [
        (
            "nested_outer_higher",
            [_rule_span(0, 20, Label.PESEL)],  # valid rule wins
            [_ner_span(5, 15, Label.OSOBA)],
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
            [_ner_span(5, 10, Label.ADRES)],
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

    assert _non_overlapping(result), f"{desc}: result has overlapping spans"

    starts = [s.start for s in result]
    assert starts == sorted(starts), f"{desc}: result not sorted by start"

    all_inputs = rule_spans + ner_spans
    assert _covered(result) == _covered(all_inputs), (
        f"{desc}: coverage mismatch: result={_covered(result)} input={_covered(all_inputs)}"
    )

    valid_sources = {"model:ner"} | {s.source for s in rule_spans}
    for span in result:
        assert span.source in valid_sources, (
            f"{desc}: span.source={span.source!r} not in {valid_sources}"
        )


def test_uc105_three_way_overlap() -> None:
    """UC-105: 3+ mutually overlapping spans resolve correctly end-to-end.

    A PESEL [0,10) rule valid (beats NER)
    B IBAN  [3,15) NER  weight=1.0  (wins [10,15) over C)
    C OSOBA [7,20) NER  weight=0.6  (keeps [15,20))

    Expected: PESEL[0,10), IBAN[10,15), OSOBA[15,20)
    """
    pesel = _rule_span(0, 10, Label.PESEL)
    iban = _ner_span(3, 15, Label.IBAN, score=0.9)
    osoba = _ner_span(7, 20, Label.OSOBA, score=0.9)

    result = fuse([pesel], [iban, osoba])

    assert _non_overlapping(result)
    assert _covered(result) == _covered([pesel, iban, osoba])

    pesel_out = [s for s in result if s.label is Label.PESEL]
    iban_out = [s for s in result if s.label is Label.IBAN]
    osoba_out = [s for s in result if s.label is Label.OSOBA]

    assert any(s.start == 0 and s.end == 10 for s in pesel_out)
    assert any(s.start == 10 and s.end == 15 for s in iban_out)
    assert any(s.start == 15 and s.end == 20 for s in osoba_out)


def test_uc105_adjacent_spans_not_merged() -> None:
    """UC-105: two adjacent non-overlapping spans are NOT merged."""
    s1 = _ner_span(0, 5, Label.OSOBA, score=0.9)
    s2 = _ner_span(5, 10, Label.OSOBA, score=0.9)

    result = fuse([], [s1, s2])

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
    assert result == [Span(5, 16, Label.PESEL, "rule", 1.0, "valid")]


def test_uc105_no_rule_returns_ner_spans() -> None:
    """UC-105: fuse with no rule spans (and no overlap) returns NER spans."""
    osoba = _ner_span(0, 5, Label.OSOBA, score=0.9)
    result = fuse([], [osoba])
    assert result == [Span(0, 5, Label.OSOBA, "model:ner", 0.9, "valid")]


def test_uc105_rule_vs_rule_from_detect_all() -> None:
    """UC-105 (real sources): two detect_all spans with overlapping offsets.

    Simulates a pathological case where the same byte range matches two rules
    by constructing rule spans with the real "rule" source and checking that
    the fuse output is always non-overlapping with full coverage.
    """
    # Both rule+valid, same weight (State identifiers), different lengths
    s1 = Span(0, 11, Label.PESEL, "rule", 1.0, "valid")  # length 11
    s2 = Span(5, 20, Label.NIP, "rule", 1.0, "valid")  # length 15 → wins overlap [5,11)

    result = fuse([s1, s2], [])

    assert _non_overlapping(result)
    assert _covered(result) == _covered([s1, s2])
    # NIP [5,20) is longer → wins [5,11); PESEL keeps [0,5)
    assert any(s.label is Label.PESEL and s.start == 0 and s.end == 5 for s in result)
    assert any(s.label is Label.NIP and s.start == 5 and s.end == 20 for s in result)


# ---------------------------------------------------------------------------
# Performance: 20 000 spans fused in < 2 s (linear sweep regression guard)
# ---------------------------------------------------------------------------


def test_performance_20k_spans_under_2s() -> None:
    """O(n log n) sweep: 20 000 partially-overlapping spans fused in under 2 s."""
    n = 20_000
    # n/2 rule spans [4i, 4i+3), n/2 NER spans [4i+1, 4i+4) — partial overlap
    rule_spans = [Span(i * 4, i * 4 + 3, Label.PESEL, "rule", 1.0, "valid") for i in range(n // 2)]
    ner_spans = [
        Span(i * 4 + 1, i * 4 + 4, Label.ADRES, "model:ner", 0.9, "valid") for i in range(n // 2)
    ]

    t0 = time.monotonic()
    result = fuse(rule_spans, ner_spans)
    elapsed = time.monotonic() - t0

    assert elapsed < 2.0, f"fuse took {elapsed:.3f}s for {n} spans (limit 2 s)"
    assert _non_overlapping(result)
    assert _covered(result) == _covered(rule_spans + ner_spans)


# ---------------------------------------------------------------------------
# Property-based: fuse → render.mask changes 0 chars outside spans
# ---------------------------------------------------------------------------


@st.composite
def _text_with_spans(
    draw: st.DrawFn,
) -> tuple[str, list[Span], list[Span]]:
    """Generate text plus random rule and NER spans within its bounds."""
    text = draw(
        st.text(
            alphabet=st.characters(blacklist_categories=("Cs",)),
            min_size=2,
            max_size=80,
        )
    )
    n = len(text)

    def _build_spans(source: str, n_max: int) -> list[Span]:
        count = draw(st.integers(0, n_max))
        spans = []
        for _ in range(count):
            s = draw(st.integers(0, n - 2))
            e = draw(st.integers(s + 1, n))
            lbl = draw(st.sampled_from(list(Label)))
            score = draw(st.floats(0.0, 1.0, allow_nan=False, allow_infinity=False))
            status = draw(st.sampled_from(["valid", "suspect"]))
            spans.append(Span(s, e, lbl, source, score, status))
        return spans

    rule_spans = _build_spans("rule", 8)
    ner_spans = _build_spans("model:ner", 8)
    return text, rule_spans, ner_spans


@given(data=_text_with_spans())
@settings(max_examples=200)
def test_property_fuse_render_fidelity(data: tuple[str, list[Span], list[Span]]) -> None:
    """Property: fuse→render changes 0 characters outside fused spans; coverage = union."""
    text, rule_spans, ner_spans = data

    result = fuse(rule_spans, ner_spans, threshold=0.0)

    # Non-overlapping and sorted
    assert _non_overlapping(result)
    starts = [s.start for s in result]
    assert starts == sorted(starts)

    # Coverage equals the union of all input spans
    all_inputs = rule_spans + ner_spans
    assert _covered(result) == _covered(all_inputs)

    # Fidelity after rendering: characters outside spans are byte-identical
    rendered = render_mask(text, result)
    assert _fidelity_ok(text, rendered, result)
