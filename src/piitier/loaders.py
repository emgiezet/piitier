"""File loaders with encoding detection.

Supports .txt, .md, .csv, .json and .pdf files through an extension registry.

Invariant: text files (.txt, .md, .csv) are read as strings and masked as one,
preserving byte-for-byte structure (Markdown syntax, delimiters, line endings).
PDF files: all pages extracted verbatim and joined with '\\n'; empty pages preserved.
JSON files: validate UTF-8 JSON while retaining BOM, whitespace and source escapes.
"""

from __future__ import annotations

import logging
from functools import partial
from pathlib import Path
from typing import Callable

from piitier.jsonmask import validate_json


class PdfNoTextError(Exception):
    """Raised when a PDF contains no extractable text on any page."""


class PasswordRequiredError(ValueError):
    """An encrypted PDF could not be opened without an explicit credential."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"password required: {path}")


class IncorrectPasswordError(ValueError):
    """An explicitly supplied PDF credential was rejected."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"wrong password: {path}")


PasswordPrompt = Callable[[Path, int, bool], str | None]


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


def decode_json_bytes(data: bytes) -> tuple[str, str]:
    """Decode supported JSON bytes without discarding BOMs or normalizing line endings."""
    try:
        try:
            text, encoding = data.decode("utf-8"), "utf-8"
        except UnicodeDecodeError:
            text, encoding = data.decode("cp1250"), "cp1250"
        validate_json(text)
    except ValueError:
        raise ValueError("invalid JSON or unsupported encoding") from None
    return text, encoding


def load_json(path: Path) -> str:
    """Read validated JSON, retaining its BOM, source characters and line endings."""
    try:
        return decode_json_bytes(path.read_bytes())[0]
    except ValueError:
        raise ValueError(f"invalid JSON: {path}") from None


def load_pdf(path: Path, password: str | None = None) -> str:
    """Authenticate before page access; preserve every page and its whitespace."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    # Parser warnings can include source bytes. Limit suppression to this read and
    # restore the caller's logging policy, including datagen's unreadable handling.
    logging.getLogger("pypdf")
    loggers = [
        (logger, logger.level)
        for name, logger in list(logging.Logger.manager.loggerDict.items())
        if (name == "pypdf" or name.startswith("pypdf.")) and isinstance(logger, logging.Logger)
    ]
    for logger, _ in loggers:
        logger.setLevel(logging.CRITICAL + 1)
    try:
        with PdfReader(str(path)) as reader:
            if reader.is_encrypted and not reader.decrypt("" if password is None else password):
                if password is None:
                    raise PasswordRequiredError(path)
                raise IncorrectPasswordError(path)
            pages_text = [page.extract_text() or "" for page in reader.pages]
    except (PasswordRequiredError, IncorrectPasswordError):
        raise
    except OSError:
        raise OSError(f"could not read: {path}") from None
    except Exception:
        # Untrusted PDF objects can raise more than PdfReadError. Keep the public
        # parser error compatible with datagen without forwarding parser excerpts.
        raise PdfReadError(f"could not read PDF: {path}") from None
    finally:
        for logger, previous_level in loggers:
            logger.setLevel(previous_level)

    if not any(t.strip() for t in pages_text):
        raise PdfNoTextError(f"no text layer: {path}")

    return "\n".join(pages_text)


# Registry: extension → loader function
_LOADERS: dict[str, Callable[[Path], str]] = {
    ".txt": load_text_file,
    ".md": load_text_file,
    ".csv": load_text_file,
    ".json": load_json,
    ".pdf": load_pdf,
}


def get_loader(path: Path, *, password: str | None = None) -> Callable[[Path], str] | None:
    """Return a one-argument loader, binding only explicitly supplied PDF credentials."""
    loader = _LOADERS.get(path.suffix.lower())
    if path.suffix.lower() == ".pdf" and password is not None:
        return partial(load_pdf, password=password)
    return loader


def load_with_password(
    path: Path,
    *,
    password: str | None = None,
    prompt: PasswordPrompt | None = None,
) -> str:
    """Load once, then allow at most three entered credentials on authentication failure."""
    for attempt in range(4):
        loader = get_loader(path, password=password)
        if loader is None:
            raise ValueError(f"unsupported file type: {path.suffix}")
        try:
            return loader(path)
        except (PasswordRequiredError, IncorrectPasswordError) as error:
            if prompt is None or attempt == 3:
                raise
            password = prompt(path, attempt + 1, isinstance(error, IncorrectPasswordError))
            if password is None:
                raise
    raise AssertionError("unreachable")
