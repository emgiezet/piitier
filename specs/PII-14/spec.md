---
ticket: PII-14
title: piitier mask <file>.xlsx — workbook input and masked workbook output
status: approved
stacks: [python]
---

# PII-14 — `piitier mask <file>.xlsx`: workbook input and masked workbook output

<!-- approved: owner instruction in session, 2026-11-06 ("dodaj wsparcie anonimizacji plików xlsx i instalację na Windows w dokumentacji"). -->

## Problem

Insurance reports and claim registers arrive as Excel workbooks. The CLI reads `.txt`, `.md`, `.csv`
and `.pdf` only, so a workbook has to be exported to CSV by hand, one sheet at a time, and the masked
result loses its sheets, number formats and formulas. The README also documents a Linux-only setup,
although the pinned wheels cover Windows x64.

## Scope

In:
- A `.xlsx` loader registered in the loader registry. Every worksheet is rendered as text: a line
  `# <sheet title>`, then one line per row with cells joined by ` | `; one blank line between sheets.
- `piitier mask <file>.xlsx -o <out>.xlsx` writes a masked workbook in which only cell values change.
  Any other output (stdout, `-o out.txt`) is the masked rendered text.
- `--skip-columns` for `.xlsx` (header names from row 1 of any sheet, or 1-based indices), with the
  same unknown-column warning as CSV. `--delimiter` stays CSV-only.
- `piitier compare <file>.xlsx` opens the column-selection screen and exports
  `<name>_anonymised.xlsx`.
- README `## Installation` with Linux/macOS and Windows (PowerShell) instructions.
- No new dependency: `openpyxl==3.1.5` is already pinned.

Out:
- `.xls`, `.xlsm`, `.ods`.
- Masking sheet names, chart titles, comments, images, defined names.
- `piitier scan` for `.xlsx` (`scan.py::scan_file` skips binary files; unchanged).
- Writing a masked PDF.
- Windows CI.

Change budget: 1100 added lines, 12 files, 5 modules

## Context

- `src/piitier/csvskip.py` (`plan_skips`, `filter_spans`) defines selector semantics and the
  protected-range contract the xlsx path reuses.
- `src/piitier/cli.py::mask_file`, `src/piitier/tui.py` (`AnonymizationDiffApp`, `compare_file`).
- `src/piitier/datagen/tabular.py::_read_xlsx` is datagen's own reader; it is not changed.
- Cell separator ` | `, not a tab: the PESEL and NIP rules accept a tab or space between digits, so
  a tab-joined row turns `90051512340<TAB>1500` into a non-match and `…2<TAB>2025-03-12 00…` into a
  false PESEL across a formula and a date. ` | ` keeps every checksum rule inside one cell while the
  NER still sees the whole row.
- New: `src/piitier/xlsx.py`, `tests/test_xlsx.py`, `tests/test_cli_xlsx.py`,
  `tests/test_readme_install.py`; edit `loaders.py`, `cli.py`, `csvskip.py`, `tui.py`,
  `tests/test_tui.py`, `tests/test_cli.py`, `README.md`.

## Acceptance criteria

Fixtures contain the synthetic PESEL `90051512340` and card `4111 1111 1111 1111` only.

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-173 | developer | `piitier mask raport.xlsx` (2 sheets, PESEL in a text cell and in an int cell, each followed by a numeric cell) | stdout is the rendered text of both sheets with `[PESEL]` in both places, no `90051512340`; exit 0 | integration |
| UC-174 | developer | `piitier mask raport.xlsx -o out.xlsx` | `out.xlsx` opens with openpyxl; masked cells hold `[PESEL]`; `1500` is still `int`, `2.5` still `float`, the date still `datetime`, `=D2*2` still that formula string; source bytes unchanged; exit 0 | unit |
| UC-175 | developer | `… -o out.xlsx --skip-columns "Nr polisy"` | every cell of that column keeps its original value; other columns masked | integration |
| UC-176 | developer | `… --skip-columns "Brak"` | stderr `warning: unknown column: Brak`; masking proceeds; exit 0 | integration |
| UC-177 | developer | `piitier mask raport.xlsx --delimiter ";"` | exit 2; stderr `--delimiter is only supported for .csv files: <path>` | integration |
| UC-178 | developer | `piitier mask corrupt.xlsx` (not a zip) | exit 2; stderr `unsupported or corrupt xlsx: <path>`; stdout empty | integration |
| UC-179 | developer | `piitier mask raport.xlsx -o out.txt` | `out.txt` is the UTF-8 rendered text, first line `# Raport`; no workbook written | integration |
| UC-180 | developer | a detection spanning two adjacent cells (a detector span crossing ` \| `), `-o out.xlsx` | both overlapped cells hold the placeholder; no character of either original value remains | unit |
| UC-181 | developer | `compare raport.xlsx` TUI: uncheck column 1, `Anonimizuj`, `Eksportuj` | one checkbox per column labelled from row 1; column 1 values unchanged in the diff; `raport_anonymised.xlsx` written and masked | unit |
| UC-182 | developer | TUI export twice | second attempt shows `Plik już istnieje`; the first file is not rewritten | unit |
| UC-183 | reader | opens `README.md` | `## Installation` with `### Linux and macOS` and `### Windows (PowerShell)`, winget/uv commands, UTF-8 output guidance, x64-only note | unit |
| UC-184 | developer | fidelity after `-o out.xlsx` | every cell with no detection is identical in value and type to the source cell, including a date right after a formula ending in a digit | unit |

## Open questions

none
