"""Tests for PII-9 — metric counts, undefined denominators, control systems,
report provenance, and PROTOCOL.md (UC-133..UC-139).
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from piitier.labels import Label
from piitier.spans import Span

_root = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Bootstrap: ensure eval package + submodules are importable.
# test_baselines.py loads eval.baselines when collected alphabetically before
# this file; when running in isolation we do it ourselves.
# ---------------------------------------------------------------------------
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# Pre-load eval package and eval.baselines into sys.modules before eval.run
# is loaded (eval.run does `from eval.baselines import ...` at the top level).
_baselines_dir = _root / "eval" / "baselines"
for _mod_name, _full_name in [
    ("__init__", "eval.baselines"),
    ("piitier_systems", "eval.baselines.piitier_systems"),
    ("control", "eval.baselines.control"),
    ("presidio_pl", "eval.baselines.presidio_pl"),
    ("bardsai_v2", "eval.baselines.bardsai_v2"),
    ("privacy_filter", "eval.baselines.privacy_filter"),
]:
    if _full_name not in sys.modules:
        _bpath = _baselines_dir / f"{_mod_name}.py"
        if _bpath.exists():
            _bspec = importlib.util.spec_from_file_location(_full_name, _bpath)
            if _bspec and _bspec.loader:
                _bmod = importlib.util.module_from_spec(_bspec)
                sys.modules[_full_name] = _bmod
                _bspec.loader.exec_module(_bmod)

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

corpus_entity_metrics = _metrics_mod.corpus_entity_metrics
corpus_risk_weighted_recall = _metrics_mod.corpus_risk_weighted_recall
EntityPRF = _metrics_mod.EntityPRF
LeakRate = _metrics_mod.LeakRate
NumberingStats = _metrics_mod.NumberingStats
ThroughputStats = _metrics_mod.ThroughputStats
leak_rate = _metrics_mod.leak_rate

write_report = _report_mod.write_report
BenchResult = _run_mod.BenchResult
main = _run_mod.main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pesel(start: int, end: int) -> Span:
    return Span(start, end, Label.PESEL, "gold", 1.0, "valid")


def _osoba(start: int, end: int) -> Span:
    return Span(start, end, Label.OSOBA, "gold", 1.0, "valid")


def _minimal_bench_result(
    originals: list[str],
    gold_per_doc: list[list[Span]],
    pred_per_doc: list[list[Span]],
) -> object:
    """Build a BenchResult-like object for write_report fixtures."""
    rendered = [orig for orig in originals]  # unchanged (no real masking)
    return BenchResult(
        gold_spans_per_doc=gold_per_doc,
        pred_spans_per_doc=pred_per_doc,
        originals=originals,
        rendered=rendered,
        doc_ids=[f"doc_{i}" for i in range(len(originals))],
        latencies=[0.01] * len(originals),
        threshold=None,
    )


# ---------------------------------------------------------------------------
# UC-133: corpus_entity_metrics tp/fp/fn fields filled correctly
# ---------------------------------------------------------------------------


def test_uc133_corpus_entity_metrics_counts() -> None:
    """UC-133: corpus_entity_metrics fills tp, fp, fn equal to manual count.

    Fixture (2 documents):
      doc A: gold PESEL [0,11), pred PESEL [0,11) → TP=1
      doc B: gold PESEL [5,16), pred PESEL [5,16) → TP=1
             gold OSOBA [20,30), no pred for OSOBA  → FN=1
             pred IBAN [40,50), no gold for IBAN     → FP=1

    Totals across corpus (strict micro):
      TP=2, FP=1, FN=1
      P = 2/(2+1) = 2/3
      R = 2/(2+1) = 2/3
      F1 = 2*2/(2*2+1+1) = 4/6 = 2/3
    """
    gold_docs = [
        [_pesel(0, 11)],
        [_pesel(5, 16), _osoba(20, 30)],
    ]
    pred_docs = [
        [_pesel(0, 11)],
        [
            _pesel(5, 16),
            Span(40, 50, Label.IBAN, "pred", 1.0, "valid"),
        ],
    ]

    prf = corpus_entity_metrics(gold_docs, pred_docs, match="strict")

    # tp/fp/fn equal manual count
    assert prf.tp == 2, f"expected tp=2, got {prf.tp}"
    assert prf.fp == 1, f"expected fp=1, got {prf.fp}"
    assert prf.fn == 1, f"expected fn=1, got {prf.fn}"

    # P/R/F1 values unchanged from arithmetic (non-zero denominators)
    assert prf.precision == pytest.approx(2 / 3)
    assert prf.recall == pytest.approx(2 / 3)
    assert prf.f1 == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# UC-134: zero-denominator → undefined (0/0) in markdown, null in JSON
# ---------------------------------------------------------------------------


def test_uc134_undefined_metric_for_zero_gold_and_zero_pred(tmp_path: Path) -> None:
    """UC-134: label with no gold and no pred → undefined in report.

    A two-document corpus has PESEL gold/pred in both docs and no OSOBA at all.
    P/R/F1 are 0.0 (float) when TP=FP=FN=0; the report layer detects undefined
    from counts and renders 'undefined (0/0)' in markdown and null in JSON.
    """
    gold_docs = [[_pesel(0, 11)], [_pesel(5, 16)]]
    pred_docs = [[_pesel(0, 11)], [_pesel(5, 16)]]

    prf_osoba = corpus_entity_metrics(
        [[s for s in g if s.label == Label.OSOBA] for g in gold_docs],
        [[s for s in p if s.label == Label.OSOBA] for p in pred_docs],
    )

    # TP=FP=FN=0 → P/R/F1 are 0.0; denominators are zero → undefined at report time
    assert prf_osoba.precision == 0.0
    assert prf_osoba.recall == 0.0
    assert prf_osoba.f1 == 0.0
    assert prf_osoba.tp == 0
    assert prf_osoba.fp == 0
    assert prf_osoba.fn == 0
    assert (prf_osoba.tp + prf_osoba.fp) == 0, "precision denominator = 0 → undefined"
    assert (prf_osoba.tp + prf_osoba.fn) == 0, "recall denominator = 0 → undefined"

    # write_report must produce 'undefined (0/0)' in markdown, not '0.0000'
    res = _minimal_bench_result(
        originals=["doc A text", "doc B text"],
        gold_per_doc=gold_docs,
        pred_per_doc=pred_docs,
    )
    pesel_prf = corpus_entity_metrics(gold_docs, pred_docs)
    metrics: dict[str, object] = {
        "strict_micro": pesel_prf,
        "strict_by_label": {Label.PESEL: pesel_prf, Label.OSOBA: prf_osoba},
        "partial_micro": corpus_entity_metrics(gold_docs, pred_docs, match="partial"),
        "partial_by_label": {Label.OSOBA: prf_osoba},
        "risk_weighted_recall": 0.0,
        "leak_rate": LeakRate(0, 2, 0, 2, [], 0),
        "fidelity": 0,
        "numbering": NumberingStats(0, 0, 0, 0),
        "throughput": ThroughputStats(100.0, 0.01),
        "peak_ram": 0,
    }
    md_path = tmp_path / "report.md"
    write_report(
        md_path,
        system_name="test",
        system_version="0.0",
        bench_version="v1",
        split="dev",
        threshold=None,
        result=res,
        metrics=metrics,
    )

    content = md_path.read_text(encoding="utf-8")

    # Markdown: 'undefined (0/0)' must appear for OSOBA row; '0.0000' must NOT
    osoba_row_match = re.search(r"\| OSOBA \|([^\n]+)", content)
    assert osoba_row_match, "OSOBA row not found in report"
    osoba_row = osoba_row_match.group(0)
    assert "undefined (0/0)" in osoba_row, f"Expected 'undefined (0/0)' in OSOBA row: {osoba_row!r}"
    assert "0.0000" not in osoba_row, f"'0.0000' must not appear in OSOBA row: {osoba_row!r}"


def test_uc135_undefined_leak_rate_and_rwr(tmp_path: Path) -> None:
    """UC-135: leak rate undefined when no docs with direct-id; RWR undefined for zero gold.

    Functions return 0.0 (float); 'undefined' is decided at the report layer:
    - doc_leak_rate: from docs_with_direct_id == 0 in LeakRate
    - rwr: from gold_count == 0 in write_report (computed from result.gold_spans_per_doc)
    """
    # Documents have only OSOBA spans (not in DIRECT_IDENTIFIERS)
    originals = ["Jan Kowalski podpisał umowę."]
    gold_spans_no_direct = [[_osoba(0, 13)]]
    rendered = ["[OSOBA] podpisał umowę."]

    lr = leak_rate(originals, gold_spans_no_direct, rendered, ["doc_x"])

    # No docs with direct identifiers → docs_with_direct_id = 0
    assert lr.docs_with_direct_id == 0
    assert lr.docs_total == 1

    # RWR on empty gold → 0.0 (undefined detected at report time from gold count)
    rwr_empty = corpus_risk_weighted_recall([[]], [[]])
    assert rwr_empty == 0.0, "RWR returns 0.0; undefined is a report-layer concern"

    # Report format helpers render 'undefined (0/0)'
    from eval.report import _fmt_doc_leak, _fmt_rwr, _fmt_val_leak

    assert _fmt_doc_leak(lr) == "undefined (0/0)", (
        f"Expected 'undefined (0/0)', got {_fmt_doc_leak(lr)!r}"
    )
    assert _fmt_rwr(0.0, undefined=True) == "undefined (0/0)"
    assert _fmt_rwr(0.5, undefined=False) == "0.5000"

    lr_empty_values = leak_rate([], [], [], [])
    assert _fmt_val_leak(lr_empty_values) == "undefined (0/0)"

    # write_report renders 'undefined (0/0)' when gold_count == 0 (rwr) and
    # docs_with_direct_id == 0 (doc leak rate).
    # Use a zero-gold single-doc corpus so that write_report sees gold_count = 0.
    zero_gold_lr = leak_rate(["no pii here"], [[]], ["no pii here"], ["d0"])
    assert zero_gold_lr.docs_with_direct_id == 0
    assert zero_gold_lr.values_total == 0
    prf_zero = corpus_entity_metrics([[]], [[]])
    res_zero = _minimal_bench_result(
        originals=["no pii here"],
        gold_per_doc=[[]],  # zero gold spans → gold_count = 0 in write_report
        pred_per_doc=[[]],
    )
    md_path = tmp_path / "report_rwr_undef.md"
    write_report(
        md_path,
        system_name="test",
        system_version="0.0",
        bench_version="v1",
        split="dev",
        threshold=None,
        result=res_zero,
        metrics={
            "strict_micro": prf_zero,
            "strict_by_label": {},
            "partial_micro": prf_zero,
            "partial_by_label": {},
            "risk_weighted_recall": 0.0,
            "leak_rate": zero_gold_lr,
            "fidelity": 0,
            "numbering": NumberingStats(0, 0, 0, 0),
            "throughput": ThroughputStats(100.0, 0.01),
            "peak_ram": 0,
        },
    )
    report_content = md_path.read_text(encoding="utf-8")
    assert "undefined (0/0)" in report_content, (
        "Report must show 'undefined (0/0)' for zero-gold RWR and zero direct-id leak"
    )


def test_uc134_uc135_json_null_assertions(tmp_path: Path) -> None:
    """UC-134/135 JSON half: eval.run on a zero-gold --docs file with system none.

    Verifies the JSON sidecar emits null (not 0.0) for:
    - strict_micro p / r / f1 (TP=FP=FN=0)
    - risk_weighted_recall (no gold spans)
    - leak_rate.doc_leak_rate (no docs with direct-id gold)
    - leak_rate.value_leak_rate (values_total=0)
    - per-label OSOBA: p=null (tp+fp=0 for none system on gold-only label)

    This test kills the mutation: _prf_dict returns floats instead of null,
    or rwr/leak-rates return 0.0 instead of null.
    """
    # Zero-gold JSONL: one doc, no spans
    zero_gold_jsonl = tmp_path / "zero_gold.jsonl"
    zero_gold_jsonl.write_text(
        '{"id": "doc_zero", "doc_type": "test", "text": "no PII here", "spans": []}\n',
        encoding="utf-8",
    )

    out_dir = tmp_path / "reports_zero"
    ret = main(
        [
            "--system",
            "none",
            "--docs",
            str(zero_gold_jsonl),
            "--out-dir",
            str(out_dir),
        ]
    )
    assert ret == 0, "eval.run on zero-gold docs must exit 0"

    json_reports = list(out_dir.glob("*.json"))
    assert len(json_reports) == 1
    data = json.loads(json_reports[0].read_text(encoding="utf-8"))

    # strict_micro: TP=FP=FN=0 → all null
    sm = data["strict_micro"]
    assert sm["p"] is None, f"strict_micro.p must be null (zero denom), got {sm['p']}"
    assert sm["r"] is None, f"strict_micro.r must be null (zero denom), got {sm['r']}"
    assert sm["f1"] is None, f"strict_micro.f1 must be null (zero denom), got {sm['f1']}"
    assert sm["tp"] == 0
    assert sm["fp"] == 0
    assert sm["fn"] == 0

    # risk_weighted_recall: no gold spans → null
    assert data["risk_weighted_recall"] is None, (
        f"risk_weighted_recall must be null for zero-gold, got {data['risk_weighted_recall']}"
    )

    # leak_rate: no gold values, no direct-id docs → both null
    lr = data["leak_rate"]
    assert lr["doc_leak_rate"] is None, (
        f"doc_leak_rate must be null for no direct-id docs, got {lr['doc_leak_rate']}"
    )
    assert lr["value_leak_rate"] is None, (
        f"value_leak_rate must be null for no gold values, got {lr['value_leak_rate']}"
    )

    # per-label OSOBA: gold-only span, no predictions → p=null (tp+fp=0)
    osoba_jsonl = tmp_path / "osoba_gold.jsonl"
    osoba_jsonl.write_text(
        '{"id": "doc_osoba", "doc_type": "test",'
        ' "text": "Jan Kowalski", "spans": ['
        '{"start": 0, "end": 12, "label": "OSOBA", "text": "Jan Kowalski"}]}\n',
        encoding="utf-8",
    )
    out_dir2 = tmp_path / "reports_osoba"
    ret2 = main(
        [
            "--system",
            "none",
            "--docs",
            str(osoba_jsonl),
            "--out-dir",
            str(out_dir2),
        ]
    )
    assert ret2 == 0
    data2 = json.loads(list(out_dir2.glob("*.json"))[0].read_text(encoding="utf-8"))
    osoba_entry = data2.get("strict_by_label", {}).get("OSOBA")
    assert osoba_entry is not None, "OSOBA must appear in strict_by_label"
    assert osoba_entry["p"] is None, (
        f"OSOBA precision must be null (no predictions), got {osoba_entry['p']}"
    )
    assert osoba_entry["r"] == 0.0, (
        f"OSOBA recall must be 0.0 (gold exists, none matched), got {osoba_entry['r']}"
    )
    assert osoba_entry["tp"] == 0
    assert osoba_entry["fp"] == 0
    assert osoba_entry["fn"] == 1


# ---------------------------------------------------------------------------
# UC-136: none system on bench/v1/dev — recall 0.0, leak values 1.0, fidelity 0
# ---------------------------------------------------------------------------


def test_uc136_none_system_bench_v1_dev(tmp_path: Path) -> None:
    """UC-136: eval.run --system none --bench v1 --split dev exits 0.

    Expected:
    - exit code 0
    - recall 0.0 (gold spans exist, none predicted → TP=0, FN>0)
    - value_leak_rate = 1.0 in JSON (all gold values present in unmasked output)
    - fidelity = 0 (no text changed, no pred spans)
    """
    bench_dir = _root / "bench" / "v1" / "dev"
    if not bench_dir.exists():
        pytest.skip("bench/v1/dev not available")

    out_dir = tmp_path / "reports"
    ret = main(
        [
            "--system",
            "none",
            "--bench",
            "v1",
            "--split",
            "dev",
            "--out-dir",
            str(out_dir),
        ]
    )
    assert ret == 0, "eval.run --system none must exit 0"

    json_reports = list(out_dir.glob("*.json"))
    assert len(json_reports) == 1, f"Expected 1 JSON report, found {len(json_reports)}"

    data = json.loads(json_reports[0].read_text(encoding="utf-8"))

    # Recall: gold exists, no predictions → tp=0, fn>0 → recall=0.0
    strict = data["strict_micro"]
    assert strict["r"] == 0.0, f"Expected recall=0.0 for none system, got {strict['r']}"
    assert strict["tp"] == 0, f"Expected tp=0, got {strict['tp']}"

    # Value leak rate: no masking → all PII values leak → value_leak_rate = 1.0
    lr = data["leak_rate"]
    assert lr["value_leak_rate"] == pytest.approx(1.0), (
        f"Expected value_leak_rate=1.0, got {lr['value_leak_rate']}"
    )

    # Fidelity: no pred spans → rendered = original → 0 chars changed
    assert data["fidelity"] == 0, f"Expected fidelity=0, got {data['fidelity']}"


# ---------------------------------------------------------------------------
# UC-137: mask-all system — value leak 0.0, fidelity 0, precision < 0.1
# ---------------------------------------------------------------------------


def test_uc137_mask_all_system_bench_v1_dev(tmp_path: Path) -> None:
    """UC-137: eval.run --system mask-all --bench v1 --split dev exits 0.

    Expected:
    - exit code 0
    - value_leak_rate = 0.0 (all text masked → no PII value survives in rendered)
    - fidelity = 0 (computed with pred spans; all chars either masked or whitespace)
    - precision < 0.1 (most predicted OSOBA spans don't match gold at exact offsets)
    """
    bench_dir = _root / "bench" / "v1" / "dev"
    if not bench_dir.exists():
        pytest.skip("bench/v1/dev not available")

    out_dir = tmp_path / "reports"
    ret = main(
        [
            "--system",
            "mask-all",
            "--bench",
            "v1",
            "--split",
            "dev",
            "--out-dir",
            str(out_dir),
        ]
    )
    assert ret == 0, "eval.run --system mask-all must exit 0"

    json_reports = list(out_dir.glob("*.json"))
    assert len(json_reports) == 1

    data = json.loads(json_reports[0].read_text(encoding="utf-8"))

    # Value leak rate: mask-all replaces every word → no PII value in rendered
    lr = data["leak_rate"]
    assert lr["value_leak_rate"] == pytest.approx(0.0), (
        f"Expected value_leak_rate=0.0, got {lr['value_leak_rate']}"
    )

    # Fidelity: computed with pred spans; all non-ws chars are masked → 0
    assert data["fidelity"] == 0, f"Expected fidelity=0, got {data['fidelity']}"

    # Precision: mask-all emits OSOBA for everything; very few exact gold hits
    strict = data["strict_micro"]
    prec = strict["p"]
    assert prec is not None, "precision should not be None for mask-all (has predictions)"
    assert prec < 0.1, f"Expected precision < 0.1 for mask-all, got {prec}"


# ---------------------------------------------------------------------------
# UC-138: any eval.run run → report contains provenance metadata
# ---------------------------------------------------------------------------


def test_uc138_report_provenance_metadata(tmp_path: Path) -> None:
    """UC-138: every eval.run produces markdown and JSON with provenance.

    Asserts:
    - Markdown: exact 'Commit: <40hex-or-unknown>' line
    - Markdown: exact 'Dokumenty: N' line (not just any line containing N)
    - JSON: git_commit, bench_sha256, docs, split, threshold fields
    """
    bench_dir = _root / "bench" / "v1" / "dev"
    if not bench_dir.exists():
        pytest.skip("bench/v1/dev not available")

    out_dir = tmp_path / "reports"
    ret = main(
        [
            "--system",
            "none",
            "--bench",
            "v1",
            "--split",
            "dev",
            "--out-dir",
            str(out_dir),
        ]
    )
    assert ret == 0

    md_reports = list(out_dir.glob("*.md"))
    json_reports = list(out_dir.glob("*.json"))
    assert len(md_reports) == 1 and len(json_reports) == 1

    md = md_reports[0].read_text(encoding="utf-8")
    data = json.loads(json_reports[0].read_text(encoding="utf-8"))

    # JSON: git_commit present and valid
    assert "git_commit" in data
    commit_val = data["git_commit"]
    assert isinstance(commit_val, str)
    assert re.fullmatch(r"[0-9a-f]{40}", commit_val) or commit_val == "unknown", (
        f"git_commit must be 40-char hex or 'unknown', got {commit_val!r}"
    )

    # Markdown: exact 'Commit: <value>' line must appear
    commit_line = f"Commit: {commit_val}"
    assert commit_line in md, f"Markdown must contain the exact line {commit_line!r}"

    # Markdown: exact 'Dokumenty: N' line (doc count)
    doc_count = data["docs"]
    assert doc_count > 0
    dokumenty_line = f"Dokumenty: {doc_count}"
    assert dokumenty_line in md, f"Markdown must contain exact line {dokumenty_line!r}"

    # JSON: bench_sha256 dict with valid SHA-256 digests
    assert "bench_sha256" in data
    sha256_map = data["bench_sha256"]
    assert isinstance(sha256_map, dict) and len(sha256_map) > 0
    sha256_pat = re.compile(r"^[0-9a-f]{64}$")
    for fname, digest in sha256_map.items():
        assert sha256_pat.match(digest), (
            f"bench_sha256[{fname!r}] is not a SHA-256 digest: {digest!r}"
        )

    # Markdown: at least one SHA-256 digest appears in the provenance section
    assert re.search(r"[0-9a-f]{64}", md), "Markdown must contain a SHA-256 digest"

    # JSON: split and threshold
    assert data["split"] == "dev"
    assert data["threshold"] is None


def test_uc138_unknown_commit_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UC-138 fallback: when git is unavailable, commit is 'unknown'."""
    bench_dir = _root / "bench" / "v1" / "dev"
    if not bench_dir.exists():
        pytest.skip("bench/v1/dev not available")

    # Monkeypatch subprocess.run in the eval.run module to simulate no git
    def _no_git(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(_run_mod.subprocess, "run", _no_git)

    out_dir = tmp_path / "reports_fallback"
    ret = main(
        [
            "--system",
            "none",
            "--bench",
            "v1",
            "--split",
            "dev",
            "--out-dir",
            str(out_dir),
        ]
    )
    assert ret == 0, "eval.run must not crash when git is unavailable"

    json_reports = list(out_dir.glob("*.json"))
    assert len(json_reports) == 1
    data = json.loads(json_reports[0].read_text(encoding="utf-8"))

    assert data["git_commit"] == "unknown", (
        f"Expected git_commit='unknown' when git unavailable, got {data['git_commit']!r}"
    )

    md = list(out_dir.glob("*.md"))[0].read_text(encoding="utf-8")
    assert "Commit: unknown" in md, "Markdown must show 'Commit: unknown' when git unavailable"


# ---------------------------------------------------------------------------
# UC-139: PROTOCOL.md contains required sections and gate names
# ---------------------------------------------------------------------------


def test_uc139_protocol_md_required_sections_and_gates() -> None:
    """UC-139: docs/bench/PROTOCOL.md contains required metric formulas, split table,
    gate table, and the 'zero denominator = undefined, never PASS' rule.
    """
    protocol_path = _root / "docs" / "bench" / "PROTOCOL.md"
    assert protocol_path.exists(), f"PROTOCOL.md not found at {protocol_path}"

    content = protocol_path.read_text(encoding="utf-8")

    # Metric formulas: P, R, F1 (strict and partial mentioned)
    assert re.search(r"(?i)precision", content), "PROTOCOL.md must define Precision"
    assert re.search(r"(?i)recall", content), "PROTOCOL.md must define Recall"
    assert re.search(r"\bF1\b", content), "PROTOCOL.md must define F1"
    assert re.search(r"(?i)strict", content), "PROTOCOL.md must mention strict match"
    assert re.search(r"(?i)partial", content), "PROTOCOL.md must mention partial match"

    # Risk-weighted recall formula
    assert re.search(r"(?i)risk.weighted", content), "PROTOCOL.md must define risk-weighted recall"

    # Leak rate (docs and values)
    assert re.search(r"(?i)leak.rate", content), "PROTOCOL.md must define leak rate"
    assert re.search(r"(?i)doc.*leak|leak.*doc", content, re.DOTALL), (
        "PROTOCOL.md must mention document leak rate"
    )
    assert re.search(r"(?i)value.*leak|leak.*value", content, re.DOTALL), (
        "PROTOCOL.md must mention value leak rate"
    )

    # Fidelity
    assert re.search(r"(?i)fidelity|wierność", content), "PROTOCOL.md must define Fidelity"

    # Numbering
    assert re.search(r"(?i)numbering|numeracja|consistency", content), (
        "PROTOCOL.md must mention numbering consistency"
    )

    # Split roles table: synthetic dev, cal, bench dev, bench test
    assert re.search(r"(?i)synthetic dev|dev.*synthetic", content), (
        "PROTOCOL.md split table must include synthetic dev"
    )
    assert re.search(r"\bcal\b", content, re.IGNORECASE), (
        "PROTOCOL.md split table must include cal (calibration) split"
    )
    assert re.search(r"bench dev|bench.*dev", content), (
        "PROTOCOL.md split table must include bench dev"
    )
    assert re.search(r"bench test|bench.*test", content), (
        "PROTOCOL.md split table must include bench test"
    )

    # Gate names and their thresholds: each gate row must contain the threshold
    # (parse the table rows and check gate-name and threshold co-occur)
    gate_thresholds = {
        "fidelity-zero": "0",  # = 0 changed chars
        "doc-leak-rate": "0.01",  # < 1 % (0.01)
        "int8-recall-drop": "0.01",  # ≤ 0.01
        "calibration-recall": "0.98",  # ≥ 0.98
    }
    table_lines = [ln for ln in content.splitlines() if ln.strip().startswith("|")]
    for gate, threshold in gate_thresholds.items():
        gate_row = next((ln for ln in table_lines if gate in ln), None)
        assert gate_row is not None, (
            f"PROTOCOL.md gate table must contain a row with gate name '{gate}'"
        )
        assert threshold in gate_row, (
            f"Gate row for '{gate}' must contain threshold '{threshold}': {gate_row!r}"
        )

    # Reporting rule: zero denominator = undefined, never PASS
    assert re.search(r"(?i)zero.denominator.*undefined|undefined.*zero.denominator", content), (
        "PROTOCOL.md must state the 'zero denominator = undefined' rule"
    )
    assert re.search(r"(?i)never.*pass|never.*PASS", content), (
        "PROTOCOL.md must state 'never PASS' for undefined metrics"
    )
