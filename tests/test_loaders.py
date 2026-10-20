"""Unit tests for piitier.loaders — file reading and encoding detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from piitier.loaders import get_loader, load_text_file


@pytest.fixture
def utf8_txt(tmp_path: Path) -> Path:
    """Create a UTF-8 text file."""
    path = tmp_path / "utf8.txt"
    path.write_text("Hello PESEL: 90051512340", encoding="utf-8")
    return path


@pytest.fixture
def utf8_with_bom(tmp_path: Path) -> Path:
    """Create a UTF-8 file with BOM."""
    path = tmp_path / "bom.txt"
    path.write_bytes(b"\xef\xbb\xbfHello 90051512340")
    return path


@pytest.fixture
def cp1250_txt(tmp_path: Path) -> Path:
    """Create a cp1250-encoded file with Polish characters."""
    path = tmp_path / "cp1250.txt"
    # Łódź in cp1250
    path.write_bytes("Łódź: 90051512340".encode("cp1250"))
    return path


@pytest.fixture
def invalid_encoding(tmp_path: Path) -> Path:
    """Create a file with invalid UTF-8 and cp1250 bytes."""
    path = tmp_path / "invalid.txt"
    # 0x81 0x98 are invalid in both UTF-8 and cp1250
    path.write_bytes(b"90051512340\x81\x98")
    return path


@pytest.fixture
def binary_file_with_nul(tmp_path: Path) -> Path:
    """Create a file with NUL byte in first 4096 bytes."""
    path = tmp_path / "binary.txt"
    path.write_bytes(b"text\x00more text 90051512340")
    return path


@pytest.fixture
def binary_file_nul_after_4096(tmp_path: Path) -> Path:
    """Create a file with NUL byte after 4096 bytes (should pass)."""
    path = tmp_path / "after_4096.txt"
    # Create a file with 4100 bytes before the NUL
    path.write_bytes(b"x" * 4100 + b"\x00")
    return path


# ---------------------------------------------------------------------------
# load_text_file — UTF-8 decoding
# ---------------------------------------------------------------------------


def test_load_utf8_file(utf8_txt: Path) -> None:
    """load_text_file reads UTF-8 file correctly."""
    result = load_text_file(utf8_txt)
    assert result == "Hello PESEL: 90051512340"


# ---------------------------------------------------------------------------
# load_text_file — BOM tolerance
# ---------------------------------------------------------------------------


def test_load_utf8_with_bom(utf8_with_bom: Path) -> None:
    """load_text_file strips UTF-8 BOM."""
    result = load_text_file(utf8_with_bom)
    assert result == "Hello 90051512340"
    assert not result.startswith("\ufeff")


# ---------------------------------------------------------------------------
# load_text_file — cp1250 fallback
# ---------------------------------------------------------------------------


def test_load_cp1250_file(cp1250_txt: Path) -> None:
    """load_text_file falls back to cp1250 on UTF-8 failure."""
    result = load_text_file(cp1250_txt)
    assert result == "Łódź: 90051512340"


# ---------------------------------------------------------------------------
# load_text_file — invalid encoding
# ---------------------------------------------------------------------------


def test_load_invalid_encoding_raises(invalid_encoding: Path) -> None:
    """load_text_file raises UnicodeDecodeError on both UTF-8 and cp1250 fail."""
    with pytest.raises(UnicodeDecodeError) as excinfo:
        load_text_file(invalid_encoding)
    assert "cannot decode:" in str(excinfo.value.reason)


# ---------------------------------------------------------------------------
# load_text_file — NUL byte detection
# ---------------------------------------------------------------------------


def test_load_binary_file_with_nul_in_4096(binary_file_with_nul: Path) -> None:
    """load_text_file raises ValueError on NUL byte in first 4096 bytes."""
    with pytest.raises(ValueError) as excinfo:
        load_text_file(binary_file_with_nul)
    assert "binary content:" in str(excinfo.value)


def test_load_file_nul_after_4096(binary_file_nul_after_4096: Path) -> None:
    """load_text_file allows NUL byte after first 4096 bytes."""
    result = load_text_file(binary_file_nul_after_4096)
    assert result == "x" * 4100 + "\x00"


# ---------------------------------------------------------------------------
# load_text_file — missing file
# ---------------------------------------------------------------------------


def test_load_missing_file(tmp_path: Path) -> None:
    """load_text_file raises FileNotFoundError on missing file."""
    missing_path = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError):
        load_text_file(missing_path)


# ---------------------------------------------------------------------------
# get_loader — registry lookup
# ---------------------------------------------------------------------------


def test_get_loader_txt() -> None:
    """get_loader returns loader for .txt files."""
    path = Path("test.txt")
    loader = get_loader(path)
    assert loader is load_text_file


def test_get_loader_md() -> None:
    """get_loader returns loader for .md files."""
    path = Path("test.md")
    loader = get_loader(path)
    assert loader is load_text_file


def test_get_loader_csv() -> None:
    """get_loader returns loader for .csv files."""
    path = Path("test.csv")
    loader = get_loader(path)
    assert loader is load_text_file


def test_get_loader_unsupported() -> None:
    """get_loader returns None for unsupported file types."""
    path = Path("test.docx")
    loader = get_loader(path)
    assert loader is None


def test_get_loader_case_insensitive() -> None:
    """get_loader is case-insensitive for extension."""
    path = Path("test.TXT")
    loader = get_loader(path)
    assert loader is load_text_file
