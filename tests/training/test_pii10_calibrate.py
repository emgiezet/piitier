"""Tests for PII-10: calibration on a separate split, minimum support, Wilson interval.

UC-140: config validation — calibration_file same as eval_file or train_file, bad
        match/recall, missing file on disk, bench/test/ rejection → ConfigError.
UC-141: main exits 2 when calibration_file absent from config; message names the key.
UC-142: unsupported (< min_support gold spans) → exit 1, reason unsupported, config unchanged.
UC-143: strict fails, partial succeeds — correct exit codes, exact threshold assertion,
        graded-score fixture kills "pick-lowest" and > vs >= mutations.
UC-144: Wilson interval and per-group recall verified against hand computation;
        doc_count in report; target_recall from config actually used; performance.
UC-145: only calibration_file is read by main(); eval_file is never opened;
        stub NerPredictor drives main([cfg]) without an external predictions file.

Run standalone: uv run pytest tests/training/test_pii10_calibrate.py
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import pytest
import yaml

from piitier.labels import Label
from piitier.spans import Span

# ---------------------------------------------------------------------------
# Bootstrap module loading so this file collects correctly when run alone.
# tests/training/__init__.py causes Python to look for 'training' inside
# tests/, shadowing the top-level package.  The importlib approach bypasses
# normal package resolution by registering modules directly in sys.modules,
# which is how the other tests/training/*.py files handle this problem.
# ---------------------------------------------------------------------------

_root = Path(__file__).resolve().parents[2]


def _ensure_module(name: str, rel: str) -> Any:
    if name not in sys.modules:
        path = _root / rel
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is not None and spec.loader is not None:
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
    return sys.modules.get(name)


# Load in dependency order before accessing any symbols
_ensure_module("eval.metrics", "eval/metrics.py")
_ensure_module("training.config", "training/config.py")
_ensure_module("training.train", "training/train.py")
_ensure_module("training.calibrate", "training/calibrate.py")

# Access exported symbols through sys.modules — no late `from ... import`
_cal_mod = sys.modules["training.calibrate"]
_cfg_mod = sys.modules["training.config"]

DocPrediction = _cal_mod.DocPrediction
ThresholdResult = _cal_mod.ThresholdResult
calibrate_threshold = _cal_mod.calibrate_threshold
wilson_interval = _cal_mod.wilson_interval
write_threshold = _cal_mod.write_threshold
calibrate_main = _cal_mod.main

ConfigError = _cfg_mod.ConfigError
load_config = _cfg_mod.load_config

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


class _StubPredictor:
    """Stub NerPredictor that cycles through a list of per-record prediction lists."""

    def __init__(self, per_record: list[list[Span]]) -> None:
        self._preds = per_record
        self._idx = 0

    def predict(self, text: str) -> list[Span]:
        spans = self._preds[self._idx % len(self._preds)]
        self._idx += 1
        return spans


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
        calibration_file=str(f),
    )
    with pytest.raises(ConfigError, match="must not be the same file as eval_file"):
        load_config(cfg)


def test_uc140_calibration_file_same_as_train_raises_config_error(tmp_path: Path) -> None:
    """UC-140: calibration_file resolving to same path as train_file → ConfigError."""
    train_f = tmp_path / "train.jsonl"
    eval_f = tmp_path / "eval.jsonl"
    train_f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    eval_f.write_text('{"text": "b", "spans": []}\n', encoding="utf-8")
    cfg = _make_config(
        tmp_path,
        train_file=str(train_f),
        eval_file=str(eval_f),
        output_dir=str(tmp_path / "out"),
        calibration_file=str(train_f),
    )
    with pytest.raises(ConfigError, match="must not be the same file as train_file"):
        load_config(cfg)


def test_uc140_calibration_file_different_from_eval_and_train_ok(tmp_path: Path) -> None:
    """UC-140: calibration_file different from eval_file and train_file → loads ok."""
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


def test_uc140_calibration_file_missing_from_disk_raises(tmp_path: Path) -> None:
    """UC-140: calibration_file pointing to a nonexistent file → ConfigError."""
    f = tmp_path / "data.jsonl"
    f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    cfg = _make_config(
        tmp_path,
        train_file=str(f),
        eval_file=str(f),
        output_dir=str(tmp_path / "out"),
        calibration_file=str(tmp_path / "no_such_file.jsonl"),
    )
    with pytest.raises(ConfigError, match="calibration_file does not exist"):
        load_config(cfg)


def test_uc140_calibration_file_in_bench_test_split_raises(tmp_path: Path) -> None:
    """UC-140: calibration_file under bench/**/test/ → ConfigError (test-split guard)."""
    bench_test = tmp_path / "bench" / "v1" / "test"
    bench_test.mkdir(parents=True)
    cal_f = bench_test / "cal.jsonl"
    cal_f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")

    other = tmp_path / "other.jsonl"
    other.write_text('{"text": "b", "spans": []}\n', encoding="utf-8")

    cfg = _make_config(
        tmp_path,
        train_file=str(other),
        eval_file=str(other),
        output_dir=str(tmp_path / "out"),
        calibration_file=str(cal_f),
    )
    with pytest.raises(ConfigError, match="forbidden"):
        load_config(cfg)


def test_uc140_calibration_match_fuzzy_raises_config_error(tmp_path: Path) -> None:
    """UC-140: calibration_match='fuzzy' → ConfigError naming the constraint."""
    f = tmp_path / "data.jsonl"
    f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    cfg = _make_config(
        tmp_path,
        train_file=str(f),
        eval_file=str(f),
        output_dir=str(tmp_path / "out"),
        calibration_match="fuzzy",
    )
    with pytest.raises(ConfigError, match="'strict' or 'partial'"):
        load_config(cfg)


def test_uc140_calibration_target_recall_too_high_raises_config_error(tmp_path: Path) -> None:
    """UC-140: calibration_target_recall=1.5 → ConfigError naming the constraint."""
    f = tmp_path / "data.jsonl"
    f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    cfg = _make_config(
        tmp_path,
        train_file=str(f),
        eval_file=str(f),
        output_dir=str(tmp_path / "out"),
        calibration_target_recall=1.5,
    )
    with pytest.raises(ConfigError, match=r"calibration_target_recall must be in \(0, 1\]"):
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
    with pytest.raises(ConfigError, match=r"calibration_target_recall must be in \(0, 1\]"):
        load_config(cfg)


def test_uc140_calibration_target_recall_nonnumeric_raises(tmp_path: Path) -> None:
    """UC-140 NIT: calibration_target_recall='x' → ConfigError, not raw ValueError."""
    f = tmp_path / "data.jsonl"
    f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    cfg = _make_config(
        tmp_path,
        train_file=str(f),
        eval_file=str(f),
        output_dir=str(tmp_path / "out"),
        calibration_target_recall="not_a_number",
    )
    with pytest.raises(ConfigError, match="calibration_target_recall"):
        load_config(cfg)


def test_uc140_calibration_min_support_nonnumeric_raises(tmp_path: Path) -> None:
    """UC-140 NIT: calibration_min_support='abc' → ConfigError, not raw ValueError."""
    f = tmp_path / "data.jsonl"
    f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    cfg = _make_config(
        tmp_path,
        train_file=str(f),
        eval_file=str(f),
        output_dir=str(tmp_path / "out"),
        calibration_min_support="abc",
    )
    with pytest.raises(ConfigError, match="calibration_min_support"):
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
    )
    original_bytes = cfg.read_bytes()
    ret = calibrate_main([str(cfg)])
    assert ret == 2
    assert cfg.read_bytes() == original_bytes
    assert "calibration_file" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# UC-142: unsupported — fewer gold spans than min_support
# ---------------------------------------------------------------------------


def _make_40_span_docs() -> list[DocPrediction]:
    """4 docs × 10 gold PESEL = 40 gold total; all predictions match."""
    return [
        DocPrediction(
            gold=[_span(j * 10, j * 10 + 5) for j in range(10)],
            pred=[_pred(j * 10, j * 10 + 5) for j in range(10)],
        )
        for _ in range(4)
    ]


def test_uc142_calibrate_threshold_unsupported_reason() -> None:
    """UC-142: calibrate_threshold returns reason='unsupported' when below min_support."""
    docs = _make_40_span_docs()
    result = calibrate_threshold(docs, target_recall=0.98, match="strict", min_support=100)
    assert result.reason == "unsupported"
    assert result.gold_span_count == 40
    assert result.target_met is False


def test_uc142_main_exits_1_config_unchanged_card_has_count_and_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UC-142: 40 gold spans < min_support=100 → exit 1, config unchanged, card records."""
    eval_f = tmp_path / "eval.jsonl"
    cal_f = tmp_path / "cal.jsonl"
    eval_f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")

    gold_json = [{"start": j * 10, "end": j * 10 + 5, "label": "PESEL"} for j in range(10)]
    _jsonl_file(cal_f, [{"id": str(i), "text": "t", "spans": gold_json} for i in range(4)])

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

    stub = _StubPredictor([[_pred(j * 10, j * 10 + 5) for j in range(10)]] * 4)
    monkeypatch.setattr(_cal_mod, "NerPredictor", lambda checkpoint, threshold: stub)

    ret = calibrate_main([str(cfg)])

    assert ret == 1
    assert cfg.read_bytes() == original_bytes, "config must be byte-identical after failure"
    card = (out_dir / "MODEL_CARD.md").read_text(encoding="utf-8")
    assert "unsupported" in card
    assert "40" in card
    assert "nie zapisano" in card  # no numeric threshold shown on failure


