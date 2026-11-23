"""Workbook rendering and masked-workbook output (PII-14).

Fixtures are synthetic: the test PESEL 90051512340 and the test card 4111 1111 1111 1111 only.
"""

from __future__ import annotations

import datetime
import time
import zipfile
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


def test_uc191_masked_workbook_keeps_types_formulas_and_source(
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


def test_uc198_detection_across_two_cells_masks_both(tmp_path: Path) -> None:
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


def test_uc202_cells_without_detection_are_identical(report: Path, tmp_path: Path) -> None:
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


def test_formula_containing_an_identifier_is_masked(tmp_path: Path) -> None:
    source = tmp_path / "formula.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(['="90051512340"'])
    workbook.save(source)

    mask_workbook(source, tmp_path / "out.xlsx", detector=piitier.detect)

    assert _values(tmp_path / "out.xlsx") == [[('="[PESEL]"',)]]


def test_mask_workbook_refuses_to_overwrite_source(report: Path) -> None:
    original = report.read_bytes()

    with pytest.raises(ValueError, match="refusing to overwrite input"):
        mask_workbook(report, report, detector=piitier.detect)

    assert report.read_bytes() == original


@pytest.fixture
def leaky_workbook(tmp_path: Path) -> Path:
    from openpyxl.comments import Comment
    from openpyxl.workbook.defined_name import DefinedName

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "90051512340"
    sheet.append(['="90051512340"&B1', "90051512340", "90051512340"])
    sheet["B1"].comment = Comment("90051512340", "90051512340")
    sheet["C1"].hyperlink = "mailto:90051512340@piitier.pl"
    for field in ("creator", "lastModifiedBy", "title", "subject"):
        setattr(workbook.properties, field, "90051512340")
    sheet.oddHeader.center.text = "90051512340"
    sheet.evenFooter.left.text = "90051512340"
    workbook.defined_names.add(DefinedName("secret", attr_text="'90051512340'!$B$1"))
    sheet.freeze_panes = "B2"
    sheet.row_dimensions[1].height = 25
    sheet.merge_cells("D2:E2")
    path = tmp_path / "leaky.xlsx"
    workbook.save(path)
    return path


def _masked_leaky(source: Path) -> openpyxl.Workbook:
    target = source.with_name("masked.xlsx")
    mask_workbook(source, target, detector=piitier.detect)
    return openpyxl.load_workbook(target)


def test_uc203_formula_detection_reports_plain_text(leaky_workbook: Path) -> None:
    warnings: list[str] = []
    target = leaky_workbook.with_name("masked.xlsx")
    count = mask_workbook(leaky_workbook, target, detector=piitier.detect, on_leak=warnings.append)
    workbook = openpyxl.load_workbook(target)
    assert count == 1
    assert warnings == ["formula: sheet Sheet1, cell A1"]
    assert workbook.sheetnames == ["Sheet1"]
    assert workbook.active["A1"].value == '="[PESEL]"&B1'
    assert workbook.active["A1"].data_type == "s"


def test_uc204_comments_are_dropped(leaky_workbook: Path) -> None:
    sheet = _masked_leaky(leaky_workbook).active
    assert sheet["B1"].value == "[PESEL]"
    assert sheet["B1"].comment is None


def test_uc205_hyperlink_targets_are_dropped(leaky_workbook: Path) -> None:
    sheet = _masked_leaky(leaky_workbook).active
    assert sheet["C1"].value == "[PESEL]"
    assert sheet["C1"].hyperlink is None
    with zipfile.ZipFile(leaky_workbook.with_name("masked.xlsx")) as archive:
        assert all(b"90051512340" not in archive.read(name) for name in archive.namelist())


def test_uc206_document_properties_are_neutral(leaky_workbook: Path) -> None:
    properties = _masked_leaky(leaky_workbook).properties
    for field in ("creator", "lastModifiedBy", "title", "subject"):
        assert getattr(properties, field) in (None, "")


def test_uc207_sheet_names_are_sanitized(leaky_workbook: Path) -> None:
    workbook = _masked_leaky(leaky_workbook)
    assert workbook.sheetnames == ["Sheet1"]
    assert workbook.active.freeze_panes == "B2"
    assert workbook.active.row_dimensions[1].height == 25
    assert str(workbook.active.merged_cells) == "D2:E2"


def test_uc208_headers_and_footers_are_dropped(leaky_workbook: Path) -> None:
    sheet = _masked_leaky(leaky_workbook).active
    for kind in (
        "oddHeader",
        "evenHeader",
        "firstHeader",
        "oddFooter",
        "evenFooter",
        "firstFooter",
    ):
        for position in ("left", "center", "right"):
            assert getattr(getattr(sheet, kind), position).text is None


def test_uc209_defined_names_are_dropped(leaky_workbook: Path) -> None:
    workbook = _masked_leaky(leaky_workbook)
    assert not workbook.defined_names
    assert not workbook.active.defined_names


def test_uc210_multiple_formulas_have_exact_conversion_count(tmp_path: Path) -> None:
    source = tmp_path / "formulas.xlsx"
    workbook = openpyxl.Workbook()
    workbook.active.append(['="90051512340"', "=1+2", '="90051512340"'])
    workbook.save(source)
    target = tmp_path / "out.xlsx"
    assert mask_workbook(source, target, detector=piitier.detect) == 2
    sheet = openpyxl.load_workbook(target).active
    assert [sheet.cell(1, col).data_type for col in range(1, 4)] == ["s", "f", "s"]
    assert list(sheet.values) == [('="[PESEL]"', "=1+2", '="[PESEL]"')]


def test_uc211_integer_pesel_is_masked(tmp_path: Path) -> None:
    source = tmp_path / "int.xlsx"
    workbook = openpyxl.Workbook()
    workbook.active["A1"] = 90051512340
    workbook.save(source)
    assert _masked_leaky(source).active["A1"].value == "[PESEL]"


def test_uc212_float_pesel_is_masked(tmp_path: Path) -> None:
    source = tmp_path / "float.xlsx"
    workbook = openpyxl.Workbook()
    workbook.active["A1"] = 90051512340.0
    workbook.save(source)
    assert _masked_leaky(source).active["A1"].value == "[PESEL]"


def test_uc213_overlapping_detections_cross_separator(tmp_path: Path) -> None:
    source = tmp_path / "overlap.xlsx"
    workbook = openpyxl.Workbook()
    workbook.active.append(["900515", "12340"])
    workbook.save(source)

    def detector(text: str) -> list[Span]:
        start = text.index("900515")
        end = text.index("12340") + 5
        return [
            Span(start, end, Label.PESEL, "rule", 1.0, "valid"),
            Span(start + 2, end - 1, Label.PESEL, "rule", 1.0, "valid"),
        ]

    target = tmp_path / "out.xlsx"
    mask_workbook(source, target, detector=detector)
    assert _values(target) == [[("[PESEL]", "[PESEL]")]]


def test_uc214_output_zip_contains_no_original_identifier(leaky_workbook: Path) -> None:
    _masked_leaky(leaky_workbook)
    with zipfile.ZipFile(leaky_workbook.with_name("masked.xlsx")) as archive:
        assert archive.testzip() is None
        assert all(b"90051512340" not in archive.read(name) for name in archive.namelist())


def test_uc215_masks_five_thousand_cells_under_five_seconds(tmp_path: Path) -> None:
    source = tmp_path / "large.xlsx"
    workbook = openpyxl.Workbook()
    for _ in range(5000):
        workbook.active.append(["90051512340"])
    workbook.save(source)
    target = tmp_path / "out.xlsx"
    start = time.monotonic()
    assert mask_workbook(source, target, detector=piitier.detect) == 0
    assert time.monotonic() - start < 5
    assert all(row == ("[PESEL]",) for row in _values(target)[0])


@pytest.mark.parametrize("skip", [False, True])
def test_uc260_sheet_title_offsets_cannot_match_cell_text(tmp_path: Path, skip: bool) -> None:
    source = tmp_path / "titles.xlsx"
    target = tmp_path / "out.xlsx"
    workbook = openpyxl.Workbook()
    workbook.active.title = "Raport"
    workbook.active.append(["Kol"])
    workbook.active.append(["# 90051512340"])
    workbook.create_sheet("90051512340")
    workbook.save(source)
    workbook.close()

    mask_workbook(source, target, detector=piitier.detect, skip_columns=["Kol"] if skip else [])

    masked = openpyxl.load_workbook(target)
    assert masked.sheetnames == ["Raport", "Sheet2"]
    assert masked["Raport"]["A2"].value == ("# 90051512340" if skip else "# [PESEL]")
    masked.close()
    with zipfile.ZipFile(target) as archive:
        for name in archive.namelist():
            if skip and name == "xl/worksheets/sheet1.xml":
                continue  # Explicitly excluded cell values are deliberately retained.
            assert b"90051512340" not in archive.read(name), name


@pytest.mark.parametrize(
    "number_format",
    [
        '"PESEL 90051512340: "0',
        r"\9\0\0\5\1\5\1\2\3\4\0 0",
        '"90051512340"@',
        "@90051512340",
        "90051512340@",
        "PESEL @",
        "[90051512340]0",
        "General",  # Isolates the unsafe font name from number-format sanitisation.
    ],
)
def test_uc261_free_text_styles_are_removed(tmp_path: Path, number_format: str) -> None:
    from openpyxl.styles import Font, NamedStyle

    source = tmp_path / "styles.xlsx"
    target = tmp_path / "out.xlsx"
    workbook = openpyxl.Workbook()
    style = NamedStyle(
        name="90051512340",
        font=Font(name="90051512340", size=14, bold=True, italic=True, color="FF123456"),
        number_format=number_format,
    )
    workbook.active["A1"] = "90051512340"
    workbook.active["A1"].style = style
    workbook.save(source)
    workbook.close()

    mask_workbook(source, target, detector=piitier.detect)

    masked = openpyxl.load_workbook(target)
    cell = masked.active["A1"]
    assert cell.value == "[PESEL]"
    assert cell.number_format == "General"
    assert cell.font.name == "Calibri"
    assert (cell.font.sz, cell.font.bold, cell.font.italic, cell.font.color.rgb) == (
        14,
        True,
        True,
        "FF123456",
    )
    assert masked.named_styles == ["Normal"]
    masked.close()
    with zipfile.ZipFile(target) as archive:
        for name in archive.namelist():
            assert b"90051512340" not in archive.read(name), name


@pytest.mark.parametrize(
    "number_format",
    ['"$"#,##0_);("$"#,##0)', "0.000", "yyyy-mm-dd", "[h]:mm:ss", "0.00;[Red]-0.00", "@"],
)
def test_uc262_safe_styles_remain_supported(tmp_path: Path, number_format: str) -> None:
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side

    source = tmp_path / "safe-styles.xlsx"
    target = tmp_path / "out.xlsx"
    workbook = openpyxl.Workbook()
    cell = workbook.active["A1"]
    cell.value = 5
    cell.number_format = number_format
    cell.font = Font(name="Arial", size=16, bold=True, italic=True, color="FF123456")
    cell.fill = PatternFill("solid", fgColor="FFABCDEF")
    cell.border = Border(left=Side(style="thin", color="FF123456"))
    cell.alignment = Alignment(horizontal="center", wrap_text=True)
    cell.protection = Protection(locked=False, hidden=True)
    workbook.save(source)
    workbook.close()

    mask_workbook(source, target, detector=piitier.detect)

    masked = openpyxl.load_workbook(target)
    cell = masked.active["A1"]
    assert cell.number_format == number_format
    assert (cell.font.name, cell.font.sz, cell.font.bold, cell.font.italic) == (
        "Arial",
        16,
        True,
        True,
    )
    assert cell.fill.fgColor.rgb == "FFABCDEF"
    assert cell.border.left.style == "thin"
    assert cell.alignment.horizontal == "center"
    assert cell.alignment.wrap_text
    assert cell.protection == Protection()
    masked.close()


def test_uc263_chartsheet_only_is_a_content_free_error(tmp_path: Path) -> None:
    from openpyxl.chart import BarChart

    source = tmp_path / "charts.xlsx"
    target = tmp_path / "out.xlsx"
    workbook = openpyxl.Workbook()
    workbook.create_chartsheet("90051512340").add_chart(BarChart())
    workbook.remove(workbook.active)
    workbook.save(source)
    workbook.close()
    target.write_bytes(b"existing target")

    with pytest.raises(ValueError, match=f"^unsupported or corrupt xlsx: {source}$"):
        mask_workbook(source, target, detector=piitier.detect)
    assert target.read_bytes() == b"existing target"
    with pytest.raises(ValueError, match=f"^unsupported or corrupt xlsx: {source}$"):
        render_workbook(source)


def test_uc263_workbook_the_reader_cannot_parse_is_a_content_free_error(tmp_path: Path) -> None:
    # A chartsheet without a chart makes openpyxl's reader raise AttributeError, not a zip error.
    source = tmp_path / "empty-chartsheet.xlsx"
    target = tmp_path / "out.xlsx"
    workbook = openpyxl.Workbook()
    workbook.create_chartsheet("90051512340")
    workbook.remove(workbook.active)
    workbook.save(source)
    workbook.close()

    with pytest.raises(ValueError, match=f"^unsupported or corrupt xlsx: {source}$"):
        mask_workbook(source, target, detector=piitier.detect)
    assert not target.exists()
    with pytest.raises(FileNotFoundError):
        render_workbook(tmp_path / "missing.xlsx")


def test_uc264_numbering_uses_original_span_offsets_across_cells(tmp_path: Path) -> None:
    source = tmp_path / "names.xlsx"
    target = tmp_path / "out.xlsx"
    workbook = openpyxl.Workbook()
    workbook.active.append(["Zoja", "Testowa", "Mira Fikcyjna"])
    workbook.save(source)
    workbook.close()
    rendered = render_workbook(source)
    first = rendered.text.index("Zoja")
    second = rendered.text.index("Mira")
    spans = [
        Span(first, first + len("Zoja | Testowa"), Label.OSOBA, "model", 1.0, "valid"),
        Span(second, second + len("Mira Fikcyjna"), Label.OSOBA, "model", 1.0, "valid"),
    ]
    numbering = {(spans[0].start, spans[0].end): 1, (spans[1].start, spans[1].end): 2}

    mask_workbook(source, target, detector=lambda _: spans, numbering=numbering)

    assert _values(target) == [[("[OSOBA_1]", "[OSOBA_1]", "[OSOBA_2]")]]


def test_uc266_numbering_survives_overlapping_span_union(tmp_path: Path) -> None:
    source = tmp_path / "overlap-names.xlsx"
    target = tmp_path / "out.xlsx"
    workbook = openpyxl.Workbook()
    workbook.active.append(["Zoja Testowa"])
    workbook.save(source)
    workbook.close()
    start = render_workbook(source).text.index("Zoja")
    spans = [
        Span(start, start + 6, Label.OSOBA, "model", 1.0, "valid"),
        Span(start + 4, start + 12, Label.OSOBA, "model", 1.0, "valid"),
    ]

    mask_workbook(source, target, detector=lambda _: spans, numbering={(start, start + 6): 1})

    assert _values(target) == [[("[OSOBA_1]",)]]
