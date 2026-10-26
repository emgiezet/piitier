"""Tests for PII-7: per-document calibration and INT8 export gate (UC-114..UC-117)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from piitier.labels import Label
from piitier.spans import Span

_root = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Bootstrap module loading
# ---------------------------------------------------------------------------


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


# Metrics must be loaded before training modules
if "eval.metrics" not in sys.modules:
    _load("eval.metrics", _root / "eval" / "metrics.py")

if "training.config" not in sys.modules:
    _load("training.config", _root / "training" / "config.py")

if "training.train" not in sys.modules:
    _load("training.train", _root / "training" / "train.py")

if "training.calibrate" not in sys.modules:
    _load("training.calibrate", _root / "training" / "calibrate.py")

if "training.export_onnx" not in sys.modules:
    _load("training.export_onnx", _root / "training" / "export_onnx.py")

_cal_mod = sys.modules["training.calibrate"]
_export_mod = sys.modules["training.export_onnx"]

DocPrediction = _cal_mod.DocPrediction
calibrate_threshold = _cal_mod.calibrate_threshold
score_checkpoint = _export_mod.score_checkpoint
export_onnx = _export_mod.export_onnx
quantize_int8 = _export_mod.quantize_int8
main = _export_mod.main
OnnxNerPredictor = _export_mod.OnnxNerPredictor


def _span(start: int, end: int, label: Label, score: float = 1.0) -> Span:
    return Span(start, end, label, "gold", score, "valid")


# ---------------------------------------------------------------------------
# UC-114: calibrate_threshold uses per-document matching
# ---------------------------------------------------------------------------


def test_uc114_calibrate_per_document_no_cross_doc_match() -> None:
    """UC-114: recall at each threshold is computed per-document (cross-doc collision ignored)."""
    # Two documents with same offset spans of same label.
    # doc A gold: PESEL at (0,5); doc A pred: PESEL at (0,5) score=0.9
    # doc B gold: PESEL at (0,5); doc B pred: nothing
    # At t=0.9: doc A TP=1,FN=0; doc B TP=0,FN=1 → recall=0.5
    # At t=0.0: same → recall=0.5 (doc B still has no pred)
    docs = [
        DocPrediction(
            gold=[_span(0, 5, Label.PESEL)],
            pred=[_span(0, 5, Label.PESEL, score=0.9)],
        ),
        DocPrediction(
            gold=[_span(0, 5, Label.PESEL)],
            pred=[],
        ),
    ]
    result = calibrate_threshold(docs, target_recall=0.98)
    # No threshold achieves 0.98 recall since doc B always misses
    assert result.target_met is False
    assert result.recall == pytest.approx(0.5, abs=1e-6)


def test_uc114_calibrate_per_document_correct_threshold() -> None:
    """UC-114: chosen threshold matches manual per-document calculation."""
    # doc A gold: PESEL(0,5); pred: PESEL(0,5) score=0.8, PESEL(10,15) score=0.3
    # doc B gold: IBAN(0,10); pred: IBAN(0,10) score=0.6
    # At t=0.6: TP=2, FN=0 → recall=1.0 ≥ 0.98 → chosen
    # At t=0.7: doc B pred filtered → TP=1, FN=1 → recall=0.5 < 0.98
    docs = [
        DocPrediction(
            gold=[_span(0, 5, Label.PESEL)],
            pred=[
                _span(0, 5, Label.PESEL, score=0.8),
                _span(10, 15, Label.PESEL, score=0.3),
            ],
        ),
        DocPrediction(
            gold=[_span(0, 10, Label.IBAN)],
            pred=[_span(0, 10, Label.IBAN, score=0.6)],
        ),
    ]
    result = calibrate_threshold(docs, target_recall=0.98)
    assert result.target_met is True
    assert result.threshold == pytest.approx(0.6, abs=1e-9)
    assert result.recall == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# UC-115: score_checkpoint dispatch — integration (tiny HF checkpoint)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_uc115_score_checkpoint_directory_uses_pytorch(tmp_path: Path) -> None:
    """UC-115: directory → PyTorch NerPredictor even if model_int8.onnx is present."""
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    model_id = "hf-internal-testing/tiny-random-BertForTokenClassification"
    ckpt_dir = tmp_path / "checkpoint"
    ckpt_dir.mkdir()

    # Save full model (weights + tokenizer) to a local directory
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForTokenClassification.from_pretrained(model_id)
    model.save_pretrained(str(ckpt_dir))
    tokenizer.save_pretrained(str(ckpt_dir))

    # Drop a junk *.onnx file directly in ckpt_dir to simulate the buggy condition
    junk_onnx = ckpt_dir / "model_int8.onnx"
    junk_onnx.write_bytes(b"junk_onnx_bytes")

    records = [{"text": "Tekst testowy bez PII.", "spans": []}]

    # score_checkpoint on a directory must use NerPredictor (not OnnxNerPredictor)
    from piitier.ner.inference import NerPredictor

    original_init = NerPredictor.__init__
    calls: list[str] = []

    def patched_init(self: Any, **kwargs: Any) -> None:
        calls.append("NerPredictor")
        original_init(self, **kwargs)

    with patch.object(NerPredictor, "__init__", patched_init):
        f1, recall = score_checkpoint(ckpt_dir, records, threshold=0.0)

    assert "NerPredictor" in calls, "directory path must dispatch to NerPredictor"
    assert isinstance(f1, float)
    assert isinstance(recall, float)


@pytest.mark.integration
def test_uc115_score_checkpoint_onnx_file_uses_onnx_predictor(tmp_path: Path) -> None:
    """UC-115: .onnx file → OnnxNerPredictor."""
    model_id = "hf-internal-testing/tiny-random-BertForTokenClassification"
    onnx_path = export_onnx(model_id, tmp_path)

    records = [{"text": "Tekst testowy bez PII.", "spans": []}]

    calls: list[str] = []
    original_init = OnnxNerPredictor.__init__

    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        calls.append("OnnxNerPredictor")
        original_init(self, *args, **kwargs)

    with patch.object(OnnxNerPredictor, "__init__", patched_init):
        f1, recall = score_checkpoint(onnx_path, records, threshold=0.0)

    assert "OnnxNerPredictor" in calls, ".onnx path must dispatch to OnnxNerPredictor"
    assert isinstance(f1, float)
    assert isinstance(recall, float)


# ---------------------------------------------------------------------------
# UC-116: main exits 1 when recall_delta > int8_recall_tolerance
# ---------------------------------------------------------------------------


def test_uc116_main_exit1_when_recall_delta_exceeds_tolerance(tmp_path: Path) -> None:
    """UC-116: exit 1; export_report.json has fp32 from FP32 ONNX and nonzero recall_delta."""
    smoke_yaml = _root / "training" / "configs" / "pii-4-smoke.yaml"
    cfg_data = yaml.safe_load(smoke_yaml.read_text(encoding="utf-8"))
    out_dir = tmp_path / "out"
    cfg_data["output_dir"] = str(out_dir)
    cfg_data["int8_recall_tolerance"] = 0.0  # any positive delta triggers exit 1
    temp_cfg = tmp_path / "smoke.yaml"
    temp_cfg.write_text(yaml.safe_dump(cfg_data), encoding="utf-8")

    # Monkeypatch export/quantize so no real model download happens
    fake_onnx = tmp_path / "onnx" / "model.onnx"
    fake_onnx.parent.mkdir(parents=True, exist_ok=True)
    fake_onnx.write_bytes(b"fake_fp32")
    fake_int8 = tmp_path / "model_int8.onnx"
    fake_int8.write_bytes(b"fake_int8")

    def fake_export(checkpoint: Any, output_dir: Path) -> Path:
        dst = output_dir / "onnx" / "model.onnx"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b"fake_fp32")
        return dst

    def fake_quantize(onnx_path: Path, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake_int8")
        return output_path

    # FP32 recall = 0.8, INT8 recall = 0.7 → delta = 0.1 > tolerance 0.0
    call_count: list[int] = [0]

    def fake_score(
        checkpoint_or_dir: Any, records: Any, threshold: Any = None
    ) -> tuple[float, float]:
        call_count[0] += 1
        if call_count[0] == 1:
            return (0.8, 0.8)  # FP32
        return (0.7, 0.7)  # INT8

    with (
        patch.object(_export_mod, "export_onnx", fake_export),
        patch.object(_export_mod, "quantize_int8", fake_quantize),
        patch.object(_export_mod, "score_checkpoint", fake_score),
    ):
        exit_code = main([str(temp_cfg)])

    assert exit_code == 1

    report_path = out_dir / "export_report.json"
    assert report_path.exists()
    rep = json.loads(report_path.read_text(encoding="utf-8"))
    assert set(rep.keys()) >= {
        "fp32_f1",
        "fp32_recall",
        "int8_f1",
        "int8_recall",
        "f1_delta",
        "recall_delta",
    }
    # delta is nonzero and positive
    assert rep["recall_delta"] > 0.0


# ---------------------------------------------------------------------------
# UC-117: main exits 0 when recall_delta <= tolerance
# ---------------------------------------------------------------------------


def test_uc117_main_exit0_when_recall_delta_within_tolerance(tmp_path: Path) -> None:
    """UC-117: exit 0; report has all keys and deltas."""
    smoke_yaml = _root / "training" / "configs" / "pii-4-smoke.yaml"
    cfg_data = yaml.safe_load(smoke_yaml.read_text(encoding="utf-8"))
    out_dir = tmp_path / "out"
    cfg_data["output_dir"] = str(out_dir)
    cfg_data["int8_recall_tolerance"] = 0.05  # delta=0.02 ≤ 0.05 → OK
    temp_cfg = tmp_path / "smoke.yaml"
    temp_cfg.write_text(yaml.safe_dump(cfg_data), encoding="utf-8")

    def fake_export(checkpoint: Any, output_dir: Path) -> Path:
        dst = output_dir / "onnx" / "model.onnx"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b"fake_fp32")
        return dst

    def fake_quantize(onnx_path: Path, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake_int8")
        return output_path

    call_count: list[int] = [0]

    def fake_score(
        checkpoint_or_dir: Any, records: Any, threshold: Any = None
    ) -> tuple[float, float]:
        call_count[0] += 1
        if call_count[0] == 1:
            return (0.85, 0.85)  # FP32
        return (0.83, 0.83)  # INT8  delta=0.02

    with (
        patch.object(_export_mod, "export_onnx", fake_export),
        patch.object(_export_mod, "quantize_int8", fake_quantize),
        patch.object(_export_mod, "score_checkpoint", fake_score),
    ):
        exit_code = main([str(temp_cfg)])

    assert exit_code == 0

    report_path = out_dir / "export_report.json"
    assert report_path.exists()
    rep = json.loads(report_path.read_text(encoding="utf-8"))
    assert set(rep.keys()) >= {
        "fp32_f1",
        "fp32_recall",
        "int8_f1",
        "int8_recall",
        "f1_delta",
        "recall_delta",
    }
    assert rep["recall_delta"] == pytest.approx(0.02, abs=1e-6)
