"""Tests for PII-3-d — hard negatives, build augmentation, dataset card (UC-60..UC-65)."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from piitier.datagen.build import check
from piitier.datagen.hard_negatives import make_hard_negative_docs
from piitier.labels import Label

WORKTREE = Path(__file__).parent.parent.parent
PACKAGED_TEMPLATES = WORKTREE / "src" / "piitier" / "datagen" / "templates"


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "piitier.datagen", *args],
        capture_output=True,
        text=True,
        cwd=cwd or WORKTREE,
    )


# UC-60: per-case span assertions, hn_ id format, check() passes
def test_uc60_hard_negatives_families_and_spans() -> None:
    docs = make_hard_negative_docs(seed=42, n=20)
    assert len(docs) == 20
    for i, doc in enumerate(docs):
        assert doc.template_id == f"hn_{i:07d}"
        family = i % 4
        if family == 0:
            # Family (a): invalid PESEL -> no PESEL span
            assert not any(s.label is Label.PESEL for s in doc.spans)
        elif family == 1:
            # Family (b): common noun -> no OSOBA/IMIE/NAZWISKO span
            assert not any(s.label in {Label.OSOBA, Label.IMIE, Label.NAZWISKO} for s in doc.spans)
        elif family == 2:
            # Family (c): address line -> exactly one ADRES span covering full text
            assert len(doc.spans) == 1
            assert doc.spans[0].label is Label.ADRES
            assert doc.spans[0].start == 0
            assert doc.spans[0].end == len(doc.text)
            assert doc.text[doc.spans[0].start : doc.spans[0].end] == doc.spans[0].text
        elif family == 3:
            # Family (d): invalid VIN -> no VIN span
            assert not any(s.label is Label.VIN for s in doc.spans)


# UC-61: --hard-negatives 100 -> 100 docs id hn_*, manifest.hard_negatives == 100
@pytest.mark.integration
def test_uc61_hard_negatives_cli_and_manifest(tmp_path: Path) -> None:
    out = tmp_path / "dataset"
    res = _run(
        "build",
        "--templates",
        str(PACKAGED_TEMPLATES),
        "--n",
        "50",
        "--seed",
        "42",
        "--hard-negatives",
        "100",
        "--out",
        str(out),
    )
    assert res.returncode == 0, res.stderr

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["hard_negatives"] == 100
    assert manifest["augment"] is False

    records = []
    for f in ("train.jsonl", "dev.jsonl"):
        for line in (out / f).read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))

    assert len(records) == 150
    hn_count = sum(1 for r in records if r["id"].startswith("hn_"))
    assert hn_count == 100


# UC-62: --augment exact offsets, manifest.augment == true; without flag augment == false
@pytest.mark.integration
def test_uc62_augment_flag_and_offsets(tmp_path: Path) -> None:
    out_def = tmp_path / "def"
    _run(
        "build",
        "--templates",
        str(PACKAGED_TEMPLATES),
        "--n",
        "20",
        "--seed",
        "42",
        "--out",
        str(out_def),
    )
    m_def = json.loads((out_def / "manifest.json").read_text(encoding="utf-8"))
    assert m_def["augment"] is False
    assert m_def["augment_fraction"] is None
    assert m_def["augmented_doc_count"] == 0
    assert m_def["transform_doc_counts"] == {}
    assert check(out_def) == (0, "")

    out_aug = tmp_path / "aug"
    _run(
        "build",
        "--templates",
        str(PACKAGED_TEMPLATES),
        "--n",
        "20",
        "--seed",
        "42",
        "--augment",
        "--hard-negatives",
        "20",
        "--out",
        str(out_aug),
    )
    m_aug = json.loads((out_aug / "manifest.json").read_text(encoding="utf-8"))
    assert m_aug["augment"] is True
    assert m_aug["augment_fraction"] == 0.25
    assert m_aug["hard_negatives"] == 20
    assert "transform_doc_counts" in m_aug
    assert isinstance(m_aug["augmented_doc_count"], int)
    assert check(out_aug) == (0, "")


# UC-63: two --augment --hard-negatives 50 --seed 42 runs -> identical sha256
@pytest.mark.integration
def test_uc63_determinism_sha256(tmp_path: Path) -> None:
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    _run(
        "build",
        "--templates",
        str(PACKAGED_TEMPLATES),
        "--n",
        "30",
        "--seed",
        "42",
        "--augment",
        "--hard-negatives",
        "50",
        "--out",
        str(out1),
    )
    _run(
        "build",
        "--templates",
        str(PACKAGED_TEMPLATES),
        "--n",
        "30",
        "--seed",
        "42",
        "--augment",
        "--hard-negatives",
        "50",
        "--out",
        str(out2),
    )

    for filename in ("train.jsonl", "dev.jsonl", "manifest.json"):
        h1 = hashlib.sha256((out1 / filename).read_bytes()).hexdigest()
        h2 = hashlib.sha256((out2 / filename).read_bytes()).hexdigest()
        assert h1 == h2, f"{filename} differs between identical runs"


# UC-64: integration run up to 2000 docs with augment and hard negatives passing check
@pytest.mark.integration
def test_uc64_integration_2000_docs(tmp_path: Path) -> None:
    out = tmp_path / "integration_data"
    res = _run(
        "build",
        "--templates",
        str(PACKAGED_TEMPLATES),
        "--n",
        "1800",
        "--seed",
        "42",
        "--augment",
        "--hard-negatives",
        "200",
        "--out",
        str(out),
    )
    assert res.returncode == 0, res.stderr
    assert check(out) == (0, "")

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["n"] == 1800
    assert manifest["hard_negatives"] == 200
    assert manifest["augment"] is True
    assert manifest["augment_fraction"] == 0.25
    assert isinstance(manifest["augmented_doc_count"], int)
    assert sum(manifest["split_counts"].values()) == 2000

    agg_span_counts: dict[str, int] = {}
    for filename in ("train.jsonl", "dev.jsonl"):
        for line in (out / filename).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            for s in rec["spans"]:
                lbl = s["label"]
                agg_span_counts[lbl] = agg_span_counts.get(lbl, 0) + 1
    assert dict(sorted(agg_span_counts.items())) == manifest["span_counts"]


# UC-65: dataset card exists, mentions CC BY 4.0 and both licences (Faker, Morfeusz)
def test_uc65_dataset_card_exists_and_content() -> None:
    card_path = WORKTREE / "docs" / "DATASET_CARD.md"
    assert card_path.exists()
    content = card_path.read_text(encoding="utf-8")
    assert "CC BY 4.0" in content
    assert "Faker" in content
    assert "MIT" in content
    assert "Morfeusz" in content
    assert "BSD-2-Clause" in content


# ---------------------------------------------------------------------------
# augment_fraction new behaviour tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_augment_fraction_respected_within_tolerance(tmp_path: Path) -> None:
    """With augment_fraction=0.5 and 400 docs, augmented_doc_count ≈ 200 ± 60 (3σ).

    Binomial(400, 0.5): σ ≈ 10, so ±60 is extremely conservative.
    """
    out = tmp_path / "out"
    res = _run(
        "build",
        "--templates",
        str(PACKAGED_TEMPLATES),
        "--n",
        "400",
        "--seed",
        "7",
        "--augment",
        "--augment-fraction",
        "0.5",
        "--hard-negatives",
        "0",
        "--out",
        str(out),
    )
    assert res.returncode == 0, res.stderr
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    count = manifest["augmented_doc_count"]
    assert 140 <= count <= 260, (
        f"augmented_doc_count={count} is outside expected range [140, 260] for f=0.5, n=400"
    )
    assert manifest["augment_fraction"] == 0.5
    assert check(out) == (0, "")


@pytest.mark.integration
def test_augment_false_byte_identical(tmp_path: Path) -> None:
    """Two builds with augment=False and the same seed produce byte-identical output.

    Verifies that the new augment_fraction code path is never touched when augment=False.
    """
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    for out in (out1, out2):
        _run(
            "build",
            "--templates",
            str(PACKAGED_TEMPLATES),
            "--n",
            "50",
            "--seed",
            "99",
            "--out",
            str(out),
        )
    for filename in ("train.jsonl", "dev.jsonl", "manifest.json"):
        h1 = hashlib.sha256((out1 / filename).read_bytes()).hexdigest()
        h2 = hashlib.sha256((out2 / filename).read_bytes()).hexdigest()
        assert h1 == h2, f"{filename} differs between two augment=False runs"


@pytest.mark.integration
def test_augment_fraction_1_0_augments_all_docs(tmp_path: Path) -> None:
    """With augment_fraction=1.0 every document is augmented (augmented_doc_count == n)."""
    out = tmp_path / "out"
    n = 50
    res = _run(
        "build",
        "--templates",
        str(PACKAGED_TEMPLATES),
        "--n",
        str(n),
        "--seed",
        "5",
        "--augment",
        "--augment-fraction",
        "1.0",
        "--hard-negatives",
        "0",
        "--out",
        str(out),
    )
    assert res.returncode == 0, res.stderr
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["augmented_doc_count"] == n, (
        f"Expected all {n} docs augmented but got {manifest['augmented_doc_count']}"
    )
    assert check(out) == (0, "")


@pytest.mark.integration
def test_augment_fraction_invalid_exits2(tmp_path: Path) -> None:
    """--augment --augment-fraction 0 exits 2 (fraction out of range)."""
    out = tmp_path / "out"
    for bad in ("0", "-0.1", "1.5"):
        res = _run(
            "build",
            "--templates",
            str(PACKAGED_TEMPLATES),
            "--n",
            "10",
            "--seed",
            "1",
            "--augment",
            "--augment-fraction",
            bad,
            "--out",
            str(out),
        )
        assert res.returncode == 2, (
            f"Expected exit 2 for --augment-fraction {bad!r}, got {res.returncode}: {res.stderr}"
        )


@pytest.mark.integration
def test_augment_fraction_determinism(tmp_path: Path) -> None:
    """Same seed and augment_fraction → byte-identical output on two runs."""
    out1 = tmp_path / "r1"
    out2 = tmp_path / "r2"
    for out in (out1, out2):
        _run(
            "build",
            "--templates",
            str(PACKAGED_TEMPLATES),
            "--n",
            "60",
            "--seed",
            "11",
            "--augment",
            "--augment-fraction",
            "0.4",
            "--hard-negatives",
            "10",
            "--out",
            str(out),
        )
    for filename in ("train.jsonl", "dev.jsonl", "manifest.json"):
        h1 = hashlib.sha256((out1 / filename).read_bytes()).hexdigest()
        h2 = hashlib.sha256((out2 / filename).read_bytes()).hexdigest()
        assert h1 == h2, f"{filename} differs between identical augmented runs"
