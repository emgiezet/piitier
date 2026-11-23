from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from transformers import EvalPrediction

from piitier.labels import Label
from piitier.spans import Span
from training.calibrate import (
    DocPrediction,
    ThresholdResult,
    calibrate_threshold,
    write_threshold,
)
from training.config import ConfigError, load_config
from training.train import bio_tag_names, compute_metrics_factory


def test_finding1_string_label_coercion_nonzero_recall() -> None:
    """Finding 1: gold/pred with string labels yield non-zero recall."""
    docs = [
        DocPrediction(
            gold=[Span(0, 11, Label.OSOBA, "gold", None, "valid")],
            pred=[Span(0, 11, "OSOBA", "pred", 1.0, "valid")],
        )
    ]
    res = calibrate_threshold(docs, target_recall=0.98)
    assert res.recall > 0.0
    assert res.precision > 0.0


def test_finding3_optional_config_keys_and_validation(
    tmp_path: Path,
) -> None:
    """Finding 3: test optional threshold, predict_checkpoint,
    int8_recall_tolerance, and unknown key rejection."""
    train_file = tmp_path / "train.jsonl"
    eval_file = tmp_path / "eval.jsonl"
    train_file.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    eval_file.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")

    # 1. Config without threshold loads successfully
    config_yaml = tmp_path / "config1.yaml"
    config_yaml.write_text(
        f"""
run: test
base_checkpoint: hf-internal-testing/tiny-random-bert
base_revision: main
train_file: {train_file.name}
eval_file: {eval_file.name}
seed: 42
max_steps: 1
per_device_batch_size: 1
learning_rate: 1e-4
max_length: 128
output_dir: out
""",
        encoding="utf-8",
    )
    cfg1 = load_config(config_yaml)
    assert cfg1.threshold is None
    assert cfg1.predict_checkpoint is None
    assert cfg1.int8_recall_tolerance == 0.01

    # 2. Config with predict_checkpoint: null and int8_recall_tolerance: 0.05
    config_yaml2 = tmp_path / "config2.yaml"
    config_yaml2.write_text(
        f"""
run: test
base_checkpoint: hf-internal-testing/tiny-random-bert
base_revision: main
train_file: {train_file.name}
eval_file: {eval_file.name}
seed: 42
max_steps: 1
per_device_batch_size: 1
learning_rate: 1e-4
max_length: 128
output_dir: out
predict_checkpoint: null
int8_recall_tolerance: 0.05
""",
        encoding="utf-8",
    )
    cfg2 = load_config(config_yaml2)
    assert cfg2.predict_checkpoint is None
    assert cfg2.int8_recall_tolerance == 0.05

    # 3. Unknown key still rejected
    config_yaml3 = tmp_path / "config3.yaml"
    config_yaml3.write_text(
        f"""
run: test
base_checkpoint: hf-internal-testing/tiny-random-bert
base_revision: main
train_file: {train_file.name}
eval_file: {eval_file.name}
seed: 42
max_steps: 1
per_device_batch_size: 1
learning_rate: 1e-4
max_length: 128
output_dir: out
unknown_key_here: true
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="Unknown config key"):
        load_config(config_yaml3)


def test_finding4_seqeval_strict_mode() -> None:
    """Finding 4: orphan I-OSOBA pred vs B-OSOBA gold is NOT
    counted as a hit in strict mode."""
    tag_names = bio_tag_names()
    b_osoba_idx = tag_names.index("B-OSOBA")
    i_osoba_idx = tag_names.index("I-OSOBA")

    num_tags = len(tag_names)
    predictions = np.zeros((1, 1, num_tags), dtype=np.float32)
    predictions[0, 0, i_osoba_idx] = 10.0

    label_ids = np.array([[b_osoba_idx]], dtype=np.int64)

    compute_metrics = compute_metrics_factory(tag_names)
    metrics = compute_metrics(EvalPrediction(predictions=predictions, label_ids=label_ids))

    assert metrics["recall"] == 0.0
    assert metrics["precision"] == 0.0
    assert metrics["f1"] == 0.0


def test_finding5_write_threshold_output_dir_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 5: write_threshold uses config-dir-relative output_dir
    when run from different cwd."""
    sub_dir = tmp_path / "configs"
    sub_dir.mkdir()
    out_dir = tmp_path / "custom_out"

    train_file = tmp_path / "train.jsonl"
    eval_file = tmp_path / "eval.jsonl"
    train_file.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    eval_file.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")

    config_yaml = sub_dir / "model.yaml"
    config_yaml.write_text(
        """
run: test
base_checkpoint: hf-internal-testing/tiny-random-bert
base_revision: main
train_file: ../train.jsonl
eval_file: ../eval.jsonl
seed: 42
max_steps: 1
per_device_batch_size: 1
learning_rate: 1e-4
max_length: 128
output_dir: ../custom_out
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    result = ThresholdResult(threshold=0.5, recall=0.99, precision=0.95, target_met=True)
    write_threshold(config_yaml, result, target_recall=0.98, doc_count=10)

    model_card = out_dir / "MODEL_CARD.md"
    assert model_card.exists()
    assert "Threshold calibration" in model_card.read_text(encoding="utf-8")
