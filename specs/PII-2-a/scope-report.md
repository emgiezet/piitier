# Scope Report — PII-2-a

## Scope Summary
- **In-scope files (7):**
  1. `src/piitier/datagen/__init__.py`
  2. `src/piitier/datagen/template.py`
  3. `src/piitier/datagen/values.py`
  4. `src/piitier/datagen/render.py`
  5. `tests/datagen/__init__.py`
  6. `tests/datagen/test_template.py`
  7. `tests/datagen/test_render.py`
- **Undeclared files:** 0
- **Out of bounds (OOB):** 0 (Context declares all including marker)
- **Native modules (first 2 path segments):** 2 (`src/piitier`, `tests/datagen`)

## Size & Budget Findings
- **Added lines:** 998 added excluding docs.
- **Budget limit:** 350 added lines + 100% tolerance = 700 added lines soft ceiling.
- **Size finding:** `over budget: 998 added lines > 700 (350 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)`
- **Status:** Retained size finding; waived under standing approval.
- **Waiver status:** `Waived: over budget: 998 added lines > 700 (350 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)` under standing approval by @local-user (2026-10-20), conditional on QA/static/all 8 UCs and review zero unwaived findings (`DatagenFinalReview` APPROVED with zero unwaived findings).
