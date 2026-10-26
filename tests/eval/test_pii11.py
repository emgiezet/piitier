"""Tests for PII-11: labelling guidelines, bench schema v2, agreement metrics.

UC-146 — GUIDELINES.md structure + boundary conventions
UC-147 — bench_schema valid v2 file exits 0
UC-148 — bench_schema invalid file exits 1 with per-record rule names
UC-149 — bench_schema twin rule errors
UC-150 — bench_schema mix rule error

UC-151 — agreement hand-computed (kappa ≥ 0.7, exit 0)
UC-152 — agreement kappa < 0.7, exit 1 with message

Additional mutation-killer and edge-case tests.
"""

from __future__ import annotations

import importlib.util
import json
import math
import re
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Module loading via importlib (same pattern as the rest of tests/eval/)
# ---------------------------------------------------------------------------

_root = Path(__file__).resolve().parents[2]

# 1. Load eval.metrics first (needed by bench_schema)
_metrics_path = _root / "eval" / "metrics.py"
_metrics_spec = importlib.util.spec_from_file_location("eval.metrics", _metrics_path)
_metrics_mod = importlib.util.module_from_spec(_metrics_spec)
sys.modules["eval.metrics"] = _metrics_mod
assert _metrics_spec is not None and _metrics_spec.loader is not None
_metrics_spec.loader.exec_module(_metrics_mod)

# 2. Load eval.bench_schema
_schema_path = _root / "eval" / "bench_schema.py"
_schema_spec = importlib.util.spec_from_file_location("eval.bench_schema", _schema_path)
_schema_mod = importlib.util.module_from_spec(_schema_spec)
sys.modules["eval.bench_schema"] = _schema_mod
assert _schema_spec is not None and _schema_spec.loader is not None
_schema_spec.loader.exec_module(_schema_mod)

# 3. Load eval.agreement
_agree_path = _root / "eval" / "agreement.py"
_agree_spec = importlib.util.spec_from_file_location("eval.agreement", _agree_path)
_agree_mod = importlib.util.module_from_spec(_agree_spec)
sys.modules["eval.agreement"] = _agree_mod
assert _agree_spec is not None and _agree_spec.loader is not None
_agree_spec.loader.exec_module(_agree_mod)

validate: Any = _schema_mod.validate
schema_main: Any = _schema_mod.main
compute_agreement: Any = _agree_mod.compute_agreement
agreement_main: Any = _agree_mod.main
_char_labels_fn: Any = _agree_mod._char_labels

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

_FIXTURES = _root / "tests" / "eval" / "fixtures"
_VALID_V2 = _FIXTURES / "valid_v2.jsonl"
_INVALID_V2 = _FIXTURES / "invalid_v2.jsonl"
_INVALID_TWIN = _FIXTURES / "invalid_twin.jsonl"
_INVALID_MIX = _FIXTURES / "invalid_mix.jsonl"
_AGREE_GOOD = _FIXTURES / "agreement_good.jsonl"
_AGREE_BAD = _FIXTURES / "agreement_bad.jsonl"
_AGREE_MULTI = _FIXTURES / "agreement_multi.jsonl"

_GUIDELINES = _root / "docs" / "labelling" / "GUIDELINES.md"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUIRED_GROUPS = {
    "Identyfikacja osoby",
    "Identyfikatory państwowe",
    "Kontakt i lokalizacja",
    "Finanse",
    "Ubezpieczenia",
    "Zdrowie",
}

_REQUIRED_SECTIONS = [
    "Granice spanów",
    "Czego nie anotujemy",
    "Spory",
    "Budżet czasu",
]


def _count_list_items(block: str, marker: str) -> int:
    """Count '- ...' items after the first line starting with *marker*."""
    in_sec = False
    count = 0
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith(marker):
            in_sec = True
            continue
        if in_sec:
            if stripped.startswith("- "):
                count += 1
            elif stripped and not stripped.startswith("- "):
                break
    return count


