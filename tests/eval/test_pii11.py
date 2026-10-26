"""Tests for PII-11: labelling guidelines, bench schema v2, agreement metrics.

UC-146 — GUIDELINES.md structure (6 groups, ≥ 2 pos/neg each, required sections)
UC-147 — bench_schema valid v2 file exits 0
UC-148 — bench_schema invalid file exits 1 with per-record rule names
UC-149 — bench_schema twin rule errors
UC-150 — bench_schema mix rule error
UC-151 — agreement metrics hand-computed (kappa ≥ 0.7 → exit 0)
UC-152 — agreement kappa < 0.7 → exit 1 with message
"""

from __future__ import annotations

import importlib.util
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

_GUIDELINES = _root / "docs" / "labelling" / "GUIDELINES.md"

# ---------------------------------------------------------------------------
# UC-146 — GUIDELINES.md structure
# ---------------------------------------------------------------------------

_REQUIRED_GROUPS = {
    "Identyfikacja osoby",
    "Identyfikatory państwowe",
    "Kontakt i lokalizacja",
    "Finanse",
    "Ubezpieczenia",
    "Zdrowie",  # heading may be truncated by em-dash or article reference
}

_REQUIRED_SECTIONS = [
    "Granice spanów",
    "Czego nie anotujemy",
    "Spory",
    "Budżet czasu",
]


def _count_list_items(block: str, marker: str) -> int:
    """Return the number of '- ...' list items after ``marker:`` in *block*."""
    in_section = False
    count = 0
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith(marker):
            in_section = True
            continue
        if in_section:
            if stripped.startswith("- "):
                count += 1
            elif stripped and not stripped.startswith("- "):
                # Next non-empty, non-list line ends the section
                break
    return count


def test_uc146_guidelines_structure() -> None:
    """UC-146: GUIDELINES.md has 6 groups with ≥ 2 pos/neg examples each and
    required sections (span boundaries, what not to annotate, disputes, time)."""
    assert _GUIDELINES.exists(), f"Missing: {_GUIDELINES}"
    text = _GUIDELINES.read_text(encoding="utf-8")

    # --- find ### group headings ---
    group_headings = re.findall(r"^###\s+(.+)$", text, re.MULTILINE)
    assert len(group_headings) >= 6, (
        f"Expected ≥ 6 group headings (###), found {len(group_headings)}: {group_headings}"
    )

    # --- at least 6 groups from TAXONOMY match ---
    matched = 0
    for required in _REQUIRED_GROUPS:
        if any(required in h for h in group_headings):
            matched += 1
    assert matched == 6, f"Only {matched}/6 required groups matched in headings: {group_headings}"

    # --- parse each group block and count pos/neg examples ---
    # Split text at ### headings; each element is the content of one group section
    parts = re.split(r"^###\s+", text, flags=re.MULTILINE)
    # parts[0] is the preamble before the first ###; skip it
    group_blocks = parts[1:]

    for block in group_blocks:
        heading = block.splitlines()[0].strip()
        # Only check taxonomy group blocks (skip non-group ### headings if any)
        if not any(g in heading for g in _REQUIRED_GROUPS):
            continue
        pos_count = _count_list_items(block, "Pozytywne")
        neg_count = _count_list_items(block, "Negatywne")
        assert pos_count >= 2, (
            f"Group '{heading}': expected ≥ 2 positive examples, found {pos_count}"
        )
        assert neg_count >= 2, (
            f"Group '{heading}': expected ≥ 2 negative examples, found {neg_count}"
        )

    # --- required sections ---
    for section in _REQUIRED_SECTIONS:
        assert section in text, f"Missing required section: {section!r}"


# ---------------------------------------------------------------------------
# UC-147 — valid v2 file exits 0
# ---------------------------------------------------------------------------


def test_uc147_valid_v2_exits_zero() -> None:
    """UC-147: bench_schema on a valid 4-record v2 file (2 PESEL + 2 twins) exits 0."""
    import json

    records = [json.loads(line) for line in _VALID_V2.read_text().splitlines() if line.strip()]
    assert len(records) == 4, f"expected 4 records, got {len(records)}"

    errors = validate(records)
    assert errors == [], "Expected no errors, got:\n" + "\n".join(errors)

    ret = schema_main([str(_VALID_V2)])
    assert ret == 0, f"Expected exit 0, got {ret}"


# ---------------------------------------------------------------------------
# UC-148 — record-level errors reported with id and rule name
# ---------------------------------------------------------------------------


