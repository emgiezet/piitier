"""File loaders with encoding detection.

Supports .txt, .md, and .csv files. Registry keyed by extension allows
adding file type support (e.g., .pdf in PII-1-g) without touching cli.py.

Invariant: text files (.txt, .md, .csv) are read as strings and masked as one,
preserving byte-for-byte structure (Markdown syntax, delimiters, line endings).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable


def load_text_file(path: Path) -> str:
    """Load a text file with UTF-8 (BOM-tolerated) then cp1250 fallback.

    Line endings (\r\n, \n, \r) are preserved exactly as in the file.

    Args:
        path: Path to the file to load.

    Returns:
        The file content as a UTF-8 string with line endings preserved.

    Raises:
        FileNotFoundError: If the file does not exist.
        UnicodeDecodeError: If both UTF-8 and cp1250 decoding fail.
        ValueError: If the file contains a NUL byte in the first 4096 bytes.
    """
    # Check for binary content: NUL byte in first 4096 bytes
    with open(path, "rb") as f:
        chunk = f.read(4096)
    if b"\x00" in chunk:
        raise ValueError(f"binary content: {path}")

    # Read entire file in binary mode to preserve line endings
    with open(path, "rb") as f:
        data = f.read()

    # UTF-8 first (with BOM tolerance)
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass

    # cp1250 fallback
    try:
        return data.decode("cp1250")
    except UnicodeDecodeError as e:
        raise UnicodeDecodeError(
            e.encoding, e.object, e.start, e.end, f"cannot decode: {path}"
        ) from None


# Registry: extension → loader function
_LOADERS: dict[str, Callable[[Path], str]] = {
    ".txt": load_text_file,
    ".md": load_text_file,
    ".csv": load_text_file,
}


def get_loader(path: Path) -> Callable[[Path], str] | None:
    """Get the loader function for a file extension.

    Args:
        path: Path to the file.

    Returns:
        The loader function, or None if the extension is not supported.
    """
    suffix = path.suffix.lower()
    return _LOADERS.get(suffix)
