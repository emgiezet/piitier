"""Tests for evaluation metrics (eval/metrics.py) — PII-4-d.

Covers UC-79 to UC-84 with hand-computed fixtures.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

from piitier.labels import Label
from piitier.render import mask as render_mask
from piitier.spans import Span

# Dynamically load eval/metrics.py to avoid test runner path resolution issues
_metrics_path = Path(__file__).resolve().parents[2] / "eval" / "metrics.py"
_spec = importlib.util.spec_from_file_location("eval.metrics", _metrics_path)
_metrics_mod = importlib.util.module_from_spec(_spec)
sys.modules["eval.metrics"] = _metrics_mod
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(_metrics_mod)

DIRECT_IDENTIFIERS = _metrics_mod.DIRECT_IDENTIFIERS
GROUP_WEIGHTS = _metrics_mod.GROUP_WEIGHTS
EntityPRF = _metrics_mod.EntityPRF
NumberingStats = _metrics_mod.NumberingStats
ThroughputStats = _metrics_mod.ThroughputStats
entity_metrics = _metrics_mod.entity_metrics
entity_metrics_by_label = _metrics_mod.entity_metrics_by_label
fidelity = _metrics_mod.fidelity
group_for_label = _metrics_mod.group_for_label
leak_rate = _metrics_mod.leak_rate
numbering_consistency = _metrics_mod.numbering_consistency
peak_ram_bytes = _metrics_mod.peak_ram_bytes
risk_weighted_recall = _metrics_mod.risk_weighted_recall
throughput_stats = _metrics_mod.throughput_stats


def test_uc79_entity_metrics() -> None:
    """UC-79: entity_metrics strict and partial, edge cases, per-label.

    Gold spans (3):
      - g1: [0, 11) PESEL "90051512340"
      - g2: [20, 31) PESEL "80010156789"
      - g3: [40, 45) NIP "12345"
    Pred spans (2):
      - p1: [0, 11) PESEL "90051512340" (exact match with g1 -> TP)
      - p2: [22, 31) PESEL partial overlap with g2 [20, 31)

    Arithmetic (strict):
      - TP = 1 (p1 matches g1)
      - Pred count = 2 -> Precision = 1 / 2 = 0.5
      - Gold count = 3 -> Recall = 1 / 3 = 0.3333333333333333
      - F1 = 2 * 0.5 * (1/3) / (0.5 + 1/3) = 2/5 = 0.4
    """
    gold = [
        Span(0, 11, Label.PESEL, "rule", 1.0, "valid"),
        Span(20, 31, Label.PESEL, "rule", 1.0, "valid"),
        Span(40, 45, Label.NIP, "rule", 1.0, "valid"),
    ]
    pred_strict = [
        Span(0, 11, Label.PESEL, "model", 0.9, "valid"),
        Span(22, 31, Label.PESEL, "model", 0.9, "valid"),
    ]

    res_strict = entity_metrics(gold, pred_strict, "strict")
    assert res_strict.precision == 0.5
    assert res_strict.recall == pytest.approx(1.0 / 3.0)
    assert res_strict.f1 == pytest.approx(0.4)

    res_partial = entity_metrics(gold, pred_strict, "partial")
    assert res_partial.precision == 1.0
    assert res_partial.recall == pytest.approx(2.0 / 3.0)
    assert res_partial.f1 == pytest.approx(0.8)

    res_zeropred = entity_metrics(gold, [], "strict")
    # No predictions: precision undefined (TP+FP=0), recall=0.0, F1=0.0 (PII-9)
    assert res_zeropred.precision is None
    assert res_zeropred.recall == 0.0
    assert res_zeropred.f1 == 0.0
    assert res_zeropred.tp == 0
    assert res_zeropred.fp == 0
    assert res_zeropred.fn == 3

    res_bothzero = entity_metrics([], [], "strict")
    # No gold, no pred: all denominators zero → all undefined (PII-9)
    assert res_bothzero.precision is None
    assert res_bothzero.recall is None
    assert res_bothzero.f1 is None
    assert res_bothzero.tp == 0
    assert res_bothzero.fp == 0
    assert res_bothzero.fn == 0

    by_lbl = entity_metrics_by_label(gold, pred_strict, "strict")
    assert Label.PESEL in by_lbl
    assert Label.NIP in by_lbl
    assert by_lbl[Label.PESEL].precision == 0.5
    assert by_lbl[Label.PESEL].recall == 0.5
    assert by_lbl[Label.PESEL].f1 == 0.5
    # NIP: gold=1 span, pred=0 NIP spans → precision=None, recall=0.0, f1=0.0 (PII-9)
    assert by_lbl[Label.NIP].precision is None
    assert by_lbl[Label.NIP].recall == 0.0
    assert by_lbl[Label.NIP].f1 == 0.0


def test_uc80_risk_weighted_recall() -> None:
    """UC-80: risk_weighted_recall hand computation and TAXONOMY sync.

    Fixture:
      - g1: PESEL (Group: Identyfikatory państwowe, weight = 1.0) -> caught
      - g2: IBAN (Group: Finanse, weight = 1.0) -> missed
      - g3: OSOBA (Group: Identyfikacja osoby, weight = 0.6) -> caught

    Arithmetic:
      - Total weight = 1.0 + 1.0 + 0.6 = 2.6
      - Matched weight = 1.0 + 0.6 = 1.6
      - Risk-weighted recall = 1.6 / 2.6
    """
    gold = [
        Span(0, 11, Label.PESEL, "rule", 1.0, "valid"),
        Span(20, 30, Label.IBAN, "rule", 1.0, "valid"),
        Span(40, 46, Label.OSOBA, "rule", 1.0, "valid"),
    ]
    pred = [
        Span(0, 11, Label.PESEL, "model", 0.9, "valid"),
        Span(40, 46, Label.OSOBA, "model", 0.9, "valid"),
    ]

    rwr = risk_weighted_recall(gold, pred)
    assert rwr == pytest.approx(1.6 / 2.6)
    # Empty gold → zero denominator → undefined/None (PII-9 contract change)
    assert risk_weighted_recall([], pred) is None

    taxonomy_path = Path(__file__).parents[2] / "docs" / "TAXONOMY.md"
    assert taxonomy_path.exists(), f"TAXONOMY.md not found at {taxonomy_path}"
    content = taxonomy_path.read_text(encoding="utf-8")

    match = re.search(
        r"## Wagi ryzyka.*?\n\n(\|.*?\n\|[-| ]+\n(?:\|.*?\n)+)",
        content,
        re.DOTALL,
    )
    assert match, "Wagi ryzyka section or table not found in docs/TAXONOMY.md"

    table_text = match.group(1)
    parsed_weights: dict[str, float] = {}
    for line in table_text.strip().split("\n"):
        if "|" in line and "---" not in line and "Grupa" not in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) == 2:
                group_name, weight_str = parts
                parsed_weights[group_name] = float(weight_str)

    assert parsed_weights == GROUP_WEIGHTS


def test_uc81_leak_rate() -> None:
    """UC-81: leak_rate counting docs leaked, values leaked, direct IDs.

    Doc 0: PESEL value unmasked in rendered -> values_leaked=1,
           docs_leaked=1 (PESEL in DIRECT_IDENTIFIERS).
    Doc 1: suspect PESEL value NOT in rendered -> masked, no leak.
    Doc 2: MIEJSCOWOSC left unmasked (not in DIRECT_IDENTIFIERS) ->
           values_leaked=1, docs_leaked=0.
    """
    originals = [
        "Mój PESEL to 90051512340.",
        "Podejrzany pesel 80010156789.",
        "Mieszkam w Warszawa.",
    ]
    gold_spans = [
        [Span(13, 24, Label.PESEL, "rule", 1.0, "valid")],
        [Span(16, 27, Label.PESEL, "rule", 0.5, "suspect")],
        [Span(11, 20, Label.MIEJSCOWOSC, "rule", 1.0, "valid")],
    ]
    rendered = [
        "Mój PESEL to 90051512340.",
        "Podejrzany pesel [PESEL].",
        "Mieszkam w Warszawa.",
    ]
    doc_ids = ["doc-0", "doc-1", "doc-2"]

    lr = leak_rate(originals, gold_spans, rendered, doc_ids)
    assert lr.docs_total == 3
    assert lr.docs_leaked == 1
    assert lr.values_total == 3
    assert lr.values_leaked == 2
    assert lr.leaked_doc_ids == ["doc-0"]


def test_uc82_fidelity() -> None:
    """UC-82: fidelity returns 0 for correct masking and > 0 for corrupted text outside spans."""
    text = "Jan Kowalski ma PESEL 90051512340 i mieszka w Poznaniu."
    spans = [
        Span(0, 11, Label.OSOBA, "rule", 1.0, "valid"),
        Span(20, 31, Label.PESEL, "rule", 1.0, "valid"),
        Span(43, 51, Label.MIEJSCOWOSC, "rule", 1.0, "valid"),
    ]
    masked = render_mask(text, spans)

    assert fidelity(text, masked, spans) == 0

    corrupted = masked.replace("ma", "maX", 1)
    assert fidelity(text, corrupted, spans) > 0


def test_uc83_numbering_consistency() -> None:
    """UC-83: numbering_consistency with render.mask and manual placeholders.

    Fixture 1: rendered via render.mask (same persons -> same placeholder;
    different persons -> same placeholder -> distinct=0).
    Fixture 2: manual placeholders [OSOBA_1] / [OSOBA_2] -> full compliance.
    """
    text = "Jan Kowalski i Jan Kowalski oraz Anna Nowak."
    spans = [
        Span(0, 12, Label.OSOBA, "rule", 1.0, "valid"),
        Span(15, 27, Label.OSOBA, "rule", 1.0, "valid"),
        Span(33, 43, Label.OSOBA, "rule", 1.0, "valid"),
    ]
    masked = render_mask(text, spans)
    labels_numbered = {Label.OSOBA}

    stats1 = numbering_consistency(
        masked,
        spans,
        labels_numbered,
        original=text,
        masked_spans=spans,
    )
    assert stats1.same_entity_total == 1
    assert stats1.same_entity_consistent == 1
    assert stats1.different_entity_total == 2
    assert stats1.different_entity_distinct == 0

    rendered_manual = "[OSOBA_1] i [OSOBA_1] oraz [OSOBA_2]."
    stats2 = numbering_consistency(
        rendered_manual,
        spans,
        labels_numbered,
        original=text,
        masked_spans=spans,
    )
    assert stats2.same_entity_total == 1
    assert stats2.same_entity_consistent == 1
    assert stats2.different_entity_total == 2
    assert stats2.different_entity_distinct == 2


def test_adjacent_spans_fidelity_and_numbering() -> None:
    """Test fidelity and numbering consistency with adjacent spans (Finding 8)."""
    text = "JanJan"
    spans = [
        Span(0, 3, Label.OSOBA, "rule", 1.0, "valid"),
        Span(3, 6, Label.OSOBA, "rule", 1.0, "valid"),
    ]
    masked = render_mask(text, spans)
    assert masked == "[OSOBA_n][OSOBA_n]"
    assert fidelity(text, masked, spans) == 0

    stats = numbering_consistency(
        masked,
        spans,
        {Label.OSOBA},
        original=text,
        masked_spans=spans,
    )
    assert stats.same_entity_total == 1
    assert stats.same_entity_consistent == 1


def test_numbering_consistency_polisa_scenario() -> None:
    """Regression test for polisa scenario (doc_polisa_01):
    Two identical gold OSOBA mentions, only PESEL masked -> NumberingStats(0, 0, 0, 0).
    """
    text = "Jan Kowalski i Jan Kowalski oraz PESEL 44051401359."
    gold = [
        Span(0, 12, Label.OSOBA, "gold", 1.0, "valid"),
        Span(17, 29, Label.OSOBA, "gold", 1.0, "valid"),
        Span(35, 47, Label.PESEL, "gold", 1.0, "valid"),
    ]
    masked_spans = [Span(35, 47, Label.PESEL, "model", 1.0, "valid")]
    rendered = "Jan Kowalski i Jan Kowalski oraz [PESEL]."

    stats = numbering_consistency(
        rendered,
        gold,
        {Label.OSOBA},
        original=text,
        masked_spans=masked_spans,
    )
    assert stats == NumberingStats(0, 0, 0, 0)


def test_numbering_consistency_partial_masking_variants() -> None:
    """Test same-entity/different-entity numbering consistency edge cases:
    (b) same-entity pair both masked -> consistent 1/1.
    (c) one mention masked, its identical partner unmasked -> pair skipped (0/0).
    """
    text = "Anna Nowak i Anna Nowak oraz Katarzyna Wiśniewska."
    gold = [
        Span(0, 10, Label.OSOBA, "gold", 1.0, "valid"),
        Span(13, 23, Label.OSOBA, "gold", 1.0, "valid"),
        Span(29, 49, Label.OSOBA, "gold", 1.0, "valid"),
    ]

    masked_spans_b = [
        Span(0, 10, Label.OSOBA, "model", 1.0, "valid"),
        Span(13, 23, Label.OSOBA, "model", 1.0, "valid"),
    ]
    rendered_b = render_mask(text, masked_spans_b)
    stats_b = numbering_consistency(
        rendered_b,
        gold,
        {Label.OSOBA},
        original=text,
        masked_spans=masked_spans_b,
    )
    assert stats_b.same_entity_total == 1
    assert stats_b.same_entity_consistent == 1
    assert stats_b.different_entity_total == 0
    assert stats_b.different_entity_distinct == 0

    masked_spans_c = [Span(0, 10, Label.OSOBA, "model", 1.0, "valid")]
    rendered_c = render_mask(text, masked_spans_c)
    stats_c = numbering_consistency(
        rendered_c,
        gold,
        {Label.OSOBA},
        original=text,
        masked_spans=masked_spans_c,
    )
    assert stats_c == NumberingStats(0, 0, 0, 0)


def test_uc84_throughput_stats_and_ram() -> None:
    """UC-84: throughput_stats and peak_ram_bytes.

    Arithmetic for throughput_stats([0.1] * 10):
      - len = 10, sum = 1.0
      - docs_per_second = 10 / 1.0 = 10.0
      - p95: nearest-rank ceil(0.95 * 10) - 1 = 9 -> 0.1
    """
    latencies = [0.1] * 10
    tp = throughput_stats(latencies)
    assert tp.docs_per_second == 10.0
    assert tp.p95_latency_seconds == 0.1

    tp_empty = throughput_stats([])
    assert tp_empty == ThroughputStats(0.0, 0.0)

    lats_ordered = [0.1 * i for i in range(1, 11)]
    tp_ordered = throughput_stats(lats_ordered)
    assert tp_ordered.docs_per_second == 10.0 / sum(lats_ordered)
    assert tp_ordered.p95_latency_seconds == 1.0

    ram = peak_ram_bytes()
    assert isinstance(ram, int)
    assert ram > 0


def test_group_for_label_and_direct_identifiers() -> None:
    """Additional assertions for group_for_label and DIRECT_IDENTIFIERS."""
    assert group_for_label(Label.PESEL) == "Identyfikatory państwowe"
    assert group_for_label(Label.OSOBA) == "Identyfikacja osoby"
    assert Label.PESEL in DIRECT_IDENTIFIERS
    assert Label.OSOBA not in DIRECT_IDENTIFIERS
