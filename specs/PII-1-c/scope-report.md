# Scope report — PII-1-c

> **GAPS** — Some changed files were not declared in the spec scope.

Base: `main`  
Checked: 2026-10-20T13:23:32Z

## File classification

| File | Classification |
|------|----------------|
| `src/piitier/rules/__init__.py` | in scope |
| `src/piitier/rules/nip.py` | in scope |
| `src/piitier/rules/regon.py` | in scope |
| `tests/rules/test_nip.py` | in scope |
| `tests/rules/test_regon.py` | in scope |
| `tests/test_api.py` | **undeclared** |

## Verdict

Verdict: GAPS

5 in scope · 1 undeclared · 0 out of bounds

## Size

| Measure | This branch | Budget |
|---|---|---|
| Added lines | 915 | 330 +100% (hard ceiling 5000) |
| Files touched | 6 | 5 +100% |
| Modules touched | 3 | 2 +100% |

Modules: src/piitier,tests/rules,tests/test_api.py

Generated output, vendored trees, lock files and the specs directory are
excluded; deleted lines never count against the budget.

### Findings

- over budget: 915 added lines > 660 (330 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)
