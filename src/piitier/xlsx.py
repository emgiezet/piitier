"""Render ``.xlsx`` workbooks as text and rebuild masked copies from an allow-list.

Layout of the rendered text: for each worksheet a line ``# <title>``, then one line per row with
cell texts joined by ``" | "``; sheets are separated by one blank line and the text ends with
``"\\n"``. Trailing empty cells of a row and trailing empty rows of a sheet are not rendered.
The separator is not a tab because the PESEL and NIP rules accept a tab or a space between
digits; ``" | "`` keeps every checksum rule inside one cell while the NER still sees the row.

Invariants this module relies on:

- Masking happens per cell, so the ``[start, end)`` of a span clipped to one cell is an offset
  into ``str(cell_value)``.
- The only folding applied to a cell (``\\t``, ``\\r``, ``\\n`` → space) is length-preserving, so
  offsets into the rendered text map 1:1 onto the raw cell string.

Detected formulas become plain text; undetected formulas retain their expressions.
Only cell values, selected styles and layout survive the rebuild.
"""

from __future__ import annotations

import zipfile
from copy import copy
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable
from xml.etree.ElementTree import ParseError

import openpyxl
from openpyxl.cell.cell import Cell, MergedCell
from openpyxl.packaging.core import DocumentProperties
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.formula import ArrayFormula, DataTableFormula

from piitier.csvskip import filter_spans
from piitier.render import mask as render_mask
from piitier.spans import Span

SEPARATOR = " | "
_FOLD = str.maketrans("\t\r\n", "   ")


@dataclass(frozen=True)
class XlsxCell:
    """One non-trailing cell and its range in :attr:`RenderedWorkbook.text`."""

    start: int  # offset into RenderedWorkbook.text
    end: int  # exclusive
    sheet_index: int  # index into wb.worksheets
    row: int  # 1-based, for ws.cell()
    col: int  # 1-based
    text: str  # rendered cell text (len == len(str(raw value)))


@dataclass(frozen=True)
class RenderedWorkbook:
    """The text of every worksheet plus the offsets of each rendered cell."""

    text: str
    cells: tuple[XlsxCell, ...]
    headers: tuple[tuple[str, ...], ...]  # per sheet: rendered row 1
    sheet_titles: tuple[str, ...]
    width: int  # max column count across sheets


def _cell_text(value: object) -> str:
    if value is None or isinstance(value, DataTableFormula):
        return ""
    text = (value.text or "") if isinstance(value, ArrayFormula) else str(value)
    return text.translate(_FOLD)


def _render(wb: Workbook) -> RenderedWorkbook:
    parts: list[str] = []
    cells: list[XlsxCell] = []
    headers: list[tuple[str, ...]] = []
    titles: list[str] = []
    width = 0
    offset = 0

    def emit(chunk: str) -> None:
        nonlocal offset
        parts.append(chunk)
        offset += len(chunk)

    for sheet_index, ws in enumerate(wb.worksheets):
        if sheet_index:
            emit("\n")
        emit(f"# {ws.title}\n")
        titles.append(ws.title)
        rows = [[_cell_text(value) for value in row] for row in ws.iter_rows(values_only=True)]
        for row in rows:
            while row and not row[-1]:
                row.pop()
        while rows and not rows[-1]:
            rows.pop()
        headers.append(tuple(rows[0]) if rows else ())
        for row_number, row in enumerate(rows, start=1):
            width = max(width, len(row))
            for col_number, text in enumerate(row, start=1):
                if col_number > 1:
                    emit(SEPARATOR)
                cells.append(
                    XlsxCell(offset, offset + len(text), sheet_index, row_number, col_number, text)
                )
                emit(text)
            emit("\n")
    return RenderedWorkbook("".join(parts), tuple(cells), tuple(headers), tuple(titles), width)


def _load(path: Path, *, read_only: bool) -> tuple[Workbook, RenderedWorkbook]:
    """Open and render *path*; every malformed-file error becomes one content-free ValueError."""
    try:
        wb = openpyxl.load_workbook(path, read_only=read_only, data_only=False)
        try:
            return wb, _render(wb)
        except BaseException:
            wb.close()
            raise
    except (zipfile.BadZipFile, InvalidFileException, KeyError, ValueError, ParseError):
        raise ValueError(f"unsupported or corrupt xlsx: {path}") from None


def render_workbook(path: Path) -> RenderedWorkbook:
    """Render every worksheet of *path* (read-only, formulas as written)."""
    wb, rendered = _load(path, read_only=True)
    wb.close()
    return rendered


def header_union(rendered: RenderedWorkbook) -> set[str]:
    """Casefolded row-1 texts of every sheet, for splitting comma-joined selectors."""
    return {header.strip().casefold() for sheet in rendered.headers for header in sheet}


def protected_ranges(
    rendered: RenderedWorkbook, selectors: list[str]
) -> tuple[list[tuple[int, int]], list[str]]:
    """Resolve column selectors per sheet and return (merged cell ranges, unknown selectors).

    Semantics mirror ``csvskip.plan_skips``: an ASCII-digit selector is a 1-based column index
    (valid below :attr:`RenderedWorkbook.width`); any other selector matches row-1 cells of each
    sheet by ``strip().casefold()``. ``plan_skips`` itself is not reused because it resolves
    against the ``FieldRange`` offsets of one flat CSV text, not per-sheet cells.
    """
    indices: set[int] = set()
    by_sheet: dict[int, set[int]] = {}
    unknown: list[str] = []
    for selector in selectors:
        if selector.isascii() and selector.isdigit():
            index = int(selector) - 1
            if 0 <= index < rendered.width:
                indices.add(index)
            else:
                unknown.append(selector)
            continue
        wanted = selector.strip().casefold()
        matched = False
        for sheet_index, header in enumerate(rendered.headers):
            for col_index, text in enumerate(header):
                if text.strip().casefold() == wanted:
                    by_sheet.setdefault(sheet_index, set()).add(col_index)
                    matched = True
        if not matched:
            unknown.append(selector)
    ranges = sorted(
        (cell.start, cell.end)
        for cell in rendered.cells
        if cell.col - 1 in indices or cell.col - 1 in by_sheet.get(cell.sheet_index, ())
    )
    merged: list[tuple[int, int]] = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged, unknown