def test_uc148_invalid_v2_exit_one_with_rules(capsys: pytest.CaptureFixture[str]) -> None:
    """UC-148: bench_schema reports offset, label, annotators, adjudication,
    twin_of errors — each with record id and rule name; no document text."""
    import json

    records = [json.loads(line) for line in _INVALID_V2.read_text().splitlines() if line.strip()]
    errors = validate(records)

    assert errors, "Expected at least one error"

    error_text = "\n".join(errors)

    # Each expected rule must appear at least once
    assert "bad_offset: offset:" in error_text, "Missing offset error for bad_offset"
    assert "bad_label: label:" in error_text, "Missing label error for bad_label"
    assert "one_annotator: annotators:" in error_text, "Missing annotators error"
    assert "no_adjudication: adjudication:" in error_text, "Missing adjudication error"
    assert "bad_twin_ref: twin_of:" in error_text, "Missing twin_of error"

    # No document text in any error: check that actual text values don't appear
    assert "Hello world" not in error_text, "Document text leaked into error output"
    assert "test document" not in error_text, "Document text leaked into error output"

    # Main CLI must exit 1
    ret = schema_main([str(_INVALID_V2)])
    assert ret == 1, f"Expected exit 1, got {ret}"


# ---------------------------------------------------------------------------
# UC-149 — twin rule errors
# ---------------------------------------------------------------------------


def test_uc149_twin_rule_errors(capsys: pytest.CaptureFixture[str]) -> None:
    """UC-149: twin rule fires for IBAN without twin, twin with PESEL,
    and twin with different doc_type."""
    import json

    records = [json.loads(line) for line in _INVALID_TWIN.read_text().splitlines() if line.strip()]
    errors = validate(records)
    error_text = "\n".join(errors)

    # Case 1: IBAN record with no twin_of
    assert "iban_no_twin: twin:" in error_text, "Missing twin error for iban_no_twin"

    # Case 2: twin contains direct identifier (PESEL)
    assert "iban_bad_twin: twin:" in error_text, "Missing twin error for iban_bad_twin"
    assert "contains direct identifier" in error_text, "Missing 'contains direct identifier'"

    # Case 3: twin has different doc_type
    assert "iban_wrong_doctype: twin:" in error_text, "Missing twin error for iban_wrong_doctype"
    assert "mismatch" in error_text, "Missing doc_type mismatch message"

    # All three cases appear under the "twin" rule
    twin_errors = [e for e in errors if ": twin:" in e]
    assert len(twin_errors) >= 3, (
        f"Expected ≥ 3 twin-rule errors, got {len(twin_errors)}: {twin_errors}"
    )

    ret = schema_main([str(_INVALID_TWIN)])
    assert ret == 1


# ---------------------------------------------------------------------------
# UC-150 — mix rule error
# ---------------------------------------------------------------------------


def test_uc150_mix_rule_error(capsys: pytest.CaptureFixture[str]) -> None:
    """UC-150: mix rule fires when one doc_type exceeds 30 % of 7 records (4/7 = 57.1 %)."""
    import json

    records = [json.loads(line) for line in _INVALID_MIX.read_text().splitlines() if line.strip()]
    assert len(records) == 7

    errors = validate(records)
    error_text = "\n".join(errors)

    # Must report the mix rule
    assert "mix:" in error_text, f"No mix error found in:\n{error_text}"
    assert "polisa" in error_text, "mix error should name the offending doc_type"

    # Must include the share/percentage
    assert "%" in error_text, "mix error should include a percentage"

    ret = schema_main([str(_INVALID_MIX)])
    assert ret == 1


# ---------------------------------------------------------------------------
# UC-151 — agreement hand-computed (kappa ≥ 0.7)
# ---------------------------------------------------------------------------
#
# Fixture: text = "Adam Nowak mieszka w Gdansku. Maria Kowalska zna Jana." (54 chars)
#
# ann_a spans (4):
#   [0,10)  OSOBA  "Adam Nowak"
#   [21,28) MIEJSCOWOSC "Gdansku"
#   [30,44) OSOBA  "Maria Kowalska"
#   [49,53) IMIE   "Jana"
#
# ann_b spans (4):
#   [0,10)  OSOBA  "Adam Nowak"      (exact)
#   [21,28) MIEJSCOWOSC "Gdansku"    (exact)
#   [30,44) OSOBA  "Maria Kowalska"  (exact)
#   [49,54) IMIE   "Jana."           (different end: +1)
#
# Strict span F1 (A as gold, B as pred):
#   TP=3, FP=1 (B's [49,54]), FN=1 (A's [49,53] not matched)
#   P = 3/4 = 0.75, R = 3/4 = 0.75, F1 = 0.75
#
# Partial span F1:
#   [49,53) and [49,54) share label IMIE and overlap → partial match
#   TP=4, FP=0, FN=0 → P=1.0, R=1.0, F1=1.0
#
# Per-label strict F1:
#   OSOBA:       TP=2, FP=0, FN=0 → 1.0
#   MIEJSCOWOSC: TP=1, FP=0, FN=0 → 1.0
#   IMIE:        TP=0, FP=1, FN=1 → 0.0
#
# Per-label partial F1:
#   OSOBA:       1.0,  MIEJSCOWOSC: 1.0,  IMIE: 1.0
#
# Cohen's kappa (character-level, n=54):
#   A labels: OSOBA×24, O×19, MIEJSCOWOSC×7, IMIE×4
#   B labels: OSOBA×24, O×18, MIEJSCOWOSC×7, IMIE×5
#   Agreements: 53 (positions 0-52 agree; pos 53: A=O, B=IMIE)
#   p_o = 53/54
#   p_e = (19·18 + 24·24 + 7·7 + 4·5) / 54² = (342+576+49+20) / 2916 = 987/2916 = 329/972
#   kappa = (53/54 − 329/972) / (1 − 329/972) = (1875/1929) = 625/643 ≈ 0.9720


