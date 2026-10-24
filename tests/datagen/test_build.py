"""Acceptance tests for PII-2-d — build and check commands (UC-22 – UC-29).

Subprocess tests invoke ``python -m piitier.datagen`` through the real interpreter
so every test exercises the actual public CLI, not mocks.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WORKTREE = Path(__file__).parent.parent.parent
PACKAGED_TEMPLATES = WORKTREE / "src" / "piitier" / "datagen" / "templates"

DOC_TYPES = frozenset(
    {
        "polisa",
        "zgloszenie_szkody",
        "umowa_kredytowa",
        "wyciag",
        "mail_klienta",
        "transkrypcja_infolinii",
        "wypis_szpitalny",
        "skierowanie",
        "zestawienie_prowizyjne",
    }
)

# Exact schema required by the spec
RECORD_KEYS = {"id", "doc_type", "template_id", "seed", "text", "spans"}
SPAN_KEYS = {"start", "end", "label", "entity", "text"}


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "piitier.datagen", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or WORKTREE),
    )


def _build(
    out: Path, n: int = 100, seed: int = 1, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return _run(
        "build",
        "--n",
        str(n),
        "--seed",
        str(seed),
        "--out",
        str(out),
        cwd=cwd,
    )


def _check(data_dir: Path, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return _run("check", str(data_dir), cwd=cwd)


def _records(data_dir: Path) -> list[dict]:
    """Return all JSONL records from train + dev."""
    records: list[dict] = []
    for fname in ("train.jsonl", "dev.jsonl"):
        p = data_dir / fname
        if p.exists():
            for raw in p.read_text(encoding="utf-8").splitlines():
                if raw.strip():
                    records.append(json.loads(raw))
    return records


def _split_for(template_id: str) -> str:
    """Mirror the production split function."""
    digest = int(hashlib.sha256(template_id.encode()).hexdigest(), 16)
    return "dev" if digest % 10 == 0 else "train"


# ---------------------------------------------------------------------------
# UC-22 — build exits 0; 100 total lines; exact schema
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_uc22_build_exit0_total_and_schema(tmp_path: Path) -> None:
    """build --n 100 --seed 1: exit 0; 100 lines total; every line has exact keys."""
    result = _build(tmp_path)
    assert result.returncode == 0, f"unexpected exit {result.returncode}: {result.stderr}"

    records = _records(tmp_path)
    assert len(records) == 100, f"expected 100 records, got {len(records)}"

    for rec in records:
        assert set(rec.keys()) == RECORD_KEYS, (
            f"doc {rec.get('id')!r} has wrong keys: {set(rec.keys())}"
        )
        assert isinstance(rec["text"], str)
        assert isinstance(rec["seed"], int)
        for span in rec["spans"]:
            assert set(span.keys()) == SPAN_KEYS, (
                f"span in {rec.get('id')!r} has wrong keys: {set(span.keys())}"
            )
            assert isinstance(span["start"], int)
            assert isinstance(span["end"], int)
            assert span["start"] < span["end"]
            assert isinstance(span["label"], str)


# ---------------------------------------------------------------------------
# UC-23 — check exits 0 on valid output
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_uc23_check_exit0_on_valid(tmp_path: Path) -> None:
    """check on valid build output: exit 0."""
    _build(tmp_path)
    result = _check(tmp_path)
    assert result.returncode == 0, f"check failed: {result.stderr}"


# ---------------------------------------------------------------------------
# UC-24 — check exits 1 naming bad doc; no document text in stderr
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_uc24_check_corrupted_exit1_names_doc_no_text(tmp_path: Path) -> None:
    """check after span.start += 1: exit 1; stderr has doc id; doc text absent."""
    _build(tmp_path)

    train = tmp_path / "train.jsonl"
    lines = train.read_text(encoding="utf-8").splitlines()

    corrupted_id: str | None = None
    corrupted_text: str | None = None
    for idx, raw in enumerate(lines):
        if not raw.strip():
            continue
        rec = json.loads(raw)
        if rec["spans"]:
            corrupted_id = rec["id"]
            corrupted_text = rec["text"]
            rec["spans"][0]["start"] += 1
            lines[idx] = json.dumps(rec, ensure_ascii=False)
            break

    assert corrupted_id is not None, "No spans found in train.jsonl — cannot corrupt"

    train.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = _check(tmp_path)
    assert result.returncode == 1, f"expected exit 1, got {result.returncode}"
    assert corrupted_id in result.stderr, (
        f"doc id {corrupted_id!r} not in stderr: {result.stderr!r}"
    )
    # Privacy: raw document text must not appear in error output
    assert corrupted_text not in result.stderr, "document text leaked into stderr"


# ---------------------------------------------------------------------------
# UC-25 — no template_id shared between train and dev
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_uc25_template_ids_disjoint(tmp_path: Path) -> None:
    """No template_id appears in both train.jsonl and dev.jsonl."""
    _build(tmp_path)

    train_ids: set[str] = set()
    dev_ids: set[str] = set()

    for raw in (tmp_path / "train.jsonl").read_text(encoding="utf-8").splitlines():
        if raw.strip():
            train_ids.add(json.loads(raw)["template_id"])

    for raw in (tmp_path / "dev.jsonl").read_text(encoding="utf-8").splitlines():
        if raw.strip():
            dev_ids.add(json.loads(raw)["template_id"])

    shared = train_ids & dev_ids
    assert not shared, f"template_ids in both splits: {shared}"


# ---------------------------------------------------------------------------
# UC-26 — byte-identical output across two identical runs
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_uc26_deterministic_output(tmp_path: Path) -> None:
    """Same build command run twice → byte-identical train.jsonl, dev.jsonl, manifest.json."""
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    out1.mkdir()
    out2.mkdir()

    _build(out1)
    _build(out2)

    for fname in ("train.jsonl", "dev.jsonl", "manifest.json"):
        assert (out1 / fname).read_bytes() == (out2 / fname).read_bytes(), (
            f"{fname} differs between runs"
        )


# ---------------------------------------------------------------------------
# UC-27 — exit 2 for bench/ and non-empty output; nothing written
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_uc27_bench_protection_exit2(tmp_path: Path) -> None:
    """build --out bench/x: exit 2; stderr 'refusing to write into bench/'; nothing written."""
    # Simulate a project layout where bench/ exists as a sibling of cwd
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    fake_bench = fake_root / "bench"
    fake_bench.mkdir()
    out = fake_bench / "x"

    result = _run(
        "build",
        "--n",
        "10",
        "--seed",
        "1",
        "--out",
        str(out),
        cwd=fake_root,
    )

    assert result.returncode == 2, f"expected exit 2, got {result.returncode}"
    assert "refusing to write into bench/" in result.stderr, result.stderr
    # Nothing must have been written
    assert not out.exists(), "output dir was created despite exit 2"


@pytest.mark.integration
def test_uc27_nonempty_protection_exit2(tmp_path: Path) -> None:
    """build --out <non-empty dir>: exit 2; stderr 'output directory not empty: <dir>'."""
    out = tmp_path / "output"
    out.mkdir()
    (out / "existing.txt").write_text("existing", encoding="utf-8")

    result = _build(out)

    assert result.returncode == 2, f"expected exit 2, got {result.returncode}"
    assert "output directory not empty" in result.stderr, result.stderr
    # Only the pre-existing file must remain — nothing extra written
    written = {p.name for p in out.iterdir()}
    assert written == {"existing.txt"}, f"unexpected files written: {written}"


@pytest.mark.integration
def test_uc27_bench_absolute_path_from_unrelated_cwd(tmp_path: Path) -> None:
    """bench guard fires on absolute path even when cwd has no bench/ sibling."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "bench").mkdir()
    out = project / "bench" / "blocked"

    # cwd is completely unrelated — old cwd-relative guard would miss this
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    result = _run(
        "build",
        "--n",
        "1",
        "--seed",
        "1",
        "--out",
        str(out),  # absolute path into bench/
        cwd=elsewhere,  # cwd has no bench/ at all
    )

    assert result.returncode == 2, f"expected exit 2, got {result.returncode}"
    assert "refusing to write into bench/" in result.stderr, result.stderr
    assert not out.exists(), "output dir was created despite exit 2"


