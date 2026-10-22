GAPS

# Scope Report — PII-2-e (Combined PII-2-c + PII-2-e)

## Scope Summary
- **Combined In-scope files (20 native files total, excluding specs and `uv.lock`):**
  - C component (8 files): `pyproject.toml`, `src/piitier/datagen/inflect.py`, `src/piitier/datagen/template.py`, `src/piitier/datagen/render.py`, `src/piitier/datagen/build.py`, `tests/datagen/test_inflect.py`, `tests/datagen/test_template.py`, `tests/datagen/test_build.py`
  - E component (12 files): `src/piitier/datagen/llm.py`, `src/piitier/datagen/__main__.py`, 8 prompt template files under `src/piitier/datagen/prompts/`, `tests/datagen/test_llm.py`, `tests/datagen/test_llm_ollama.py` (no original packaged templates or generators changed).
- **Undeclared files:** 0
- **Out of bounds (OOB):** 0
- **Native modules (first 2 path segments):** 3 (`pyproject.toml`, `src/piitier`, `tests/datagen`), excluding `uv.lock`.

## Size & Budget Findings

| Measure | This PR (Combined) | Budget (with 100% tolerance) | Hard Ceiling |
|---|---|---|---|
| Added lines | 2432 | 800 (400 + 100%) | 5000 |
| Files touched | 20 | 30 (15 + 100%) | - |
| Modules touched | 3 | 6 (3 + 100%) | - |

Component breakdown:
- **PII-2-c:** 621 added lines / 8 files / 3 modules (Budget: 560 lines / 8 files / 6 modules)
- **PII-2-e:** 1811 added lines / 12 files / 2 modules (Budget: 760 lines / 14 files / 6 modules)

## GAPS

Verdict: GAPS

Exact findings:
over budget: 621 added lines > 560 (280 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)
over budget: 1811 added lines > 760 (380 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)
over budget: 2432 added lines > 800 (400 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)

Waivers activated under standing owner approval by @local-user (2026-10-20), conditional on total added lines ≤ 5000 (actual 2432), all UCs green, zero other unwaived findings, and both reviews APPROVED.
