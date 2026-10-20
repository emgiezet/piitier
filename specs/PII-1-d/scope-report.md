# Scope report — PII-1-d

> **GAPS** — Some changed files were not declared in the spec scope.

Base: `main`  
Checked: 2026-10-20T13:21:06Z

## File classification

| File | Classification |
|------|----------------|
| `src/piitier/rules/__init__.py` | in scope |
| `src/piitier/rules/iban.py` | in scope |
| `tests/rules/test_iban.py` | in scope |

## Verdict

Verdict: GAPS

3 in scope · 0 undeclared · 0 out of bounds

## Size

| Measure | This branch | Budget |
|---|---|---|
| Added lines | 546 | 240 +100% (hard ceiling 5000) |
| Files touched | 3 | 3 +100% |
| Modules touched | 2 | 2 +100% |

Modules: src/piitier,tests/rules

Generated output, vendored trees, lock files and the specs directory are
excluded; deleted lines never count against the budget.

### Findings

- over budget: 546 added lines > 480 (240 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)
