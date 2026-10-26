"""Tests for per-document corpus metrics — PII-7 (UC-111, UC-112, UC-113)."""

from __future__ import annotations

import importlib.util
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
# UC-113: BenchResult has no flat gold_spans/pred_spans; report reflects per-doc
# ---------------------------------------------------------------------------


def test_uc113_bench_result_and_report_use_per_document_metrics(tmp_path: Path) -> None:
    """UC-113: BenchResult no longer has flat gold_spans/pred_spans; report reflects per-doc."""
    # gold_spans_per_doc: doc A has one PESEL span, doc B has none
    gold_per_doc = [[_pesel(0, 11)], []]
    # pred_spans_per_doc: doc A predicts the PESEL correctly, doc B predicts nothing
    pred_per_doc = [[_pesel(0, 11)], []]

    result = BenchResult(
        gold_spans_per_doc=gold_per_doc,
        pred_spans_per_doc=pred_per_doc,
        originals=["12345678901", "no pii here"],
        rendered=["[PESEL_1]", "no pii here"],
        doc_ids=["doc_a", "doc_b"],
        latencies=[0.01, 0.01],
        threshold=0.5,
    )

    # BenchResult must NOT have flat gold_spans / pred_spans attributes
    assert not hasattr(result, "gold_spans"), "gold_spans flat field must be removed"
    assert not hasattr(result, "pred_spans"), "pred_spans flat field must be removed"

    # gold count in report must equal sum of per-doc spans
    gold_count = sum(len(g) for g in result.gold_spans_per_doc)
    assert gold_count == 1

    # Verify report renders correctly
    report_file = tmp_path / "report.md"
    write_report(
        report_file,
        system_name="test",
        system_version="0.1",
        bench_version="v1",
        split="dev",
        threshold=0.5,
        result=result,
        metrics={
            "strict_micro": EntityPRF(1.0, 1.0, 1.0),
            "strict_by_label": {},
            "partial_micro": EntityPRF(1.0, 1.0, 1.0),
            "partial_by_label": {},
            "risk_weighted_recall": 1.0,
            "leak_rate": LeakRate(0, 2, 0, 1, []),
            "fidelity": 0,
            "numbering": NumberingStats(0, 0, 0, 0),
            "throughput": ThroughputStats(50.0, 0.02),
            "peak_ram": 2048,
        },
    )
    content = report_file.read_text(encoding="utf-8")
    # gold_count must appear as 1 in the report (not 2)
    assert "Liczba spanów gold: 1" in content
