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
    assert stderr_bytes == f"cannot decode: {txt_path}\n".encode("utf-8")
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


# ---------------------------------------------------------------------------
# UC-109: nonexistent --model dir → exit 2, no traceback, no doc text
# ---------------------------------------------------------------------------


def test_uc109_nonexistent_model_exits_2() -> None:
    """UC-109: piitier mask <file> --model /nie/istnieje exits 2."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("PESEL: 90051512340\n")
        tmp_path = Path(f.name)
    try:
        exit_code, stdout_bytes, stderr_bytes = run_piitier_mask(
            ["mask", str(tmp_path), "--model", "/nie/istnieje"]
        )
        assert exit_code == 2
    finally:
        tmp_path.unlink(missing_ok=True)


def test_uc109_stderr_contains_model_path() -> None:
    """UC-109: stderr names the nonexistent model path."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("PESEL: 90051512340\n")
        tmp_path = Path(f.name)
    try:
        _, _, stderr_bytes = run_piitier_mask(["mask", str(tmp_path), "--model", "/nie/istnieje"])
        assert b"/nie/istnieje" in stderr_bytes
    finally:
        tmp_path.unlink(missing_ok=True)


def test_uc109_stderr_no_traceback_no_doc_text() -> None:
    """UC-109: stderr contains no traceback and no document text."""
    import tempfile

    doc_content = "PESEL: 90051512340\n"
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write(doc_content)
        tmp_path = Path(f.name)
    try:
        _, stdout_bytes, stderr_bytes = run_piitier_mask(
            ["mask", str(tmp_path), "--model", "/nie/istnieje"]
        )
        assert b"Traceback" not in stderr_bytes
        assert b"90051512340" not in stderr_bytes
        assert stdout_bytes == b""
    finally:
        tmp_path.unlink(missing_ok=True)


def test_uc109_nothing_written_to_output_file(tmp_path: Path) -> None:
    """UC-109: nothing written to -o when model path is invalid."""
    in_file = tmp_path / "in.txt"
    out_file = tmp_path / "out.txt"
    in_file.write_text("PESEL: 90051512340\n", encoding="utf-8")

    run_piitier_mask(["mask", str(in_file), "-o", str(out_file), "--model", "/nie/istnieje"])
    assert not out_file.exists()


# ---------------------------------------------------------------------------
# UC-108: piitier mask --model <tiny-checkpoint> (integration)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tiny_checkpoint(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Save the tiny HF checkpoint to a local directory (downloaded once per session)."""
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    model_name = "hf-internal-testing/tiny-random-BertForTokenClassification"
    ckpt_dir = tmp_path_factory.mktemp("tiny_bert")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForTokenClassification.from_pretrained(model_name)
    tokenizer.save_pretrained(str(ckpt_dir))
    model.save_pretrained(str(ckpt_dir))
    return ckpt_dir


@pytest.mark.integration
def test_uc108_mask_with_model_exits_0(tmp_path: Path, tiny_checkpoint: Path) -> None:
    """UC-108: piitier mask <file> --model <dir> --threshold 0.5 exits 0."""
    in_file = tmp_path / "in.txt"
    in_file.write_text("PESEL: 90051512340, tel.", encoding="utf-8")

    exit_code, _out, _err = run_piitier_mask(
        ["mask", str(in_file), "--model", str(tiny_checkpoint), "--threshold", "0.5"]
    )
    assert exit_code == 0


@pytest.mark.integration
def test_uc108_mask_with_model_contains_pesel_placeholder(
    tmp_path: Path, tiny_checkpoint: Path
) -> None:
    """UC-108: output contains [PESEL] placeholder (detected by rules regardless of NER)."""
    in_file = tmp_path / "in.txt"
    in_file.write_text("PESEL: 90051512340, tel.", encoding="utf-8")

    _, stdout_bytes, _ = run_piitier_mask(
        ["mask", str(in_file), "--model", str(tiny_checkpoint), "--threshold", "0.5"]
    )
    assert b"[PESEL]" in stdout_bytes
    assert b"90051512340" not in stdout_bytes