def copy_styles(src_cell: Cell | MergedCell, dst_cell: Cell) -> None:
    """Copy only the supported presentation attributes, never values or relationships."""
    # openpyxl returns StyleProxy objects; copying unwraps them to serialisable styles.
    dst_cell.font = copy(src_cell.font)  # type: ignore[assignment]
    dst_cell.fill = copy(src_cell.fill)  # type: ignore[assignment]
    dst_cell.border = copy(src_cell.border)  # type: ignore[assignment]
    dst_cell.alignment = copy(src_cell.alignment)  # type: ignore[assignment]
    dst_cell.number_format = src_cell.number_format


def mask_workbook(
    source: Path,
    target: Path,
    *,
    detector: Callable[[str], list[Span]],
    skip_columns: list[str] | None = None,
    on_unknown_column: Callable[[str], None] | None = None,
    on_leak: Callable[[str], None] | None = None,
) -> int:
    """Rebuild *target* from masked cells and allow-listed styles and layout.

    Return the number of detected formulas converted to plain text. Unsupported workbook
    objects and metadata are deliberately not copied. Column exclusions apply only to cells.
    """
    if target.resolve() == source.resolve():
        raise ValueError(f"refusing to overwrite input: {target}")
    wb, rendered = _load(source, read_only=False)
    try:
        spans = detector(rendered.text)
        ranges, unknown = protected_ranges(rendered, skip_columns or [])
        if on_unknown_column is not None:
            for selector in unknown:
                on_unknown_column(selector)
        spans = sorted(filter_spans(spans, ranges), key=lambda span: (span.start, -span.end))
        # Detectors normally fuse overlaps; union them here too so clipping cannot expose PII.
        merged: list[Span] = []
        for span in spans:
            if merged and span.start < merged[-1].end:
                merged[-1] = replace(merged[-1], end=max(merged[-1].end, span.end))
            else:
                merged.append(span)
        output = openpyxl.Workbook()
        active = output.active
        if active is not None:
            output.remove(active)
        output.properties = DocumentProperties(creator="", lastModifiedBy="")
        converted = 0
        try:
            cursor = 0
            for index, sheet in enumerate(wb.worksheets):
                title_start = rendered.text.index(f"# {sheet.title}\n", cursor) + 2
                title_end = title_start + len(sheet.title)
                title_hits = [
                    replace(
                        s,
                        start=max(s.start, title_start) - title_start,
                        end=min(s.end, title_end) - title_start,
                    )
                    for s in merged
                    if s.start < title_end and s.end > title_start
                ]
                title = render_mask(sheet.title, title_hits)
                if len(title) > 31 or any(char in title for char in "[]"):
                    title = f"Sheet{index + 1}"
                suffix = 0
                while title.casefold() in {s.title.casefold() for s in output.worksheets}:
                    suffix += 1
                    title = f"Sheet{index + 1}_{suffix}"
                destination = output.create_sheet(title)
                cursor = title_end
                for column_key, column_dimension in sheet.column_dimensions.items():
                    destination.column_dimensions[column_key].width = column_dimension.width
                for row_key, row_dimension in sheet.row_dimensions.items():
                    destination.row_dimensions[row_key].height = row_dimension.height
                destination.freeze_panes = sheet.freeze_panes
                for row in sheet.iter_rows():
                    for original in row:
                        cell = destination.cell(original.row, original.column)
                        cell.value = copy(original.value)
                        cell.data_type = original.data_type
                        copy_styles(original, cell)
                for area in sheet.merged_cells.ranges:
                    destination.merge_cells(str(area))

            span_index = 0
            for cell in rendered.cells:
                if cell.start == cell.end:
                    continue
                while span_index < len(merged) and merged[span_index].end <= cell.start:
                    span_index += 1
                hits: list[Span] = []
                if span_index < len(merged) and merged[span_index].start < cell.end:
                    hits.append(merged[span_index])
                next_index = span_index + 1
                while next_index < len(merged) and merged[next_index].start < cell.end:
                    hits.append(merged[next_index])
                    next_index += 1
                if not hits:
                    continue
                original = wb.worksheets[cell.sheet_index].cell(cell.row, cell.col)
                destination = output.worksheets[cell.sheet_index].cell(cell.row, cell.col)
                relative = [
                    replace(
                        span,
                        start=max(span.start, cell.start) - cell.start,
                        end=min(span.end, cell.end) - cell.start,
                    )
                    for span in hits
                ]
                value = original.value
                raw = (value.text or "") if isinstance(value, ArrayFormula) else str(value)
                destination.value = render_mask(raw, relative)
                destination.data_type = "s"
                if original.data_type == "f":
                    converted += 1
                    if on_leak is not None:
                        # The output title: the source title may itself be personal data.
                        on_leak(
                            f"formula: sheet {destination.parent.title}, cell {original.coordinate}"
                        )
            output.save(target)
            return converted
        finally:
            output.close()
    finally:
        wb.close()
