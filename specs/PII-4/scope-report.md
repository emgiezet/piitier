GAPS
# Scope Report — PII-4 Batch

## Scope Summary
- **In-scope files (excluding specs and lock):** 37 files across 19 modules (`bench/`, `docs/TAXONOMY.md`, `eval/`, `pyproject.toml`, `src/piitier/ner`, `tests/`, `training/`).
- **Undeclared files:** 0
- **Out of bounds (OOB):** 0

## Size & Budget Findings
- **Added lines:** 4440 added lines excluding docs and lock.
- **Budget limit:** 400 added lines + 100% tolerance = 800 added lines soft ceiling.
- **Combined Size Finding:** `over budget: 4440 added lines > 800 (400 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)`
- **Waiver Status:**
  - `Waived: over budget: 4440 added lines > 800 (400 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)` under standing approval by @local-user (2026-10-20), conditional on batch total ≤ 5000 hard ceiling passing (4440 < 5000), all 26 UCs green, all review findings fixed.