def test_uc142_match_mode_honoured_in_unsupported_branch() -> None:
    """UC-142 mutation: match parameter affects recall even in the unsupported branch."""
    # Gold: [0,10). Pred: [1,10) — strict miss, partial hit.
    docs = [DocPrediction(gold=[_span(0, 10)], pred=[_pred(1, 10)])]
    result_strict = calibrate_threshold(docs, target_recall=0.98, match="strict", min_support=100)
    result_partial = calibrate_threshold(docs, target_recall=0.98, match="partial", min_support=100)
    assert result_strict.reason == "unsupported"
    assert result_partial.reason == "unsupported"
    assert result_strict.recall == pytest.approx(0.0)
    assert result_partial.recall == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# UC-143: strict fails, partial succeeds — exact threshold
# ---------------------------------------------------------------------------


def _make_offset_docs() -> list[DocPrediction]:
    """3 docs; gold [0,10) and [20,30); pred [1,10) and [20,30).

    Strict: only [20,30) matches → recall = 3/6 = 0.5.
    Partial: both match → recall = 6/6 = 1.0.
    """
    return [
        DocPrediction(gold=[_span(0, 10), _span(20, 30)], pred=[_pred(1, 10), _pred(20, 30)])
        for _ in range(3)
    ]


def test_uc143_calibrate_threshold_strict_returns_target_not_met() -> None:
    """UC-143: strict mode → target_not_met, recall = 0.5."""
    result = calibrate_threshold(_make_offset_docs(), target_recall=0.98, match="strict")
    assert result.reason == "target_not_met"
    assert abs(result.recall - 0.5) < 1e-6


