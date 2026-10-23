from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

_config_path = Path(__file__).resolve().parents[2] / "training" / "config.py"
_spec = importlib.util.spec_from_file_location("training.config", _config_path)
if _spec is not None and _spec.loader is not None:
    _config_mod = importlib.util.module_from_spec(_spec)
    sys.modules["training.config"] = _config_mod
    _spec.loader.exec_module(_config_mod)

load_config = _config_mod.load_config
TrainingConfig = _config_mod.TrainingConfig
ConfigError = _config_mod.ConfigError


def test_uc72_load_config_valid(tmp_path: Path) -> None:
    """UC-72: load_config with valid YAML returns correct TrainingConfig."""
    fixture = tmp_path / "smoke.jsonl"
    fixture.write_text(
        '{"id": "1", "doc_type": "polisa", "text": "test", "spans": []}\n',
        encoding="utf-8",
    )

    config_data = {
        "run": "test-run",
        "base_checkpoint": "hf-internal-testing/tiny-random-BertForTokenClassification",
        "base_revision": "main",
        "train_file": str(fixture),
        "eval_file": str(fixture),
        "seed": 42,
        "max_steps": 10,
        "per_device_batch_size": 4,
        "learning_rate": 1e-4,
        "max_length": 64,
        "output_dir": str(tmp_path / "out"),
        "threshold": 0.5,
    }
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump(config_data), encoding="utf-8")

    cfg = load_config(cfg_file)
    assert cfg.run == "test-run"
    assert cfg.seed == 42
    assert cfg.max_steps == 10
    assert cfg.threshold == 0.5


def test_uc72_missing_key_raises(tmp_path: Path) -> None:
    """UC-72: missing key raises ConfigError naming the key."""
    fixture = tmp_path / "smoke.jsonl"
    fixture.write_text(
        '{"id": "1", "doc_type": "polisa", "text": "test", "spans": []}\n',
        encoding="utf-8",
    )

    config_data = {
        "run": "test-run",
        "base_revision": "main",
        "train_file": str(fixture),
        "eval_file": str(fixture),
        "seed": 42,
        "max_steps": 10,
        "per_device_batch_size": 4,
        "learning_rate": 1e-4,
        "max_length": 64,
        "output_dir": str(tmp_path / "out"),
        "threshold": None,
    }
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump(config_data), encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info:
        load_config(cfg_file)
    assert "base_checkpoint" in str(exc_info.value)


def test_uc72_unknown_key_raises(tmp_path: Path) -> None:
    """UC-72: unknown key raises ConfigError."""
    fixture = tmp_path / "smoke.jsonl"
    fixture.write_text(
        '{"id": "1", "doc_type": "polisa", "text": "test", "spans": []}\n',
        encoding="utf-8",
    )

    config_data = {
        "run": "test-run",
        "base_checkpoint": "foo",
        "base_revision": "main",
        "train_file": str(fixture),
        "eval_file": str(fixture),
        "seed": 42,
        "max_steps": 10,
        "per_device_batch_size": 4,
        "learning_rate": 1e-4,
        "max_length": 64,
        "output_dir": str(tmp_path / "out"),
        "threshold": None,
        "unknown_extra_key": 123,
    }
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump(config_data), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(cfg_file)


def test_uc72_nonexistent_file_raises(tmp_path: Path) -> None:
    """UC-72: non-existent train_file raises ConfigError."""
    config_data = {
        "run": "test-run",
        "base_checkpoint": "foo",
        "base_revision": "main",
        "train_file": str(tmp_path / "missing.jsonl"),
        "eval_file": str(tmp_path / "missing.jsonl"),
        "seed": 42,
        "max_steps": 10,
        "per_device_batch_size": 4,
        "learning_rate": 1e-4,
        "max_length": 64,
        "output_dir": str(tmp_path / "out"),
        "threshold": None,
    }
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump(config_data), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(cfg_file)


def test_uc72_test_split_guard(tmp_path: Path) -> None:
    """UC-72: path under bench/v1/test/ and symlink to it raises ConfigError; dev/ OK."""
    bench_dir = tmp_path / "bench" / "v1"
    test_dir = bench_dir / "test"
    dev_dir = bench_dir / "dev"
    test_dir.mkdir(parents=True, exist_ok=True)
    dev_dir.mkdir(parents=True, exist_ok=True)

    test_file = test_dir / "test.jsonl"
    test_file.write_text(
        '{"id": "1", "doc_type": "polisa", "text": "test", "spans": []}\n',
        encoding="utf-8",
    )

    dev_file = dev_dir / "dev.jsonl"
    dev_file.write_text(
        '{"id": "2", "doc_type": "polisa", "text": "test", "spans": []}\n',
        encoding="utf-8",
    )

    symlink_file = tmp_path / "symlink_test.jsonl"
    try:
        symlink_file.symlink_to(test_file)
    except OSError:
        pytest.skip("Symlinks not supported on this platform")

    def make_config(fpath: Path) -> Path:
        d = {
            "run": "test-run",
            "base_checkpoint": "foo",
            "base_revision": "main",
            "train_file": str(fpath),
            "eval_file": str(dev_file),
            "seed": 42,
            "max_steps": 10,
            "per_device_batch_size": 4,
            "learning_rate": 1e-4,
            "max_length": 64,
            "output_dir": str(tmp_path / "out"),
            "threshold": None,
        }
        cf = tmp_path / f"cfg_{fpath.name}.yaml"
        cf.write_text(yaml.dump(d), encoding="utf-8")
        return cf

    with pytest.raises(ConfigError):
        load_config(make_config(test_file))

    with pytest.raises(ConfigError):
        load_config(make_config(symlink_file))

    cfg = load_config(make_config(dev_file))
    assert cfg.train_file == dev_file.resolve()
