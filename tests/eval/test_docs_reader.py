"""Tests for eval/run.py read_docs and synthetic JSONL reader (--docs path)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Dynamic module loading
# ---------------------------------------------------------------------------

_root = Path(__file__).resolve().parents[2]

# Load eval.metrics first (run.py imports it)
for _mod_name, _mod_path in [
    ("eval.metrics", _root / "eval" / "metrics.py"),
    ("eval.report", _root / "eval" / "report.py"),
]:
    if _mod_name not in sys.modules:
        _spec = importlib.util.spec_from_file_location(_mod_name, _mod_path)
        assert _spec is not None and _spec.loader is not None
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules[_mod_name] = _mod
        _spec.loader.exec_module(_mod)

# Load eval.baselines chain
_baselines_dir = _root / "eval" / "baselines"
for _bname in ["__init__", "piitier_systems", "presidio_pl", "bardsai_v2", "privacy_filter"]:
    _full = "eval.baselines" if _bname == "__init__" else f"eval.baselines.{_bname}"
    _bpath = _baselines_dir / ("__init__.py" if _bname == "__init__" else f"{_bname}.py")
    if _full not in sys.modules:
        _bs = importlib.util.spec_from_file_location(_full, _bpath)
        if _bs and _bs.loader:
            _bm = importlib.util.module_from_spec(_bs)
            sys.modules[_full] = _bm
            _bs.loader.exec_module(_bm)

_run_path = _root / "eval" / "run.py"
_run_spec = importlib.util.spec_from_file_location("eval.run", _run_path)
assert _run_spec is not None and _run_spec.loader is not None
_run_mod = importlib.util.module_from_spec(_run_spec)
sys.modules["eval.run"] = _run_mod
_run_spec.loader.exec_module(_run_mod)

read_docs = _run_mod.read_docs
BenchDoc = _run_mod.BenchDoc

# ---------------------------------------------------------------------------
# Fixture: two synthetic records in datagen format
# ---------------------------------------------------------------------------

_DOC1: dict[str, Any] = {
    "id": "doc_0000001",
    "doc_type": "polisa",
    "template_id": "polisa/ubezpieczenie_mieszkania_01",
    "seed": 42,
    "text": "Jan Kowalski, PESEL 90010112345.",
    "spans": [
        {"start": 0, "end": 12, "label": "OSOBA", "entity": "osoba", "text": "Jan Kowalski"},
        {"start": 20, "end": 31, "label": "PESEL", "entity": "pesel", "text": "90010112345"},
    ],
}

_DOC2: dict[str, Any] = {
    "id": "doc_0000002",
    "doc_type": "szkoda",
    "template_id": "szkoda/kolizja_01",
    "seed": 43,
    "text": "Email: test@example.com",
    "spans": [
        {
            "start": 7,
            "end": 23,
            "label": "EMAIL",
            "entity": "email",
            "text": "test@example.com",
        },
    ],
}


def _write_fixture(path: Path, records: list[dict[str, Any]]) -> Path:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records),
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_read_docs_two_records(tmp_path: Path) -> None:
    """read_docs parses both records from a 2-record JSONL file."""
    fixture = _write_fixture(tmp_path / "dev.jsonl", [_DOC1, _DOC2])

    docs = read_docs(fixture)

    assert len(docs) == 2
    assert docs[0].id == "doc_0000001"
    assert docs[0].doc_type == "polisa"
    assert len(docs[0].gold) == 2  # OSOBA + PESEL
    assert docs[1].id == "doc_0000002"
    assert docs[1].doc_type == "szkoda"
    assert len(docs[1].gold) == 1  # EMAIL


def test_read_docs_span_offsets_match_text(tmp_path: Path) -> None:
    """Gold span char slices exactly match the recorded span text."""
    fixture = _write_fixture(tmp_path / "dev.jsonl", [_DOC1])

    docs = read_docs(fixture)
    doc = docs[0]

    osoba = next(s for s in doc.gold if s.label.name == "OSOBA")
    assert doc.text[osoba.start : osoba.end] == "Jan Kowalski"

    pesel = next(s for s in doc.gold if s.label.name == "PESEL")
    assert doc.text[pesel.start : pesel.end] == "90010112345"


def test_read_docs_limit(tmp_path: Path) -> None:
    """read_docs with limit=1 returns only the first document."""
    fixture = _write_fixture(tmp_path / "dev.jsonl", [_DOC1, _DOC2])

    docs = read_docs(fixture, limit=1)

    assert len(docs) == 1
    assert docs[0].id == "doc_0000001"


def test_read_docs_limit_zero(tmp_path: Path) -> None:
    """read_docs with limit=0 returns empty list."""
    fixture = _write_fixture(tmp_path / "dev.jsonl", [_DOC1, _DOC2])

    docs = read_docs(fixture, limit=0)

    assert docs == []


def test_read_docs_extra_fields_ignored(tmp_path: Path) -> None:
    """Extra fields (template_id, seed, unknown) are silently ignored."""
    record = {**_DOC1, "extra_field": "ignored"}
    fixture = _write_fixture(tmp_path / "dev.jsonl", [record])

    docs = read_docs(fixture)  # must not raise

    assert len(docs) == 1


def test_read_docs_missing_file_raises(tmp_path: Path) -> None:
    """read_docs raises FileNotFoundError for a non-existent path."""
    with pytest.raises(FileNotFoundError, match="not found"):
        read_docs(tmp_path / "nonexistent.jsonl")


def test_read_docs_unknown_label_raises(tmp_path: Path) -> None:
    """read_docs raises ValueError for an unknown label name."""
    bad_record: dict[str, Any] = {
        **_DOC1,
        "spans": [
            {"start": 0, "end": 3, "label": "UNKNOWN_LABEL", "entity": "x", "text": "Jan"},
        ],
    }
    fixture = _write_fixture(tmp_path / "dev.jsonl", [bad_record])

    with pytest.raises(ValueError, match="unknown label"):
        read_docs(fixture)


def test_read_docs_empty_file(tmp_path: Path) -> None:
    """read_docs returns empty list for an empty file."""
    fixture = tmp_path / "dev.jsonl"
    fixture.write_text("", encoding="utf-8")

    docs = read_docs(fixture)
    assert docs == []


def test_read_docs_blank_lines_skipped(tmp_path: Path) -> None:
    """read_docs skips blank lines without error."""
    content = (
        json.dumps(_DOC1, ensure_ascii=False)
        + "\n\n"
        + json.dumps(_DOC2, ensure_ascii=False)
        + "\n"
    )
    fixture = tmp_path / "dev.jsonl"
    fixture.write_text(content, encoding="utf-8")

    docs = read_docs(fixture)
    assert len(docs) == 2


def test_read_docs_gold_source_is_gold(tmp_path: Path) -> None:
    """Gold spans have source='gold', status='valid', and score=1.0."""
    fixture = _write_fixture(tmp_path / "dev.jsonl", [_DOC1])
    docs = read_docs(fixture)

    for span in docs[0].gold:
        assert span.source == "gold"
        assert span.status == "valid"
        assert span.score == 1.0
