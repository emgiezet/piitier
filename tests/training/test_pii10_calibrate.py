"""Tests for PII-10: calibration on a separate split, minimum support, Wilson interval.

UC-140: config validation — calibration_file same as eval_file, bad match/recall → ConfigError.
UC-141: main exits 2 when calibration_file absent from config; message names the key.
UC-142: unsupported (< min_support gold spans) → exit 1, reason unsupported, config unchanged.
UC-143: strict fails, partial succeeds → correct exit codes and config write behaviour.
UC-144: Wilson interval and per-group recall verified against hand computation.
UC-145: only calibration_file is read; eval_file is never accessed.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from piitier.labels import Label
from piitier.spans import Span
from training.calibrate import (
    DocPrediction,
    ThresholdResult,
    calibrate_threshold,
    wilson_interval,
    write_threshold,
)
from training.calibrate import main as calibrate_main
from training.config import ConfigError, load_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUIRED_BASE: dict[str, Any] = {
    "run": "test-run",
    "base_checkpoint": "fake-ckpt",
    "base_revision": "main",
    "seed": 42,
    "max_steps": 1,
    "per_device_batch_size": 1,
    "learning_rate": 1e-4,
    "max_length": 128,
}


def _make_config(tmp_path: Path, **overrides: Any) -> Path:
    """Write a minimal config YAML; callers supply train_file, eval_file, output_dir."""
    data = dict(_REQUIRED_BASE)
    data.update(overrides)
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.dump(data), encoding="utf-8")
    return cfg


def _jsonl_file(path: Path, records: list[dict[str, Any]]) -> Path:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )
    return path


def _span(start: int, end: int, label: Label = Label.PESEL, score: float = 1.0) -> Span:
    return Span(start, end, label, "gold", score, "valid")


def _pred(start: int, end: int, label: Label = Label.PESEL, score: float = 0.9) -> Span:
    return Span(start, end, label, "pred", score, "valid")


def _predictions_jsonl(path: Path, docs: list[DocPrediction]) -> Path:
    rows = []
    for doc in docs:
        rows.append(
            {
                "gold": [
                    {
                        "start": s.start,
                        "end": s.end,
                        "label": s.label.name if isinstance(s.label, Label) else s.label,
                    }
                    for s in doc.gold
                ],
                "pred": [
                    {
                        "start": s.start,
                        "end": s.end,
                        "label": s.label.name if isinstance(s.label, Label) else s.label,
                        "score": s.score,
                    }
                    for s in doc.pred
                ],
            }
        )
    return _jsonl_file(path, rows)


# ---------------------------------------------------------------------------
# UC-140: config validation
# ---------------------------------------------------------------------------


def test_uc140_calibration_file_same_as_eval_raises_config_error(tmp_path: Path) -> None:
    """UC-140: calibration_file resolving to same path as eval_file → ConfigError."""
    f = tmp_path / "data.jsonl"
    f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    cfg = _make_config(
        tmp_path,
        train_file=str(f),
        eval_file=str(f),
        output_dir=str(tmp_path / "out"),
        calibration_file=str(f),  # same as eval_file
    )
    with pytest.raises(ConfigError, match="calibration_file"):
        load_config(cfg)


def test_uc140_calibration_file_different_from_eval_ok(tmp_path: Path) -> None:
    """UC-140: calibration_file different from eval_file → loads successfully."""
    eval_f = tmp_path / "eval.jsonl"
    cal_f = tmp_path / "cal.jsonl"
    eval_f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    cal_f.write_text('{"text": "b", "spans": []}\n', encoding="utf-8")
    cfg = _make_config(
        tmp_path,
        train_file=str(eval_f),
        eval_file=str(eval_f),
        output_dir=str(tmp_path / "out"),
        calibration_file=str(cal_f),
    )
    config = load_config(cfg)
    assert config.calibration_file == cal_f.resolve()


def test_uc140_calibration_match_fuzzy_raises_config_error(tmp_path: Path) -> None:
    """UC-140: calibration_match='fuzzy' → ConfigError."""
    f = tmp_path / "data.jsonl"
    f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    cfg = _make_config(
        tmp_path,
        train_file=str(f),
        eval_file=str(f),
        output_dir=str(tmp_path / "out"),
        calibration_match="fuzzy",
    )
    with pytest.raises(ConfigError, match="calibration_match"):
        load_config(cfg)


def test_uc140_calibration_target_recall_too_high_raises_config_error(tmp_path: Path) -> None:
    """UC-140: calibration_target_recall=1.5 → ConfigError."""
    f = tmp_path / "data.jsonl"
    f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    cfg = _make_config(
        tmp_path,
        train_file=str(f),
        eval_file=str(f),
        output_dir=str(tmp_path / "out"),
        calibration_target_recall=1.5,
    )
    with pytest.raises(ConfigError, match="calibration_target_recall"):
        load_config(cfg)


def test_uc140_calibration_target_recall_zero_raises_config_error(tmp_path: Path) -> None:
    """UC-140: calibration_target_recall=0 (not in (0,1]) → ConfigError."""
    f = tmp_path / "data.jsonl"
    f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    cfg = _make_config(
        tmp_path,
        train_file=str(f),
        eval_file=str(f),
        output_dir=str(tmp_path / "out"),
        calibration_target_recall=0.0,
    )
    with pytest.raises(ConfigError, match="calibration_target_recall"):
        load_config(cfg)


# ---------------------------------------------------------------------------
# UC-141: main exits 2 when calibration_file absent
# ---------------------------------------------------------------------------


def test_uc141_main_exits_2_when_calibration_file_absent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """UC-141: main exits 2; message names 'calibration_file'; config byte-identical."""
    f = tmp_path / "data.jsonl"
    f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    cfg = _make_config(
        tmp_path,
        train_file=str(f),
        eval_file=str(f),
        output_dir=str(tmp_path / "out"),
        # no calibration_file key
    )
    original_bytes = cfg.read_bytes()

    ret = calibrate_main([str(cfg)])

    assert ret == 2
    assert cfg.read_bytes() == original_bytes, "config must be unchanged after exit 2"
    captured = capsys.readouterr()
    assert "calibration_file" in captured.err


# ---------------------------------------------------------------------------
# UC-142: unsupported — fewer gold spans than min_support
# ---------------------------------------------------------------------------


def _make_40_span_docs() -> list[DocPrediction]:
    """40 gold PESEL spans across 4 documents, all matched."""
    docs = []
    for _i in range(4):
        gold = [_span(j * 10, j * 10 + 5) for j in range(10)]
        pred = [_pred(j * 10, j * 10 + 5) for j in range(10)]
        docs.append(DocPrediction(gold=gold, pred=pred))
    return docs


def test_uc142_unsupported_exits_1_config_unchanged_model_card_has_count(
    tmp_path: Path,
) -> None:
    """UC-142: 40 gold spans < min_support=100 → exit 1, reason unsupported, config unchanged."""
    eval_f = tmp_path / "eval.jsonl"
    cal_f = tmp_path / "cal.jsonl"
    eval_f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    cal_f.write_text('{"text": "b", "spans": []}\n', encoding="utf-8")

    out_dir = tmp_path / "out"
    cfg = _make_config(
        tmp_path,
        train_file=str(eval_f),
        eval_file=str(eval_f),
        output_dir=str(out_dir),
        calibration_file=str(cal_f),
        calibration_min_support=100,
        calibration_target_recall=0.98,
    )
    original_bytes = cfg.read_bytes()

    pred_file = _predictions_jsonl(tmp_path / "preds.jsonl", _make_40_span_docs())

    ret = calibrate_main([str(cfg), str(pred_file)])

    assert ret == 1
    assert cfg.read_bytes() == original_bytes, "config must be byte-identical after failure"

    # MODEL_CARD must record count and reason
    model_card = out_dir / "MODEL_CARD.md"
    assert model_card.exists(), "MODEL_CARD.md must be written even on failure"
    content = model_card.read_text(encoding="utf-8")
    assert "unsupported" in content
    assert "40" in content  # gold span count


def test_uc142_calibrate_threshold_unsupported_reason(tmp_path: Path) -> None:
    """UC-142: calibrate_threshold returns reason='unsupported' when below min_support."""
    docs = _make_40_span_docs()
    result = calibrate_threshold(docs, target_recall=0.98, match="strict", min_support=100)
    assert result.reason == "unsupported"
    assert result.gold_span_count == 40
    assert result.target_met is False


# ---------------------------------------------------------------------------
# UC-143: strict fails, partial succeeds (hand-built fixture)
# ---------------------------------------------------------------------------


def _make_strict_partial_docs() -> list[DocPrediction]:
    """Fixture where strict recall < target but partial recall >= target.

    Gold: [0,10) and [20,30) per doc.
    Pred: [1,10) (off-by-one, strict miss) and [20,30) (strict match).
    Strict recall = 1/2 = 0.50.
    Partial recall = 2/2 = 1.00 (overlap at [1,10) and exact at [20,30)).
    3 docs → consistent ratios.
    """
    docs = []
    for _ in range(3):
        gold = [_span(0, 10, Label.PESEL), _span(20, 30, Label.PESEL)]
        pred_strict = [
            _pred(1, 10, Label.PESEL),  # overlaps but different start → strict miss
            _pred(20, 30, Label.PESEL),  # exact match
        ]
        docs.append(DocPrediction(gold=gold, pred=pred_strict))
    return docs


def test_uc143_strict_mode_target_not_met_config_unchanged(tmp_path: Path) -> None:
    """UC-143: strict mode → exit 1, target_not_met, config byte-identical."""
    eval_f = tmp_path / "eval.jsonl"
    cal_f = tmp_path / "cal.jsonl"
    eval_f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    cal_f.write_text('{"text": "b", "spans": []}\n', encoding="utf-8")

    out_dir = tmp_path / "out"
    cfg = _make_config(
        tmp_path,
        train_file=str(eval_f),
        eval_file=str(eval_f),
        output_dir=str(out_dir),
        calibration_file=str(cal_f),
        calibration_match="strict",
        calibration_target_recall=0.98,
        calibration_min_support=1,
    )
    original_bytes = cfg.read_bytes()

    pred_file = _predictions_jsonl(tmp_path / "preds.jsonl", _make_strict_partial_docs())
    ret = calibrate_main([str(cfg), str(pred_file)])

    assert ret == 1
    assert cfg.read_bytes() == original_bytes, "config must be byte-identical when strict fails"
    # MODEL_CARD reason recorded
    card = (out_dir / "MODEL_CARD.md").read_text(encoding="utf-8")
    assert "target_not_met" in card


def test_uc143_partial_mode_target_met_threshold_written_to_config(tmp_path: Path) -> None:
    """UC-143: partial mode → exit 0, highest valid threshold written to config."""
    eval_f = tmp_path / "eval.jsonl"
    cal_f = tmp_path / "cal.jsonl"
    eval_f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    cal_f.write_text('{"text": "b", "spans": []}\n', encoding="utf-8")

    out_dir = tmp_path / "out"
    cfg = _make_config(
        tmp_path,
        train_file=str(eval_f),
        eval_file=str(eval_f),
        output_dir=str(out_dir),
        calibration_file=str(cal_f),
        calibration_match="partial",
        calibration_target_recall=0.98,
        calibration_min_support=1,
    )

    pred_file = _predictions_jsonl(tmp_path / "preds.jsonl", _make_strict_partial_docs())
    ret = calibrate_main([str(cfg), str(pred_file)])

    assert ret == 0
    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert data.get("threshold") is not None, "threshold must be written to config on success"
    # Partial recall is 1.0, so the highest threshold that still achieves >=0.98 is chosen
    assert data["threshold"] >= 0.0


def test_uc143_calibrate_threshold_strict_returns_target_not_met() -> None:
    """UC-143: calibrate_threshold strict → target_not_met when strict recall = 0.5."""
    docs = _make_strict_partial_docs()
    result = calibrate_threshold(docs, target_recall=0.98, match="strict", min_support=1)
    assert result.reason == "target_not_met"
    assert result.target_met is False
    assert abs(result.recall - 0.5) < 1e-6


def test_uc143_calibrate_threshold_partial_returns_success() -> None:
    """UC-143: calibrate_threshold partial → target_met, reason None, threshold chosen."""
    docs = _make_strict_partial_docs()
    result = calibrate_threshold(docs, target_recall=0.98, match="partial", min_support=1)
    assert result.reason is None
    assert result.target_met is True
    assert result.recall >= 0.98


# ---------------------------------------------------------------------------
# UC-144: Wilson interval and per-group recall match hand computation
# ---------------------------------------------------------------------------


def _make_pesel_docs_90_recall() -> list[DocPrediction]:
    """10 docs × 10 gold PESEL spans, 9 matched per doc → recall=0.9, n=100, tp=90."""
    docs = []
    for _ in range(10):
        # 10 gold spans at [0,5), [10,15), ..., [90,95)
        gold = [_span(j * 10, j * 10 + 5) for j in range(10)]
        # 9 predictions matching first 9 gold spans
        pred = [_pred(j * 10, j * 10 + 5) for j in range(9)]
        docs.append(DocPrediction(gold=gold, pred=pred))
    return docs


def test_uc144_wilson_interval_matches_hand_computation() -> None:
    """UC-144: Wilson interval in result equals hand-computed value to 4 decimal places."""
    docs = _make_pesel_docs_90_recall()
    # calibrate with low target so it succeeds (all gold = PESEL, recall=0.9 ≥ 0.85)
    result = calibrate_threshold(docs, target_recall=0.85, match="strict", min_support=0)

    # Hand computation: n=100, tp=90, p=0.9, z=1.96
    n, tp = 100, 90
    z = 1.96
    p = tp / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    expected_lower = max(0.0, center - margin)
    expected_upper = min(1.0, center + margin)

    # Tolerance = 0.5 × 10⁻⁴ (half unit in the 4th decimal place)
    assert abs(result.wilson_lower - expected_lower) < 5e-5, (
        f"wilson_lower={result.wilson_lower:.6f} != expected={expected_lower:.6f}"
    )
    assert abs(result.wilson_upper - expected_upper) < 5e-5, (
        f"wilson_upper={result.wilson_upper:.6f} != expected={expected_upper:.6f}"
    )


def test_uc144_gold_span_count_and_doc_count() -> None:
    """UC-144: result reports correct gold_span_count and doc_count."""
    docs = _make_pesel_docs_90_recall()
    result = calibrate_threshold(docs, target_recall=0.85, match="strict", min_support=0)
    assert result.gold_span_count == 100
    assert result.doc_count == 10


def test_uc144_per_group_recall_pesel_group() -> None:
    """UC-144: all spans are PESEL → 'Identyfikatory państwowe' group recall = 0.9."""
    docs = _make_pesel_docs_90_recall()
    result = calibrate_threshold(docs, target_recall=0.85, match="strict", min_support=0)

    id_group = next(
        (gr for gr in result.group_recalls if gr.group == "Identyfikatory państwowe"), None
    )
    assert id_group is not None, "group 'Identyfikatory państwowe' must appear in group_recalls"
    assert id_group.span_count == 100
    assert abs(id_group.recall - 0.9) < 1e-6


def test_uc144_model_card_contains_wilson_and_groups(tmp_path: Path) -> None:
    """UC-144: write_threshold puts Wilson interval and group recall into MODEL_CARD.md."""
    docs = _make_pesel_docs_90_recall()
    result = calibrate_threshold(docs, target_recall=0.85, match="strict", min_support=0)

    out_dir = tmp_path / "out"
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        yaml.dump({"run": "t", "output_dir": str(out_dir), "threshold": None}),
        encoding="utf-8",
    )

    write_threshold(cfg, result, target_recall=0.85, match_mode="strict")

    content = (out_dir / "MODEL_CARD.md").read_text(encoding="utf-8")
    assert "Przedział ufności Wilsona" in content
    assert "Recall per grupa ryzyka" in content
    assert "Identyfikatory państwowe" in content
    assert "0.9" in content  # recall appears as a number in MODEL_CARD


# ---------------------------------------------------------------------------
# UC-145: calibration reads only calibration_file, eval_file never touched
# ---------------------------------------------------------------------------


def test_uc145_only_calibration_file_is_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """UC-145: main uses calibration_file data only; eval_file is never read."""
    eval_f = tmp_path / "eval.jsonl"
    cal_f = tmp_path / "cal.jsonl"
    eval_f.write_text('{"text": "EVAL", "spans": []}\n', encoding="utf-8")
    cal_f.write_text('{"text": "CALIBRATION", "spans": []}\n', encoding="utf-8")

    out_dir = tmp_path / "out"
    cfg = _make_config(
        tmp_path,
        train_file=str(eval_f),
        eval_file=str(eval_f),
        output_dir=str(out_dir),
        calibration_file=str(cal_f),
        calibration_target_recall=0.98,
        calibration_min_support=1,
    )

    # Predictions derived from calibration_file B (different from eval_file A)
    # 5 docs with 5 gold PESEL spans each; all predicted → recall=1.0
    cal_docs = [
        DocPrediction(
            gold=[_span(j * 10, j * 10 + 5) for j in range(5)],
            pred=[_pred(j * 10, j * 10 + 5, score=0.9) for j in range(5)],
        )
        for _ in range(5)
    ]
    pred_file = _predictions_jsonl(tmp_path / "preds.jsonl", cal_docs)

    # Monkeypatch read_jsonl in calibrate module to detect if eval_file is accessed
    eval_file_path = eval_f.resolve()

    from training import calibrate as cal_mod

    original_read_jsonl = cal_mod.read_jsonl
    accessed_paths: list[Path] = []

    def tracking_read_jsonl(path: Path) -> list[dict[str, Any]]:
        accessed_paths.append(path.resolve())
        return original_read_jsonl(path)

    with patch.object(cal_mod, "read_jsonl", side_effect=tracking_read_jsonl):
        ret = calibrate_main([str(cfg), str(pred_file)])

    # Should succeed (recall=1.0 ≥ 0.98, enough support)
    assert ret == 0
    # eval_file must NOT have been passed to read_jsonl
    assert eval_file_path not in accessed_paths, (
        f"eval_file was unexpectedly accessed: {accessed_paths}"
    )
    # calibration predictions file was accessed
    assert pred_file.resolve() in accessed_paths


def test_uc145_calibrate_threshold_distinct_doc_sources() -> None:
    """UC-145: calibrate_threshold result reflects calibration docs, not eval docs."""
    # cal_docs: recall=1.0
    cal_docs = [
        DocPrediction(
            gold=[_span(0, 5), _span(10, 15)],
            pred=[_pred(0, 5), _pred(10, 15)],
        )
        for _ in range(5)
    ]
    # eval_docs (different): recall=0.5 — must NOT affect calibration
    eval_docs = [
        DocPrediction(
            gold=[_span(0, 5), _span(10, 15)],
            pred=[_pred(0, 5)],  # only half matched
        )
        for _ in range(5)
    ]
    # Calibrate only on cal_docs
    result_cal = calibrate_threshold(cal_docs, target_recall=0.98, match="strict", min_support=1)
    result_eval = calibrate_threshold(eval_docs, target_recall=0.98, match="strict", min_support=1)

    assert result_cal.target_met is True, "calibration file achieves target"
    assert result_eval.target_met is False, "eval file would not achieve target (control)"
    assert result_cal.gold_span_count == 10  # only cal_docs counted


# ---------------------------------------------------------------------------
# Backward-compat: existing write_threshold behaviour preserved
# ---------------------------------------------------------------------------


def test_write_threshold_success_writes_config_and_model_card(tmp_path: Path) -> None:
    """Backward compat: write_threshold with reason=None writes both config and MODEL_CARD."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        yaml.dump({"run": "t", "output_dir": str(tmp_path / "out"), "threshold": None}),
        encoding="utf-8",
    )
    res = ThresholdResult(threshold=0.42, recall=0.99, precision=0.85, target_met=True)
    write_threshold(cfg, res, target_recall=0.98, doc_count=10)

    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert data["threshold"] == pytest.approx(0.42)

    card = (tmp_path / "out" / "MODEL_CARD.md").read_text(encoding="utf-8")
    assert "Kalibracja progu" in card
    assert "0.42" in card


