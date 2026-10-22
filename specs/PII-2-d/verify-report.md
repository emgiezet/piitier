PASS

# Verify — PII-2-d

Base: `18c6a6b` (ai/pii-1g-2a-integration)  
Head: `207a145`  
Checked: 2026-10-21

| check | result | detail |
|---|---|---|
| committed | PASS | `207a145` is the commit being shipped |
| `uv sync --frozen` | PASS | exit 0 |
| `uv run ruff format --check .` | PASS | exit 0 |
| `uv run ruff check .` | PASS | exit 0 |
| `uv run mypy src` | PASS | exit 0 (19 source files) |
| `uv run pytest -q` | PASS | 362 passed, 0 skipped (3.39 s) |
| UC coverage | PASS | 8 UC(s), each named by a test in `tests/datagen/test_build.py` |
| tests not weakened | PASS | no test deleted, skipped or focused |
| code review | APPROVED | DatasetReview: CRLF delta correct; read_bytes decode confirmed; regression proves exact prefix/suffix; zero new/unwaived findings |
