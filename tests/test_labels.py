"""Tests for Label enum and taxonomy sync (UC-2, UC-3, UC-4)."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TAXONOMY_PATH = Path(__file__).parent.parent / "docs" / "TAXONOMY.md"


# ---------------------------------------------------------------------------
# Helpers — taxonomy parser (not production code; lives here for sync tests)
# ---------------------------------------------------------------------------


def _parse_taxonomy_placeholders(path: Path) -> set[str]:
    """Return the set of placeholder strings in the Placeholder column of *path*.

    Skips the header row and any separator / non-data rows.  The table format is:
    ``| Grupa | Encja | Placeholder | Metoda |`` — placeholder is column index 3
    (0-indexed after splitting on ``|``).
    """
    placeholders: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")]
        # parts: ['', Grupa, Encja, Placeholder, Metoda, '']
        if len(parts) < 5:
            continue
        cell = parts[3]
        if cell.startswith("[") and cell.endswith("]"):
            placeholders.add(cell)
    return placeholders


def _check_taxonomy_sync(taxonomy_path: Path) -> None:
    """Assert that *taxonomy_path* placeholders and ``Label`` placeholders are identical.

    Raises ``AssertionError`` naming every out-of-sync placeholder so the failure
    message can be inspected in UC-3.
    """
    from piitier.labels import Label  # imported here so test file is importable before impl

    taxonomy = _parse_taxonomy_placeholders(taxonomy_path)
    labels = {lbl.placeholder for lbl in Label}

    extra_in_taxonomy = taxonomy - labels
    extra_in_labels = labels - taxonomy

    parts: list[str] = []
    if extra_in_taxonomy:
        parts.append(f"in taxonomy but not in Label: {sorted(extra_in_taxonomy)}")
    if extra_in_labels:
        parts.append(f"in Label but not in taxonomy: {sorted(extra_in_labels)}")
    assert not parts, "; ".join(parts)


# ---------------------------------------------------------------------------
# UC-1 — package importable (integration: runs after uv sync)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_uc1_version_printed_by_interpreter() -> None:
    """UC-1: `python -c 'import piitier; print(piitier.__version__)'` prints 0.1.0."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import piitier; print(piitier.__version__)",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"non-zero exit: {result.stderr}"
    assert result.stdout.strip() == "0.1.0"


# ---------------------------------------------------------------------------
# UC-2 — taxonomy / Label sync passes for the real files
# ---------------------------------------------------------------------------


def test_uc2_taxonomy_label_sync_passes() -> None:
    """UC-2: TAXONOMY.md placeholders == Label.placeholder set; exactly 39 entries."""
    _check_taxonomy_sync(TAXONOMY_PATH)  # raises AssertionError on mismatch
    assert len(_parse_taxonomy_placeholders(TAXONOMY_PATH)) == 39


# ---------------------------------------------------------------------------
# UC-3 — adding a taxonomy row without a Label member is caught
# ---------------------------------------------------------------------------


def test_uc3_sync_fails_and_names_the_missing_placeholder(tmp_path: Path) -> None:
    """UC-3: extra taxonomy row (no matching Label member) → AssertionError naming it."""
    modified = tmp_path / "TAXONOMY.md"
    shutil.copy(TAXONOMY_PATH, modified)
    with modified.open("a", encoding="utf-8") as fh:
        fh.write("| Test | EXTRA_ENTITY | [UC3_EXTRA_PH] | NER |\n")

    with pytest.raises(AssertionError, match=r"\[UC3_EXTRA_PH\]"):
        _check_taxonomy_sync(modified)


# ---------------------------------------------------------------------------
# UC-4 — placeholder / numbered attributes on every member
# ---------------------------------------------------------------------------

_NUMBERED_NAMES = {"OSOBA", "IMIE", "NAZWISKO", "ADRES", "LEKARZ"}


def test_uc4_numbered_types_have_flag_and_n_suffix() -> None:
    """UC-4: numbered types have numbered=True and '[..._n]' placeholder."""
    from piitier.labels import Label

    for lbl in Label:
        if lbl.name in _NUMBERED_NAMES:
            assert lbl.numbered is True, f"Label.{lbl.name}.numbered should be True"
            assert lbl.placeholder.endswith("_n]"), (
                f"Label.{lbl.name}.placeholder={lbl.placeholder!r} should end with '_n]'"
            )
        else:
            assert lbl.numbered is False, f"Label.{lbl.name}.numbered should be False"
            assert not lbl.placeholder.endswith("_n]"), (
                f"Label.{lbl.name}.placeholder={lbl.placeholder!r} should not end with '_n]'"
            )


def test_uc4_diacritics_preserved_in_placeholders() -> None:
    """UC-4: ASCII member names, Unicode placeholders (diacritics verbatim)."""
    from piitier.labels import Label

    # Spec UC-4 example: Label.MIEJSCOWOSC.placeholder == "[MIEJSCOWOŚĆ]"
    assert Label.MIEJSCOWOSC.placeholder == "[MIEJSCOWOŚĆ]"
    assert Label.IMIE.placeholder == "[IMIĘ_n]"
    assert Label.PLEC.placeholder == "[PŁEĆ]"
    assert Label.DOCHOD.placeholder == "[DOCHÓD]"
    assert Label.PLACOWKA.placeholder == "[PLACÓWKA]"


def test_uc4_all_placeholders_roundtrip_taxonomy() -> None:
    """UC-4: every Label member's placeholder is found verbatim in TAXONOMY.md."""
    from piitier.labels import Label

    taxonomy_set = _parse_taxonomy_placeholders(TAXONOMY_PATH)
    for lbl in Label:
        assert lbl.placeholder in taxonomy_set, (
            f"Label.{lbl.name}.placeholder={lbl.placeholder!r} not in TAXONOMY.md"
        )