@pytest.mark.integration
def test_uc108_without_model_byte_identical(tmp_path: Path, tiny_checkpoint: Path) -> None:
    """UC-108: without --model the CLI output is byte-identical to piitier.mask(text)."""
    import piitier

    text = "PESEL: 90051512340, tel."
    in_file = tmp_path / "in.txt"
    in_file.write_text(text, encoding="utf-8")

    # Direct library call — today's behaviour
    expected = piitier.mask(text).encode("utf-8")

    # CLI without --model
    _, out_no_model, _ = run_piitier_mask(["mask", str(in_file)])
    assert out_no_model == expected, "CLI without --model must match piitier.mask(text)"

    # CLI with --model must also produce the same PESEL masking
    _, out_with_model, _ = run_piitier_mask(["mask", str(in_file), "--model", str(tiny_checkpoint)])
    assert b"[PESEL]" in out_with_model
    assert b"90051512340" not in out_with_model


# ---------------------------------------------------------------------------
# Threshold CLI validation — NaN and >1 (finding 3)
# ---------------------------------------------------------------------------


def _make_txt(tmp_path: Path, content: str = "PESEL: 90051512340\n") -> Path:
    """Write content to a .txt file in tmp_path and return its path."""
    p = tmp_path / "in.txt"
    p.write_text(content, encoding="utf-8")
    return p


def test_threshold_nan_exits_2_no_traceback(tmp_path: Path) -> None:
    """--threshold nan with valid model dir exits 2 and prints no traceback."""
    in_file = _make_txt(tmp_path)
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    rc, stdout_bytes, stderr_bytes = run_piitier_mask(
        ["mask", str(in_file), "--model", str(model_dir), "--threshold", "nan"]
    )
    assert rc == 2
    assert b"Traceback" not in stderr_bytes
    assert b"invalid threshold" in stderr_bytes
    assert stdout_bytes == b""


def test_threshold_gt1_exits_2_no_traceback(tmp_path: Path) -> None:
    """--threshold 1.5 with valid model dir exits 2 and prints no traceback."""
    in_file = _make_txt(tmp_path)
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    rc, stdout_bytes, stderr_bytes = run_piitier_mask(
        ["mask", str(in_file), "--model", str(model_dir), "--threshold", "1.5"]
    )
    assert rc == 2
    assert b"Traceback" not in stderr_bytes
    assert b"invalid threshold" in stderr_bytes
    assert stdout_bytes == b""


# ---------------------------------------------------------------------------
# Empty (invalid) model directory exits 2 cleanly (finding 4)
# ---------------------------------------------------------------------------


def test_empty_model_dir_exits_2_no_traceback(tmp_path: Path) -> None:
    """An existing but empty model directory causes exit 2 without traceback."""
    in_file = _make_txt(tmp_path)
    empty_model = tmp_path / "empty_model"
    empty_model.mkdir()

    rc, stdout_bytes, stderr_bytes = run_piitier_mask(
        ["mask", str(in_file), "--model", str(empty_model)]
    )
    assert rc == 2
    assert b"Traceback" not in stderr_bytes
    assert stdout_bytes == b""
    assert b"90051512340" not in stderr_bytes


@pytest.fixture
def skip_csv(tmp_path: Path) -> Path:
    path = tmp_path / "in.csv"
    path.write_bytes("Imie;PESEL;Uwagi\r\nJan;90051512340;PESEL klienta 90051512340\r\n".encode())
    return path


@pytest.mark.parametrize(
    ("selector", "warning"),
    [
        ("PESEL", b""),
        ("2", b""),
        ("  pesel  ", b""),
        ("BrakujacaKolumna,PESEL", b"warning: unknown column: BrakujacaKolumna\n"),
    ],
)
def test_uc163_uc164_uc165_uc166_skip_selected_csv_column(
    skip_csv: Path, selector: str, warning: bytes
) -> None:
    rc, out, err = run_piitier_mask(["mask", str(skip_csv), "--skip-columns", selector])
    assert rc == 0
    assert out == b"Imie;PESEL;Uwagi\r\nJan;90051512340;PESEL klienta [PESEL]\r\n"
    assert err == warning


