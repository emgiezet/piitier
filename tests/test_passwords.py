"""Exact credential preservation and safe malformed-map failures."""

import csv
import io
import secrets
from pathlib import Path

import pytest

from piitier.passwords import parse_passwords_csv


@pytest.mark.parametrize("delimiter", [",", ";"])
@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
def test_uc179_exact_mapping(tmp_path: Path, delimiter: str, bom: bytes) -> None:
    expected = {
        "Case.PDF": " " + secrets.token_hex(12) + ',;"\r\n\t ',
        "empty.pdf": "",
        "case.pdf": "\v\f",
        " spaced.pdf ": " padded ",
    }
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=delimiter, quoting=csv.QUOTE_ALL)
    writer.writerow(["filename", "password"])
    writer.writerows(expected.items())
    path = tmp_path / "map.csv"
    path.write_bytes(bom + stream.getvalue().encode())
    assert parse_passwords_csv(path) == expected
    path.write_bytes(bom + f"filename{delimiter}password\r\n\r\n".encode())
    assert parse_passwords_csv(path) == {}


@pytest.mark.parametrize(
    "data,line",
    [
        (b"", 1),
        (b"\xef\xbb\xbf", 1),
        (b"file,password\na,secret\n", 1),
        (b"filename;password,extra\n", 1),
        (b"filename,password\n,\n", 2),
        (b"filename,password\n\na,p\na,q\n", 4),
        (b"filename,password\na,p,extra\n", 2),
        (b"filename,password\na\n", 2),
        (b'filename,password\na,"secret\nunterminated', 2),
        (b'filename,password\na,"secret"junk\n', 2),
        (b'filename,password\na,"secret\n\xff"\n', 2),
        (b"filename,password\na,p\nb,\xff\n", 3),
        *[
            (f"filename,password\n{name},secret\n".encode(), 2)
            for name in ["", ".", "..", "sub/a.pdf", "sub\\a.pdf"]
        ],
    ],
)
def test_uc180_malformed_map_safe_record_line(tmp_path: Path, data: bytes, line: int) -> None:
    path = tmp_path / "map.csv"
    path.write_bytes(data)
    with pytest.raises(ValueError) as error:
        parse_passwords_csv(path)
    assert str(error.value) == f"malformed CSV {path}:{line}"
