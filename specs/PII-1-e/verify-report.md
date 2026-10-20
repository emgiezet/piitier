PASS

# Verify — PII-1-e

Base: `main`  
Head: `a8d6436`  
Checked: 2026-10-20T13:53:34Z

| check | result | detail |
|---|---|---|
| committed | PASS | the working tree is the commit being shipped |
| `uv sync --frozen` | PASS | exit 0 |
| `uv run ruff format --check .` | PASS | exit 0 |
| `uv run ruff check .` | PASS | exit 0 |
| `uv run mypy src` | PASS | exit 0 |
| `uv run pytest -q -m "not integration"` | PASS | exit 0 |
| UC coverage | PASS | 6 UC(s), each named by a changed test |
| tests not weakened | PASS | no test deleted, skipped or focused |
