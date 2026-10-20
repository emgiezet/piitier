# QA Report — PII-1-g

## Verdict: PASS

Every UC has a passing test carrying its id. Full suite: 299 passed (2.07s), zero skipped.
Code Review: PdfReview APPROVED (zero findings).

## UC Coverage Map

| UC | actor | use case | automated test | status |
|----|-------|----------|---|---|
| UC-31 | developer | `piitier mask policy.pdf` (two pages, text layer, PESEL on page 2) | `test_uc31_two_page_text_pdf_exact_masked_stdout` | ✓ |
| UC-32 | developer | `piitier mask scan.pdf` (image only, no text layer) | `test_uc32_image_only_pdf_exit3_exact_stderr`, `test_uc32_boundary_image_page_then_text_page_exact_stdout` | ✓ |
| UC-42 | developer | `piitier mask locked.pdf` (encrypted) | `test_uc42_encrypted_pdf_exit2_exact_stderr` | ✓ |

All UCs present: 3/3 automated. All passing.

## Suite output

**Unit & Integration Tests:**
```
uv run pytest -q: 299 passed (2.07s)
```

- Baseline: 295 tests; feature branch: 299 tests.
- Skipped: 0.
- Ruff format/check, mypy PASS.

**Installed Console Actual 4 Cases PASS:**
1. Text-2-page PDF: exact spaces/join/masking, exit 0
2. Image + text page: preserves leading newline, exit 0
3. Real image-only PDF: exit 3, exact safe error (`no text layer: <path>`)
4. Encrypted PDF: exit 2, exact safe error (`encrypted pdf: <path>`)

## Implementation Scope & Sizing
- Files changed: 5 (`pyproject.toml`, `uv.lock`, `src/piitier/cli.py`, `src/piitier/loaders.py`, `tests/test_loaders_pdf.py`).
- Added lines: pyproject 3, cli 8, loaders 38, test 241, lock 13 => 303 including lock / 290 excluding lock. Well under the 400 soft limit.
- Text-layer PDF only (via `pypdf==6.21.1`, BSD-3-Clause license).
- Output is text only, not PDF; no OCR.
- Current behavior preserves page whitespace and empty page separators, and rejects encrypted PDF before extraction.
