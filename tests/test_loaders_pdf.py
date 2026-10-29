"""Acceptance tests for PII-1-g: piitier mask <file>.pdf — text-layer PDF input.

UC-31: two-page text-layer PDF → exact masked joined stdout (verbatim, no strip), exit 0
UC-32: image-only PDF (real XObject) → exit 3, exact stderr, stdout empty
UC-32 boundary: image page 1 + text page 2 → exit 0, exact stdout with leading '\\n'
UC-42: encrypted PDF → exit 2, exact stderr, stdout empty, no PII leak

pypdf==6.21.1 supplied by parent: uv run --with pypdf==6.21.1 pytest tests/test_loaders_pdf.py
"""

from __future__ import annotations

import io
import secrets
import subprocess
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
)

# Synthetic PESEL used across all fixtures (spec requirement: no real PII)
SYNTHETIC_PESEL = "90051512340"

# UC-31 fixture page texts.
# Page 1 carries deliberate leading and trailing spaces; the loader must preserve
# them verbatim — pages are joined with '\n' and output without any transformation.
_PAGE1_TEXT = "  Polisa ubezpieczeniowa.  "
_PAGE2_TEXT = f"PESEL: {SYNTHETIC_PESEL}."

# Exact stdout the CLI must emit for UC-31.
# All pages joined verbatim with '\n'; PESEL replaced; no strip; no trailing newline
# (matches existing CLI behaviour: stdout == masked content, no added newline).
UC31_EXPECTED_STDOUT = f"{_PAGE1_TEXT}\nPESEL: [PESEL].".encode("utf-8")

# UC-32 boundary fixture: page 1 image-only → extract_text() == ""; page 2 has PESEL.
# Joined verbatim: "" + "\n" + "PESEL: 90051512340." → "\nPESEL: 90051512340."
# Masked: "\nPESEL: [PESEL]."  Leading '\n' is preserved — empty page counts.
_MIXED_PAGE2_TEXT = f"PESEL: {SYNTHETIC_PESEL}."
MIXED_EXPECTED_STDOUT = "\nPESEL: [PESEL].".encode("utf-8")


# ---------------------------------------------------------------------------
# PDF builders
# ---------------------------------------------------------------------------


def _add_text_page(writer: PdfWriter, text: str) -> None:
    """Append a page with *text* in a Type1 content stream (single Tj, latin-1 safe)."""
    page = writer.add_blank_page(width=595, height=842)
    font_obj = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font_obj)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
    )
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 40 780 Td ({escaped}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)


def _add_image_only_page(writer: PdfWriter) -> None:
    """Append a page with a 1×1 white-pixel /DeviceRGB image XObject, no text operators.

    pypdf's extract_text() returns '' for this page; it is genuinely image-only.
    """
    page = writer.add_blank_page(width=595, height=842)

    img_stream = DecodedStreamObject()
    img_stream.set_data(b"\xff\xff\xff")  # 1×1 white RGB pixel, raw
    img_stream[NameObject("/Type")] = NameObject("/XObject")
    img_stream[NameObject("/Subtype")] = NameObject("/Image")
    img_stream[NameObject("/Width")] = NumberObject(1)
    img_stream[NameObject("/Height")] = NumberObject(1)
    img_stream[NameObject("/ColorSpace")] = NameObject("/DeviceRGB")
    img_stream[NameObject("/BitsPerComponent")] = NumberObject(8)
    img_ref = writer._add_object(img_stream)

    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/XObject"): DictionaryObject({NameObject("/Im0"): img_ref})}
    )
    content = DecodedStreamObject()
    content.set_data(b"q 595 0 0 842 0 0 cm /Im0 Do Q")
    page[NameObject("/Contents")] = writer._add_object(content)


def _two_page_text_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "policy.pdf"
    writer = PdfWriter()
    _add_text_page(writer, _PAGE1_TEXT)
    _add_text_page(writer, _PAGE2_TEXT)
    with path.open("wb") as fh:
        writer.write(fh)
    return path


def _image_only_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "scan.pdf"
    writer = PdfWriter()
    _add_image_only_page(writer)
    with path.open("wb") as fh:
        writer.write(fh)
    return path


def _mixed_pdf(tmp_path: Path) -> Path:
    """Page 1: image-only (extract_text()==''); page 2: text layer with PESEL."""
    path = tmp_path / "mixed.pdf"
    writer = PdfWriter()
    _add_image_only_page(writer)
    _add_text_page(writer, _MIXED_PAGE2_TEXT)
    with path.open("wb") as fh:
        writer.write(fh)
    return path