def test_uc143_calibrate_threshold_partial_returns_success() -> None:
    """UC-143: partial mode → reason=None, target_met, recall ≥ 0.98."""
    result = calibrate_threshold(_make_offset_docs(), target_recall=0.98, match="partial")
    assert result.reason is None
    assert result.target_met is True
    assert result.recall >= 0.98


def test_uc143_strict_main_exits_1_config_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UC-143: strict mode main exits 1; config byte-identical; card shows nie zapisano."""
    eval_f = tmp_path / "eval.jsonl"
    cal_f = tmp_path / "cal.jsonl"
    eval_f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    gold_json = [
        {"start": 0, "end": 10, "label": "PESEL"},
        {"start": 20, "end": 30, "label": "PESEL"},
    ]
    _jsonl_file(cal_f, [{"id": str(i), "text": "t", "spans": gold_json} for i in range(3)])

    cfg = _make_config(
        tmp_path,
        train_file=str(eval_f),
        eval_file=str(eval_f),
        output_dir=str(tmp_path / "out"),
        calibration_file=str(cal_f),
        calibration_match="strict",
        calibration_target_recall=0.98,
        calibration_min_support=1,
    )
    original_bytes = cfg.read_bytes()
    stub = _StubPredictor([[_pred(1, 10), _pred(20, 30)]] * 3)
    monkeypatch.setattr(_cal_mod, "NerPredictor", lambda checkpoint, threshold: stub)

    ret = calibrate_main([str(cfg)])
    assert ret == 1
    assert cfg.read_bytes() == original_bytes
    card = (tmp_path / "out" / "MODEL_CARD.md").read_text(encoding="utf-8")
    assert "nie zapisano" in card


def test_uc143_partial_main_exits_0_threshold_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UC-143: partial mode main exits 0; threshold written to config."""
    eval_f = tmp_path / "eval.jsonl"
    cal_f = tmp_path / "cal.jsonl"
    eval_f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    gold_json = [
        {"start": 0, "end": 10, "label": "PESEL"},
        {"start": 20, "end": 30, "label": "PESEL"},
    ]
    _jsonl_file(cal_f, [{"id": str(i), "text": "t", "spans": gold_json} for i in range(3)])

    cfg = _make_config(
        tmp_path,
        train_file=str(eval_f),
        eval_file=str(eval_f),
        output_dir=str(tmp_path / "out"),
        calibration_file=str(cal_f),
        calibration_match="partial",
        calibration_target_recall=0.98,
        calibration_min_support=1,
    )
    stub = _StubPredictor([[_pred(1, 10), _pred(20, 30)]] * 3)
    monkeypatch.setattr(_cal_mod, "NerPredictor", lambda checkpoint, threshold: stub)

    assert calibrate_main([str(cfg)]) == 0
    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert data.get("threshold") is not None