_KAPPA_UC151 = float(Fraction(625, 643))  # ≈ 0.972006


def test_uc151_agreement_hand_computed_exit_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """UC-151: agreement matches hand-computed numbers (4 decimal places); exit 0."""
    import json

    records = [json.loads(line) for line in _AGREE_GOOD.read_text().splitlines() if line.strip()]
    metrics = compute_agreement(records)

    # Overall strict F1 = 3/4 = 0.75
    assert math.isclose(metrics["strict_overall"], 0.75, abs_tol=5e-5), (
        f"strict_overall = {metrics['strict_overall']:.6f}, expected 0.75"
    )

    # Overall partial F1 = 1.0
    assert math.isclose(metrics["partial_overall"], 1.0, abs_tol=5e-5), (
        f"partial_overall = {metrics['partial_overall']:.6f}, expected 1.0"
    )

    # Per-label strict
    assert math.isclose(metrics.get("strict_OSOBA", -1.0), 1.0, abs_tol=5e-5), (
        f"strict_OSOBA = {metrics.get('strict_OSOBA')}"
    )
    assert math.isclose(metrics.get("strict_MIEJSCOWOSC", -1.0), 1.0, abs_tol=5e-5), (
        f"strict_MIEJSCOWOSC = {metrics.get('strict_MIEJSCOWOSC')}"
    )
    assert math.isclose(metrics.get("strict_IMIE", -1.0), 0.0, abs_tol=5e-5), (
        f"strict_IMIE = {metrics.get('strict_IMIE')}"
    )

    # Per-label partial: all 1.0 (even IMIE overlaps)
    assert math.isclose(metrics.get("partial_IMIE", -1.0), 1.0, abs_tol=5e-5), (
        f"partial_IMIE = {metrics.get('partial_IMIE')}"
    )

    # Kappa ≈ 0.9720 (= 625/643)
    assert math.isclose(metrics["kappa"], _KAPPA_UC151, abs_tol=5e-5), (
        f"kappa = {metrics['kappa']:.6f}, expected {_KAPPA_UC151:.6f}"
    )

    # Exit code 0 (kappa ≥ 0.7)
    ret = agreement_main([str(_AGREE_GOOD)])
    assert ret == 0, f"Expected exit 0, got {ret}"


# ---------------------------------------------------------------------------
# UC-152 — kappa < 0.7 → exit 1 with message
# ---------------------------------------------------------------------------
#
# Fixture: text = "Nowak" (5 chars)
#   ann_a: [{0,5,NAZWISKO}]
#   ann_b: []
#
# Strict/partial F1: TP=0, FP=0, FN=1 → P=0, R=0, F1=0
# Character labels:
#   A: NAZWISKO×5, O×0
#   B: O×5
#   Agreements: 0 (no position agrees)
#   p_o = 0
#   p_e = (5/5)·(0/5) + (0/5)·(5/5) = 0
#   kappa = (0 − 0) / (1 − 0) = 0


def test_uc152_agreement_kappa_below_threshold_exit_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """UC-152: kappa = 0.0 < 0.7 → exit 1; stderr message contains kappa and threshold."""
    import json

    records = [json.loads(line) for line in _AGREE_BAD.read_text().splitlines() if line.strip()]
    metrics = compute_agreement(records)

    # Strict/partial F1 = 0
    assert math.isclose(metrics["strict_overall"], 0.0, abs_tol=5e-5)
    assert math.isclose(metrics["partial_overall"], 0.0, abs_tol=5e-5)

    # Kappa = 0
    assert math.isclose(metrics["kappa"], 0.0, abs_tol=5e-5), (
        f"kappa = {metrics['kappa']:.6f}, expected 0.0"
    )

    # CLI exit 1 with message on stderr
    ret = agreement_main([str(_AGREE_BAD)])
    captured = capsys.readouterr()
    assert ret == 1, f"Expected exit 1, got {ret}"

    # Stderr must include kappa value and threshold
    assert "kappa" in captured.err.lower(), f"kappa not in stderr: {captured.err!r}"
    assert "0.7" in captured.err, f"threshold 0.7 not in stderr: {captured.err!r}"

    # Stdout must not contain document text
    assert "Nowak" not in captured.out, "Document text in stdout"
