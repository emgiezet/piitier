---
ticket: PII-1-g
title: piitier mask <file>.pdf — text-layer PDF input
status: approved
stacks: [python]
depends-on: PII-1-f
---

# PII-1-g — `piitier mask <file>.pdf`: text-layer PDF input

## Problem

Insurance policies and invoices, two of the inputs the author has scripted by hand, arrive as PDF
[EVIDENCE: session reply, specs/briefs/polish-pii-anonymizer.md]. The CLI from PII-1-f reads only text
formats, so PDFs still need a separate script.

## Scope

In:
- A `.pdf` loader registered in the PII-1-f loader registry. It extracts the text layer page by page,
  joins pages with `\n`, and the output is the masked extracted text.
- Dependency `pypdf==6.21.1` (BSD-3-Clause, compatible with Apache-2.0). This is the current stable
  release and the version prior art already pins (`requirements-pii.txt`). PyMuPDF is excluded
  because it is AGPL.
- Exit code 3 for a PDF with no extractable text on any page. Exit code 2 for an encrypted PDF.

Out:
- OCR of scanned PDFs or images [EVIDENCE: specs/briefs/polish-pii-anonymizer.md, Non-goals].
- XMP metadata, annotations, form fields, attachments embedded in the PDF.
- Writing a masked PDF. Output is text only.
- Any change to `cli.py` beyond what registering the loader requires, and any detector change.

Change budget: 200 added lines, 5 files, 5 modules

## Context

- `src/piitier/loaders.py` (registry) and `src/piitier/cli.py`, from PII-1-f.
- Prior art: `trasti/complaint-classifier/scripts/scan_pii.py` lines 814–818 (page extraction), and
  `tests/test_scan_pii.py::test_encrypted_pdf_is_not_reported_clean` (line 355) and
  `tests/fixtures.py::pdf_bytes` / `scanned_pdf_bytes` (lines 26, 81). Read them for behaviour.
  Do not copy code from that repository.
- New: `tests/test_loaders_pdf.py`, `tests/fixtures/` (synthetic PDFs, or a builder in the test that
  writes them); edit `src/piitier/loaders.py`, `pyproject.toml`, `uv.lock`.

## Acceptance criteria

Fixtures contain the synthetic PESEL `90051512340` only.

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-31 | developer | `piitier mask policy.pdf` (two pages, text layer, PESEL on page 2) | stdout is the masked extracted text of both pages, contains `[PESEL]`, and does not contain `90051512340`; exit 0 | integration |
| UC-32 | developer | `piitier mask scan.pdf` (image only, no text layer) | exit 3; stderr `no text layer: scan.pdf`; stdout empty *(added)* | integration |
| UC-42 | developer | `piitier mask locked.pdf` (encrypted) | exit 2; stderr `encrypted pdf: locked.pdf`; stdout empty *(added from prior art)* | integration |

## Open questions

none