def test_uc143_graded_scores_strict_selects_highest_valid_threshold() -> None:
    """UC-143 exact threshold: graded-score fixture, strict match.

    Gold: [0,5) [10,15) [20,25); preds at scores 0.9, 0.7, 0.5 respectively.
    t=0.9 → 1 pred → recall=1/3;  t=0.7 → 2 preds → recall=2/3;
    t=0.5 → all preds → recall=1.0 ≥ 0.98 — first hit: threshold=0.5.

    Also kills 'pick lowest threshold' and '>  vs >=' mutations.
    """
    gold = [_span(0, 5), _span(10, 15), _span(20, 25)]
    pred = [_pred(0, 5, score=0.9), _pred(10, 15, score=0.7), _pred(20, 25, score=0.5)]
    docs = [DocPrediction(gold=gold, pred=pred)]

    result = calibrate_threshold(docs, target_recall=0.98, match="strict")
    assert result.threshold == pytest.approx(0.5)
    assert result.target_met is True

    # target=0.6: t=0.7 gives recall=2/3≈0.67 ≥ 0.6 → first hit at 0.7
    result2 = calibrate_threshold(docs, target_recall=0.6, match="strict")
    assert result2.threshold == pytest.approx(0.7)


def test_uc143_graded_scores_partial_differs_from_strict() -> None:
    """UC-143: partial match selects a higher threshold than strict for the same fixture.

    Gold: [0,10). Pred: [1,10) at 0.9 (partial hit, strict miss); [0,10) at 0.5 (exact).
    Strict: first exact match at t=0.5 → threshold=0.5.
    Partial: overlap [1,10)∩[0,10) at t=0.9 → threshold=0.9 (higher).
    """
    gold = [_span(0, 10)]
    pred = [_pred(1, 10, score=0.9), _pred(0, 10, score=0.5)]
    docs = [DocPrediction(gold=gold, pred=pred)]

    result_strict = calibrate_threshold(docs, target_recall=0.98, match="strict")
    result_partial = calibrate_threshold(docs, target_recall=0.98, match="partial")

    assert result_strict.threshold == pytest.approx(0.5)
    assert result_partial.threshold == pytest.approx(0.9)
    assert result_partial.threshold > result_strict.threshold


