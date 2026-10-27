"""Tests for per-document corpus metrics — PII-7 (UC-111, UC-112, UC-113)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from piitier.labels import Label
from piitier.spans import Span

_root = Path(__file__).resolve().parents[2]

# Load eval.metrics
_metrics_path = _root / "eval" / "metrics.py"
_metrics_spec = importlib.util.spec_from_file_location("eval.metrics", _metrics_path)
_metrics_mod = importlib.util.module_from_spec(_metrics_spec)
sys.modules["eval.metrics"] = _metrics_mod
assert _metrics_spec is not None and _metrics_spec.loader is not None
_metrics_spec.loader.exec_module(_metrics_mod)

# Load eval.report and eval.run (needed for UC-113)
_report_path = _root / "eval" / "report.py"
_report_spec = importlib.util.spec_from_file_location("eval.report", _report_path)
_report_mod = importlib.util.module_from_spec(_report_spec)
sys.modules["eval.report"] = _report_mod
assert _report_spec is not None and _report_spec.loader is not None
_report_spec.loader.exec_module(_report_mod)

_run_path = _root / "eval" / "run.py"
_run_spec = importlib.util.spec_from_file_location("eval.run", _run_path)
_run_mod = importlib.util.module_from_spec(_run_spec)
sys.modules["eval.run"] = _run_mod
assert _run_spec is not None and _run_spec.loader is not None
_run_spec.loader.exec_module(_run_mod)

corpus_entity_metrics = _metrics_mod.corpus_entity_metrics
corpus_entity_metrics_by_label = _metrics_mod.corpus_entity_metrics_by_label
corpus_risk_weighted_recall = _metrics_mod.corpus_risk_weighted_recall
EntityPRF = _metrics_mod.EntityPRF
LeakRate = _metrics_mod.LeakRate
NumberingStats = _metrics_mod.NumberingStats
ThroughputStats = _metrics_mod.ThroughputStats

BenchResult = _run_mod.BenchResult
run_benchmark = _run_mod.run_benchmark
read_docs = _run_mod.read_docs
write_report = _report_mod.write_report


def _pesel(start: int, end: int) -> Span:
    return Span(start, end, Label.PESEL, "gold", 1.0, "valid")


def _iban(start: int, end: int) -> Span:
    return Span(start, end, Label.IBAN, "gold", 1.0, "valid")


# ---------------------------------------------------------------------------
# UC-111: corpus_entity_metrics — cross-document collision is not a hit
# ---------------------------------------------------------------------------


def test_uc111_cross_document_collision_is_not_a_hit() -> None:
    """UC-111: span in doc B cannot match gold in doc A even at same offsets."""
    # gold only in doc A; pred only in doc B — same offsets
    gold_docs = [[_pesel(10, 20)], []]
    pred_docs = [[], [_pesel(10, 20)]]

    prf = corpus_entity_metrics(gold_docs, pred_docs)
    assert prf.precision == 0.0
    assert prf.recall == 0.0
    assert prf.f1 == 0.0


def test_uc111_same_doc_same_span_is_a_hit() -> None:
    """UC-111: same span in same document → P = R = F1 = 1.0."""
    gold_docs = [[_pesel(10, 20)], []]
    pred_docs = [[_pesel(10, 20)], []]

    prf = corpus_entity_metrics(gold_docs, pred_docs)
    assert prf.precision == 1.0
    assert prf.recall == 1.0
    assert prf.f1 == 1.0


def test_uc111_values_equal_sum_per_document() -> None:
    """UC-111: corpus PRF equals manual micro-aggregate from per-doc TP/FP/FN."""
    # doc A: 1 gold, 1 pred matching → TP=1, FP=0, FN=0
    # doc B: 1 gold, 0 pred           → TP=0, FP=0, FN=1
    gold_docs = [[_pesel(0, 10)], [_iban(0, 10)]]
    pred_docs = [[_pesel(0, 10)], []]

    prf = corpus_entity_metrics(gold_docs, pred_docs)
    # total TP=1, FP=0, FN=1 → P=1.0, R=0.5
    assert prf.precision == 1.0
    assert prf.recall == 0.5
    assert pytest.approx(prf.f1, abs=1e-6) == 2 * 1.0 * 0.5 / (1.0 + 0.5)


def test_uc111_length_mismatch_raises() -> None:
    """UC-111: mismatched list lengths raise ValueError."""
    with pytest.raises(ValueError):
        corpus_entity_metrics([[_pesel(0, 5)]], [[], []])


# ---------------------------------------------------------------------------
# UC-112: corpus_entity_metrics_by_label and corpus_risk_weighted_recall
# ---------------------------------------------------------------------------


def test_uc112_by_label_collision_not_counted() -> None:
    """UC-112: cross-doc collision does not count as hit per label."""
    gold_docs = [[_pesel(10, 20)], []]
    pred_docs = [[], [_pesel(10, 20)]]

    by_label = corpus_entity_metrics_by_label(gold_docs, pred_docs)
    assert Label.PESEL in by_label
    prf = by_label[Label.PESEL]
    assert prf.recall == 0.0
    assert prf.precision == 0.0


def test_uc112_risk_weighted_recall_collision_not_counted() -> None:
    """UC-112: cross-doc collision does not raise risk-weighted recall."""
    gold_docs = [[_pesel(10, 20)], []]
    pred_docs = [[], [_pesel(10, 20)]]

    rwr = corpus_risk_weighted_recall(gold_docs, pred_docs)
    assert rwr == 0.0


def test_uc112_risk_weighted_recall_length_mismatch_raises() -> None:
    """UC-112: mismatched lengths raise ValueError."""
    with pytest.raises(ValueError):
        corpus_risk_weighted_recall([[_pesel(0, 5)]], [[], []])


# ---------------------------------------------------------------------------
# UC-113: run_benchmark + corpus metrics with cross-doc collision scenario
#
# Verifies end-to-end: read_docs (eval.run) → run_benchmark (eval.run) →
# corpus_entity_metrics / by_label / risk_weighted_recall → gold_spans count.
# Cross-doc collision: gold PESEL(0,11) only in doc A, pred PESEL(0,11) only in
# doc B → strict/partial micro, by-label PESEL, risk-weighted recall all 0;
# JSON gold_spans count == 1.
#
# This test FAILS on origin/main because:
#  (a) corpus_entity_metrics does not exist in old metrics.py
#  (b) BenchResult still has flat gold_spans/pred_spans fields
# ---------------------------------------------------------------------------


def test_uc113_run_benchmark_cross_doc_collision_all_metrics_zero(tmp_path: Path) -> None:
    """UC-113: cross-doc collision via run_benchmark → all P/R metrics 0, gold_count=1."""
    # Two-doc JSONL: doc A has PESEL gold at (0,11), doc B has no gold
    docs_file = tmp_path / "docs.jsonl"
    docs_file.write_text(
        json.dumps(
            {
                "id": "docA",
                "doc_type": "t",
                "text": "12345678901 X",
                "spans": [{"start": 0, "end": 11, "label": "PESEL", "text": "12345678901"}],
            }
        )
        + "\n"
        + json.dumps(
            {
                "id": "docB",
                "doc_type": "t",
                "text": "12345678901 Y",
                "spans": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    docs = read_docs(docs_file)

    class CrossDocSystem:
        """Predicts PESEL(0,11) ONLY for doc B (text ends with Y), nothing for doc A."""

        def predict(self, text: str) -> list[Span]:
            if text.endswith("Y"):
                return [Span(0, 11, Label.PESEL, "pred", 1.0, "valid")]
            return []

    result = run_benchmark(CrossDocSystem(), docs)

    # BenchResult must not carry flat gold_spans/pred_spans
    assert not hasattr(result, "gold_spans"), "flat gold_spans must be removed"
    assert not hasattr(result, "pred_spans"), "flat pred_spans must be removed"

    # Per-document structure
    assert len(result.gold_spans_per_doc) == 2
    assert len(result.gold_spans_per_doc[0]) == 1  # doc A has 1 gold span
    assert len(result.gold_spans_per_doc[1]) == 0  # doc B has no gold
    assert len(result.pred_spans_per_doc[0]) == 0  # doc A: no pred
    assert len(result.pred_spans_per_doc[1]) == 1  # doc B: pred PESEL(0,11)

    # Cross-doc collision → strict micro P=R=F1=0
    strict_micro = corpus_entity_metrics(
        result.gold_spans_per_doc, result.pred_spans_per_doc, match="strict"
    )
    assert strict_micro.precision == 0.0
    assert strict_micro.recall == 0.0
    assert strict_micro.f1 == 0.0

    # Partial micro also 0 (span offsets match but docs differ)
    partial_micro = corpus_entity_metrics(
        result.gold_spans_per_doc, result.pred_spans_per_doc, match="partial"
    )
    assert partial_micro.precision == 0.0
    assert partial_micro.recall == 0.0

    # By-label PESEL
    by_label = corpus_entity_metrics_by_label(
        result.gold_spans_per_doc, result.pred_spans_per_doc, match="strict"
    )
    assert Label.PESEL in by_label
    assert by_label[Label.PESEL].recall == 0.0
    assert by_label[Label.PESEL].precision == 0.0

    # Risk-weighted recall
    rwr = corpus_risk_weighted_recall(result.gold_spans_per_doc, result.pred_spans_per_doc)
    assert rwr == 0.0

    # JSON gold_spans count: sum of per-doc, not flat
    gold_count = sum(len(g) for g in result.gold_spans_per_doc)
    assert gold_count == 1

    # Report reflects the per-doc gold count correctly
    report_file = tmp_path / "report.md"
    write_report(
        report_file,
        system_name="cross-doc-test",
        system_version="0.0",
        bench_version="v0",
        split="dev",
        threshold=None,
        result=result,
        metrics={
            "strict_micro": strict_micro,
            "strict_by_label": by_label,
            "partial_micro": partial_micro,
            "partial_by_label": by_label,
            "risk_weighted_recall": rwr,
            "leak_rate": LeakRate(0, 2, 0, gold_count, [], 0),
            "fidelity": 0,
            "numbering": NumberingStats(0, 0, 0, 0),
            "throughput": ThroughputStats(100.0, 0.01),
            "peak_ram": 0,
        },
    )
    assert "Number of gold spans: 1" in report_file.read_text(encoding="utf-8")
