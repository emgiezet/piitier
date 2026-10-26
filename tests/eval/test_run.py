"""Tests for evaluation runner and report generation (UC-90, UC-91) — PII-4-f."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]

_metrics_path = _root / "eval" / "metrics.py"
_metrics_spec = importlib.util.spec_from_file_location("eval.metrics", _metrics_path)
_metrics_mod = importlib.util.module_from_spec(_metrics_spec)
sys.modules["eval.metrics"] = _metrics_mod
assert _metrics_spec is not None and _metrics_spec.loader is not None
_metrics_spec.loader.exec_module(_metrics_mod)

_report_path = _root / "eval" / "report.py"
_report_spec = importlib.util.spec_from_file_location("eval.report", _report_path)
_report_mod = importlib.util.module_from_spec(_report_spec)
sys.modules["eval.report"] = _report_mod
assert _report_spec is not None and _report_spec.loader is not None
_report_spec.loader.exec_module(_report_mod)

_run_path = _root / "eval" / "run.py"
_run_spec = importlib.util.spec_from_file_location("eval.run", _run_path)
_run_mod = importlib.util.module_from_spec(_run_spec)
sys.modules["eval.run"] = _run_mod
assert _run_spec is not None and _run_spec.loader is not None
_run_spec.loader.exec_module(_run_mod)

write_report = _report_mod.write_report
BenchResult = _run_mod.BenchResult
EntityPRF = _metrics_mod.EntityPRF
LeakRate = _metrics_mod.LeakRate
NumberingStats = _metrics_mod.NumberingStats
ThroughputStats = _metrics_mod.ThroughputStats


def test_uc90_write_report_and_zero_gold(tmp_path: Path) -> None:
    res = BenchResult(
        gold_spans_per_doc=[],
        pred_spans_per_doc=[],
        originals=["Test doc without PII."],
        rendered=["Test doc without PII."],
        doc_ids=["doc_0"],
        latencies=[0.01],
        threshold=0.0,
    )

    metrics = {
        "strict_micro": EntityPRF(0.0, 0.0, 0.0, 0, 0, 0),
        "strict_by_label": {},
        "partial_micro": EntityPRF(0.0, 0.0, 0.0, 0, 0, 0),
        "partial_by_label": {},
        "risk_weighted_recall": 0.0,
        "leak_rate": LeakRate(0, 1, 0, 0, []),
        "fidelity": 0,
        "numbering": NumberingStats(0, 0, 0, 0),
        "throughput": ThroughputStats(100.0, 0.01),
        "peak_ram": 1024,
    }

    report_file = tmp_path / "report.md"
    write_report(
        report_file,
        system_name="rules",
        system_version="0.1.0",
        bench_version="v1",
        split="dev",
        threshold=0.0,
        result=res,
        metrics=metrics,
    )

    content = report_file.read_text(encoding="utf-8")
    expected_headings = [
        "# Raport:",
        "## System",
        "## Benchmark",
        "## Sprzęt",
        "## Encje (strict)",
        "## Encje (partial)",
        "## Recall ważony ryzykiem",
        "## Leak rate",
        "## Wierność",
        "## Numeracja",
        "## Throughput",
    ]
    last_idx = 0
    for h in expected_headings:
        idx = content.find(h, last_idx)
        assert idx != -1, f"Missing heading {h!r} in report"
        last_idx = idx


def test_uc91_e2e_subprocess(tmp_path: Path) -> None:
    out_dir = tmp_path / "reports"
    cmd = [
        sys.executable,
        "-m",
        "eval.run",
        "--system",
        "rules",
        "--bench",
        "v1",
        "--split",
        "dev",
        "--out-dir",
        str(out_dir),
    ]
    env = {**os.environ, "PYTHONPATH": str(_root)}
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert res.returncode == 0, f"Subprocess failed: {res.stderr}"

    reports = list(out_dir.glob("*.md"))
    assert len(reports) == 1
    report_content = reports[0].read_text(encoding="utf-8")

    assert "PESEL" in report_content
    assert "IBAN" in report_content
    assert "NIP" in report_content
    assert "1.0000" in report_content


def test_test_split_stdout_and_final_numbers(tmp_path: Path) -> None:
    test_dir = _root / "bench" / "v1" / "test"
    test_dir.mkdir(parents=True, exist_ok=True)
    dummy_jsonl = test_dir / "test.jsonl"
    dummy_jsonl.write_text(
        '{"id": "doc_test_1", "doc_type": "polisa", '
        '"text": "Jan 12345678901", "spans": ['
        '{"start": 0, "end": 3, "label": "OSOBA", "text": "Jan"}, '
        '{"start": 4, "end": 15, "label": "PESEL", "text": "12345678901"}]}\n',
        encoding="utf-8",
    )

    try:
        out_dir = tmp_path / "reports"
        cmd = [
            sys.executable,
            "-m",
            "eval.run",
            "--system",
            "rules",
            "--bench",
            "v1",
            "--split",
            "test",
            "--out-dir",
            str(out_dir),
        ]
        env = {**os.environ, "PYTHONPATH": str(_root)}
        res = subprocess.run(cmd, capture_output=True, text=True, env=env)
        assert res.returncode == 0, f"Subprocess failed: {res.stderr}"
        assert "WARNING: Running on test split (final numbers)." in res.stdout

        reports = list(out_dir.glob("*.md"))
        assert len(reports) == 1
        report_content = reports[0].read_text(encoding="utf-8")
        assert "test (final numbers)" in report_content
    finally:
        if dummy_jsonl.exists():
            dummy_jsonl.unlink()
        if test_dir.exists() and not list(test_dir.iterdir()):
            test_dir.rmdir()

    res_obj = BenchResult(
        gold_spans_per_doc=[],
        pred_spans_per_doc=[],
        originals=["Test."],
        rendered=["Test."],
        doc_ids=["d1"],
        latencies=[0.1],
        threshold=None,
    )
    report_file = tmp_path / "final_report.md"
    write_report(
        report_file,
        system_name="rules",
        system_version="0.1.0",
        bench_version="v1",
        split="test",
        threshold=None,
        result=res_obj,
        metrics={},
        is_final=True,
    )
    content = report_file.read_text(encoding="utf-8")
    assert "test (final numbers)" in content
