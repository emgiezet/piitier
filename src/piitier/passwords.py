"""Strict UTF-8 filename/password CSV maps; diagnostics never include record contents."""

from __future__ import annotations

import csv
from pathlib import Path


def parse_passwords_csv(path: Path) -> dict[str, str]:
    """Preserve credentials verbatim and report the starting physical line of bad records."""
    try:
        lines = path.read_bytes().removeprefix(b"\xef\xbb\xbf").splitlines(keepends=True)
    except OSError:
        raise ValueError(f"cannot read password map: {path}") from None
    try:
        header = lines[0].decode("utf-8")
    except (IndexError, UnicodeDecodeError):
        raise ValueError(f"malformed CSV {path}:1") from None
    for delimiter in (",", ";"):
        try:
            if next(csv.reader([header], delimiter=delimiter, strict=True)) == [
                "filename",
                "password",
            ]:
                break
        except (csv.Error, StopIteration):
            continue
    else:
        raise ValueError(f"malformed CSV {path}:1")

    # Decode lazily by physical line so errors in multiline records name their
    # starting line. Binary splitting preserves CRLF inside quoted credentials.
    reader = csv.reader(
        (line.decode("utf-8") for line in lines[1:]), delimiter=delimiter, strict=True
    )
    mapping: dict[str, str] = {}
    while True:
        start = reader.line_num + 2
        try:
            row = next(reader)
        except StopIteration:
            return mapping
        except (UnicodeDecodeError, csv.Error):
            raise ValueError(f"malformed CSV {path}:{start}") from None
        if not row:
            continue
        if (
            len(row) != 2
            or not row[0]
            or row[0] in {".", ".."}
            or "/" in row[0]
            or "\\" in row[0]
            or row[0] in mapping
        ):
            raise ValueError(f"malformed CSV {path}:{start}")
        mapping[row[0]] = row[1]