def _encrypted_pdf(tmp_path: Path) -> Path:
    src_buf = io.BytesIO()
    src_writer = PdfWriter()
    _add_text_page(src_writer, "Confidential document.")
    src_writer.write(src_buf)
    src_buf.seek(0)

    enc_writer = PdfWriter(clone_from=PdfReader(src_buf))
    enc_writer.encrypt(secrets.token_hex(16))
    path = tmp_path / "locked.pdf"
    with path.open("wb") as fh:
        enc_writer.write(fh)
    return path


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _run(args: list[str]) -> tuple[int, bytes, bytes]:
    result = subprocess.run(
        [sys.executable, "-m", "piitier.cli", "mask"] + args,
        capture_output=True,
    )
    return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# UC-31: two-page text-layer PDF → exact masked stdout, exit 0
# ---------------------------------------------------------------------------


def test_uc31_two_page_text_pdf_exact_masked_stdout(tmp_path: Path) -> None:
    """UC-31: piitier mask policy.pdf exits 0; stdout is the exact masked joined text.

    Pages are joined verbatim with '\\n' — no strip, no filtering.  Leading/trailing
    spaces on page 1 are preserved in output.  PESEL is replaced with [PESEL].
    Raw PESEL is absent.  stderr is empty.
    """
    pdf_path = _two_page_text_pdf(tmp_path)
    exit_code, stdout, stderr = _run([str(pdf_path)])

    assert exit_code == 0, f"expected exit 0, got {exit_code}; stderr={stderr!r}"
    assert stdout == UC31_EXPECTED_STDOUT, (
        f"stdout mismatch.\n  got:      {stdout!r}\n  expected: {UC31_EXPECTED_STDOUT!r}"
    )
    assert SYNTHETIC_PESEL.encode() not in stdout
    assert stderr == b""


# ---------------------------------------------------------------------------
# UC-32: image-only PDF → exit 3, exact stderr, stdout empty
# ---------------------------------------------------------------------------


def test_uc32_image_only_pdf_exit3_exact_stderr(tmp_path: Path) -> None:
    """UC-32: piitier mask scan.pdf exits 3; stderr 'no text layer: <path>\\n'; stdout empty.

    Fixture has a real image XObject so extract_text() returns '' — not a bare blank page.
    No-text decision uses strip(); output transformation does not.
    """
    pdf_path = _image_only_pdf(tmp_path)
    exit_code, stdout, stderr = _run([str(pdf_path)])

    assert exit_code == 3, f"expected exit 3, got {exit_code}; stderr={stderr!r}"
    assert stderr == f"no text layer: {pdf_path}\n".encode(), f"stderr mismatch: {stderr!r}"
    assert stdout == b""


# ---------------------------------------------------------------------------
# UC-32 boundary: image page 1 + text page 2 → exit 0, exact stdout with leading '\n'
# ---------------------------------------------------------------------------


def test_uc32_boundary_image_page_then_text_page_exact_stdout(tmp_path: Path) -> None:
    """UC-32 boundary: image-only p1 + text-layer p2 must exit 0.

    Joined verbatim: '' + '\\n' + 'PESEL: [PESEL].' → stdout starts with '\\n'.
    Loader must not declare 'no text layer' when at least one page has text.
    The leading '\\n' (from the empty page 1) is preserved in output.
    """
    pdf_path = _mixed_pdf(tmp_path)
    exit_code, stdout, stderr = _run([str(pdf_path)])

    assert exit_code == 0, (
        f"mixed PDF (image p1, text p2) must exit 0, got {exit_code}; stderr={stderr!r}"
    )
    assert stdout == MIXED_EXPECTED_STDOUT, (
        f"stdout mismatch.\n  got:      {stdout!r}\n  expected: {MIXED_EXPECTED_STDOUT!r}"
    )
    assert SYNTHETIC_PESEL.encode() not in stdout
    assert stderr == b""


# ---------------------------------------------------------------------------
# UC-42: encrypted PDF → exit 2, exact stderr, stdout empty, no PII leak
# ---------------------------------------------------------------------------


def test_uc42_encrypted_pdf_refuses_unauthenticated_extraction(tmp_path: Path) -> None:
    """UC-42 protection remains; PII-14-a supersedes blanket rejection wording."""
    pdf_path = _encrypted_pdf(tmp_path)
    exit_code, stdout, stderr = _run([str(pdf_path)])

    assert exit_code == 2, f"expected exit 2, got {exit_code}; stderr={stderr!r}"
    assert stdout == b""
    assert SYNTHETIC_PESEL.encode() not in stderr


def password_pdf(
    tmp_path: Path,
    password: str,
    *,
    owner: str | None = None,
    algorithm: str = "RC4-128",
    image: bool = False,
) -> Path:
    writer = PdfWriter()
    if image:
        _add_image_only_page(writer)
    else:
        _add_text_page(writer, "  PESEL: 90051512340  ")
        writer.add_blank_page(width=595, height=842)
        _add_text_page(writer, "End.")
    writer.encrypt(password, owner_password=owner, algorithm=algorithm)
    path = tmp_path / "authenticated.pdf"
    writer.write(path)
    return path


