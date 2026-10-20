# Scope report — PII-1-e

> **GAPS** — Some changed files were not declared in the spec scope.

Base: `main`  
Checked: 2026-10-20T13:53:27Z

## File classification

| File | Classification |
|------|----------------|
| `src/piitier/rules/__init__.py` | in scope |
| `src/piitier/rules/id_card.py` | in scope |
| `src/piitier/rules/payment_card.py` | in scope |
| `tests/rules/test_id_card.py` | in scope |
| `tests/rules/test_payment_card.py` | in scope |

## Verdict

Verdict: GAPS

5 in scope · 0 undeclared · 0 out of bounds

## Size

| Measure | This branch | Budget |
|---|---|---|
| Added lines | 871 | 270 +100% (hard ceiling 5000) |
| Files touched | 5 | 5 +100% |
| Modules touched | 2 | 2 +100% |

Modules: src/piitier,tests/rules

Generated output, vendored trees, lock files and the specs directory are
excluded; deleted lines never count against the budget.

### Findings

- over budget: 871 added lines > 540 (270 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)
