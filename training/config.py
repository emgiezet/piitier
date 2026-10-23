from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class TrainingConfig:
    run: str
    base_checkpoint: str
    base_revision: str
    train_file: Path
    eval_file: Path
    seed: int
    max_steps: int
    per_device_batch_size: int
    learning_rate: float
    max_length: int
    output_dir: Path
    threshold: float | None = None
    predict_checkpoint: str | None = None
    int8_recall_tolerance: float = 0.01


class ConfigError(Exception):
    """Raised when configuration loading or validation fails."""


_REQUIRED_KEYS = {
    "run",
    "base_checkpoint",
    "base_revision",
    "train_file",
    "eval_file",
    "seed",
    "max_steps",
    "per_device_batch_size",
    "learning_rate",
    "max_length",
    "output_dir",
}

_OPTIONAL_KEYS = {
    "threshold",
    "predict_checkpoint",
    "int8_recall_tolerance",
}


def _check_test_split(path: Path) -> None:
    resolved = path.resolve()
    parts = resolved.parts
    if "bench" in parts:
        bench_idx = parts.index("bench")
        if "test" in parts[bench_idx:]:
            raise ConfigError(f"Training on test split is forbidden: {path}")


def load_config(path: Path) -> TrainingConfig:
    if not path.exists():
        raise ConfigError(f"Config file does not exist: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        raise ConfigError(f"Failed to parse YAML config: {e}") from e

    if not isinstance(data, dict):
        raise ConfigError("Config must be a YAML mapping")

    for k in _REQUIRED_KEYS:
        if k not in data:
            raise ConfigError(f"Missing required config key: {k}")

    for k in data:
        if k not in _REQUIRED_KEYS and k not in _OPTIONAL_KEYS:
            raise ConfigError(f"Unknown config key: {k}")
    run = str(data["run"])
    base_checkpoint = str(data["base_checkpoint"])
    base_revision = str(data["base_revision"])
    seed = int(data["seed"])
    max_steps = int(data["max_steps"])
    per_device_batch_size = int(data["per_device_batch_size"])
    learning_rate = float(data["learning_rate"])
    max_length = int(data["max_length"])
    threshold = data["threshold"] if data.get("threshold") is not None else None
    if threshold is not None:
        threshold = float(threshold)

    predict_checkpoint = (
        str(data["predict_checkpoint"]) if data.get("predict_checkpoint") is not None else None
    )
    int8_recall_tolerance = (
        float(data["int8_recall_tolerance"]) if "int8_recall_tolerance" in data else 0.01
    )
    config_dir = path.parent

    def resolve_file_path(val: str | Path) -> Path:
        p = Path(val)
        if not p.is_absolute():
            cand = config_dir / p
            if cand.exists():
                p = cand
            else:
                cand2 = Path.cwd() / p
                if cand2.exists():
                    p = cand2
        return p.resolve()

    train_file = resolve_file_path(data["train_file"])
    eval_file = resolve_file_path(data["eval_file"])
    output_dir = Path(data["output_dir"])
    if not output_dir.is_absolute():
        output_dir = (config_dir / output_dir).resolve()

    if not train_file.exists():
        raise ConfigError(f"train_file does not exist: {train_file}")
    if not eval_file.exists():
        raise ConfigError(f"eval_file does not exist: {eval_file}")

    _check_test_split(train_file)
    _check_test_split(eval_file)

    if max_steps <= 0:
        raise ConfigError(f"max_steps must be > 0, got {max_steps}")
    if per_device_batch_size <= 0:
        raise ConfigError(f"per_device_batch_size must be > 0, got {per_device_batch_size}")
    if learning_rate <= 0:
        raise ConfigError(f"learning_rate must be > 0, got {learning_rate}")
    if not (0 < max_length <= 8192):
        raise ConfigError(f"max_length must be between 1 and 8192, got {max_length}")
    if threshold is not None and not (0 <= threshold <= 1):
        raise ConfigError(f"threshold must be between 0 and 1, got {threshold}")

    return TrainingConfig(
        run=run,
        base_checkpoint=base_checkpoint,
        base_revision=base_revision,
        train_file=train_file,
        eval_file=eval_file,
        seed=seed,
        max_steps=max_steps,
        per_device_batch_size=per_device_batch_size,
        learning_rate=learning_rate,
        max_length=max_length,
        output_dir=output_dir,
        threshold=threshold,
        predict_checkpoint=predict_checkpoint,
        int8_recall_tolerance=int8_recall_tolerance,
    )
