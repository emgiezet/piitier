---
ticket: PII-28
title: "Mask .xlsx workbooks; Windows installation docs"
status: approved
stacks: [python]
---

# PII-28 — Mask .xlsx workbooks; Windows installation docs

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
| UC-190 | developer | `piitier mask raport.xlsx` (2 sheets, PESEL in a text cell and in an int cell, each followed by a numeric cell) | stdout is the rendered text of both sheets with `[PESEL]` in both places, no `90051512340`; exit 0 | integration |
| UC-191 | developer | `piitier mask raport.xlsx -o out.xlsx` | `out.xlsx` opens with openpyxl; masked cells hold `[PESEL]`; `1500` is still `int`, `2.5` still `float`, the date still `datetime`, `=D2*2` still that formula string; source bytes unchanged; exit 0 | unit |
| UC-192 | developer | `… -o out.xlsx --skip-columns "Nr polisy"` | every cell of that column keeps its original value; other columns masked | integration |
| UC-193 | developer | `… -o out.xlsx --skip-columns "Brak"` | stderr `warning: unknown column: Brak`; masking proceeds; exit 0 | integration |
| UC-194 | developer | `… --skip-columns "Brak"` with text output | stderr `warning: unknown column: Brak`; masking proceeds; exit 0 | integration |
| UC-195 | developer | `piitier mask raport.xlsx --delimiter ";"` | exit 2; stderr `--delimiter is only supported for .csv files: <path>` | integration |
| UC-196 | developer | `piitier mask corrupt.xlsx` (not a zip) | exit 2; stderr `unsupported or corrupt xlsx: <path>`; stdout empty | integration |
| UC-197 | developer | `piitier mask raport.xlsx -o out.txt` | `out.txt` is the UTF-8 rendered text, first line `# Raport`; no workbook written | integration |
| UC-198 | developer | a detection spanning two adjacent cells (a detector span crossing ` \| `), `-o out.xlsx` | both overlapped cells hold the placeholder; no character of either original value remains | unit |
| UC-199 | developer | `compare raport.xlsx` TUI: uncheck column 1, `Anonimizuj`, `Eksportuj` | one checkbox per column labelled from row 1; column 1 values unchanged in the diff; `raport_anonymised.xlsx` written and masked | unit |
| UC-200 | developer | TUI export twice | second attempt shows `Plik już istnieje`; the first file is not rewritten | unit |
| UC-201 | reader | opens `README.md` | `## Installation` with `### Linux and macOS` and `### Windows (PowerShell)`, winget/uv commands, UTF-8 output guidance, x64-only note | unit |
| UC-202 | developer | fidelity after `-o out.xlsx` | every cell with no detection is identical in value and type to the source cell, including a date right after a formula ending in a digit | unit |

## Open questions

none

## Leak fix additions

This section supersedes the earlier cell-values-only fidelity promise and metadata exclusions.
Workbook output is rebuilt from an allow-list: cell values, fonts, fills, borders, alignments,
number formats, column widths, row heights, merged ranges and freeze panes. Comments (including
authors), hyperlinks, headers/footers, defined names, charts, images and other unsupported objects
are dropped; core document properties are reset to neutral values.

Detection runs over the rendered workbook, including sheet names. Detected sheet names are masked;
if the result exceeds 31 characters or contains `[` or `]`, a neutral unique sheet name replaces it.
Undetected formulas retain their expressions; detected formulas become masked **plain strings**,
even when their masked content starts with `=`. Numeric detections become strings.
Column exclusions protect cell contents, not metadata. Explicitly excluded PII may remain.

`mask_workbook(..., on_leak: Callable[[str], None] | None = None) -> int` returns the number
of formula cells converted to strings. For each conversion, the optional callback receives
`formula: sheet <output_sheet_name>, cell <column_letter><row>`; the source sheet name is never
reported because it may itself be personal data.

