# Scope Report — Combined PII-1-g + PII-2-a

## Scope Summary
- **In-scope files (11 excluding specs and lock):**
  - PII-1-g (5): `src/piitier/cli.py`, `src/piitier/loaders.py`, `tests/test_loaders_pdf.py`, `pyproject.toml`, `uv.lock`
  - PII-2-a (6 code/test): `src/piitier/datagen/__init__.py`, `src/piitier/datagen/template.py`, `src/piitier/datagen/values.py`, `src/piitier/datagen/render.py`, `tests/datagen/__init__.py`, `tests/datagen/test_template.py`, `tests/datagen/test_render.py` (total 11 files across 4 native modules: `src/piitier`, `tests`, etc.).
- **Undeclared files:** 0
- **Out of bounds (OOB):** 0
- **Native modules (first 2 path segments):** 4 modules excluding specs and `uv.lock`.

## Size & Budget Findings (Combined PR)
- **Added lines:** 1288 added excluding docs and lock.
- **Budget limit:** 400 added lines + 100% tolerance = 800 added lines soft ceiling.
- **Combined Size Finding:** `over budget: 1288 added lines > 800 (400 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)`
- **Component Size Finding (PII-2-a):** `over budget: 998 added lines > 700 (350 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)`
- **Waiver Status:** 
  - `Waived: over budget: 1288 added lines > 800 (400 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)` under standing approval by @local-user (2026-10-20), conditional on all 11 UCs covered, all gates PASS, and zero unwaived findings.
  - `Waived: over budget: 998 added lines > 700 (350 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)` under standing approval by @local-user (2026-10-20).
