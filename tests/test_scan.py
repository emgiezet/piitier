"""Tests for ``piitier scan`` and the repository licence files (PII-8)."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from piitier import cli
from piitier.labels import Label
from piitier.scan import fingerprint

REPO_ROOT = Path(__file__).resolve().parents[1]
VALID_PESEL = "44051401359"  # synthetic, checksum-valid
INVALID_PESEL = "44051401358"  # same shape, checksum fails → suspect

# SHA-256 of https://www.apache.org/licenses/LICENSE-2.0.txt
APACHE_2_SHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"


def _scan(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["piitier", "scan", *args])
    return cli.main()


def test_uc126_license_is_canonical_apache_2_and_notice_names_owner() -> None:
    license_bytes = (REPO_ROOT / "LICENSE").read_bytes()
    assert hashlib.sha256(license_bytes).hexdigest() == APACHE_2_SHA256
    notice = (REPO_ROOT / "NOTICE").read_text(encoding="utf-8")
    assert "piitier" in notice
    assert "Copyright" in notice


def test_uc127_valid_identifier_outside_allowlist_fails_without_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    doc = tmp_path / "doc.txt"
    doc.write_text(f"Klient\nPESEL {VALID_PESEL} w drugiej linii.\n", encoding="utf-8")

    rc = _scan(monkeypatch, str(doc))

    out, err = capsys.readouterr()
    assert rc == 1
    assert f"{doc}:2:7: PESEL" in out
    assert VALID_PESEL not in out
    assert VALID_PESEL not in err


def test_uc128_allowlisted_fingerprint_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    doc = tmp_path / "doc.txt"
    doc.write_text(f"PESEL {VALID_PESEL}\n", encoding="utf-8")
    allow = tmp_path / "allow.txt"
    allow.write_text(f"# synthetic\n{fingerprint(Label.PESEL, VALID_PESEL)}\n", encoding="utf-8")

    rc = _scan(monkeypatch, "--allowlist", str(allow), str(doc))

    assert rc == 0
    assert capsys.readouterr().out == ""


def test_uc129_suspect_clean_and_binary_files_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    suspect = tmp_path / "suspect.txt"
    suspect.write_text(f"PESEL {INVALID_PESEL}\n", encoding="utf-8")
    clean = tmp_path / "clean.md"
    clean.write_text("Brak identyfikatorów.\n", encoding="utf-8")
    binary = tmp_path / "blob.bin"
    binary.write_bytes(b"\x00\xff" + VALID_PESEL.encode() + b"\x00")
    latin = tmp_path / "latin.txt"
    latin.write_bytes(b"\xe6\xf3\xb3 " + VALID_PESEL.encode())  # not valid UTF-8

    rc = _scan(monkeypatch, str(suspect), str(clean), str(binary), str(latin))

    assert rc == 0
    assert capsys.readouterr().out == ""


def test_uc130_write_allowlist_then_rescan_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = tmp_path / "doc.txt"
    doc.write_text(f"PESEL {VALID_PESEL} i ponownie {VALID_PESEL}\n", encoding="utf-8")
    allow = tmp_path / "allow.txt"

    assert _scan(monkeypatch, "--write-allowlist", str(allow), str(doc)) == 0

    written = allow.read_text(encoding="utf-8")
    entries = [line for line in written.splitlines() if line and not line.startswith("#")]
    assert entries == [fingerprint(Label.PESEL, VALID_PESEL)]
    assert VALID_PESEL not in written
    assert _scan(monkeypatch, "--allowlist", str(allow), str(doc)) == 0


def test_scan_missing_path_or_allowlist_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _scan(monkeypatch, str(tmp_path / "missing.txt")) == 2
    doc = tmp_path / "doc.txt"
    doc.write_text("x\n", encoding="utf-8")
    assert _scan(monkeypatch, "--allowlist", str(tmp_path / "nope"), str(doc)) == 2


def test_scan_does_not_import_torch(tmp_path: Path) -> None:
    doc = tmp_path / "doc.txt"
    doc.write_text(f"PESEL {VALID_PESEL}\n", encoding="utf-8")
    probe = (
        "import sys\n"
        "from piitier import cli\n"
        f"sys.argv = ['piitier', 'scan', {str(doc)!r}]\n"
        "rc = cli.main()\n"
        "print(rc, 'torch' in sys.modules, 'transformers' in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip().splitlines()[-1] == "1 False False"