def test_uc143_recall_exactly_equal_to_target_is_met() -> None:
    """UC-143: recall == target_recall is target_met (kills > vs >= mutation)."""
    docs = [DocPrediction(gold=[_span(0, 5), _span(10, 15)], pred=[_pred(0, 5)])]
    result = calibrate_threshold(docs, target_recall=0.5, match="strict")
    assert result.target_met is True, "recall == target must be recognised as target_met"
    assert abs(result.recall - 0.5) < 1e-9


# ---------------------------------------------------------------------------
# UC-144: Wilson interval, group recall, doc_count, performance
# ---------------------------------------------------------------------------


def _make_pesel_docs_90_recall() -> list[DocPrediction]:
    """10 docs × 10 gold PESEL; 9 matched per doc → recall=0.9, n=100, tp=90."""
    return [
        DocPrediction(
            gold=[_span(j * 10, j * 10 + 5) for j in range(10)],
            pred=[_pred(j * 10, j * 10 + 5) for j in range(9)],
        )
        for _ in range(10)
    ]


def test_uc144_wilson_interval_matches_hand_computation() -> None:
    """UC-144: Wilson interval equals hand-computed value to 4 decimal places."""
    docs = _make_pesel_docs_90_recall()
    result = calibrate_threshold(docs, target_recall=0.85, match="strict", min_support=0)

    n, tp = 100, 90
    z = 1.96
    p = tp / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    expected_lower = max(0.0, center - margin)
    expected_upper = min(1.0, center + margin)

    assert abs(result.wilson_lower - expected_lower) < 5e-5
    assert abs(result.wilson_upper - expected_upper) < 5e-5


def test_uc144_gold_span_count_and_doc_count() -> None:
    """UC-144: gold_span_count=100 and doc_count=10 in result."""
    result = calibrate_threshold(
        _make_pesel_docs_90_recall(), target_recall=0.85, match="strict", min_support=0
    )
    assert result.gold_span_count == 100
    assert result.doc_count == 10


def test_uc144_doc_count_appears_in_model_card(tmp_path: Path) -> None:
    """UC-144 mutation: doc_count must appear in MODEL_CARD section."""
    result = calibrate_threshold(
        _make_pesel_docs_90_recall(), target_recall=0.85, match="strict", min_support=0
    )
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        yaml.dump({"run": "t", "output_dir": str(tmp_path / "out"), "threshold": None}),
        encoding="utf-8",
    )
    write_threshold(cfg, result, target_recall=0.85, match_mode="strict")
    content = (tmp_path / "out" / "MODEL_CARD.md").read_text(encoding="utf-8")
    assert "10" in content  # doc_count == 10


def test_uc144_per_group_recall_pesel_group() -> None:
    """UC-144: all spans PESEL → 'Identyfikatory państwowe' recall=0.9, span_count=100."""
    result = calibrate_threshold(
        _make_pesel_docs_90_recall(), target_recall=0.85, match="strict", min_support=0
    )
    id_group = next(
        (gr for gr in result.group_recalls if gr.group == "Identyfikatory państwowe"), None
    )
    assert id_group is not None
    assert id_group.span_count == 100
    assert abs(id_group.recall - 0.9) < 1e-6


