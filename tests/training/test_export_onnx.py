from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

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

_export_path = Path(__file__).resolve().parents[2] / "training" / "export_onnx.py"
_spec_export = importlib.util.spec_from_file_location("training.export_onnx", _export_path)
if _spec_export is not None and _spec_export.loader is not None:
    _export_mod = importlib.util.module_from_spec(_spec_export)
    sys.modules["training.export_onnx"] = _export_mod
    _spec_export.loader.exec_module(_export_mod)

export_onnx = _export_mod.export_onnx
quantize_int8 = _export_mod.quantize_int8
exceeds_tolerance = _export_mod.exceeds_tolerance
main = _export_mod.main


@pytest.mark.integration
def test_uc77_export_onnx(tmp_path: Path) -> None:
    """UC-77: export_onnx on tiny checkpoint produces non-empty onnx/model.onnx."""
    model_id = "hf-internal-testing/tiny-random-BertForTokenClassification"
    onnx_path = export_onnx(model_id, tmp_path)

    assert onnx_path.exists()
    assert onnx_path.stat().st_size > 0
    assert onnx_path.name == "model.onnx"
    assert onnx_path.parent.name == "onnx"


@pytest.mark.integration
def test_uc78_export_quantize_and_main(tmp_path: Path) -> None:
    """UC-78: Full export, quantize_int8, export_report.json, and exceeds_tolerance."""
    model_id = "hf-internal-testing/tiny-random-BertForTokenClassification"
    onnx_path = export_onnx(model_id, tmp_path)

    int8_path = tmp_path / "model_int8.onnx"
    quantized = quantize_int8(onnx_path, int8_path)
    assert quantized.exists()
    assert quantized.stat().st_size > 0

    # Test exceeds_tolerance unit logic
    report = {"fp32_recall": 0.95, "int8_recall": 0.90}
    assert exceeds_tolerance(report, 0.01) is True
    assert exceeds_tolerance(report, 0.10) is False

    # Test running main with smoke config
    smoke_yaml = Path("training/configs/pii-4-smoke.yaml")
    if smoke_yaml.exists():
        cfg_data = yaml.safe_load(smoke_yaml.read_text(encoding="utf-8"))
        cfg_data["output_dir"] = str(tmp_path / "smoke_out")
        temp_cfg = tmp_path / "smoke.yaml"
        temp_cfg.write_text(yaml.safe_dump(cfg_data), encoding="utf-8")

        exit_code = main([str(temp_cfg)])
        assert exit_code == 0

        report_file = tmp_path / "smoke_out" / "export_report.json"
        assert report_file.exists()
        rep_data = json.loads(report_file.read_text(encoding="utf-8"))

        expected_keys = {
            "fp32_f1",
            "fp32_recall",
            "int8_f1",
            "int8_recall",
            "f1_delta",
            "recall_delta",
        }
        assert expected_keys.issubset(rep_data.keys())
        for k in expected_keys:
            assert 0.0 <= rep_data[k] <= 1.0 or -1.0 <= rep_data[k] <= 1.0
