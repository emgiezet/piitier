"""Integration tests for the piitier public API — detect() and mask().

Covers the integration-level acceptance criteria from PII-1-b:
  UC-7, UC-8, UC-9, UC-36 (mask on separated formats).

All PESEL numbers are synthetic, computed for this spec.
"""

from __future__ import annotations

import pytest

import piitier
from piitier.labels import Label

# ---------------------------------------------------------------------------
# UC-7: mask() replaces PESEL with [PESEL], leaves surrounding text intact
# ---------------------------------------------------------------------------


def test_uc7_mask_replaces_valid_pesel() -> None:
    """UC-7: piitier.mask('PESEL: 90051512340, tel.') → 'PESEL: [PESEL], tel.'"""
    result = piitier.mask("PESEL: 90051512340, tel.")
    assert result == "PESEL: [PESEL], tel."


# ---------------------------------------------------------------------------
# UC-8: detect() returns exactly one span with expected fields
# ---------------------------------------------------------------------------


def test_uc8_detect_returns_one_span() -> None:
    """UC-8: detect on 90051512340 returns one span with all expected fields."""
    spans = piitier.detect("PESEL: 90051512340, tel.")
    assert len(spans) == 1
    span = spans[0]
    assert span.start == 7
    assert span.end == 18
    assert span.label is Label.PESEL
    assert span.source == "rule"
    assert span.score == 1.0
    assert span.status == "valid"


def test_uc8_detect_span_slice_equals_pesel() -> None:
    """UC-8: text[span.start:span.end] reproduces the matched PESEL digits."""
    text = "PESEL: 90051512340, tel."
    spans = piitier.detect(text)
    assert len(spans) == 1
    assert text[spans[0].start : spans[0].end] == "90051512340"


# ---------------------------------------------------------------------------
# UC-9: wrong check digit → masked, status='suspect'
# ---------------------------------------------------------------------------


def test_uc9_suspect_pesel_is_masked() -> None:
    """UC-9: mask on 90051512341 (wrong check digit) returns [PESEL]."""
    result = piitier.mask("id: 90051512341")
    assert result == "id: [PESEL]"


def test_uc9_suspect_pesel_detect_status() -> None:
    """UC-9: detect on 90051512341 returns one span with status='suspect'."""
    spans = piitier.detect("id: 90051512341")
    assert len(spans) == 1
    assert spans[0].status == "suspect"
    assert spans[0].label is Label.PESEL


def test_uc9_suspect_pesel_is_never_dropped() -> None:
    """UC-9 / invariant-6: a bad check digit never causes the span to be dropped."""
    # 90051512341 — wrong check digit (correct is 0)
    spans = piitier.detect("90051512341")
    assert len(spans) == 1


# ---------------------------------------------------------------------------
# Additional API surface tests (density grid — public symbols)
# ---------------------------------------------------------------------------


def test_mask_empty_string_returns_empty() -> None:
    """mask('') → '' (UC-13 sub-case, exercised here at API level too)."""
    assert piitier.mask("") == ""


def test_detect_empty_string_returns_empty_list() -> None:
    """detect('') → [] — empty input produces no spans."""
    assert piitier.detect("") == []


def test_detect_no_pesel_in_text() -> None:
    """detect on text with no PESEL → empty list."""
    spans = piitier.detect("Brak danych osobowych tutaj.")
    assert spans == []


def test_mask_no_pesel_unchanged() -> None:
    """mask on text with no PESEL → identical string."""
    text = "Nic do zanonimizowania."
    assert piitier.mask(text) == text


def test_detect_sorted_by_start() -> None:
    """detect returns spans in ascending start-offset order."""
    text = "A: 90051512340 B: 05250112343 C"
    spans = piitier.detect(text)
    assert len(spans) == 2
    assert spans[0].start < spans[1].start


def test_mask_multiple_pesels() -> None:
    """mask handles multiple PESEL occurrences in one string."""
    text = "P1=90051512340 P2=05250112343"
    result = piitier.mask(text)
    assert result == "P1=[PESEL] P2=[PESEL]"


