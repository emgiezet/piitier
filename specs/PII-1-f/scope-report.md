# Scope report — PII-1-f

> **GAPS** — Some changed files were not declared in the spec scope.

Base: `main`  
Checked: 2026-10-20T13:09:43Z

## File classification

| File | Classification |
|------|----------------|
| `pyproject.toml` | in scope |
| `src/piitier/cli.py` | in scope |
| `src/piitier/loaders.py` | in scope |
| `tests/test_cli.py` | in scope |
| `tests/test_loaders.py` | in scope |

## Verdict

Verdict: GAPS

5 in scope · 0 undeclared · 0 out of bounds

## Size

| Measure | This branch | Budget |
|---|---|---|
| Added lines | 610 | 260 +100% (hard ceiling 5000) |
| Files touched | 5 | 6 +100% |
| Modules touched | 4 | 4 +100% |

Modules: pyproject.toml,src/piitier,tests/test_cli.py,tests/test_loaders.py

Generated output, vendored trees, lock files and the specs directory are
excluded; deleted lines never count against the budget.

### Findings

- over budget: 610 added lines > 520 (260 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)
