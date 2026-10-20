# Scope report — PII-1-b

> **GAPS** — Some changed files were not declared in the spec scope.

Base: `main`  
Checked: 2026-10-20T11:59:59Z

## File classification

| File | Classification |
|------|----------------|
| `src/piitier/__init__.py` | in scope |
| `src/piitier/render.py` | in scope |
| `src/piitier/rules/__init__.py` | in scope |
| `src/piitier/rules/pesel.py` | in scope |
| `tests/rules/test_pesel.py` | in scope |
| `tests/test_api.py` | in scope |
| `tests/test_render.py` | in scope |

## Verdict

Verdict: GAPS

7 in scope · 0 undeclared · 0 out of bounds

## Size

| Measure | This branch | Budget |
|---|---|---|
| Added lines | 1135 | 360 +100% (hard ceiling 5000) |
| Files touched | 7 | 7 +100% |
| Modules touched | 4 | 4 +100% |

Modules: src/piitier,tests/rules,tests/test_api.py,tests/test_render.py

Generated output, vendored trees, lock files and the specs directory are
excluded; deleted lines never count against the budget.

### Findings

- over budget: 1135 added lines > 720 (360 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)
