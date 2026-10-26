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
    base_license: str | None = None
    bf16: bool = False
    calibration_file: Path | None = None
    calibration_target_recall: float = 0.98
    calibration_match: str = "strict"
    calibration_min_support: int = 100


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
    "base_license",
    "bf16",
    "calibration_file",
    "calibration_target_recall",
    "calibration_match",
    "calibration_min_support",
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
    base_license = str(data["base_license"]) if data.get("base_license") is not None else None
    bf16 = bool(data.get("bf16", False))
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

    # calibration_file: optional, resolved like eval_file
    calibration_file: Path | None = None
    if data.get("calibration_file") is not None:
        calibration_file = resolve_file_path(data["calibration_file"])
        if not calibration_file.exists():
            raise ConfigError(f"calibration_file does not exist: {calibration_file}")
        _check_test_split(calibration_file)
        if calibration_file == eval_file:
            raise ConfigError("calibration_file must not be the same file as eval_file")

    calibration_target_recall = float(data.get("calibration_target_recall", 0.98))
    calibration_match = str(data.get("calibration_match", "strict"))
    calibration_min_support = int(data.get("calibration_min_support", 100))

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
    if calibration_match not in {"strict", "partial"}:
        raise ConfigError(
            f"calibration_match must be 'strict' or 'partial', got {calibration_match!r}"
        )
    if not (0 < calibration_target_recall <= 1):
        raise ConfigError(
            f"calibration_target_recall must be in (0, 1], got {calibration_target_recall}"
        )
    if calibration_min_support < 1:
        raise ConfigError(f"calibration_min_support must be >= 1, got {calibration_min_support}")

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
        base_license=base_license,
        bf16=bf16,
        calibration_file=calibration_file,
        calibration_target_recall=calibration_target_recall,
        calibration_match=calibration_match,
        calibration_min_support=calibration_min_support,
    )