@pytest.mark.integration
def test_uc27_bench_symlink_alias_protection(tmp_path: Path) -> None:
    """bench guard follows symlinks: a symlink resolving into bench/ is also rejected."""
    project = tmp_path / "project"
    project.mkdir()
    real_bench = project / "bench"
    real_bench.mkdir()

    # Symlink that aliases into bench/
    alias = tmp_path / "not_bench_looking"
    alias.symlink_to(real_bench)
    out = alias / "x"  # resolves to real_bench / "x" which is inside bench/

    result = _run(
        "build",
        "--n",
        "1",
        "--seed",
        "1",
        "--out",
        str(out),
        cwd=tmp_path,
    )

    assert result.returncode == 2, f"expected exit 2, got {result.returncode}"
    assert "refusing to write into bench/" in result.stderr, result.stderr
    assert not (real_bench / "x").exists(), "output written inside bench/ via symlink"


# ---------------------------------------------------------------------------
# UC-28 — manifest counts match JSONL
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_uc28_manifest_counts_match_jsonl(tmp_path: Path) -> None:
    """manifest span_counts, split_counts, n and seed all match the JSONL files."""
    _build(tmp_path)

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))

    # n and seed
    assert manifest["n"] == 100
    assert manifest["seed"] == 1

    # Recount from JSONL
    label_counts: dict[str, int] = {}
    split_counts: dict[str, int] = {"train": 0, "dev": 0}

    for fname, split in (("train.jsonl", "train"), ("dev.jsonl", "dev")):
        for raw in (tmp_path / fname).read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            rec = json.loads(raw)
            split_counts[split] += 1
            for span in rec["spans"]:
                lbl = span["label"]
                label_counts[lbl] = label_counts.get(lbl, 0) + 1

    assert manifest["span_counts"] == label_counts, (
        f"span_counts mismatch:\n  manifest={manifest['span_counts']}\n  jsonl={label_counts}"
    )
    assert manifest["split_counts"] == split_counts, (
        f"split_counts mismatch: manifest={manifest['split_counts']} jsonl={split_counts}"
    )
    assert split_counts["train"] + split_counts["dev"] == 100

    # Manifest must declare all expected fields
    expected_fields = {
        "n",
        "seed",
        "template_counts",
        "span_counts",
        "split_counts",
        "version",
        "inflection_fallbacks",
    }
    assert expected_fields <= set(manifest.keys()), (
        f"missing manifest fields: {expected_fields - set(manifest.keys())}"
    )
    assert manifest["inflection_fallbacks"] == 0


