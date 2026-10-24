"""Unit tests for eval/compare.py — compare logic, regression detection, edge cases."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------------------
# Dynamic module loading (mirrors pattern in test_metrics.py / test_run.py)
# ---------------------------------------------------------------------------

_root = Path(__file__).resolve().parents[2]
_compare_path = _root / "eval" / "compare.py"
_compare_spec = importlib.util.spec_from_file_location("eval.compare", _compare_path)
assert _compare_spec is not None and _compare_spec.loader is not None
_compare_mod = importlib.util.module_from_spec(_compare_spec)
sys.modules["eval.compare"] = _compare_mod
_compare_spec.loader.exec_module(_compare_mod)

_compare_fn: Callable[..., tuple[str, bool]] = _compare_mod.compare_reports
_main_fn: Callable[..., int] = _compare_mod.main


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _report(
    *,
    by_label: dict[str, dict[str, float]] | None = None,
    comparable_labels: list[str] | None = None,
    by_doc_type: dict[str, object] | None = None,
    comparable_strict_micro: dict[str, float] | None = None,
    leak_rate: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build a minimal report dict for testing."""
    return {
        "system": "test-system",
        "strict_by_label": by_label or {},
        "partial_by_label": {},
        "comparable_labels": comparable_labels or [],
        "comparable_strict_micro": comparable_strict_micro,
        "comparable_partial_micro": None,
        "by_doc_type": by_doc_type or {},
        "leak_rate": leak_rate,
    }


# ---------------------------------------------------------------------------
# Regression detection
# ---------------------------------------------------------------------------


def test_regression_flagged_on_recall_drop() -> None:
    """compare_reports returns regression=True when a comparable label drops >0.02 recall."""
    base = _report(
        by_label={"OSOBA": {"p": 0.9, "r": 0.8, "f1": 0.85}},
        comparable_labels=["OSOBA"],
        comparable_strict_micro={"p": 0.9, "r": 0.8, "f1": 0.85},
    )
    new = _report(
        by_label={"OSOBA": {"p": 0.9, "r": 0.75, "f1": 0.82}},  # drop = -0.05
        comparable_labels=["OSOBA"],
        comparable_strict_micro={"p": 0.9, "r": 0.75, "f1": 0.82},
    )

    table, regression = _compare_fn(base, new, threshold=0.02)

    assert regression is True
    assert "REGRESSION" in table
    assert "OSOBA" in table


def test_no_regression_within_threshold() -> None:
    """compare_reports returns regression=False when recall drop is below threshold."""
    base = _report(
        by_label={"EMAIL": {"p": 1.0, "r": 0.9, "f1": 0.95}},
        comparable_labels=["EMAIL"],
        comparable_strict_micro={"p": 1.0, "r": 0.9, "f1": 0.95},
    )
    # Drop is 0.01 — clearly within 0.02 threshold
    new = _report(
        by_label={"EMAIL": {"p": 1.0, "r": 0.89, "f1": 0.945}},
        comparable_labels=["EMAIL"],
        comparable_strict_micro={"p": 1.0, "r": 0.89, "f1": 0.945},
    )

    table, regression = _compare_fn(base, new, threshold=0.02)

    assert regression is False
    assert "No recall regression" in table


# ---------------------------------------------------------------------------
# Zero-gold edge cases
# ---------------------------------------------------------------------------


def test_zero_gold_label_not_in_base() -> None:
    """A comparable label present only in new report does not trigger regression."""
    base = _report(
        by_label={},
        comparable_labels=["PESEL"],
        comparable_strict_micro={"p": 0.0, "r": 0.0, "f1": 0.0},
    )
    new = _report(
        by_label={"PESEL": {"p": 0.8, "r": 0.8, "f1": 0.8}},
        comparable_labels=["PESEL"],
        comparable_strict_micro={"p": 0.8, "r": 0.8, "f1": 0.8},
    )

    table, regression = _compare_fn(base, new, threshold=0.02)

    assert regression is False
    assert "PESEL" in table


def test_zero_gold_label_not_in_new() -> None:
    """A label in base but absent in new triggers regression when drop > threshold."""
    base = _report(
        by_label={"NIP": {"p": 1.0, "r": 1.0, "f1": 1.0}},
        comparable_labels=["NIP"],
        comparable_strict_micro={"p": 1.0, "r": 1.0, "f1": 1.0},
    )
    new = _report(
        by_label={},
        comparable_labels=["NIP"],
        comparable_strict_micro={"p": 0.0, "r": 0.0, "f1": 0.0},
    )

    table, regression = _compare_fn(base, new, threshold=0.02)

    assert regression is True
    assert "NIP" in table
    assert "REGRESSION" in table