def test_uc167_quoted_multiline_column_stays_untouched(tmp_path: Path) -> None:
    path = tmp_path / "in.csv"
    path.write_bytes(
        (
            '"Imie";"Opis, ze srednikiem ; i\nnowa ""linia""";"PESEL"\r\n'
            '"Jan";"tekst 90051512340";"90051512340"\r\n'
        ).encode()
    )
    rc, out, err = run_piitier_mask(
        ["mask", str(path), "--skip-columns", 'Opis, ze srednikiem ; i\nnowa "linia"']
    )
    assert rc == 0
    assert (
        out
        == (
            '"Imie";"Opis, ze srednikiem ; i\nnowa ""linia""";"PESEL"\r\n'
            '"Jan";"tekst 90051512340";"[PESEL]"\r\n'
        ).encode()
    )
    assert err == b""


def test_uc168_cross_boundary_span_remains_masked(tmp_path: Path) -> None:
    path = tmp_path / "in.csv"
    path.write_text("col1 col2 col3 col4\n4111 1111 1111 1111\n", encoding="utf-8")
    rc, out, err = run_piitier_mask(
        ["mask", str(path), "--skip-columns", "col2", "--delimiter", " "]
    )
    assert rc == 0
    assert out == b"col1 col2 col3 col4\n[NR_KARTY]\n"
    assert err == b""


def test_uc169_skip_columns_rejected_for_txt(tmp_txt_pesel: Path) -> None:
    rc, out, err = run_piitier_mask(["mask", str(tmp_txt_pesel), "--skip-columns", "PESEL"])
    assert rc == 2
    assert out == b""
    assert err == f"--skip-columns is only supported for .csv files: {tmp_txt_pesel}\n".encode()


def test_uc170_delimiter_requires_skip_columns(skip_csv: Path) -> None:
    rc, out, err = run_piitier_mask(["mask", str(skip_csv), "--delimiter", ";"])
    assert rc == 2
    assert out == b""
    assert err == b"cannot use --delimiter without --skip-columns\n"


def test_uc171_tab_delimiter_escape(tmp_path: Path) -> None:
    path = tmp_path / "in.csv"
    path.write_text("ID\tNotes\n90051512340\t90051512340\n", encoding="utf-8")
    rc, out, err = run_piitier_mask(
        ["mask", str(path), "--delimiter", "\\t", "--skip-columns", "1"]
    )
    assert rc == 0
    assert out == b"ID\tNotes\n90051512340\t[PESEL]\n"
    assert err == b""


# ---------------------------------------------------------------------------
# PII-5-v4: --version flag
# ---------------------------------------------------------------------------


