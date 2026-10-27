from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

from piitier.spans import Span

_config_path = Path(__file__).resolve().parents[2] / "training" / "config.py"
_spec_cfg = importlib.util.spec_from_file_location("training.config", _config_path)
if _spec_cfg is not None and _spec_cfg.loader is not None:
    _config_mod = importlib.util.module_from_spec(_spec_cfg)
    sys.modules["training.config"] = _config_mod
    _spec_cfg.loader.exec_module(_config_mod)

_train_path = Path(__file__).resolve().parents[2] / "training" / "train.py"
_spec_train = importlib.util.spec_from_file_location("training.train", _train_path)
if _spec_train is not None and _spec_train.loader is not None:
    _train_mod = importlib.util.module_from_spec(_spec_train)
    sys.modules["training.train"] = _train_mod
    _spec_train.loader.exec_module(_train_mod)

_cal_path = Path(__file__).resolve().parents[2] / "training" / "calibrate.py"
_spec_cal = importlib.util.spec_from_file_location("training.calibrate", _cal_path)
if _spec_cal is not None and _spec_cal.loader is not None:
    _cal_mod = importlib.util.module_from_spec(_spec_cal)
    sys.modules["training.calibrate"] = _cal_mod
    _spec_cal.loader.exec_module(_cal_mod)

ThresholdResult = _cal_mod.ThresholdResult
DocPrediction = _cal_mod.DocPrediction
calibrate_threshold = _cal_mod.calibrate_threshold
write_threshold = _cal_mod.write_threshold


def test_uc75_calibrate_threshold_target_met() -> None:
    """UC-75: Hand-computed fixture where recall >= 0.98 is achievable up to threshold 0.5."""
    docs = [
        DocPrediction(
            gold=[Span(0, 5, "PESEL", "gold", 1.0, "valid")],
            pred=[
                Span(0, 5, "PESEL", "pred", 0.9, "valid"),
                Span(10, 15, "PESEL", "pred", 0.4, "valid"),
            ],
        ),
        DocPrediction(
            gold=[Span(20, 25, "IBAN", "gold", 1.0, "valid")],
            pred=[Span(20, 25, "IBAN", "pred", 0.5, "valid")],
        ),
        DocPrediction(
            gold=[Span(30, 35, "OSOBA", "gold", 1.0, "valid")],
            pred=[Span(30, 35, "OSOBA", "pred", 0.7, "valid")],
        ),
    ]

    result = calibrate_threshold(docs, target_recall=0.98)
    assert result.target_met is True
    assert result.threshold == 0.5
    assert result.recall >= 0.98


def test_uc76_calibrate_threshold_target_not_met() -> None:
    """UC-76: Fixture where even at threshold 0.0 recall < target."""
    docs = [
        DocPrediction(
            gold=[
                Span(0, 5, "PESEL", "gold", 1.0, "valid"),
                Span(10, 15, "IBAN", "gold", 1.0, "valid"),
            ],
            pred=[Span(0, 5, "PESEL", "pred", 0.5, "valid")],
        )
    ]

    result = calibrate_threshold(docs, target_recall=0.98)
    assert result.target_met is False
    assert result.threshold == 0.0
    assert result.recall == 0.5


def test_write_threshold(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "run: test\noutput_dir: " + str(tmp_path / "out") + "\nthreshold: null\n",
        encoding="utf-8",
    )
    res = ThresholdResult(threshold=0.42, recall=0.99, precision=0.85, target_met=True)
    write_threshold(config_path, res, target_recall=0.98, doc_count=10)

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert data["threshold"] == 0.42

    model_card = tmp_path / "out" / "MODEL_CARD.md"
    assert model_card.exists()
    content = model_card.read_text(encoding="utf-8")
    assert "Threshold calibration" in content
    assert "0.42" in content