def test_manifest_fallback_aggregation_sum(monkeypatch, tmp_path: Path) -> None:
    """manifest inflection_fallbacks sums fallbacks across rendered documents with unknown names."""
    import random
    from dataclasses import replace

    from piitier.datagen import people
    from piitier.datagen.build import build

    tmpl_dir = tmp_path / "templates"
    polisa_dir = tmpl_dir / "polisa"
    polisa_dir.mkdir(parents=True)
    (polisa_dir / "cases.txt").write_text("{{OSOBA#1:gen}}", encoding="utf-8")

    base_person = people.make_person(random.Random(0))
    fixed = replace(base_person, first_name="Xqzwy", last_name="Xqzwy")
    monkeypatch.setattr(people, "make_person", lambda rng, avoid=frozenset(): fixed)

    corpus_out = tmp_path / "corpus"
    build(tmpl_dir, n=2, seed=0, out=corpus_out)
    manifest_data = json.loads((corpus_out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_data["inflection_fallbacks"] == 4


# ---------------------------------------------------------------------------
# UC-29 — every packaged template renders without error; all 8 doc types present
# ---------------------------------------------------------------------------


def test_uc29_packaged_templates_render_all_doc_types() -> None:
    """Render every packaged template at seed 0; no TemplateError; all 8 doc types covered."""
    from piitier.datagen.build import collect_templates
    from piitier.datagen.render import render

    templates = collect_templates(PACKAGED_TEMPLATES)
    assert templates, "No packaged templates found — check src/piitier/datagen/templates/"

    doc_types_seen: set[str] = set()
    for tmpl in templates:
        # Must not raise TemplateError
        doc = render(tmpl, seed=0)
        doc_types_seen.add(doc.doc_type)
        # Offset integrity as a bonus sanity check
        for span in doc.spans:
            assert doc.text[span.start : span.end] == span.text, (
                f"offset mismatch in {tmpl.template_id}: "
                f"{doc.text[span.start : span.end]!r} != {span.text!r}"
            )

    assert doc_types_seen == DOC_TYPES, f"Missing doc types: {DOC_TYPES - doc_types_seen}"


# ---------------------------------------------------------------------------
# Split correctness: sha256, not Python hash
# ---------------------------------------------------------------------------


def test_split_function_uses_sha256_not_python_hash() -> None:
    """_split_for must use sha256; mail_klienta_01 → dev; all others → train."""
    from piitier.datagen.build import _split_for

    assert _split_for("mail_klienta_01") == "dev"

    for tid in (
        "polisa_01",
        "zgloszenie_szkody_01",
        "umowa_kredytowa_01",
        "wyciag_01",
        "transkrypcja_infolinii_01",
        "wypis_szpitalny_01",
        "skierowanie_01",
    ):
        assert _split_for(tid) == "train", f"{tid!r} should be train"


# ---------------------------------------------------------------------------
# Train-coverage guard (UC-G1 – UC-G3)
# ---------------------------------------------------------------------------


def test_guard_forces_solo_dev_template_to_train(tmp_path: Path) -> None:
    """mail_klienta_01 hashes to dev; as the only mail_klienta template it must be
    forced to train: all documents are in train.jsonl and manifest lists it."""
    import json

    from piitier.datagen.build import _split_for, build

    # Sanity: confirm the fixture property holds.
    assert _split_for("mail_klienta_01") == "dev"

    tmpl_dir = tmp_path / "templates"
    mk_dir = tmpl_dir / "mail_klienta"
    mk_dir.mkdir(parents=True)
    (mk_dir / "mail_klienta_01.txt").write_text("Treść wiadomości.", encoding="utf-8")

    out = tmp_path / "corpus"
    build(tmpl_dir, n=5, seed=42, out=out)

    train_records = [
        json.loads(line)
        for line in (out / "train.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    dev_records = [
        json.loads(line)
        for line in (out / "dev.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert all(r["doc_type"] == "mail_klienta" for r in train_records)
    assert len(train_records) == 5
    assert len(dev_records) == 0

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert "mail_klienta" in manifest["split_forced_train"]


def test_guard_preserves_sha256_split_for_mixed_type(tmp_path: Path) -> None:
    """A doc type with one train-hashed (polisa_01) and one dev-hashed (polisa_06)
    template must NOT be forced; each template keeps its sha256 assignment."""
    import json

    from piitier.datagen.build import _split_for, build

    # Sanity: confirm fixture properties.
    assert _split_for("polisa_01") == "train"
    assert _split_for("polisa_06") == "dev"

    tmpl_dir = tmp_path / "templates"
    polisa_dir = tmpl_dir / "polisa"
    polisa_dir.mkdir(parents=True)
    (polisa_dir / "polisa_01.txt").write_text("Polisa A.", encoding="utf-8")
    (polisa_dir / "polisa_06.txt").write_text("Polisa B.", encoding="utf-8")

    out = tmp_path / "corpus"
    # Use enough docs so both templates are visited.
    build(tmpl_dir, n=10, seed=7, out=out)

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert "polisa" not in manifest["split_forced_train"]

    train_tids = {
        json.loads(line)["template_id"]
        for line in (out / "train.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    dev_tids = {
        json.loads(line)["template_id"]
        for line in (out / "dev.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }

    assert "polisa_01" in train_tids, "polisa_01 (train hash) must be in train"
    assert "polisa_06" in dev_tids, "polisa_06 (dev hash) must be in dev"
    assert "polisa_01" not in dev_tids, "polisa_01 must not appear in dev"
    assert "polisa_06" not in train_tids, "polisa_06 must not appear in train"


# ---------------------------------------------------------------------------
# Span offset integrity across multiple seeds (unit)
# ---------------------------------------------------------------------------


def test_packaged_template_span_integrity_across_seeds() -> None:
    """For seeds 0-9, every packaged template: doc.text[start:end] == span.text."""
    from piitier.datagen.build import collect_templates
    from piitier.datagen.render import render

    templates = collect_templates(PACKAGED_TEMPLATES)
    for seed in range(10):
        for tmpl in templates:
            doc = render(tmpl, seed=seed)
            for span in doc.spans:
                actual = doc.text[span.start : span.end]
                assert actual == span.text, (
                    f"seed={seed} tmpl={tmpl.template_id}: {actual!r} != {span.text!r}"
                )


# ---------------------------------------------------------------------------
# Regression: concrete check defects (CLI)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_check_missing_files_exit1(tmp_path: Path) -> None:
    """check on a directory without train.jsonl/dev.jsonl: exit 1 (dataset absent)."""
    # data_dir exists but has no JSONL files
    result = _check(tmp_path)
    assert result.returncode == 1, f"expected exit 1, got {result.returncode}: {result.stderr}"


# Parameterised cases: each tuple is (train_content, expected_exit_code, description).
# All cases use a valid dev.jsonl so only train is the anomaly (except case 4 which is
# valid — missing spans key → exit 1 because 'spans' is a required field).
_MALFORMED_TRAIN_CASES: list[tuple[str, int, str]] = [
    # Case 2 (from Main): record is a JSON array, not an object → TRACEBACK without fix
    (
        "[]\n",
        1,
        "record is a list not a dict",
    ),
    # Case 3 (from Main): text field is an integer → TypeError without fix
    (
        '{"id":"bad-text","text":123,"spans":[{"start":0,"end":1,"text":"x"}]}\n',
        1,
        "text is int not str",
    ),
    # Boolean offset: JSON true is not a valid integer index
    (
        '{"id":"bool-start","text":"ab","spans":[{"start":true,"end":2,"text":"ab"}]}\n',
        1,
        "start is boolean",
    ),
    # Case 4 (from Main): spans key absent → must not silently exit 0
    (
        '{"id":"missing-spans","text":"not-a-valid-record"}\n',
        1,
        "spans key missing",
    ),
    # spans is null (JSON null → Python None) → not a list
    (
        '{"id":"null-spans","text":"hello","spans":null}\n',
        1,
        "spans is null",
    ),
    # span item is not a dict
    (
        '{"id":"span-not-dict","text":"hello","spans":["bad"]}\n',
        1,
        "span item is a string not a dict",
    ),
]


@pytest.mark.integration
@pytest.mark.parametrize("train_content,expected_exit,description", _MALFORMED_TRAIN_CASES)
def test_check_rejects_malformed_records(
    tmp_path: Path,
    train_content: str,
    expected_exit: int,
    description: str,
) -> None:
    """check rejects malformed JSONL records safely; exit 1; no traceback in stderr."""
    # Write a minimal valid dev.jsonl (empty but present)
    (tmp_path / "dev.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "train.jsonl").write_text(train_content, encoding="utf-8")

    result = _check(tmp_path)

    assert result.returncode == expected_exit, (
        f"[{description}] expected exit {expected_exit}, "
        f"got {result.returncode}; stderr={result.stderr!r}"
    )
    # No Python traceback must appear in stderr
    assert "Traceback" not in result.stderr, f"[{description}] traceback leaked: {result.stderr!r}"


@pytest.mark.integration
def test_check_invalid_utf8_exit1_no_traceback(tmp_path: Path) -> None:
    """check on a file with invalid UTF-8 bytes: exit 1; no traceback in stderr."""
    # b'\xff' is not valid UTF-8 — triggers UnicodeDecodeError in read_text.
    (tmp_path / "train.jsonl").write_bytes(b"\xff")
    (tmp_path / "dev.jsonl").write_text("", encoding="utf-8")

    result = _check(tmp_path)

    assert result.returncode == 1, f"expected exit 1, got {result.returncode}"
    assert "Traceback" not in result.stderr, f"traceback leaked: {result.stderr!r}"
    # Error message must reference the filename but not raw bytes
    assert "train.jsonl" in result.stderr, f"filename absent from stderr: {result.stderr!r}"


# ---------------------------------------------------------------------------
# Regression: CRLF template fidelity (CLAUDE.md invariant 4)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_crlf_template_literal_preservation(tmp_path: Path) -> None:
    """collect_templates preserves CRLF verbatim; text outside spans is byte-identical
    to the template source (CLAUDE.md invariant 4).

    Root cause: Path.read_text() performs universal-newline translation (\\r\\n → \\n).
    Fix: read_bytes().decode('utf-8') is used instead.
    """
    # Build a custom template directory with a single CRLF template.
    tmpl_dir = tmp_path / "templates" / "polisa"
    tmpl_dir.mkdir(parents=True)

    # write_bytes guarantees no OS newline translation at write time.
    crlf_template = "Naglowek\r\nPESEL {{PESEL}}\r\nKoniec\r\n"
    (tmpl_dir / "crlf_01.txt").write_bytes(crlf_template.encode("utf-8"))

    out = tmp_path / "output"
    result = _run(
        "build",
        "--templates",
        str(tmp_path / "templates"),
        "--n",
        "1",
        "--seed",
        "0",
        "--out",
        str(out),
    )
    assert result.returncode == 0, f"build failed: {result.stderr}"

    records = _records(out)
    assert len(records) == 1
    rec = records[0]
    text = rec["text"]
    spans = rec["spans"]
    assert spans, "Expected at least one span (PESEL)"

    pesel_span = spans[0]
    start = pesel_span["start"]
    end = pesel_span["end"]

    # Exact prefix and suffix outside the generated span must match the template source.
    expected_prefix = "Naglowek\r\nPESEL "
    expected_suffix = "\r\nKoniec\r\n"

    assert text[:start] == expected_prefix, (
        f"Prefix outside span not preserved (CRLF lost?): {text[:start]!r}"
    )
    assert text[end:] == expected_suffix, (
        f"Suffix outside span not preserved (CRLF lost?): {text[end:]!r}"
    )

    # Offset integrity: the slice must equal the recorded span text.
    assert text[start:end] == pesel_span["text"], (
        f"Span offset mismatch: {text[start:end]!r} != {pesel_span['text']!r}"
    )