# ---------------------------------------------------------------------------
# UC-36: mask() on separated-format PESELs — public-API assertion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "900 515 123 40",
        "9005-1512-340",
        "90051 512340",
    ],
)
def test_uc36_mask_separated_format_returns_placeholder(text: str) -> None:
    """UC-36: mask on each separated format returns exactly '[PESEL]'."""
    assert piitier.mask(text) == "[PESEL]"


# ---------------------------------------------------------------------------
# PII-6-a: Anonymizer, sys.modules guard, ValueError
# ---------------------------------------------------------------------------


class _StubPredictor:
    """Minimal predictor stub: returns a single IMIE span at the start."""

    def predict(self, text: str) -> list:
        from piitier.labels import Label
        from piitier.spans import Span

        if len(text) < 3:
            return []
        return [Span(0, 3, Label.IMIE, "model:ner", 0.9, "valid")]


# UC-106 -----------------------------------------------------------------------


def test_uc106_anonymizer_stub_predictor_masks_name_and_pesel() -> None:
    """UC-106: Anonymizer(predictor=stub, threshold=0.5) masks name (NER) and PESEL (rule).

    Text: "Jan 90051512340"
    Stub returns IMIE [0,3) score=0.9 (>= 0.5 → kept).
    Rules detect PESEL [4,15).
    Expected: "[IMIĘ_n] [PESEL]"; zero changed characters outside spans.
    """
    text = "Jan 90051512340"
    anon = piitier.Anonymizer(predictor=_StubPredictor(), threshold=0.5)
    result = anon.mask(text)

    assert "[IMIĘ_n]" in result
    assert "[PESEL]" in result
    # The space between name and PESEL must be preserved (outside any span)
    assert result == "[IMIĘ_n] [PESEL]"


def test_uc106_anonymizer_detect_returns_fused_spans() -> None:
    """UC-106: Anonymizer.detect returns both rule and NER spans fused."""
    from piitier.labels import Label

    text = "Jan 90051512340"
    anon = piitier.Anonymizer(predictor=_StubPredictor(), threshold=0.0)
    spans = anon.detect(text)

    labels = {s.label for s in spans}
    assert Label.IMIE in labels
    assert Label.PESEL in labels

    # Non-overlapping, sorted
    starts = [s.start for s in spans]
    assert starts == sorted(starts)
    for i in range(len(spans) - 1):
        assert spans[i].end <= spans[i + 1].start


# UC-107 -----------------------------------------------------------------------


def test_uc107_mask_without_model_no_torch() -> None:
    """UC-107: piitier.mask(text) without a model does not load transformers or torch.

    Verified by running in a subprocess so that no prior test's imports contaminate
    sys.modules.
    """
    import subprocess
    import sys

    script = (
        "import piitier, sys;"
        "piitier.mask('PESEL: 90051512340');"
        "bad = [m for m in ('transformers', 'torch') if m in sys.modules];"
        "assert not bad, f'unexpected heavy imports: {bad}'"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"subprocess failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_uc107_mask_without_model_same_result() -> None:
    """UC-107: piitier.mask(text) without model produces the same output as before."""
    text = "PESEL: 90051512340, tel."
    assert piitier.mask(text) == "PESEL: [PESEL], tel."


# UC-110 -----------------------------------------------------------------------


def test_uc110_anonymizer_neither_arg_raises_valueerror() -> None:
    """UC-110: Anonymizer() with no arguments raises ValueError."""
    with pytest.raises(ValueError, match="exactly one"):
        piitier.Anonymizer()


def test_uc110_anonymizer_both_args_raises_valueerror() -> None:
    """UC-110: Anonymizer(model=..., predictor=...) raises ValueError."""
    from pathlib import Path

    with pytest.raises(ValueError, match="exactly one"):
        piitier.Anonymizer(model=Path("/some/path"), predictor=_StubPredictor())


def test_uc110_valueerror_before_torch_import() -> None:
    """UC-110: ValueError is raised before transformers/torch enter sys.modules."""
    import subprocess
    import sys

    script = (
        "import piitier, sys\n"
        "try:\n"
        "    piitier.Anonymizer()\n"
        "except ValueError:\n"
        "    pass\n"
        "assert 'transformers' not in sys.modules, 'transformers was imported'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"subprocess failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