def test_write_threshold_failure_does_not_write_config(tmp_path: Path) -> None:
    """write_threshold with reason='target_not_met' → config untouched, MODEL_CARD written."""
    cfg = tmp_path / "config.yaml"
    original_text = yaml.dump({"run": "t", "output_dir": str(tmp_path / "out"), "threshold": None})
    cfg.write_text(original_text, encoding="utf-8")

    res = ThresholdResult(
        threshold=0.0,
        recall=0.5,
        precision=0.9,
        target_met=False,
        reason="target_not_met",
    )
    write_threshold(cfg, res, target_recall=0.98, doc_count=5)

    # Config must be byte-identical
    assert cfg.read_text(encoding="utf-8") == original_text

    # MODEL_CARD is still written
    card = (tmp_path / "out" / "MODEL_CARD.md").read_text(encoding="utf-8")
    assert "target_not_met" in card
    assert "Kalibracja progu" in card


def test_wilson_interval_hand_computation() -> None:
    """wilson_interval formula verified against direct arithmetic."""
    n, tp = 100, 90
    lower, upper = wilson_interval(tp, n)

    z = 1.96
    p = tp / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    expected_lower = max(0.0, center - margin)
    expected_upper = min(1.0, center + margin)

    assert abs(lower - expected_lower) < 1e-12
    assert abs(upper - expected_upper) < 1e-12