@pytest.mark.parametrize("algorithm", ["RC4-128", "AES-128", "AES-256"])
@pytest.mark.parametrize("kind", ["user", "owner"])
def test_uc173_authenticated_pdf_fidelity(tmp_path: Path, algorithm: str, kind: str) -> None:
    from piitier.loaders import load_pdf

    user, owner = secrets.token_hex(12), secrets.token_hex(12)
    path = password_pdf(tmp_path, user, owner=owner, algorithm=algorithm)
    assert load_pdf(path, user if kind == "user" else owner) == "  PESEL: 90051512340  \n\nEnd."


def test_uc174_missing_wrong_empty_and_no_text(tmp_path: Path) -> None:
    from piitier.loaders import (
        IncorrectPasswordError,
        PasswordRequiredError,
        PdfNoTextError,
        load_pdf,
    )

    password = secrets.token_hex(12)
    path = password_pdf(tmp_path, password)
    with pytest.raises(PasswordRequiredError, match="password required:"):
        load_pdf(path)
    for value in ("", secrets.token_hex(12)):
        with pytest.raises(IncorrectPasswordError, match="wrong password:") as error:
            load_pdf(path, value)
        assert password not in str(error.value)
        assert isinstance(error.value, ValueError)
    path = password_pdf(tmp_path, "", owner=password)
    assert load_pdf(path) == "  PESEL: 90051512340  \n\nEnd."
    path = password_pdf(tmp_path, password, image=True)
    with pytest.raises(PdfNoTextError, match="no text layer:"):
        load_pdf(path, password)


@pytest.mark.parametrize("mode", ["explicit", "stdin"])
@pytest.mark.parametrize("password", ["", "  padded\t", "runtime"])
def test_uc175_uc177_cli_credentials_exact(
    tmp_path: Path,
    mode: str,
    password: str,
) -> None:
    if password == "runtime":
        password = secrets.token_hex(12)
    path = password_pdf(tmp_path, password)
    flags = ["--password", password] if mode == "explicit" else ["--password-stdin"]
    result = subprocess.run(
        [sys.executable, "-m", "piitier.cli", "mask", str(path), *flags],
        input=(password + "\r\n").encode(),
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == b"  PESEL: [PESEL]  \n\nEnd."
    assert result.stderr == b""


@pytest.mark.parametrize("existing", [False, True])
def test_uc175_authentication_failure_preserves_destination(tmp_path: Path, existing: bool) -> None:
    password = secrets.token_hex(12)
    path = password_pdf(tmp_path, password)
    output = tmp_path / "out.txt"
    if existing:
        output.write_bytes(b"keep")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "piitier.cli",
            "mask",
            str(path),
            "--password-stdin",
            "-o",
            str(output),
        ],
        input=b"wrong\n",
        capture_output=True,
    )
    assert result.returncode == 2
    assert result.stdout == b""
    assert password.encode() not in result.stderr and b"90051512340" not in result.stderr
    assert output.read_bytes() == b"keep" if existing else not output.exists()


def test_uc176_callback_retries_cancel_and_interrupt(tmp_path: Path) -> None:
    from piitier.loaders import IncorrectPasswordError, PasswordRequiredError, load_with_password

    password = secrets.token_hex(12)
    path = password_pdf(tmp_path, password)
    attempts = []
    answers = iter(["wrong", password])

    def prompt(path: Path, attempt: int, incorrect: bool) -> str:
        attempts.append((attempt, incorrect))
        return next(answers)

    assert load_with_password(path, prompt=prompt) == "  PESEL: 90051512340  \n\nEnd."
    assert attempts == [(1, False), (2, True)]
    attempts.clear()
    answers = iter(["wrong"] * 3)
    with pytest.raises(IncorrectPasswordError):
        load_with_password(path, prompt=prompt)
    assert attempts == [(1, False), (2, True), (3, True)]
    with pytest.raises(PasswordRequiredError):
        load_with_password(path, prompt=lambda *_: None)

    def interrupt(*_: object) -> str:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        load_with_password(path, prompt=interrupt)


def test_uc178_registry_and_parser_diagnostics(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from pypdf.errors import PdfReadError

    from piitier.loaders import get_loader, load_with_password

    password = secrets.token_hex(12)
    path = password_pdf(tmp_path, password)
    loader = get_loader(path, password=password)
    assert loader is not None
    assert loader(path) == "  PESEL: 90051512340  \n\nEnd."
    path.write_bytes(b"SECRET-PII-90051512340 not a PDF")
    with pytest.raises(PdfReadError) as error:
        load_with_password(path)
    assert "SECRET-PII" not in str(error.value)
    assert capsys.readouterr() == ("", "")


def test_uc178_explicit_parser_logger_cannot_leak(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    from pypdf.errors import PdfReadError

    from piitier.loaders import load_pdf

    path = tmp_path / "bad.pdf"
    path.write_bytes(b"PRIVATE-PARSER-CONTENT")
    with caplog.at_level(logging.WARNING, logger="pypdf._reader"):
        with pytest.raises(PdfReadError):
            load_pdf(path)
        assert caplog.records == []
        assert logging.getLogger("pypdf._reader").level == logging.WARNING