| id | action | expected observable result | test |
|----|--------|----------------------------|------|
| UC-203 | mask a formula containing a PESEL | masked plain string; callback and conversion count | unit |
| UC-204 | mask a workbook with comment text and author PII | comments and authors absent | unit |
| UC-205 | mask an email cell with a mailto hyperlink | masked display value; target absent from ZIP | unit |
| UC-206 | mask PII-bearing core properties | creator, lastModifiedBy, title and subject neutral | unit |
| UC-207 | mask a PESEL sheet name | safe neutral name when placeholder is invalid; layout preserved | unit |
| UC-208 | mask workbook headers/footers | all header/footer text absent | unit |
| UC-209 | mask workbook with defined names | workbook and sheet-local names absent | unit |
| UC-210 | mask multiple detected and undetected formulas | only detected formulas converted; exact count | unit |
| UC-211 | mask an integer PESEL | placeholder string | unit |
| UC-212 | mask a floating-point PESEL | placeholder string | unit |
| UC-213 | apply overlapping detections across a cell separator | both cells masked without residual identifier | unit |
| UC-214 | inspect every decompressed output ZIP member | valid ZIP; original synthetic identifier absent everywhere | unit |
| UC-215 | mask 5000 PESEL cells | all cells masked in less than five seconds | performance |
| UC-216 | CLI mask a workbook with multiple detected formulas and a safe formula using `-o out.xlsx` | one warning per converted formula on stderr naming sheet and cell; no PII values; stdout empty and exit 0; safe formula unchanged | integration |
| UC-217 | TUI export workbooks with zero, one or multiple detected formulas | existing export success status includes the exact converted-formula count; detected formulas saved as text and safe formulas retained | unit |
| UC-260 | export sheets when an earlier cell duplicates a later sheet-title line, with and without excluded columns | title ranges recorded during rendering drive masking; source identifier absent from sheet names and every ZIP member except intentionally excluded cell XML | unit |
| UC-261 | export custom formats containing quoted, escaped, text-adjacent or unknown literal text, font names and named-style names containing PII | unsafe formats become `General`; unsafe fonts become Calibri while size/bold/italic/colour remain; identifier absent from every ZIP member | unit |
| UC-262 | export builtin and supported literal-free custom formats and common fonts | supported number formats, font presentation, fills, borders and alignment retained; source protection and named styles not copied | unit |
| UC-263 | load or mask a workbook containing chartsheets but no worksheets, including an existing destination | content-free `unsupported or corrupt xlsx: <path>` ValueError; CLI exit 2 with empty stdout; existing target unchanged | integration |
| UC-264 | supply workbook numbering keyed by original span offsets for a detection crossing two cells | both clipped replacements retain the same assigned index; later detections retain their own indices | unit |
| UC-265 | TUI export after model-backed detection and coreference of repeated/distinct people | exported numbered placeholders match the displayed diff, including repeated entity indices | unit |
| UC-266 | union overlapping numbered detections before cell clipping | the union retains the leading span's original assigned entity index despite its extended end offset | unit |

### Export hardening

Sheet-title ranges are captured in `RenderedWorkbook` while rendering, never recovered by a
text search that could match cell contents. Excluded columns still protect only cell values.
Workbooks with no worksheets are rejected during loading before output creation or truncation.

Style retention is restricted to presentation data. Font names are limited to Calibri, Arial,
Aptos, Cambria, Times New Roman, Courier New, Tahoma and Verdana; other names become Calibri.
Size, bold, italic and colour remain. Number formats retain openpyxl builtins and a restricted
grammar of numeric/date/time/colour tokens or standalone `@` sections; other formats become
`General`. In particular, custom quoted literals, backslash-escaped text, literal text adjacent
to `@` and unknown bracket literals are discarded. Fill, border and alignment fields are
constrained enums/numbers/booleans/colour values. Source protection and named styles are not copied.

`mask_workbook(..., numbering: Mapping[tuple[int, int], int] | None = None)` accepts indices keyed
by original detector offsets in the rendered workbook. Clipping spans into cells preserves those
indices. TUI export passes the same mapping used to render its diff.
