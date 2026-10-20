## PII-1-g — `piitier mask <file>.pdf`: text-layer PDF input
**QA verdict: PASS** · **Code Review: PdfReview APPROVED (zero findings)** · UC coverage: 3/3 automated · Tests: 295 → 299 · Skipped: 0

### What the spec asked for

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-31 | developer | `piitier mask policy.pdf` (two pages, text layer, PESEL on page 2) | stdout is the masked extracted text of both pages, contains `[PESEL]`, and does not contain `90051512340`; exit 0 | integration |
| UC-32 | developer | `piitier mask scan.pdf` (image only, no text layer) | exit 3; stderr `no text layer: scan.pdf`; stdout empty *(added)* | integration |
| UC-42 | developer | `piitier mask locked.pdf` (encrypted) | exit 2; stderr `encrypted pdf: locked.pdf`; stdout empty *(added from prior art)* | integration |

### How to verify
```bash
uv run pytest -q                                    # 299 passed (2.07s)
uv run ruff format --check . && uv run ruff check . # no lint issues
uv run mypy src                                     # no type issues
```

Installed console 4 cases verified:
1. Text-2-page PDF: exact spaces/join/masking, exit 0
2. Image + text page: preserves leading newline, exit 0
3. Real image-only PDF: exit 3, exact safe error (`no text layer: <path>`)
4. Encrypted PDF: exit 2, exact safe error (`encrypted pdf: <path>`)

### Review here first
- `src/piitier/loaders.py`: PDF loader integration using `pypdf==6.21.1` (BSD license).
- `src/piitier/cli.py`: PDF handling and loader registration.
- `tests/test_loaders_pdf.py`: 
  - `test_uc31_two_page_text_pdf_exact_masked_stdout`
  - `test_uc32_image_only_pdf_exit3_exact_stderr`
  - `test_uc32_boundary_image_page_then_text_page_exact_stdout`
  - `test_uc42_encrypted_pdf_exit2_exact_stderr`

### Scope, Sizing & Constraints
- Sizing: 5 files changed (`pyproject.toml`, `uv.lock`, `src/piitier/cli.py`, `src/piitier/loaders.py`, `tests/test_loaders_pdf.py`). Added lines: pyproject 3, cli 8, loaders 38, test 241, lock 13 => 303 including lock / 290 excluding lock. Under 400 soft limit.
- Text-layer PDF only; output text not PDF; no OCR.
- Preserves page whitespace/empty page separators and rejects encrypted PDF before extraction.
