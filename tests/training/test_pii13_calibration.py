"""PII-13: bounded sweep, diagnostic artifact, and configurable inference device."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from piitier.labels import Label
from piitier.spans import Span

_root = Path(__file__).resolve().parents[2]


def _ensure_module(name: str, rel: str) -> None:
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, _root / rel)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)


for _name, _rel in (
    ("eval.metrics", "eval/metrics.py"),
    ("training.config", "training/config.py"),
    ("training.train", "training/train.py"),
    ("training.calibrate", "training/calibrate.py"),
):
    _ensure_module(_name, _rel)

cal = sys.modules["training.calibrate"]
config = sys.modules["training.config"]


def _span(start: int, score: float, source: str = "pred") -> Span:
    return Span(start, start + 4, Label.PESEL, source, score, "valid")


def _config(tmp_path: Path, **values: Any) -> Path:
    train = tmp_path / "train.jsonl"
    eval_file = tmp_path / "eval.jsonl"
    calibration = tmp_path / "cal.jsonl"
    train.write_text('{"text":"train","spans":[]}\n', encoding="utf-8")
    eval_file.write_text('{"text":"eval","spans":[]}\n', encoding="utf-8")
    calibration.write_text(
        json.dumps({"text": "xxxx", "spans": [{"start": 0, "end": 4, "label": "PESEL"}]}) + "\n",
        encoding="utf-8",
    )
    data: dict[str, Any] = {
        "run": "pii13-fixture",
        "base_checkpoint": "unused",
        "base_revision": "unused",
        "train_file": str(train),
        "eval_file": str(eval_file),
        "calibration_file": str(calibration),
        "seed": 42,
        "max_steps": 1,
        "per_device_batch_size": 1,
        "learning_rate": 0.0001,
        "max_length": 128,
        "output_dir": str(tmp_path / "out"),
        "calibration_min_support": 1,
    }
    data.update(values)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_uc155_grid_bounds_matching_work_and_reports_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gold = _span(0, 1.0, "gold")
    # 500 distinct false-positive scores, plus a hit at .015. At grid threshold
    # .01 the 491 false positives with scores .010..500 are retained.
    false_positives = [_span(10 + 5 * i, i / 1000) for i in range(1, 501)]
    docs = [cal.DocPrediction(gold=[gold], pred=[*false_positives, _span(0, 0.015)])]
    original = cal.corpus_entity_metrics
    calls = 0

    def counted(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(cal, "corpus_entity_metrics", counted)
    result = cal.calibrate_threshold(docs, target_recall=1.0, min_support=1)
    assert calls <= 101
    assert result.threshold == pytest.approx(0.01)
    assert result.recall == pytest.approx(1.0)
    assert result.precision == pytest.approx(1 / 492)


def test_uc155_exact_decimal_score_keeps_higher_precision() -> None:
    docs = [
        cal.DocPrediction(
            gold=[_span(0, 1.0, "gold")],
            pred=[_span(0, 0.29), _span(10, 0.285)],
        )
    ]
    result = cal.calibrate_threshold(docs, target_recall=1.0, min_support=1)
    assert result.threshold == 0.29
    assert result.recall == 1.0
    assert result.precision == 1.0


def test_uc155_score_just_below_grid_boundary_never_promotes_above_it() -> None:
    docs = [
        cal.DocPrediction(
            gold=[_span(0, 1.0, "gold")],
            pred=[_span(0, math.nextafter(1.0, 0.0)), _span(10, 0.95)],
        )
    ]
    result = cal.calibrate_threshold(docs, target_recall=1.0, min_support=1)
    assert result.threshold == 0.99
    assert result.recall == 1.0
    assert result.precision == 1.0


@pytest.mark.parametrize(
    "target, reason, chosen, last_recall",
    [(0.5, None, 0.76, 0.5), (1.0, "target_not_met", None, 0.5)],
)
def test_uc156_sweep_records_measured_success_and_failure(
    tmp_path: Path, target: float, reason: str | None, chosen: float | None, last_recall: float
) -> None:
    cfg = _config(tmp_path)
    docs = [
        cal.DocPrediction(
            gold=[_span(0, 1.0, "gold"), _span(5, 1.0, "gold")],
            pred=[_span(0, 0.76), _span(15, 0.76)],
        )
    ]
    result = cal.calibrate_threshold(docs, target_recall=target, min_support=1)
    original = cfg.read_bytes()
    cal.write_threshold(cfg, result, target_recall=target, match_mode="strict")
    sweep = json.loads((tmp_path / "out" / "calibration_sweep.json").read_text(encoding="utf-8"))
    assert sweep["run"] == "pii13-fixture"
    assert sweep["match"] == "strict"
    assert sweep["target_recall"] == target
    assert sweep["min_support"] == 1
    assert sweep["gold_spans"] == 2
    assert sweep["docs"] == 1
    assert sweep["chosen_threshold"] == chosen
    assert sweep["reason"] == reason
    assert sweep["stopped_early"] is (reason is None)
    assert sweep["points"] == (
        [{"threshold": 0.76, "recall": last_recall, "precision": 0.5, "tp": 1, "fp": 1, "fn": 1}]
        if reason is None
        else [
            {"threshold": 0.76, "recall": 0.5, "precision": 0.5, "tp": 1, "fp": 1, "fn": 1},
            {"threshold": 0.0, "recall": 0.5, "precision": 0.5, "tp": 1, "fp": 1, "fn": 1},
        ]
    )
    if reason is not None:
        assert cfg.read_bytes() == original


def test_uc156_unsupported_sweep_records_zero_candidate(tmp_path: Path) -> None:
    cfg = _config(tmp_path, calibration_min_support=100)
    result = cal.calibrate_threshold(
        [cal.DocPrediction(gold=[_span(0, 1.0, "gold")], pred=[_span(0, 0.5)])],
        min_support=100,
    )
    cal.write_threshold(cfg, result)
    sweep = json.loads((tmp_path / "out" / "calibration_sweep.json").read_text(encoding="utf-8"))
    assert sweep["reason"] == "unsupported"
    assert sweep["min_support"] == 100
    assert sweep["chosen_threshold"] is None
    assert sweep["points"] == [
        {"threshold": 0.0, "recall": 1.0, "precision": 1.0, "tp": 1, "fp": 0, "fn": 0}
    ]


def test_uc157_default_device_cpu(tmp_path: Path) -> None:
    assert config.load_config(_config(tmp_path)).calibration_device == "cpu"


@pytest.mark.parametrize("bad", ["", "   ", 123, None])
def test_uc157_invalid_device_rejected(tmp_path: Path, bad: Any) -> None:
    with pytest.raises(config.ConfigError, match="calibration_device must be a non-empty string"):
        config.load_config(_config(tmp_path, calibration_device=bad))


def test_uc157_main_uses_configured_device(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _config(tmp_path, calibration_device="cuda")
    devices: list[str] = []

    class Predictor:
        def __init__(self, checkpoint: str | Path, threshold: float, device: str) -> None:
            devices.append(device)

        def predict(self, text: str) -> list[Span]:
            return [_span(0, 0.9)]

    monkeypatch.setattr(cal, "NerPredictor", Predictor)
    assert cal.main([str(cfg)]) == 0
    assert devices == ["cuda"]
