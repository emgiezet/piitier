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


def test_uc42_encrypted_pdf_exit2_exact_stderr(tmp_path: Path) -> None:
    """UC-42: piitier mask locked.pdf exits 2; stderr 'encrypted pdf: <path>\\n'.

    reader.is_encrypted is True before page access; implementation must check it
    before iterating pages (no auto-decrypt attempted).
    stdout is empty; PESEL does not appear in stderr.
    """
    pdf_path = _encrypted_pdf(tmp_path)
    exit_code, stdout, stderr = _run([str(pdf_path)])

    assert exit_code == 2, f"expected exit 2, got {exit_code}; stderr={stderr!r}"
    assert stderr == f"encrypted pdf: {pdf_path}\n".encode(), f"stderr mismatch: {stderr!r}"
    assert stdout == b""
    assert SYNTHETIC_PESEL.encode() not in stderr
