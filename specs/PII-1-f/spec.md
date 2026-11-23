---
ticket: PII-1-f
title: piitier mask <file> — CLI for TXT, Markdown and CSV
status: approved
stacks: [python]
depends-on: PII-1-b
---

# PII-1-f — `piitier mask <file>`: CLI for TXT, Markdown and CSV

## Problem

The author has written a separate anonymisation script five times: for CSV, plain text,
insurance policies, invoices, PDF and markdown [EVIDENCE: session reply, specs/briefs/polish-pii-anonymizer.md].
Success criterion #1 is that a sixth script is never needed [EVIDENCE: session reply — answer "a"].
The library can mask a string, but there is no command that takes a file.

## Scope

In:
- A `piitier` console script (`[project.scripts]` in `pyproject.toml`) with the subcommand
  `piitier mask <path> [-o <out>]`.
- `.txt`, `.md` and `.csv` are read as text and masked as one string, so structure (Markdown syntax,
  delimiters, quoting, line endings) survives byte for byte.
- Decoding is UTF-8 first (BOM tolerated), then `cp1250`; if both fail, exit 2. Output is always
  UTF-8. A NUL byte in the first 4096 bytes means the file is binary: exit 2. Both rules are carried
  over from an earlier private script `scan_pii.py` (lines 1058–1065 and 460).
- Exit codes: 0 success, 2 usage or input error.
- A loader registry keyed by extension, so PII-1-g adds `.pdf` without touching `cli.py`.

Out:
- PDF, which is PII-1-g. Until then `.pdf` is an unsupported file type (UC-34).
- OCR, `.docx`, `.xlsx`, `.msg`, `.eml`, HTML, ZIP archives, and images.
- Directory or batch mode, `--mode pseudonymize`, and JSON span output.
- Per-column CSV rules. The CSV is masked as text.
- Any detector change (PII-1-b…e), and any change to `piitier.mask()`.
- Packaging for PyPI, Docker, or the gateway.

Change budget: 260 added lines, 6 files, 4 modules

## Context

- `src/piitier/__init__.py`: `mask()` from PII-1-b.
- `.claude/rules/python.md`: never log document text; error messages carry paths only.
- Prior art: `scan_pii.py` lines cited under Scope, and
  `tests/test_scan_pii.py::test_text_and_csv_are_scanned_but_office_stays_unsupported` (line 524).
  Read them for behaviour. Do not copy code from that repository.
- New: `src/piitier/cli.py`, `src/piitier/loaders.py`, `tests/test_cli.py`, `tests/test_loaders.py`;
  edit `pyproject.toml`.

## Acceptance criteria

Fixtures are written by the tests themselves and contain the synthetic PESEL `90051512340` only.

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-28 | developer | `piitier mask in.txt` | stdout is `piitier.mask(<file text>)` exactly; exit 0 | integration |
| UC-29 | developer | `piitier mask in.md` containing headings, a table and a code block | Markdown markup unchanged byte for byte; only the PESEL replaced; exit 0 | integration |
| UC-30 | developer | `piitier mask in.csv` with `;` delimiter, quoted fields and CRLF line endings | same row count, delimiter, quoting and CRLF; the PESEL cell becomes `[PESEL]`; exit 0 | integration |
| UC-33 | developer | `piitier mask in.txt -o out.txt` | `out.txt` holds the masked text; stdout empty; exit 0. With `-o in.txt`: exit 2, stderr `refusing to overwrite input: in.txt`, the input file unchanged *(added)* | integration |
| UC-34 | developer | `piitier mask in.docx`; `piitier mask missing.txt` | exit 2; stderr `unsupported file type: .docx` / `not found: missing.txt`; stdout empty *(added)* | integration |
| UC-35 | developer | `piitier mask` on a `.txt` holding `90051512340` followed by bytes `0x81 0x98` (invalid UTF-8, undefined in cp1250) | exit 2; stderr `cannot decode: <path>`; stdout empty; `90051512340` absent from stderr *(added)* | integration |
| UC-40 | developer | `piitier mask` on a cp1250-encoded `.csv` containing `Łódź;90051512340` | stdout is UTF-8 `Łódź;[PESEL]`; exit 0 *(added from prior art)* | integration |
| UC-41 | developer | `piitier mask` on a `.txt` with a NUL byte in its first 4096 bytes | exit 2; stderr `binary content: <path>`; stdout empty *(added from prior art)* | integration |

UC-31 and UC-32 moved to PII-1-g together with PDF support. Their ids are unchanged.

## Non-functional

- `\n` vs `\r\n` is preserved as read.

## Open questions

none
