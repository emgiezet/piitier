# Scope report — PII-1-a

> **GAPS** — Some changed files were not declared in the spec scope.

Base: `main`  
Checked: 2026-10-20T10:11:41Z

## File classification

| File | Classification |
|------|----------------|
| `docs/TAXONOMY.md` | in scope |
| `pyproject.toml` | in scope |
| `src/piitier/__init__.py` | in scope |
| `src/piitier/labels.py` | in scope |
| `src/piitier/py.typed` | in scope |
| `src/piitier/spans.py` | in scope |
| `tests/test_labels.py` | in scope |
| `tests/test_spans.py` | in scope |
| `uv.lock` | in scope |
| `specs/PII-1-a/qa-report.md` | **undeclared** |
| `tests/__init__.py` | **undeclared** |

## Verdict

Verdict: GAPS

9 in scope · 2 undeclared · 0 out of bounds

## Size

| Measure | This branch | Budget |
|---|---|---|
| Added lines | 655 | 610 (hard ceiling 3000) |
| Files touched | 9 | 10 |
| Modules touched | 6 | 7 |

Modules: docs/TAXONOMY.md,pyproject.toml,src/piitier,tests/__init__.py,tests/test_labels.py,tests/test_spans.py

Generated output, vendored trees, lock files and the specs directory are
excluded; deleted lines never count against the budget.

### Findings

- over budget: 655 added lines > 610. One spec is one PR: split it (spec-authoring, Sizing)
