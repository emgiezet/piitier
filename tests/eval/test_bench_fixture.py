"""Tests for bench v1 fixture (UC-89) — PII-4-f."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import piitier.rules.iban as iban_mod
import piitier.rules.nip as nip_mod
import piitier.rules.pesel as pesel_mod
from piitier.labels import Label

_root = Path(__file__).resolve().parents[2]

_metrics_path = _root / "eval" / "metrics.py"
_metrics_spec = importlib.util.spec_from_file_location("eval.metrics", _metrics_path)
_metrics_mod = importlib.util.module_from_spec(_metrics_spec)
sys.modules["eval.metrics"] = _metrics_mod
assert _metrics_spec is not None and _metrics_spec.loader is not None
_metrics_spec.loader.exec_module(_metrics_mod)

_run_path = _root / "eval" / "run.py"
_spec = importlib.util.spec_from_file_location("eval.run", _run_path)
_run_mod = importlib.util.module_from_spec(_spec)
sys.modules["eval.run"] = _run_mod
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(_run_mod)

read_bench = _run_mod.read_bench


def test_uc89_bench_fixture() -> None:
    bench_dir = Path("bench/v1/dev")
    docs = read_bench(bench_dir)
    assert len(docs) == 6

    all_labels = set()
    multi_mention_doc_found = False

    for doc in docs:
        for span in doc.gold:
            assert 0 <= span.start < span.end <= len(doc.text)
            assert isinstance(span.label, Label)
            all_labels.add(span.label)

            span_text = doc.text[span.start : span.end]
            assert span_text
            if span.label == Label.PESEL:
                assert pesel_mod.is_valid(span_text)
            elif span.label == Label.NIP:
                assert nip_mod.is_valid(span_text)
            elif span.label == Label.IBAN:
                assert iban_mod.is_valid(span_text)

        person_spans = [s for s in doc.gold if s.label == Label.OSOBA]
        if len(person_spans) >= 2:
            offsets = {(s.start, s.end) for s in person_spans}
            assert len(offsets) == len(person_spans)
            for s in person_spans:
                assert doc.text[s.start : s.end]
            multi_mention_doc_found = True

    assert len(all_labels) >= 8
    assert multi_mention_doc_found
