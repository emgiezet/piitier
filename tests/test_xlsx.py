"""Workbook rendering and masked-workbook output (PII-14).

Fixtures are synthetic: the test PESEL 90051512340 and the test card 4111 1111 1111 1111 only.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import openpyxl
import pytest

import piitier
from piitier.labels import Label
from piitier.spans import Span
from piitier.xlsx import mask_workbook, protected_ranges, render_workbook

DATE = datetime.datetime(2025, 3, 12)


def _write_report(path: Path) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Raport"
    sheet.append(["Nr polisy", "Klient", "PESEL", "Kwota", "Suma", "Data"])
    sheet.append(["POL-1", "Jan Testowy", "90051512340", 1500, "=D2*2", DATE])
    sheet.append(["POL-2", "PESEL 90051512340\nlinia 2", 90051512340, 2.5, "=D3*2"])
    sheet["D2"].number_format = "0.00"
    sheet.column_dimensions["B"].width = 30
    second = workbook.create_sheet("Druga")
    second.append(["Notatka", "Karta"])
    second.append(["bez danych", "4111 1111 1111 1111"])
    workbook.save(path)


def _values(path: Path) -> list[list[tuple[object, ...]]]:
    workbook = openpyxl.load_workbook(path)
    return [list(ws.iter_rows(values_only=True)) for ws in workbook.worksheets]


@pytest.fixture
def report(tmp_path: Path) -> Path:
    path = tmp_path / "raport.xlsx"
    _write_report(path)
    return path


def test_render_lists_every_sheet_with_cell_offsets(report: Path) -> None:
    rendered = render_workbook(report)

    assert rendered.text == (
        "# Raport\n"
        "Nr polisy | Klient | PESEL | Kwota | Suma | Data\n"
        "POL-1 | Jan Testowy | 90051512340 | 1500 | =D2*2 | 2025-03-12 00:00:00\n"
        "POL-2 | PESEL 90051512340 linia 2 | 90051512340 | 2.5 | =D3*2\n"
        "\n"
        "# Druga\n"
        "Notatka | Karta\n"
        "bez danych | 4111 1111 1111 1111\n"
    )
    assert all(rendered.text[c.start : c.end] == c.text for c in rendered.cells)
    assert rendered.sheet_titles == ("Raport", "Druga")
    assert rendered.headers[1] == ("Notatka", "Karta")
    assert rendered.width == 6


def test_protected_ranges_resolve_names_per_sheet_and_indices_everywhere(report: Path) -> None:
    rendered = render_workbook(report)

    by_name, unknown = protected_ranges(rendered, ["karta ", "Brak", "7"])
    by_index, _ = protected_ranges(rendered, ["2"])

    def texts(ranges: list[tuple[int, int]]) -> list[str]:
        return [rendered.text[start:end] for start, end in ranges]

    assert texts(by_name) == ["Karta", "4111 1111 1111 1111"]
    assert unknown == ["Brak", "7"]
    assert texts(by_index) == [
        "Klient",
        "Jan Testowy",
        "PESEL 90051512340 linia 2",
        "Karta",
        "4111 1111 1111 1111",
    ]


def test_corrupt_workbook_raises_content_free_error(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.xlsx"
    path.write_bytes(b"90051512340 is not a zip")

    with pytest.raises(ValueError) as excinfo:
        render_workbook(path)

    assert str(excinfo.value) == f"unsupported or corrupt xlsx: {path}"
    with pytest.raises(FileNotFoundError):
        render_workbook(tmp_path / "missing.xlsx")


def test_uc174_masked_workbook_keeps_types_formulas_and_source(
    report: Path, tmp_path: Path
) -> None:
    original = report.read_bytes()
    target = tmp_path / "out.xlsx"

    mask_workbook(report, target, detector=piitier.detect)

    raport, druga = _values(target)
    assert raport[1] == ("POL-1", "Jan Testowy", "[PESEL]", 1500, "=D2*2", DATE)
    assert raport[2] == ("POL-2", "PESEL [PESEL]\nlinia 2", "[PESEL]", 2.5, "=D3*2", None)
    assert druga[1] == ("bez danych", "[NR_KARTY]")
    assert report.read_bytes() == original


def test_uc180_detection_across_two_cells_masks_both(tmp_path: Path) -> None:
    source = tmp_path / "split.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["karta 4111 1111", "1111 1111 koniec"])
    workbook.save(source)
    text = render_workbook(source).text
    start = text.index("4111")
    end = text.index(" koniec")

    def detector(rendered: str) -> list[Span]:
        return [Span(start, end, Label.NR_KARTY, "model:ner", 0.9, "valid")]

    mask_workbook(source, tmp_path / "out.xlsx", detector=detector)

    assert _values(tmp_path / "out.xlsx") == [[("karta [NR_KARTY]", "[NR_KARTY] koniec")]]


def test_uc184_cells_without_detection_are_identical(report: Path, tmp_path: Path) -> None:
    target = tmp_path / "out.xlsx"

    mask_workbook(report, target, detector=piitier.detect, skip_columns=["Karta", "PESEL"])

    source_book = openpyxl.load_workbook(report)
    masked_book = openpyxl.load_workbook(target)
    changed = []
    for source_ws, masked_ws in zip(source_book.worksheets, masked_book.worksheets, strict=True):
        for source_row, masked_row in zip(
            source_ws.iter_rows(), masked_ws.iter_rows(), strict=True
        ):
            for before, after in zip(source_row, masked_row, strict=True):
                if (type(before.value), before.value) != (type(after.value), after.value):
                    changed.append(before.coordinate)
    # Only the free-text PESEL outside the skipped columns changes; F2, a date right after a
    # formula ending in a digit, stays a datetime (a tab separator made it a false PESEL).
    assert changed == ["B3"]
    masked = masked_book.worksheets[0]
    assert masked["D2"].number_format == "0.00"
    assert masked.column_dimensions["B"].width == 30


def test_formula_containing_an_identifier_is_never_rewritten(tmp_path: Path) -> None:
    source = tmp_path / "formula.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(['="90051512340"'])
    workbook.save(source)

    mask_workbook(source, tmp_path / "out.xlsx", detector=piitier.detect)

    assert _values(tmp_path / "out.xlsx") == [[('="90051512340"',)]]


def test_mask_workbook_refuses_to_overwrite_source(report: Path) -> None:
    original = report.read_bytes()

    with pytest.raises(ValueError, match="refusing to overwrite input"):
        mask_workbook(report, report, detector=piitier.detect)

    assert report.read_bytes() == original
