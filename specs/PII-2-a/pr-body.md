## Combined PR: PII-1-g + PII-2-a — PDF Text Input & Synthetic Document Rendering
**QA verdict: PASS (340/340 passed)** · **Code Review: Both component independent reviews APPROVED (zero unwaived findings)** · UC coverage: 11/11 automated · Tests: 295 → 340 · Skipped: 0

### Executive Summary & Integration Scope
This PR merges two completed feature tracks:
1. **PII-1-g**: `piitier mask <file>.pdf` text-layer PDF input (3/3 UCs, 4 new integration tests).
2. **PII-2-a**: Render a labelled synthetic document from a placeholder template (8/8 UCs, datagen module & tests).

**Important Note:** This is a training-data building block, not a trained LLM; no OCR/dataset export yet.

### Observed Merged Test & Verification Results
- `uv sync --frozen` — PASS
- `uv run ruff format --check . && uv run ruff check .` — PASS
- `uv run mypy src` (17 src files) — PASS
- `uv run pytest -q` — 340 passed (2.99s), 0 skipped.
- Actual installed CLI 4 PDF scenarios PASS; public API 100 docs / 700 spans PASS; existing 27 API examples + TXT/MD/CSV UTF8/cp1250/BOM/CRLF/output-protection/error smoke PASS.
- Both component independent reviews APPROVED with zero unwaived findings.
- Native combined scope: 1288 added lines, 11 files, 4 modules (excluding specs and `uv.lock`). Profile limit: 400 added lines, 15 files, 3 modules with 100% tolerance, hard ceiling 5000.

### Individual Feature Evidence

#### PII-1-g (`piitier mask <file>.pdf`)
- **UC-31**: Two-page text-layer PDF masking (exit 0, exact masked stdout).
- **UC-32**: Image-only PDF rejection (exit 3, exact stderr `no text layer: <path>`).
- **UC-42**: Encrypted PDF rejection (exit 2, exact stderr `encrypted pdf: <path>`).

#### PII-2-a (`render()` synthetic documents)
- **UC-1 to UC-3**: PESEL rendering & validation, seed reproducibility, numbered entity `#1`/`#2` caching.
- **UC-4**: All 6 labels (PESEL, NIP, REGON, IBAN, NR_DOWODU, NR_KARTY) detectable across 50 seeds with detectors.
- **UC-5 to UC-7**: `TemplateError` contracts for unknown labels, missing generators, and malformed syntax.
- **UC-8**: Hypothesis property tests for offset integrity, non-overlapping spans, and literal preservation.

### How to Verify
```bash
uv sync --frozen
uv run pytest -q                                    # 340 passed (2.99s)
uv run ruff format --check . && uv run ruff check . # no lint issues
uv run mypy src                                     # no type issues
```

### Scope, Sizing & Constraints
- Native combined scope: 1288 added lines, 11 files, 4 modules (excluding specs and `uv.lock`). Profile 400/15/3 with 100% tolerance, hard ceiling 5000.
- `Waived: over budget: 1288 added lines > 800 (400 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)` activated under standing approval by @local-user (2026-10-20), all 11 UCs covered and all gates PASS, zero unwaived findings.
- `Waived: over budget: 998 added lines > 700 (350 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)` activated under standing approval by @local-user (2026-10-20).
- Limitations: training-data building block, not a trained LLM; no OCR/dataset export, person, or inflection yet.
