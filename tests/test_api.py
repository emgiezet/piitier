"""Integration tests for the piitier public API — detect() and mask().

Covers the integration-level acceptance criteria from PII-1-b:
  UC-7, UC-8, UC-9, UC-36 (mask on separated formats).

All PESEL numbers are synthetic, computed for this spec.
"""

from __future__ import annotations

import re
from pathlib import Path

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
    Expected: "[IMIĘ_1] [PESEL]" (IMIE is a numbered label; one occurrence → index 1).
    """
    text = "Jan 90051512340"
    anon = piitier.Anonymizer(predictor=_StubPredictor(), threshold=0.5)
    result = anon.mask(text)

    assert "[IMIĘ_1]" in result
    assert "[PESEL]" in result
    # The space between name and PESEL must be preserved (outside any span)
    assert result == "[IMIĘ_1] [PESEL]"


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


# ---------------------------------------------------------------------------
# Threshold validation (finding 3)
# ---------------------------------------------------------------------------


def test_threshold_nan_raises_valueerror() -> None:
    """Anonymizer raises ValueError for NaN threshold before any heavy import."""
    import math

    with pytest.raises(ValueError, match="threshold"):
        piitier.Anonymizer(predictor=_StubPredictor(), threshold=math.nan)


def test_threshold_gt1_raises_valueerror() -> None:
    """Anonymizer raises ValueError for threshold > 1."""
    with pytest.raises(ValueError, match="threshold"):
        piitier.Anonymizer(predictor=_StubPredictor(), threshold=1.5)


def test_threshold_lt0_raises_valueerror() -> None:
    """Anonymizer raises ValueError for threshold < 0."""
    with pytest.raises(ValueError, match="threshold"):
        piitier.Anonymizer(predictor=_StubPredictor(), threshold=-0.1)


# ---------------------------------------------------------------------------
# Nonexistent model path raises ValueError (finding 5)
# ---------------------------------------------------------------------------


def test_uc110_anonymizer_nonexistent_model_raises_valueerror() -> None:
    """Anonymizer(model=<nonexistent>) raises ValueError before loading transformers."""
    from pathlib import Path

    with pytest.raises(ValueError, match="not found"):
        piitier.Anonymizer(model=Path("/absolutely/nonexistent/path/xyz"))


def test_uc110_nonexistent_model_no_torch_import() -> None:
    """Nonexistent model path raises ValueError without touching torch/transformers."""
    import subprocess
    import sys

    script = (
        "import piitier, sys\n"
        "try:\n"
        "    piitier.Anonymizer(model='/absolutely/nonexistent/xyz')\n"
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


# ---------------------------------------------------------------------------
# PII-5-v4: resolve_checkpoint — hub.py unit tests (offline, monkeypatched)
# ---------------------------------------------------------------------------


def test_resolve_checkpoint_local_dir_returns_path(tmp_path: Path) -> None:
    """resolve_checkpoint on an existing dir returns that dir (local always wins)."""
    import piitier.ner.hub as hub

    assert hub.resolve_checkpoint(tmp_path) == tmp_path


def test_resolve_checkpoint_local_dir_beats_repo_id(tmp_path: Path) -> None:
    """A path that both is a local dir AND matches owner/name returns the local dir."""
    import piitier.ner.hub as hub

    # Build a directory whose string representation matches 'owner/name'.
    owner_dir = tmp_path / "owner"
    owner_dir.mkdir()
    ckpt_dir = owner_dir / "name"
    ckpt_dir.mkdir()

    assert hub.resolve_checkpoint(ckpt_dir) == ckpt_dir


def test_resolve_checkpoint_hub_id_calls_seam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hub repo id calls _snapshot_download with repo_id and revision; returns its path."""
    import piitier.ner.hub as hub

    fake_path = str(tmp_path)

    def fake_download(*, repo_id: str, revision: str | None = None) -> str:
        assert repo_id == "emgiezet/piitier"
        assert revision == "abc123"
        return fake_path

    monkeypatch.setattr(hub, "_snapshot_download", fake_download)
    result = hub.resolve_checkpoint("emgiezet/piitier", revision="abc123")
    assert result == tmp_path


def test_resolve_checkpoint_hub_id_no_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hub resolve with revision=None passes None through to the seam."""
    import piitier.ner.hub as hub

    fake_path = str(tmp_path)
    calls: list[dict[str, object]] = []

    def fake_download(*, repo_id: str, revision: str | None = None) -> str:
        calls.append({"repo_id": repo_id, "revision": revision})
        return fake_path

    monkeypatch.setattr(hub, "_snapshot_download", fake_download)
    hub.resolve_checkpoint("emgiezet/piitier")
    assert calls == [{"repo_id": "emgiezet/piitier", "revision": None}]


def test_resolve_checkpoint_non_dir_non_id_raises_valueerror() -> None:
    """Non-dir, non-id string raises ValueError with the path in the message."""
    import piitier.ner.hub as hub

    with pytest.raises(ValueError, match="model checkpoint not found"):
        hub.resolve_checkpoint("/absolutely/nonexistent/path/xyz")


def test_resolve_checkpoint_non_dir_non_id_message_contains_path() -> None:
    """ValueError message for an unrecognised path names the path."""
    import piitier.ner.hub as hub

    bad = "/no/such/dir"
    with pytest.raises(ValueError, match=re.escape(bad)):
        hub.resolve_checkpoint(bad)


def test_resolve_checkpoint_seam_raising_wraps_as_could_not_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the seam raises, resolve_checkpoint raises ValueError 'could not download'."""
    import piitier.ner.hub as hub

    def boom(*, repo_id: str, revision: str | None = None) -> str:
        raise OSError("network unreachable")

    monkeypatch.setattr(hub, "_snapshot_download", boom)
    with pytest.raises(ValueError, match="could not download emgiezet/piitier"):
        hub.resolve_checkpoint("emgiezet/piitier")


def test_resolve_checkpoint_import_error_mentions_ner_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ImportError from huggingface_hub produces ValueError mentioning piitier[ner]."""
    import piitier.ner.hub as hub

    # Force _snapshot_download to None so _load_snapshot_download tries to import.
    monkeypatch.setattr(hub, "_snapshot_download", None)

    # Patch builtins.__import__ so that importing huggingface_hub raises ImportError.
    import builtins

    real_import = builtins.__import__

    def patched_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "huggingface_hub":
            raise ImportError("No module named 'huggingface_hub'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", patched_import)
    with pytest.raises(ValueError, match="piitier\\[ner\\]"):
        hub.resolve_checkpoint("emgiezet/piitier")


def test_anonymizer_revision_passed_to_resolve_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anonymizer(model='owner/name', revision='rev') passes revision to resolve_checkpoint."""
    import piitier.ner.hub as hub
    from piitier.spans import Span

    class _FakePredictor:
        def predict(self, text: str) -> list[Span]:
            return []

    calls: list[dict[str, object]] = []
    fake_path = str(tmp_path)

    def fake_download(*, repo_id: str, revision: str | None = None) -> str:
        calls.append({"repo_id": repo_id, "revision": revision})
        return fake_path

    monkeypatch.setattr(hub, "_snapshot_download", fake_download)

    # NerPredictor will fail to load (empty dir) — catch that separately.
    with pytest.raises((ValueError, OSError, Exception)):
        piitier.Anonymizer(model="emgiezet/piitier", revision="v0.1.0")

    # The seam was called with the correct arguments.
    assert calls == [{"repo_id": "emgiezet/piitier", "revision": "v0.1.0"}]
