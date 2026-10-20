FAIL

# Verify — PII-1-f

Base: `main`  
Head: `8e22688`  
Checked: 2026-10-20T13:40:59Z

| check | result | detail |
|---|---|---|
| committed | **FAIL** | uncommitted: smoke_bin.txt smoke_cp1250.csv smoke_in.csv smoke_in.docx smoke_in.md smoke_in.txt smoke_invalid.txt smoke_out.txt|
| `uv sync --frozen` | PASS | exit 0 |
| `uv run ruff format --check .` | PASS | exit 0 |
| `uv run ruff check .` | PASS | exit 0 |
| `uv run mypy src` | PASS | exit 0 |
| `uv run pytest -q -m "not integration"` | PASS | exit 0 |
| UC coverage | PASS | 8 UC(s), each named by a changed test |
| tests not weakened | PASS | no test deleted, skipped or focused |
