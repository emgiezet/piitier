FAIL

# Verify — PII-1-a

Base: `main`  
Head: `6c49c8a`  
Checked: 2026-10-20T09:45:44Z

| check | result | detail |
|---|---|---|
| committed | PASS | the working tree is the commit being shipped |
| `uv sync --frozen` | PASS | exit 0 |
| `uv run ruff format --check .` | **FAIL** | exit 1 — see verify.log |
| `uv run ruff check .` | **FAIL** | exit 1 — see verify.log |
| `uv run mypy src` | **FAIL** | exit 1 — see verify.log |
| `uv run pytest -q -m "not integration"` | **FAIL** | exit 1 — see verify.log |
| UC coverage | PASS | 6 UC(s), each named by a changed test |
| tests not weakened | PASS | no test deleted, skipped or focused |