def test_uc144_calibration_target_recall_from_config_is_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UC-144 mutation: target_recall=0.8 from config is forwarded, not hard-coded.

    Fixture recall=0.9.  If code hard-codes 0.98: exit 1 (0.9 < 0.98).
    With correct forwarding: exit 0 (0.9 ≥ 0.8).
    """
    eval_f = tmp_path / "eval.jsonl"
    cal_f = tmp_path / "cal.jsonl"
    eval_f.write_text('{"text": "a", "spans": []}\n', encoding="utf-8")
    gold_json = [{"start": j * 10, "end": j * 10 + 5, "label": "PESEL"} for j in range(10)]
    _jsonl_file(cal_f, [{"id": str(i), "text": "t", "spans": gold_json} for i in range(10)])

    cfg = _make_config(
        tmp_path,
        train_file=str(eval_f),
        eval_file=str(eval_f),
        output_dir=str(tmp_path / "out"),
        calibration_file=str(cal_f),
        calibration_target_recall=0.8,
        calibration_min_support=1,
    )
    stub = _StubPredictor([[_pred(j * 10, j * 10 + 5) for j in range(9)]] * 10)
    monkeypatch.setattr(_cal_mod, "NerPredictor", lambda checkpoint, threshold: stub)

    assert calibrate_main([str(cfg)]) == 0, "recall=0.9 ≥ target=0.8 → must succeed"


def test_uc144_model_card_contains_wilson_and_groups(tmp_path: Path) -> None:
    """UC-144: MODEL_CARD has Wilson interval and group recall section."""
    result = calibrate_threshold(
        _make_pesel_docs_90_recall(), target_recall=0.85, match="strict", min_support=0
    )
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        yaml.dump({"run": "t", "output_dir": str(tmp_path / "out"), "threshold": None}),
        encoding="utf-8",
    )
    write_threshold(cfg, result, target_recall=0.85, match_mode="strict")
    content = (tmp_path / "out" / "MODEL_CARD.md").read_text(encoding="utf-8")
    assert "Przedział ufności Wilsona" in content
    assert "Recall per grupa ryzyka" in content
    assert "Identyfikatory państwowe" in content


def test_uc144_performance_2000_docs_finishes_under_10s() -> None:
    """UC-144 perf: 2000 docs × 5 spans, early-exit on first hit, completes in < 10 s."""
    n_docs, n_spans = 2000, 5
    docs = [
        DocPrediction(
            gold=[_span(j * 10, j * 10 + 5) for j in range(n_spans)],
            pred=[_pred(j * 10, j * 10 + 5, score=0.9) for j in range(n_spans)],
        )
        for _ in range(n_docs)
    ]
    t0 = time.monotonic()
    result = calibrate_threshold(docs, target_recall=0.98, match="strict", min_support=0)
    elapsed = time.monotonic() - t0
    assert result.target_met is True
    assert elapsed < 10.0, f"took {elapsed:.1f} s — early-exit optimisation may be missing"


# ---------------------------------------------------------------------------
# UC-145: only calibration_file read; eval_file never opened
# ---------------------------------------------------------------------------


def test_uc145_main_reads_calibration_file_not_eval_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UC-145: main([cfg]) reads calibration_file, never touches eval_file.

    Kills read_jsonl(config.calibration_file) → read_jsonl(config.eval_file) mutation.

    eval_file has 0 gold spans; if read, min_support=1 → exit 1 (unsupported).
    calibration_file has 25 gold spans, all predicted → exit 0 (success).
    """
    eval_f = tmp_path / "eval.jsonl"
    cal_f = tmp_path / "cal.jsonl"
    eval_f.write_text('{"text": "eval_text", "spans": []}\n', encoding="utf-8")

    gold_json = [{"start": j * 10, "end": j * 10 + 5, "label": "PESEL"} for j in range(5)]
    _jsonl_file(cal_f, [{"id": str(i), "text": "cal_text", "spans": gold_json} for i in range(5)])

    cfg = _make_config(
        tmp_path,
        train_file=str(eval_f),
        eval_file=str(eval_f),
        output_dir=str(tmp_path / "out"),
        calibration_file=str(cal_f),
        calibration_target_recall=0.98,
        calibration_min_support=1,
    )

    stub = _StubPredictor([[_pred(j * 10, j * 10 + 5, score=0.9) for j in range(5)]] * 5)
    monkeypatch.setattr(_cal_mod, "NerPredictor", lambda checkpoint, threshold: stub)

    accessed: list[Path] = []
    original_read = _cal_mod.read_jsonl

    def tracking_read(path: Path) -> list[dict[str, Any]]:
        accessed.append(path.resolve())
        return original_read(path)

    monkeypatch.setattr(_cal_mod, "read_jsonl", tracking_read)

    ret = calibrate_main([str(cfg)])

    assert ret == 0, (
        f"exit 0 expected; got {ret} — mutation may have swapped calibration_file for eval_file"
    )
    assert eval_f.resolve() not in accessed, (
        f"eval_file must never be passed to read_jsonl; accessed={accessed}"
    )
    assert cal_f.resolve() in accessed


