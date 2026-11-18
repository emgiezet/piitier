"""Integration tests for ``piitier mask <file>.xlsx`` (PII-14).

Fixtures are synthetic and contain only the test PESEL 90051512340.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import openpyxl
import pytest

RENDERED_MASKED = (
    "# Raport\n"
    "Nr polisy | Klient | PESEL | Kwota\n"
    "POL-1 | Jan Testowy | [PESEL] | 1500\n"
    "POL-2 | Anna Nowak | [PESEL] | 2.5\n"
    "\n"
    "# Druga\n"
    "Notatka\n"
    "PESEL [PESEL]\n"
)


def run_piitier_mask(args: list[str]) -> tuple[int, bytes, bytes]:
    """Run the piitier CLI and return (exit_code, stdout_bytes, stderr_bytes)."""
    result = subprocess.run(
        [sys.executable, "-m", "piitier.cli"] + args,
        capture_output=True,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.fixture
def report(tmp_path: Path) -> Path:
    path = tmp_path / "raport.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Raport"
    sheet.append(["Nr polisy", "Klient", "PESEL", "Kwota"])
    sheet.append(["POL-1", "Jan Testowy", "90051512340", 1500])
    sheet.append(["POL-2", "Anna Nowak", 90051512340, 2.5])
    workbook.create_sheet("Druga").append(["Notatka"])
    workbook["Druga"].append(["PESEL 90051512340"])
    workbook.save(path)
    return path


def test_uc190_mask_xlsx_prints_every_sheet_masked(report: Path) -> None:
    rc, out, err = run_piitier_mask(["mask", str(report)])

    assert rc == 0
    assert out.decode("utf-8") == RENDERED_MASKED
    assert b"90051512340" not in out
    assert err == b""


def test_uc192_skip_columns_keep_original_cells(report: Path, tmp_path: Path) -> None:
    target = tmp_path / "out.xlsx"

    rc, out, err = run_piitier_mask(
        ["mask", str(report), "-o", str(target), "--skip-columns", "PESEL"]
    )

    assert (rc, out, err) == (0, b"", b"")
    workbook = openpyxl.load_workbook(target)
    raport, druga = (list(ws.iter_rows(values_only=True)) for ws in workbook.worksheets)
    assert [row[2] for row in raport] == ["PESEL", "90051512340", 90051512340]
    assert druga == [("Notatka",), ("PESEL [PESEL]",)]


def test_uc193_unknown_column_warns_and_masks(report: Path, tmp_path: Path) -> None:
    target = tmp_path / "out.xlsx"

    rc, out, err = run_piitier_mask(
        ["mask", str(report), "-o", str(target), "--skip-columns", "Brak,1"]
    )

    assert rc == 0
    assert err == b"warning: unknown column: Brak\n"
    raport = list(openpyxl.load_workbook(target).worksheets[0].iter_rows(values_only=True))
    assert raport[1] == ("POL-1", "Jan Testowy", "[PESEL]", 1500)


def test_uc194_unknown_column_warns_for_text_output(report: Path) -> None:
    rc, out, err = run_piitier_mask(["mask", str(report), "--skip-columns", "Brak"])

    assert rc == 0
    assert err == b"warning: unknown column: Brak\n"
    assert out.decode("utf-8") == RENDERED_MASKED


def test_uc195_delimiter_rejected_for_xlsx(report: Path) -> None:
    rc, out, err = run_piitier_mask(["mask", str(report), "--delimiter", ";"])

    assert rc == 2
    assert out == b""
    assert err == f"--delimiter is only supported for .csv files: {report}\n".encode()


@pytest.mark.parametrize("output", [None, "out.xlsx"])
def test_uc196_corrupt_xlsx_exits_2(tmp_path: Path, output: str | None) -> None:
    path = tmp_path / "corrupt.xlsx"
    path.write_bytes(b"not a zip archive")
    args = ["mask", str(path)] + (["-o", str(tmp_path / output)] if output else [])

    rc, out, err = run_piitier_mask(args)

    assert rc == 2
    assert out == b""
    assert err == f"unsupported or corrupt xlsx: {path}\n".encode()
    assert not (tmp_path / "out.xlsx").exists()


def test_uc197_text_output_for_non_xlsx_target(report: Path, tmp_path: Path) -> None:
    target = tmp_path / "out.txt"

    rc, out, err = run_piitier_mask(["mask", str(report), "-o", str(target)])

    assert (rc, out, err) == (0, b"", b"")
    assert target.read_text(encoding="utf-8") == RENDERED_MASKED
    assert target.read_text(encoding="utf-8").splitlines()[0] == "# Raport"
    assert list(tmp_path.glob("*.xlsx")) == [report]


def test_uc216_converted_formulas_warn_on_stderr(tmp_path: Path) -> None:
    source = tmp_path / "formulas.xlsx"
    target = tmp_path / "out.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Raport"
    sheet.append(['="90051512340"', "=1+2", '="90051512340"'])
    workbook.save(source)
    workbook.close()

    rc, out, err = run_piitier_mask(["mask", str(source), "-o", str(target)])

    assert rc == 0
    assert out == b""
    assert err == (
        b"warning: formula: sheet Raport, cell A1 converted to text\n"
        b"warning: formula: sheet Raport, cell C1 converted to text\n"
    )
    masked = openpyxl.load_workbook(target)
    assert list(masked["Raport"].values) == [('="[PESEL]"', "=1+2", '="[PESEL]"')]
    assert [masked["Raport"].cell(1, col).data_type for col in (1, 2, 3)] == ["s", "f", "s"]
    masked.close()