def test_version_flag_exits_0_and_prints_version() -> None:
    """piitier --version prints 'piitier <version>' and exits 0."""
    import piitier

    result = subprocess.run(
        [sys.executable, "-m", "piitier.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert f"piitier {piitier.__version__}" in result.stdout + result.stderr


# ---------------------------------------------------------------------------
# PII-5-v4: --revision flag passes through to resolve_checkpoint
# ---------------------------------------------------------------------------


def test_revision_passed_through_to_seam(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """mask_file(..., revision='abc') passes revision to the hub seam (in-process)."""
    import piitier.ner.hub as hub
    from piitier.cli import mask_file

    in_file = tmp_path / "in.txt"
    in_file.write_text("PESEL: 90051512340\n", encoding="utf-8")
    ckpt_dir = tmp_path / "ckpt"
    ckpt_dir.mkdir()

    calls: list[dict[str, object]] = []

    def fake_download(*, repo_id: str, revision: str | None = None) -> str:
        calls.append({"repo_id": repo_id, "revision": revision})
        return str(ckpt_dir)

    monkeypatch.setattr(hub, "_snapshot_download", fake_download)

    # The seam returns an empty directory; NerPredictor will fail with ValueError/OSError.
    # We only care that the seam was called with the right args.
    mask_file(in_file, None, model="emgiezet/piitier", revision="abc")
    assert calls == [{"repo_id": "emgiezet/piitier", "revision": "abc"}]


# ---------------------------------------------------------------------------
# PII-5-v4: repo-id with HF_HUB_OFFLINE → exit 2 'could not download'
# ---------------------------------------------------------------------------


def test_hub_repo_id_offline_exits_2_could_not_download(tmp_path: Path) -> None:
    """mask --model no/such-repo exits 2 with 'model error: could not download' when offline."""
    import os

    in_file = tmp_path / "in.txt"
    in_file.write_text("PESEL: 90051512340\n", encoding="utf-8")

    env = {**os.environ, "HF_HUB_OFFLINE": "1"}
    result = subprocess.run(
        [sys.executable, "-m", "piitier.cli", "mask", str(in_file), "--model", "no/such-repo"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 2
    assert "could not download" in result.stderr
    assert "no/such-repo" in result.stderr


@pytest.mark.parametrize("case", ["conflict", "nonpdf", "eof"])
def test_uc177_password_input_errors(tmp_path: Path, case: str) -> None:
    import secrets

    from test_loaders_pdf import password_pdf

    secret = secrets.token_hex(12)
    path = password_pdf(tmp_path, secret)
    flags = ["--password-stdin"]
    if case == "conflict":
        flags += ["--password", secret]
    elif case == "nonpdf":
        path = tmp_path / "source.txt"
        path.write_text("PESEL: 90051512340")
    output = tmp_path / "out.txt"
    result = subprocess.run(
        [sys.executable, "-m", "piitier.cli", "mask", str(path), "-o", str(output), *flags],
        input=b"",
        capture_output=True,
    )
    assert result.returncode == 2
    assert result.stdout == b""
    assert not output.exists()
    assert secret.encode() not in result.stderr


@pytest.mark.parametrize("ending", ["\n", "\r\n", ""])
def test_uc177_stdin_preserves_bare_cr(tmp_path: Path, ending: str) -> None:
    import secrets

    from test_loaders_pdf import password_pdf

    secret = " " + secrets.token_hex(8) + "\r"
    path = password_pdf(tmp_path, secret)
    data = secret + ("\r\n" if ending == "\n" else ending)
    result = subprocess.run(
        [sys.executable, "-m", "piitier.cli", "mask", str(path), "--password-stdin"],
        input=data.encode(),
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == b"  PESEL: [PESEL]  \n\nEnd."


@pytest.mark.parametrize(
    "outcome", ["correct", "explicit", "eof", "fallback", "interrupt", "exhaust"]
)
def test_uc176_hidden_cli_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    outcome: str,
) -> None:
    import getpass
    import secrets
    import warnings

    from test_loaders_pdf import password_pdf

    from piitier.cli import main

    secret = secrets.token_hex(12)
    path = password_pdf(tmp_path, secret)
    output = tmp_path / "out.txt"
    args = ["piitier", "mask", str(path), "-o", str(output)]
    if outcome == "explicit":
        args += ["--password", secrets.token_hex(12)]
    monkeypatch.setattr(sys, "argv", args)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    answers = iter(
        [secret]
        if outcome == "explicit"
        else ["wrong", secret]
        if outcome == "correct"
        else ["wrong"] * 3
    )
    entered = []

    def hidden(prompt: str, stream: object) -> str:
        entered.append(prompt)
        if outcome == "eof":
            raise EOFError
        if outcome == "interrupt":
            raise KeyboardInterrupt
        if outcome == "fallback":
            warnings.warn("echo fallback", getpass.GetPassWarning)
            pytest.fail("echoed read must not be reached")
        return next(answers)

    monkeypatch.setattr(getpass, "getpass", hidden)
    success = outcome in ("correct", "explicit")
    assert main() == (0 if success else 130 if outcome == "interrupt" else 2)
    if success:
        assert output.read_text() == "  PESEL: [PESEL]  \n\nEnd."
        assert len(entered) == (1 if outcome == "explicit" else 2)
    else:
        assert not output.exists()
        assert len(entered) == (3 if outcome == "exhaust" else 1)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert secret not in captured.err and "90051512340" not in captured.err


def test_uc181_uc182_batch_command(tmp_path: Path) -> None:
    source = tmp_path / "input"
    source.mkdir()
    (source / "a.txt").write_text("PESEL: 90051512340")
    (source / "b.pdf").write_bytes(b"not a PDF")
    output = tmp_path / "output"
    result = subprocess.run(
        [sys.executable, "-m", "piitier.cli", "mask-batch", str(source), "-o", str(output)],
        capture_output=True,
    )
    assert result.returncode == 4 and result.stdout == b""
    assert result.stderr.endswith(b"batch: 1 masked, 1 failed\n")
    assert (output / "a.txt").read_text() == "PESEL: [PESEL]"
    assert not (output / "b.txt").exists()


def test_json_model_masking_uses_decoded_aliases_and_keeps_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_jsonmask import JsonNamePredictor

    import piitier
    from piitier.cli import mask_file

    real_anonymizer = piitier.Anonymizer
    monkeypatch.setattr(
        piitier, "Anonymizer", lambda **kwargs: real_anonymizer(predictor=JsonNamePredictor())
    )
    source = tmp_path / "names.JSON"
    output = tmp_path / "masked.json"
    source.write_bytes(
        b'{\r\n "Zoja Testowa": ["\\u005aoja Testowa", "Mira Fikcyjna", '
        b'{"alias": "Zoja Testowa"}], "n": 90051512340\r\n}\r\n'
    )
    assert mask_file(source, output, model="offline-test-model") == 0
    assert output.read_bytes() == (
        b'{\r\n "Zoja Testowa": ["[OSOBA_1]", "[OSOBA_2]", '
        b'{"alias": "[OSOBA_1]"}], "n": 90051512340\r\n}\r\n'
    )


@pytest.mark.parametrize("existing_output", [False, True])
@pytest.mark.parametrize(
    "payload",
    [b'{"private":"90051512340",}', b'{"private":"90051512340\xff"}'],
)
def test_invalid_json_preserves_output_before_model_initialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    existing_output: bool,
    payload: bytes,
) -> None:
    import piitier
    from piitier.cli import mask_file

    def forbidden_model(**kwargs):
        raise AssertionError("invalid input must fail before model loading")

    monkeypatch.setattr(piitier, "Anonymizer", forbidden_model)
    source = tmp_path / "bad.json"
    output = tmp_path / "output.json"
    source.write_bytes(payload)
    if existing_output:
        output.write_bytes(b"existing content\r\n")
    assert mask_file(source, output, model="must-not-load") == 2
    assert source.read_bytes() == payload
    if existing_output:
        assert output.read_bytes() == b"existing content\r\n"
    else:
        assert not output.exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "private" not in captured.err and "90051512340" not in captured.err


@pytest.mark.parametrize("stdin_tty,stderr_tty", [(False, True), (True, False), (False, False)])
def test_uc176_nonterminal_authentication_never_prompts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stdin_tty: bool,
    stderr_tty: bool,
) -> None:
    import getpass
    import secrets

    from test_loaders_pdf import password_pdf

    from piitier.cli import main

    path = password_pdf(tmp_path, secrets.token_hex(12))
    output = tmp_path / "out.txt"
    output.write_bytes(b"preserve existing output")
    monkeypatch.setattr(sys, "argv", ["piitier", "mask", str(path), "-o", str(output)])
    monkeypatch.setattr(sys.stdin, "isatty", lambda: stdin_tty)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: stderr_tty)

    def forbidden_prompt(*args: object, **kwargs: object) -> str:
        pytest.fail("nonterminal authentication must not attempt hidden input")

    monkeypatch.setattr(getpass, "getpass", forbidden_prompt)
    assert main() == 2
    assert output.read_bytes() == b"preserve existing output"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"password required: {path}\n"


@pytest.mark.parametrize("command", ["mask", "compare"])
def test_uc174_uc188_authenticated_scan_exits3(tmp_path: Path, command: str) -> None:
    import secrets

    from test_loaders_pdf import password_pdf

    password = secrets.token_hex(12) if command == "mask" else ""
    owner = secrets.token_hex(12)
    path = password_pdf(tmp_path, password, owner=owner, algorithm="AES-256", image=True)
    output = tmp_path / "out.txt"
    output.write_bytes(b"preserve existing output")
    flags = (
        ["--password-stdin", "-o", str(output)]
        if command == "mask"
        else ["--model", str(tmp_path / "model-must-not-load")]
    )
    result = subprocess.run(
        [sys.executable, "-m", "piitier.cli", command, str(path), *flags],
        input=(password + "\n").encode(),
        capture_output=True,
    )
    assert result.returncode == 3
    assert result.stdout == b""
    assert owner.encode() not in result.stderr
    if password:
        assert password.encode() not in result.stderr
    assert b"Traceback" not in result.stderr
    assert output.read_bytes() == b"preserve existing output"