def test_uc145_calibrate_threshold_uses_only_calibration_docs() -> None:
    """UC-145: calibrate_threshold on cal_docs differs from eval_docs (control)."""
    cal_docs = [
        DocPrediction(gold=[_span(0, 5), _span(10, 15)], pred=[_pred(0, 5), _pred(10, 15)])
        for _ in range(5)
    ]
    eval_docs = [
        DocPrediction(gold=[_span(0, 5), _span(10, 15)], pred=[_pred(0, 5)]) for _ in range(5)
    ]
    result_cal = calibrate_threshold(cal_docs, target_recall=0.98, match="strict", min_support=1)
    result_eval = calibrate_threshold(eval_docs, target_recall=0.98, match="strict", min_support=1)
    assert result_cal.target_met is True
    assert result_eval.target_met is False


# ---------------------------------------------------------------------------
# Backward-compat / regression
# ---------------------------------------------------------------------------


def test_write_threshold_success_writes_config_and_model_card(tmp_path: Path) -> None:
    """Backward compat: write_threshold with reason=None writes config and MODEL_CARD."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        yaml.dump({"run": "t", "output_dir": str(tmp_path / "out"), "threshold": None}),
        encoding="utf-8",
    )
    res = ThresholdResult(threshold=0.42, recall=0.99, precision=0.85, target_met=True)
    write_threshold(cfg, res, target_recall=0.98, doc_count=10)

    assert yaml.safe_load(cfg.read_text(encoding="utf-8"))["threshold"] == pytest.approx(0.42)
    card = (tmp_path / "out" / "MODEL_CARD.md").read_text(encoding="utf-8")
    assert "Kalibracja progu" in card
    assert "0.42" in card


def test_write_threshold_failure_preserves_previous_success_section(tmp_path: Path) -> None:
    """Failure run keeps config byte-identical and preserves the previous success threshold."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        yaml.dump({"run": "t", "output_dir": str(tmp_path / "out"), "threshold": None}),
        encoding="utf-8",
    )
    success = ThresholdResult(threshold=0.7, recall=0.99, precision=0.95, target_met=True)
    write_threshold(cfg, success, target_recall=0.98, doc_count=5)
    config_after_success = cfg.read_bytes()
    card_after_success = (tmp_path / "out" / "MODEL_CARD.md").read_text(encoding="utf-8")
    assert "0.7" in card_after_success

    failure = ThresholdResult(
        threshold=0.0, recall=0.5, precision=0.9, target_met=False, reason="target_not_met"
    )
    write_threshold(cfg, failure, target_recall=0.98, doc_count=5)

    assert cfg.read_bytes() == config_after_success, "config unchanged after failure"
    card = (tmp_path / "out" / "MODEL_CARD.md").read_text(encoding="utf-8")
    assert "0.7" in card, "previous success threshold still visible"
    assert "nie zapisano" in card
    assert "target_not_met" in card


def test_wilson_interval_zero_n_returns_max_uncertainty() -> None:
    """NIT: wilson_interval(0, 0) → (0.0, 1.0), not (0.0, 0.0)."""
    lower, upper = wilson_interval(0, 0)
    assert lower == pytest.approx(0.0)
    assert upper == pytest.approx(1.0)


def test_wilson_interval_score_none_included_in_candidates() -> None:
    """NIT: score=None is coerced to 1.0 and added to the candidate set.

    Without the fix, None scores are skipped from candidates; the null-score pred
    is always included (coerced to 1.0 at application time) regardless of t,
    but 1.0 is never a candidate threshold, so the returned threshold is 0.0.
    With the fix, 1.0 is a candidate and the function correctly returns t=1.0.
    """
    docs = [
        DocPrediction(
            gold=[_span(0, 5)],
            pred=[Span(0, 5, Label.PESEL, "pred", None, "valid")],
        )
    ]
    result = calibrate_threshold(docs, target_recall=0.98, match="strict")
    assert result.target_met is True
    assert result.threshold == pytest.approx(1.0)
