"""Locate CSV cells in original-text offsets and protect selected columns."""

from __future__ import annotations

import csv
from bisect import bisect_right
from dataclasses import dataclass

from piitier.spans import Span


@dataclass(frozen=True)
class FieldRange:
    start: int
    end: int
    row_index: int
    col_index: int
    value: str


@dataclass(frozen=True)
class ParseResult:
    delimiter: str
    rows: list[list[FieldRange]]


@dataclass(frozen=True)
class SkipPlan:
    protected_ranges: list[tuple[int, int]]
    unknown_selectors: list[str]


def sniff_delimiter(text: str) -> str:
    """Guess a CSV delimiter from the first 4096 characters."""
    sample = text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,\t|").delimiter
    except csv.Error:
        first_line = next((line for line in sample.split("\n") if line), "")
        return max(";,\t|", key=first_line.count) if any(c in first_line for c in ";,\t|") else ";"


def parse_csv_field_ranges(text: str, delimiter: str) -> ParseResult:
    """Scan field boundaries without changing quotes, delimiters or line endings."""
    rows: list[list[FieldRange]] = []
    if not text:
        return ParseResult(delimiter, rows)
    row: list[FieldRange] = []
    i = 0
    n = len(text)
    while i <= n:
        start = i
        quoted = i < n and text[i] == '"'
        if quoted:
            i += 1
        while i < n:
            char = text[i]
            if quoted and char == '"':
                if i + 1 < n and text[i + 1] == '"':
                    i += 2
                    continue
                quoted = False
            elif not quoted and (char == delimiter or char in "\r\n"):
                break
            i += 1
        raw = text[start:i]
        value = raw[1:-1].replace('""', '"') if raw.startswith('"') and raw.endswith('"') else raw
        row.append(FieldRange(start, i, len(rows), len(row), value))
        if i == n:
            rows.append(row)
            break
        if text[i] == delimiter:
            i += 1
        else:
            rows.append(row)
            row = []
            if text[i : i + 2] == "\r\n":
                i += 2
            else:
                i += 1
            if i == n:
                break
    return ParseResult(delimiter, rows)


def plan_skips(parse_result: ParseResult, selectors: list[str]) -> SkipPlan:
    """Resolve names or 1-based indices against parsed CSV columns."""
    rows = parse_result.rows
    headers = rows[0] if rows else []
    max_cols = max((len(row) for row in rows), default=0)
    selected: set[int] = set()
    unknown: list[str] = []
    for selector in selectors:
        if selector.isascii() and selector.isdigit():
            index = int(selector) - 1
            if 0 <= index < max_cols:
                selected.add(index)
            else:
                unknown.append(selector)
        else:
            matches = [
                cell.col_index
                for cell in headers
                if cell.value.strip().casefold() == selector.strip().casefold()
            ]
            if matches:
                selected.update(matches)
            else:
                unknown.append(selector)
    ranges = sorted(
        (cell.start, cell.end) for row in rows for cell in row if cell.col_index in selected
    )
    merged: list[tuple[int, int]] = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return SkipPlan(merged, unknown)


def split_column_selectors(items: list[str], headers: set[str]) -> list[str]:
    """Split comma-joined selectors unless the whole item is a known header (casefolded)."""
    if not any("," in item for item in items):
        return items
    return [
        token.strip()
        for item in items
        for token in ([item] if item.casefold() in headers else item.split(","))
        if token.strip()
    ]


def filter_spans(spans: list[Span], protected_ranges: list[tuple[int, int]]) -> list[Span]:
    """Discard only detections entirely within a protected cell range."""
    starts = [start for start, _ in protected_ranges]
    kept: list[Span] = []
    for span in spans:
        index = bisect_right(starts, span.start) - 1
        if index < 0 or span.end > protected_ranges[index][1]:
            kept.append(span)
    return kept
