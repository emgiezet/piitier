"""Integration tests for piitier mask <file> CLI.

Tests the end-to-end command-line interface for masking files.
Fixtures are synthetic and contain only the test PESEL 90051512340.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def tmp_txt_pesel(tmp_path: Path) -> Path:
    """Create a temporary .txt file with a PESEL."""
    path = tmp_path / "in.txt"
    path.write_text("PESEL: 90051512340, tel.", encoding="utf-8")
    return path


@pytest.fixture
def tmp_md_pesel(tmp_path: Path) -> Path:
    """Create a temporary .md file with Markdown structure and PESEL."""
    path = tmp_path / "in.md"
    content = (
        "# Header\n\nTable:\n| Name | ID |\n|------|----|\n"
        "| Test | 90051512340 |\n\nCode:\n```python\n"
        "id = 90051512340\n```"
    )
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def tmp_csv_pesel(tmp_path: Path) -> Path:
    """Create a temporary .csv file with semicolon delimiter and CRLF."""
    path = tmp_path / "in.csv"
    content = "Name;ID;Amount\r\nJohn;90051512340;1000\r\nJane;12345678901;2000\r\n"
    path.write_bytes(content.encode("utf-8"))
    return path


@pytest.fixture
def tmp_csv_cp1250(tmp_path: Path) -> Path:
    """Create a temporary .csv file with cp1250 encoding and Polish chars."""
    path = tmp_path / "in.csv"
    # Łódź;90051512340 in cp1250
    content = "Łódź;90051512340"
    path.write_bytes(content.encode("cp1250"))
    return path


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def run_piitier_mask(args: list[str]) -> tuple[int, bytes, bytes]:
    """Run piitier mask command and return (exit_code, stdout_bytes, stderr_bytes).

    Uses binary mode to preserve exact line endings (CRLF vs LF).
    """
    result = subprocess.run(
        [sys.executable, "-m", "piitier.cli"] + args,
        capture_output=True,
    )
    return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# UC-28: piitier mask in.txt
# ---------------------------------------------------------------------------


def test_uc28_mask_txt_stdout(tmp_txt_pesel: Path) -> None:
    """UC-28: piitier mask in.txt outputs masked text to stdout."""
    exit_code, stdout_bytes, stderr_bytes = run_piitier_mask(["mask", str(tmp_txt_pesel)])

    assert exit_code == 0
    assert stdout_bytes == b"PESEL: [PESEL], tel."
    assert stderr_bytes == b""


# ---------------------------------------------------------------------------
# UC-29: piitier mask in.md with Markdown structure
# ---------------------------------------------------------------------------


def test_uc29_mask_md_preserves_structure(tmp_md_pesel: Path) -> None:
    """UC-29: piitier mask in.md preserves Markdown byte-for-byte outside spans."""
    original = tmp_md_pesel.read_text(encoding="utf-8")
    exit_code, stdout_bytes, stderr_bytes = run_piitier_mask(["mask", str(tmp_md_pesel)])

    assert exit_code == 0
    assert stderr_bytes == b""
    stdout = stdout_bytes.decode("utf-8")
    # Verify structure is preserved: headings, pipes, backticks all present
    assert "# Header" in stdout
    assert "| Name | ID |" in stdout
    assert "```python" in stdout
    # Verify PESEL is masked
    assert "[PESEL]" in stdout
    assert "90051512340" not in stdout
    # Verify structure: exact same bytes outside PESEL span in original
    pesel_str = "90051512340"
    pesel_idx = original.find(pesel_str)
    # Characters before PESEL should be identical
    assert original[:pesel_idx] == stdout[:pesel_idx]
    # Verify replacement happened
    assert stdout[pesel_idx : pesel_idx + 7] == "[PESEL]"


# ---------------------------------------------------------------------------
# UC-30: piitier mask in.csv with delimiters and line endings
# ---------------------------------------------------------------------------


def test_uc30_mask_csv_preserves_format(tmp_csv_pesel: Path) -> None:
    """UC-30: piitier mask in.csv preserves row count, delimiter, CRLF."""
    exit_code, stdout_bytes, stderr_bytes = run_piitier_mask(["mask", str(tmp_csv_pesel)])

    assert exit_code == 0
    assert stderr_bytes == b""
    # Verify line endings are CRLF
    assert stdout_bytes == (b"Name;ID;Amount\r\nJohn;[PESEL];1000\r\nJane;[PESEL];2000\r\n")
    # Verify row count (split by CRLF)
    lines = stdout_bytes.split(b"\r\n")
    assert len(lines) == 4  # 3 rows + empty after final CRLF
    # Verify delimiter is preserved
    assert b";" in stdout_bytes
    # Verify PESEL is replaced with placeholder
    assert b"[PESEL]" in stdout_bytes
    assert b"90051512340" not in stdout_bytes


# ---------------------------------------------------------------------------
# UC-33: piitier mask -o out.txt and refusal to overwrite
# ---------------------------------------------------------------------------


def test_uc33_mask_with_output_file(tmp_path: Path, tmp_txt_pesel: Path) -> None:
    """UC-33: piitier mask -o out.txt writes to file, stdout empty."""
    out_path = tmp_path / "out.txt"
    exit_code, stdout_bytes, stderr_bytes = run_piitier_mask(
        ["mask", str(tmp_txt_pesel), "-o", str(out_path)]
    )

    assert exit_code == 0
    assert stdout_bytes == b""  # stdout must be empty
    assert stderr_bytes == b""
    assert out_path.read_text(encoding="utf-8") == "PESEL: [PESEL], tel."


def test_uc33_refuse_overwrite_input(tmp_txt_pesel: Path) -> None:
    """UC-33: piitier mask -o in.txt exits 2, input unchanged."""
    original_content = tmp_txt_pesel.read_text(encoding="utf-8")
    exit_code, stdout_bytes, stderr_bytes = run_piitier_mask(
        ["mask", str(tmp_txt_pesel), "-o", str(tmp_txt_pesel)]
    )

    assert exit_code == 2
    assert stderr_bytes.decode("utf-8") == f"refusing to overwrite input: {tmp_txt_pesel}\n"
    assert stdout_bytes == b""
    assert tmp_txt_pesel.read_text(encoding="utf-8") == original_content


# ---------------------------------------------------------------------------
# UC-34: unsupported file type and missing file
# ---------------------------------------------------------------------------


def test_uc34_unsupported_file_type(tmp_path: Path) -> None:
    """UC-34: piitier mask in.docx exits 2, stderr 'unsupported file type'."""
    docx_path = tmp_path / "in.docx"
    docx_path.write_bytes(b"fake docx content")
    exit_code, stdout_bytes, stderr_bytes = run_piitier_mask(["mask", str(docx_path)])

    assert exit_code == 2
    assert b"unsupported file type: .docx" in stderr_bytes
    assert stdout_bytes == b""


def test_uc34_missing_file(tmp_path: Path) -> None:
    """UC-34: piitier mask missing.txt exits 2, stderr 'not found'."""
    missing_path = tmp_path / "missing.txt"
    exit_code, stdout_bytes, stderr_bytes = run_piitier_mask(["mask", str(missing_path)])

    assert exit_code == 2
    assert b"not found:" in stderr_bytes
    assert stdout_bytes == b""


# ---------------------------------------------------------------------------
# UC-35: invalid UTF-8 and undefined cp1250
# ---------------------------------------------------------------------------


def test_uc35_invalid_utf8_undefined_cp1250(tmp_path: Path) -> None:
    """UC-35: piitier mask on invalid UTF-8/cp1250 exits 2, stderr."""
    txt_path = tmp_path / "invalid.txt"
    # PESEL followed by bytes invalid in both UTF-8 and cp1250
    txt_path.write_bytes(b"90051512340\x81\x98")
    exit_code, stdout_bytes, stderr_bytes = run_piitier_mask(["mask", str(txt_path)])

    assert exit_code == 2
    assert b"cannot decode:" in stderr_bytes
    assert stdout_bytes == b""
    # Verify PESEL is not in stderr (privacy: no PII in errors)
    assert b"90051512340" not in stderr_bytes


# ---------------------------------------------------------------------------
# UC-40: cp1250-encoded CSV with Polish characters
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_uc40_mask_cp1250_csv(tmp_csv_cp1250: Path) -> None:
    """UC-40: piitier mask on cp1250 .csv outputs UTF-8 'Łódź;[PESEL]'."""
    exit_code, stdout_bytes, stderr_bytes = run_piitier_mask(["mask", str(tmp_csv_cp1250)])

    assert exit_code == 0
    assert stderr_bytes == b""
    assert stdout_bytes == "Łódź;[PESEL]".encode("utf-8")


# ---------------------------------------------------------------------------
# UC-41: NUL byte detection (binary file)
# ---------------------------------------------------------------------------


def test_uc41_binary_file_with_nul_byte(tmp_path: Path) -> None:
    """UC-41: piitier mask on file with NUL in first 4096 bytes exits 2."""
    bin_path = tmp_path / "binary.txt"
    bin_path.write_bytes(b"some text\x0089051512340 more text")
    exit_code, stdout_bytes, stderr_bytes = run_piitier_mask(["mask", str(bin_path)])

    assert exit_code == 2
    assert b"binary content:" in stderr_bytes
    assert stdout_bytes == b""
