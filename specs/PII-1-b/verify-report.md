FAIL

# Verify — PII-1-b

Base: `main`  
Head: `6743887`  
Checked: 2026-10-20T09:31:33Z

| check | result | detail |
|---|---|---|
| committed | PASS | the working tree is the commit being shipped |
| `uv sync --frozen` | **FAIL** | exit 2 — see verify.log |
| `uv run ruff format --check .` | PASS | exit 0 |
| `uv run ruff check .` | PASS | exit 0 |
| `uv run mypy src` | **FAIL** | exit 1 — see verify.log |
| `uv run pytest -q -m "not integration"` | **FAIL** | exit 1 — see verify.log |
| UC coverage | **FAIL** | no changed test names UC-10, UC-11, UC-12, UC-13, UC-36, UC-37, UC-7, UC-8, UC-9 |
| tests not weakened | PASS | no test deleted, skipped or focused |
