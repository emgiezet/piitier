## PR: PII-3 — Finance & Medical Generators, Augmentation & Hard Negatives

**QA verdict: PASS (491/491 passed)** · **Code Review: Approved after addressing all review findings in commit `5c37ab2`** · UC coverage: 38/38 automated (UC-38..UC-66) · Tests: 463 → 491 (+28 tests) · Skipped: 0

### Executive Summary & Integration Scope
This PR merges the complete PII-3 batch of the synthetic data generation pipeline:
1. **PII-3-a**: Finance and insurance identifier generators (`NR_UMOWY`, `NR_POLISY`, `NR_SZKODY`, `NR_REJESTRACYJNY`, `VIN`, `NR_KW`), validation, templates, and LLM prompt integration (UC-38..UC-45).
2. **PII-3-b**: Medical identifier and Article 9 RODO data generators (`ICD10`, `LEK`, `ROZPOZNANIE`, `PLACOWKA`, `LEKARZ`, `NPWZ`), inflection, templates, and prompt list expansion to 27 labels (UC-46..UC-53).
3. **PII-3-c**: Augmentation module (`augment.py`) implementing diacritic stripping, OCR confusions (0/O, 1/l), digit spacing, and uppercase transform with precise offset recalculation (UC-54..UC-59).
4. **PII-3-d**: Hard negatives module (`hard_negatives.py`), CLI flags `--augment` and `--hard-negatives N`, dataset card (`docs/DATASET_CARD.md`), and full 20k-doc corpus build verification (UC-60..UC-66).

### Stacking & Base
- **Base branch:** `main`
- **Feature branch:** `ai/pii-3-integration`

### Observed Test & Verification Results
- `uv run ruff format --check . && uv run ruff check .` — PASS (131 files)
- `uv run mypy src` (24 src files) — PASS
- `uv run pytest -q` — 491 passed, 0 skipped (~41s).
- Full integration run (20k docs, seed 42, augment, hard negatives 2000): byte-identical reproducibility across independent runs, check returned 0, train split 20 252 / dev split 1 748, sha256 checksums verified.
- Code review: Independent reviewer findings (#2-#10 + nits) resolved in commit `5c37ab2`. Finding #1 (dataset card stats) refuted with evidence (`sha256(template_id) % 10` split, hard negatives span addition, recount matching manifest).

### Usage Example
```bash
uv run python -m piitier.datagen build --templates src/piitier/datagen/templates --n 20000 --seed 42 --augment --hard-negatives 2000 --out data/synthetic/v0.1/
uv run python -m piitier.datagen check data/synthetic/v0.1/
```

### Scope & Sizing Table
- **Native scope (excluding specs and `uv.lock`):** 1757 added lines, 28 files, 3 modules (`docs`, `src/piitier`, `tests/datagen`). Profile limit: 400 added lines, 15 files, 3 modules with 100% tolerance, hard ceiling 5000.
- **Exact Waiver Line:** 
  `Waived: over budget: 1757 added lines > 800 (400 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)` under standing approval by @local-user (2026-10-20), conditional on all UCs covered, all gates PASS, and zero unwaived findings.

### Links to Specs and Reports
- **PII-3-a:**
  - [Spec](https://github.com/emgiezet/piitier/blob/ai/pii-3-integration/specs/PII-3-a/spec.md)
  - [QA Report](https://github.com/emgiezet/piitier/blob/ai/pii-3-integration/specs/PII-3-a/qa-report.md)
  - [Verify Report](https://github.com/emgiezet/piitier/blob/ai/pii-3-integration/specs/PII-3-a/verify-report.md)
- **PII-3-b:**
  - [Spec](https://github.com/emgiezet/piitier/blob/ai/pii-3-integration/specs/PII-3-b/spec.md)
  - [QA Report](https://github.com/emgiezet/piitier/blob/ai/pii-3-integration/specs/PII-3-b/qa-report.md)
  - [Verify Report](https://github.com/emgiezet/piitier/blob/ai/pii-3-integration/specs/PII-3-b/verify-report.md)
- **PII-3-c:**
  - [Spec](https://github.com/emgiezet/piitier/blob/ai/pii-3-integration/specs/PII-3-c/spec.md)
  - [QA Report](https://github.com/emgiezet/piitier/blob/ai/pii-3-integration/specs/PII-3-c/qa-report.md)
  - [Verify Report](https://github.com/emgiezet/piitier/blob/ai/pii-3-integration/specs/PII-3-c/verify-report.md)
- **PII-3-d:**
  - [Spec](https://github.com/emgiezet/piitier/blob/ai/pii-3-integration/specs/PII-3-d/spec.md)
  - [QA Report](https://github.com/emgiezet/piitier/blob/ai/pii-3-integration/specs/PII-3-d/qa-report.md)
  - [Verify Report](https://github.com/emgiezet/piitier/blob/ai/pii-3-integration/specs/PII-3-d/verify-report.md)
- **Combined Scope Report:**
  - [Scope Report](https://github.com/emgiezet/piitier/blob/ai/pii-3-integration/specs/PII-3/scope-report.md)
