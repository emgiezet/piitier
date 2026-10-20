FAIL

# Verify — PII-1-e

Base: `main`  
Head: `3f6121e`  
Checked: 2026-10-20T13:29:06Z

| check | result | detail |
|---|---|---|
| committed | PASS | the working tree is the commit being shipped |
| `uv sync --frozen` | PASS | exit 0 |
| `uv run ruff format --check .` | **FAIL** | exit 1 — see verify.log |
| `uv run ruff check .` | **FAIL** | exit 1 — see verify.log |
| `uv run mypy src` | PASS | exit 0 |
| `uv run pytest -q -m "not integration"` | PASS | exit 0 |
| UC coverage | PASS | 6 UC(s), each named by a changed test |
| tests not weakened | PASS | no test deleted, skipped or focused |