# ---------------------------------------------------------------------------
# Non-comparable labels do not trigger regression
# ---------------------------------------------------------------------------


def test_unmapped_label_recall_drop_not_regression() -> None:
    """A label NOT in comparable_labels that drops recall does NOT trigger regression."""
    base = _report(
        by_label={
            "OSOBA": {"p": 0.9, "r": 0.9, "f1": 0.9},
            "WIEK": {"p": 0.8, "r": 0.8, "f1": 0.8},
        },
        comparable_labels=["OSOBA"],  # WIEK is NOT in comparable subset
        comparable_strict_micro={"p": 0.9, "r": 0.9, "f1": 0.9},
    )
    new = _report(
        by_label={
            "OSOBA": {"p": 0.9, "r": 0.89, "f1": 0.89},  # tiny drop, within threshold
            "WIEK": {"p": 0.0, "r": 0.0, "f1": 0.0},  # large drop but not comparable
        },
        comparable_labels=["OSOBA"],
        comparable_strict_micro={"p": 0.9, "r": 0.89, "f1": 0.89},
    )

    table, regression = _compare_fn(base, new, threshold=0.02)

    assert regression is False


# ---------------------------------------------------------------------------
# Per-doc_type table
# ---------------------------------------------------------------------------


def test_per_doc_type_table_rendered() -> None:
    """compare_reports includes per-doc_type table when both reports have by_doc_type."""
    dt: dict[str, object] = {
        "polisa": {"strict_micro": {"p": 0.8, "r": 0.8, "f1": 0.8}},
        "szkoda": {"strict_micro": {"p": 0.7, "r": 0.7, "f1": 0.7}},
    }
    base = _report(by_doc_type=dt)
    new = _report(by_doc_type=dt)

    table, _ = _compare_fn(base, new, threshold=0.02)

    assert "Per-Doc-Type" in table
    assert "polisa" in table
    assert "szkoda" in table


# ---------------------------------------------------------------------------
# Leak rate section
# ---------------------------------------------------------------------------


def test_leak_rate_section_rendered() -> None:
    """compare_reports includes leak rate section when available."""
    lr: dict[str, object] = {
        "docs_leaked": 3,
        "docs_total": 10,
        "values_leaked": 5,
        "values_total": 20,
    }
    base = _report(leak_rate=lr)
    new = _report(leak_rate=lr)

    table, _ = _compare_fn(base, new)

    assert "Leak Rate" in table
    assert "3/10" in table


# ---------------------------------------------------------------------------
# Empty comparable_labels
# ---------------------------------------------------------------------------


def test_empty_comparable_labels() -> None:
    """When base has no comparable_labels the comparison runs without regression."""
    base = _report(by_label={"PESEL": {"p": 1.0, "r": 1.0, "f1": 1.0}}, comparable_labels=[])
    new = _report(by_label={}, comparable_labels=[])

    table, regression = _compare_fn(base, new, threshold=0.02)
    assert regression is False


# ---------------------------------------------------------------------------
# CLI exit codes
# ---------------------------------------------------------------------------


def test_cli_regression_exit_code(tmp_path: Path) -> None:
    """CLI exits 1 when regression detected."""
    base_d = _report(
        by_label={"OSOBA": {"p": 0.9, "r": 0.9, "f1": 0.9}},
        comparable_labels=["OSOBA"],
    )
    new_d = _report(
        by_label={"OSOBA": {"p": 0.9, "r": 0.8, "f1": 0.85}},  # drop 0.1 > 0.02
        comparable_labels=["OSOBA"],
    )
    base_path = tmp_path / "base.json"
    new_path = tmp_path / "new.json"
    base_path.write_text(json.dumps(base_d), encoding="utf-8")
    new_path.write_text(json.dumps(new_d), encoding="utf-8")

    rc = _main_fn([str(base_path), str(new_path), "--threshold", "0.02"])
    assert rc == 1


def test_cli_no_regression_exit_zero(tmp_path: Path) -> None:
    """CLI exits 0 when no regression detected."""
    rep = _report(
        by_label={"OSOBA": {"p": 0.9, "r": 0.9, "f1": 0.9}},
        comparable_labels=["OSOBA"],
    )
    base_path = tmp_path / "base.json"
    new_path = tmp_path / "new.json"
    base_path.write_text(json.dumps(rep), encoding="utf-8")
    new_path.write_text(json.dumps(rep), encoding="utf-8")

    rc = _main_fn([str(base_path), str(new_path)])
    assert rc == 0