def _make_rec(
    rid: str = "r1",
    doc_type: str = "polisa",
    text: str = "Jan.",
    spans: list[dict[str, Any]] | None = None,
    annotations: list[dict[str, Any]] | None = None,
    adjudicated_by: str = "c",
    twin_of: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    if spans is None:
        spans = []
    if annotations is None:
        annotations = [{"annotator": "a", "spans": []}, {"annotator": "b", "spans": []}]
    return {
        "id": rid,
        "doc_type": doc_type,
        "text": text,
        "spans": spans,
        "annotations": annotations,
        "adjudicated_by": adjudicated_by,
        "twin_of": twin_of,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# UC-146 — GUIDELINES.md structure and boundary conventions
# ---------------------------------------------------------------------------


def test_uc146_guidelines_structure() -> None:
    """UC-146: GUIDELINES.md has 6 groups with ≥ 2 pos/neg examples each,
    required sections, and correct boundary conventions for dr/lek.med.,
    currency, OSOBA, DATA_URODZENIA."""
    assert _GUIDELINES.exists(), f"Missing: {_GUIDELINES}"
    text = _GUIDELINES.read_text(encoding="utf-8")

    # --- 6 group headings ---
    group_headings = re.findall(r"^###\s+(.+)$", text, re.MULTILINE)
    assert len(group_headings) >= 6, (
        f"Expected ≥ 6 group headings (###), found {len(group_headings)}"
    )
    matched = sum(1 for req in _REQUIRED_GROUPS if any(req in h for h in group_headings))
    assert matched == 6, f"Only {matched}/6 required groups matched"

    # --- ≥ 2 pos/neg per group ---
    parts = re.split(r"^###\s+", text, flags=re.MULTILINE)
    for block in parts[1:]:
        heading = block.splitlines()[0].strip()
        if not any(g in heading for g in _REQUIRED_GROUPS):
            continue
        pos = _count_list_items(block, "Pozytywne")
        neg = _count_list_items(block, "Negatywne")
        assert pos >= 2, f"Group '{heading}': {pos} positive examples (need ≥ 2)"
        assert neg >= 2, f"Group '{heading}': {neg} negative examples (need ≥ 2)"

    # --- required sections ---
    for section in _REQUIRED_SECTIONS:
        assert section in text, f"Missing required section: {section!r}"

    # --- boundary conventions ---
    # dr / lek. med. inside LEKARZ span
    assert "dr" in text and "LEKARZ" in text
    # Check that the boundary table or text explicitly states dr is inside LEKARZ
    assert "dr" in text and "wchodzi do spanu" in text.lower() or "tytuł" in text

    # currency inside KWOTA/DOCHOD
    assert "waluta" in text.lower() or "PLN" in text

    # full name = one OSOBA span
    assert "OSOBA" in text

    # DATA_URODZENIA span = date only, ur. is outside
    # The guidelines must state that ur. is outside the span
    assert "ur." in text
    # Must explicitly say ur. is NOT part of the span (nie wchodzi or poza spanem)
    guidelines_lower = text.lower()
    assert "nie wchodzi" in guidelines_lower or "poza spanem" in guidelines_lower, (
        "GUIDELINES must explicitly state that 'ur.' is outside the DATA_URODZENIA span"
    )

    # DATA_URODZENIA and WIEK must appear in the boundary table (§2)
    boundary_section = text[text.find("## 2. Granice") :]
    assert "DATA_URODZENIA" in boundary_section, "DATA_URODZENIA missing from boundary table"
    assert "WIEK" in boundary_section, "WIEK missing from boundary table"


# ---------------------------------------------------------------------------
# UC-147 — valid v2 file (7 records, 2 PESEL + 2 twins across 5 doc_types)
# ---------------------------------------------------------------------------


def test_uc147_valid_v2_exits_zero() -> None:
    """UC-147: bench_schema on a valid 7-record v2 file exits 0."""
    records = [json.loads(line) for line in _VALID_V2.read_text().splitlines() if line.strip()]
    assert len(records) == 7, f"expected 7 records, got {len(records)}"

    # Mix rule must hold: ≤ 30% per doc_type
    from collections import Counter

    counts = Counter(r["doc_type"] for r in records)
    for dt, n in counts.items():
        assert n / len(records) <= 0.30, f"{dt}: {n}/{len(records)} > 30%"

    errors = validate(records)
    assert errors == [], "Expected no errors, got:\n" + "\n".join(errors)

    ret = schema_main([str(_VALID_V2)])
    assert ret == 0, f"Expected exit 0, got {ret}"


# ---------------------------------------------------------------------------
# UC-148 — record-level errors
# ---------------------------------------------------------------------------


def test_uc148_invalid_v2_exit_one_with_rules(capsys: pytest.CaptureFixture[str]) -> None:
    """UC-148: bench_schema reports offset, label, annotators, adjudication,
    twin_of errors — each with line number and rule name; no document text echoed."""
    records = [json.loads(line) for line in _INVALID_V2.read_text().splitlines() if line.strip()]
    errors = validate(records)

    assert errors, "Expected at least one error"
    error_text = "\n".join(errors)

    # Each rule must appear (format: "line N: rule: ...")
    assert re.search(r"line \d+: offset:", error_text), "Missing offset error"
    assert re.search(r"line \d+: label:", error_text), "Missing label error"
    assert re.search(r"line \d+: annotators:", error_text), "Missing annotators error"
    assert re.search(r"line \d+: adjudication:", error_text), "Missing adjudication error"
    assert re.search(r"line \d+: twin_of:", error_text), "Missing twin_of error"

    # No document text in any error
    assert "Hello world" not in error_text, "Document text leaked into output"
    assert "test document" not in error_text, "Document text leaked into output"

    ret = schema_main([str(_INVALID_V2)])
    assert ret == 1, f"Expected exit 1, got {ret}"


# ---------------------------------------------------------------------------
# UC-149 — twin rule errors
# ---------------------------------------------------------------------------


def test_uc149_twin_rule_errors() -> None:
    """UC-149: twin rule fires for IBAN without twin, twin with PESEL,
    and twin with different doc_type."""
    records = [json.loads(line) for line in _INVALID_TWIN.read_text().splitlines() if line.strip()]
    errors = validate(records)
    error_text = "\n".join(errors)

    twin_errors = [e for e in errors if ": twin:" in e]
    # Expected twin errors: iban_no_twin, iban_bad_twin, twin_with_pesel, iban_wrong_doctype
    assert len(twin_errors) >= 3, (
        f"Expected ≥ 3 twin-rule errors, got {len(twin_errors)}: {twin_errors}"
    )

    # Case 1: missing twin_of
    assert any("missing twin_of" in e for e in twin_errors), "No 'missing twin_of' error"

    # Case 2: twin contains direct identifier
    assert any("contains direct identifier" in e for e in twin_errors), (
        "No 'contains direct identifier' error"
    )

    # Case 3: doc_type mismatch
    assert any("doc_type mismatch" in e for e in twin_errors), "No 'doc_type mismatch' error"

    # No file-supplied strings (ids, doc_type values) in error output
    assert "polisa" not in error_text, "doc_type value echoed in output"
    assert "iban_no_twin" not in error_text, "record id echoed in output"

    ret = schema_main([str(_INVALID_TWIN)])
    assert ret == 1


# ---------------------------------------------------------------------------
# UC-150 — mix rule error
# ---------------------------------------------------------------------------


def test_uc150_mix_rule_error() -> None:
    """UC-150: mix rule fires when one doc_type > 30 % of 7 records (4/7 ≈ 57.1 %)."""
    records = [json.loads(line) for line in _INVALID_MIX.read_text().splitlines() if line.strip()]
    assert len(records) == 7

    errors = validate(records)
    error_text = "\n".join(errors)

    assert "mix:" in error_text, f"No mix error in:\n{error_text}"
    assert "%" in error_text, "mix error should include a percentage"

    ret = schema_main([str(_INVALID_MIX)])
    assert ret == 1


def test_uc150_mix_boundary_exact_30_pct_passes() -> None:
    """Mix rule: 30 % exactly (3/10) must pass."""
    recs = [_make_rec(str(i), "polisa" if i < 3 else f"type_{i}") for i in range(10)]
    errors = [e for e in validate(recs) if "mix" in e]
    assert errors == [], f"Expected no mix errors at 30%, got: {errors}"


def test_uc150_mix_boundary_above_30_pct_fails() -> None:
    """Mix rule: just above 30 % (4/10 = 40 %) must fail."""
    recs = [_make_rec(str(i), "polisa" if i < 4 else f"type_{i}") for i in range(10)]
    errors = [e for e in validate(recs) if "mix" in e]
    assert errors, "Expected mix error at 40%, got none"


# ---------------------------------------------------------------------------
# UC-151 — agreement hand-computed (kappa ≥ 0.7)
# ---------------------------------------------------------------------------
#
# Fixture: text = "Adam Nowak mieszka w Gdansku. Maria Kowalska zna Jana." (54 chars)
#
# ann_a spans (4):  [0,10) OSOBA  [21,28) MIEJSCOWOSC  [30,44) OSOBA  [49,53) IMIE
# ann_b spans (4):  [0,10) OSOBA  [21,28) MIEJSCOWOSC  [30,44) OSOBA  [49,54) IMIE
#
# Strict span F1 (A=gold, B=pred):
#   TP=3, FP=1 (B's [49,54)), FN=1 (A's [49,53) unmatched)
#   P = 3/4 = 0.75, R = 3/4 = 0.75, F1 = 0.75
#
# Partial span F1:  [49,53) and [49,54) overlap (same label) → partial TP
#   TP=4, FP=0, FN=0 → F1 = 1.0
#
# Cohen's kappa (n=54):
#   A: OSOBA=24, O=19, MIEJSCOWOSC=7, IMIE=4
#   B: OSOBA=24, O=18, MIEJSCOWOSC=7, IMIE=5  (pos 53: A=O, B=IMIE)
#   agree = 53 (pos 53 disagrees)
#   p_o = 53/54
#   p_e = (19·18 + 24·24 + 7·7 + 4·5) / 54² = (342+576+49+20) / 2916 = 987/2916
#   kappa = (53/54 − 329/972) / (1 − 329/972) = 1875/1929 = 625/643

_KAPPA_UC151 = float(Fraction(625, 643))  # ≈ 0.9720


def test_uc151_agreement_hand_computed_exit_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """UC-151: agreement matches hand-computed numbers (4 decimal places); exit 0."""
    records = [json.loads(line) for line in _AGREE_GOOD.read_text().splitlines() if line.strip()]
    metrics = compute_agreement(records)

    assert math.isclose(metrics["strict_overall"], 0.75, abs_tol=5e-5), (
        f"strict_overall = {metrics['strict_overall']:.6f}, expected 0.75"
    )
    assert math.isclose(metrics["partial_overall"], 1.0, abs_tol=5e-5), (
        f"partial_overall = {metrics['partial_overall']:.6f}, expected 1.0"
    )
    assert math.isclose(metrics.get("strict_OSOBA", -1.0), 1.0, abs_tol=5e-5)
    assert math.isclose(metrics.get("strict_MIEJSCOWOSC", -1.0), 1.0, abs_tol=5e-5)
    assert math.isclose(metrics.get("strict_IMIE", -1.0), 0.0, abs_tol=5e-5)
    assert math.isclose(metrics.get("partial_IMIE", -1.0), 1.0, abs_tol=5e-5)
    assert math.isclose(metrics["kappa"], _KAPPA_UC151, abs_tol=5e-5), (
        f"kappa = {metrics['kappa']:.6f}, expected {_KAPPA_UC151:.6f}"
    )

    ret = agreement_main([str(_AGREE_GOOD)])
    assert ret == 0, f"Expected exit 0, got {ret}"


# ---------------------------------------------------------------------------
# UC-152 — kappa < 0.7, exit 1 with message
# ---------------------------------------------------------------------------
#
# Fixture: text = "Nowak" (5 chars)
#   ann_a: [{0,5,NAZWISKO}]  ann_b: []
#   p_o = 0,  p_e = 0,  kappa = 0


def test_uc152_agreement_kappa_below_threshold_exit_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """UC-152: kappa = 0.0 < 0.7 → exit 1; stderr contains kappa and threshold."""
    records = [json.loads(line) for line in _AGREE_BAD.read_text().splitlines() if line.strip()]
    metrics = compute_agreement(records)

    assert math.isclose(metrics["strict_overall"], 0.0, abs_tol=5e-5)
    assert math.isclose(metrics["partial_overall"], 0.0, abs_tol=5e-5)
    assert math.isclose(metrics["kappa"], 0.0, abs_tol=5e-5)

    ret = agreement_main([str(_AGREE_BAD)])
    captured = capsys.readouterr()
    assert ret == 1, f"Expected exit 1, got {ret}"
    assert "kappa" in captured.err.lower(), f"kappa not in stderr: {captured.err!r}"
    assert "0.7" in captured.err, f"threshold 0.7 not in stderr: {captured.err!r}"
    assert "Nowak" not in captured.out, "Document text in stdout"


# ---------------------------------------------------------------------------
# M2 kill — _char_labels deterministic regardless of span input order
# ---------------------------------------------------------------------------


def test_char_labels_deterministic_span_order() -> None:
    """M2 kill: _char_labels sorts spans so the result is independent of input order."""
    text = "ABCDE"
    span_large = {"start": 0, "end": 5, "label": "OSOBA", "text": "ABCDE"}
    span_small = {"start": 2, "end": 4, "label": "IMIE", "text": "CD"}

    labels_large_first = _char_labels_fn(text, [span_large, span_small])
    labels_small_first = _char_labels_fn(text, [span_small, span_large])

    assert labels_large_first == labels_small_first, (
        f"Span order changes labels:\n  large_first: {labels_large_first}\n"
        f"  small_first: {labels_small_first}"
    )


# ---------------------------------------------------------------------------
# M3 kill — all-O kappa = 1.0
# ---------------------------------------------------------------------------


def test_kappa_all_O_is_one() -> None:
    """M3 kill: when both annotators have no spans (all-O), kappa = 1.0."""
    record: dict[str, Any] = {
        "id": "r1",
        "text": "ABC",
        "annotations": [
            {"annotator": "ann_a", "spans": []},
            {"annotator": "ann_b", "spans": []},
        ],
    }
    metrics = compute_agreement([record])
    assert math.isclose(metrics["kappa"], 1.0, abs_tol=5e-5), (
        f"kappa = {metrics['kappa']:.6f}, expected 1.0"
    )


# ---------------------------------------------------------------------------
# M8 kill — annotation spans are validated
# ---------------------------------------------------------------------------


def test_annotation_span_offset_is_validated() -> None:
    """M8 kill: an annotation span with a wrong 'text' field triggers offset error."""
    # text = "Hello", annotation span text="XYZ" but text[0:3]="Hel" != "XYZ"
    rec = _make_rec(
        "ann_offset",
        text="Hello",
        annotations=[
            {"annotator": "a", "spans": [{"start": 0, "end": 3, "label": "OSOBA", "text": "XYZ"}]},
            {"annotator": "b", "spans": []},
        ],
    )
    errors = validate([rec])
    assert any("offset" in e and "annotations" in e for e in errors), (
        f"Expected annotation offset error, got: {errors}"
    )


# ---------------------------------------------------------------------------
# M9 kill — missing file exits 2 (not 1)
# ---------------------------------------------------------------------------


def test_schema_missing_file_exit_two(tmp_path: Path) -> None:
    """M9 kill: bench_schema on a missing file exits 2."""
    ret = schema_main([str(tmp_path / "nonexistent.jsonl")])
    assert ret == 2, f"Expected exit 2, got {ret}"


def test_agreement_missing_file_exit_two(tmp_path: Path) -> None:
    """M9 kill: agreement on a missing file exits 2."""
    ret = agreement_main([str(tmp_path / "nonexistent.jsonl")])
    assert ret == 2, f"Expected exit 2, got {ret}"


# ---------------------------------------------------------------------------
# Exit 2 cases
# ---------------------------------------------------------------------------


def test_schema_malformed_json_exit_two(tmp_path: Path) -> None:
    """bench_schema on malformed JSON exits 2."""
    f = tmp_path / "bad.jsonl"
    f.write_text("not json\n")
    ret = schema_main([str(f)])
    assert ret == 2


def test_agreement_malformed_json_exit_two(tmp_path: Path) -> None:
    """agreement on malformed JSON exits 2."""
    f = tmp_path / "bad.jsonl"
    f.write_text("not json\n")
    ret = agreement_main([str(f)])
    assert ret == 2


def test_schema_no_args_exit_two() -> None:
    """bench_schema with no arguments exits 2."""
    ret = schema_main([])
    assert ret == 2


def test_agreement_no_args_exit_two() -> None:
    """agreement with no arguments exits 2."""
    ret = agreement_main([])
    assert ret == 2


def test_agreement_empty_file_exit_two(tmp_path: Path) -> None:
    """agreement on a file with no records exits 2."""
    f = tmp_path / "empty.jsonl"
    f.write_text("")
    ret = agreement_main([str(f)])
    assert ret == 2


def test_schema_empty_file_exit_one(tmp_path: Path) -> None:
    """bench_schema on an empty JSONL file exits 1 (empty-file validation error)."""
    f = tmp_path / "empty.jsonl"
    f.write_text("")
    ret = schema_main([str(f)])
    assert ret == 1


def test_agreement_unknown_label_exit_two(tmp_path: Path) -> None:
    """agreement exits 2 when an annotation span has an unknown label."""
    rec = {
        "id": "r1",
        "text": "test",
        "annotations": [
            {"annotator": "a", "spans": [{"start": 0, "end": 4, "label": "NOSUCHLABEL"}]},
            {"annotator": "b", "spans": []},
        ],
    }
    f = tmp_path / "unknown_label.jsonl"
    f.write_text(json.dumps(rec) + "\n")
    ret = agreement_main([str(f)])
    assert ret == 2


# ---------------------------------------------------------------------------
# No-echo test: PII values in ids/labels/annotators must not appear in output
# ---------------------------------------------------------------------------


def test_no_pii_value_in_error_output() -> None:
    """No file-supplied value (including a PESEL used as label, annotator, id)
    appears in bench_schema error output."""
    pesel = "44051401359"  # already allowlisted; used here only as a string value
    rec: dict[str, Any] = {
        "id": pesel,  # PESEL as record id
        "doc_type": "polisa",
        "text": f"Value {pesel} embedded.",
        "spans": [{"start": 0, "end": 5, "label": pesel, "text": "Value"}],  # PESEL as label
        "annotations": [
            {
                "annotator": pesel,  # PESEL as annotator name
                "spans": [{"start": 0, "end": 5, "label": pesel, "text": "Value"}],
            },
            {"annotator": "ann_b", "spans": []},
        ],
        "adjudicated_by": "",
        "twin_of": None,
        "notes": "",
    }
    errors = validate([rec])
    error_text = "\n".join(errors)
    assert pesel not in error_text, f"PESEL value {pesel!r} leaked into error output:\n{error_text}"


# ---------------------------------------------------------------------------
# Cross-document kappa pooling (multi-record fixture)
# ---------------------------------------------------------------------------
#
# Fixture: 2 records
#   Record 1: text="AB" (2 chars), both annotators: OSOBA[0,2)
#   Record 2: text="CD" (2 chars), ann_a: IMIE[0,2), ann_b: []
#
# Pooled kappa:
#   cnt_a = {OSOBA:2, IMIE:2}   cnt_b = {OSOBA:2, O:2}
#   total=4, agree=2 (record 1 only)
#   p_o = 1/2,  p_e = (2*2)/(4*4) = 4/16 = 1/4
#   kappa = (1/2 - 1/4) / (1 - 1/4) = (1/4) / (3/4) = 1/3
#
# Per-doc mean would be: record 1 → p_e=1 → kappa=1.0; record 2 → kappa=0.0
# Mean = 0.5  ≠  pooled 1/3  ← proves pooling is used

_KAPPA_MULTI = float(Fraction(1, 3))  # ≈ 0.3333


def test_agreement_multi_record_pooled_kappa() -> None:
    """Cross-document pooling: kappa = 1/3, not per-doc mean 0.5."""
    records = [json.loads(line) for line in _AGREE_MULTI.read_text().splitlines() if line.strip()]
    assert len(records) == 2
    metrics = compute_agreement(records)

    assert math.isclose(metrics["kappa"], _KAPPA_MULTI, abs_tol=5e-5), (
        f"kappa = {metrics['kappa']:.6f}, expected {_KAPPA_MULTI:.6f} (1/3). "
        "Per-doc mean would be 0.5; pooled kappa is 1/3."
    )


# ---------------------------------------------------------------------------
# Overlap validation
# ---------------------------------------------------------------------------


def test_overlap_rule_gold_spans() -> None:
    """bench_schema reports 'overlap' for overlapping gold spans."""
    # text = "Jan Kowalski" (12 chars); spans [0,12) and [4,12) overlap
    rec = _make_rec(
        "overlap_gold",
        text="Jan Kowalski",
        spans=[
            {"start": 0, "end": 12, "label": "OSOBA", "text": "Jan Kowalski"},
            {"start": 4, "end": 12, "label": "NAZWISKO", "text": "Kowalski"},
        ],
    )
    errors = validate([rec])
    assert any("overlap" in e for e in errors), f"Expected overlap error, got: {errors}"


def test_overlap_rule_annotation_spans() -> None:
    """bench_schema reports 'overlap' for overlapping annotation spans."""
    rec = _make_rec(
        "overlap_ann",
        text="Jan Kowalski",
        annotations=[
            {
                "annotator": "ann_a",
                "spans": [
                    {"start": 0, "end": 12, "label": "OSOBA", "text": "Jan Kowalski"},
                    {"start": 4, "end": 12, "label": "NAZWISKO", "text": "Kowalski"},
                ],
            },
            {"annotator": "ann_b", "spans": []},
        ],
    )
    errors = validate([rec])
    assert any("overlap" in e and "annotations" in e for e in errors), (
        f"Expected annotation overlap error, got: {errors}"
    )


# ---------------------------------------------------------------------------
# Strict schema rules
# ---------------------------------------------------------------------------


def test_schema_empty_file_reports_error() -> None:
    """validate([]) reports an error (not silently passes)."""
    errors = validate([])
    assert errors, "Expected error for empty file"


def test_schema_duplicate_ids() -> None:
    """Duplicate record ids are detected."""
    r1 = _make_rec("dup_id")
    r2 = _make_rec("dup_id")
    errors = validate([r1, r2])
    assert any("duplicate" in e.lower() for e in errors), (
        f"Expected duplicate-id error, got: {errors}"
    )


def test_schema_missing_required_field() -> None:
    """Missing required record fields are reported."""
    rec: dict[str, Any] = {
        "id": "missing_fields",
        "doc_type": "polisa",
        # 'text', 'spans', 'annotations', 'adjudicated_by', 'twin_of', 'notes' absent
    }
    errors = validate([rec])
    # Should report missing fields; also annotators < 2 and adjudication missing
    assert any("schema" in e and "missing" in e for e in errors), (
        f"Expected schema/missing error, got: {errors}"
    )


def test_schema_span_text_required() -> None:
    """A span without a 'text' field is reported."""
    rec = _make_rec(
        "no_text_span",
        text="Hello",
        spans=[{"start": 0, "end": 5, "label": "OSOBA"}],  # no 'text' key
    )
    errors = validate([rec])
    assert any("schema" in e and "text" in e for e in errors), (
        f"Expected schema error for missing span 'text', got: {errors}"
    )


def test_schema_type_error_no_traceback(tmp_path: Path) -> None:
    """Wrong types (twin_of as list, label as int) produce rule errors, not tracebacks."""
    bad = tmp_path / "bad_types.jsonl"
    rec: dict[str, Any] = {
        "id": "bad_types",
        "doc_type": "polisa",
        "text": "test",
        "spans": [{"start": 0, "end": 4, "label": 42, "text": "test"}],
        "annotations": [{"annotator": "a", "spans": []}, {"annotator": "b", "spans": []}],
        "adjudicated_by": "c",
        "twin_of": ["not", "a", "string"],
        "notes": "",
    }
    bad.write_text(json.dumps(rec) + "\n")
    # Must not raise; must exit 1 (validation errors), not crash
    ret = schema_main([str(bad)])
    assert ret == 1, f"Expected exit 1, got {ret}"
