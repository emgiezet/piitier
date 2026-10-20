## PII-1-a — Project skeleton, entity taxonomy, and the Label/Span core types
**QA verdict: PASS** · UC coverage: 6/6 automated · Tests: 0 → 27 (26 unit + 1 integration) · Skipped: 0

🤖 Written by an agent from `specs/PII-1-a/spec.md`. Review the spec's `Out:` scope first —
that is where an unattended run is most likely to have overstepped.

### What the spec asked for

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-1 | developer | `uv sync`, then `uv run python -c "import piitier; print(piitier.__version__)"` | prints `0.1.0`; exit 0 | integration |
| UC-2 | maintainer | runs the test suite with `docs/TAXONOMY.md` and `Label` in agreement | the sync test passes; the set of placeholders parsed from the taxonomy table equals the set of `Label` placeholders, 39 entries | unit |
| UC-3 | maintainer | adds a row to the `docs/TAXONOMY.md` table without adding a `Label` member (simulated with a fixture copy of the file) | the sync test fails, and its message names the missing placeholder | unit |
| UC-4 | developer | reads `Label.<member>.placeholder` for every member | equals the taxonomy column verbatim, diacritics included (`Label.MIEJSCOWOSC.placeholder == "[MIEJSCOWOŚĆ]"`); numbered types (`OSOBA`, `IMIE`, `NAZWISKO`, `ADRES`, `LEKARZ`) have `numbered is True` and placeholder `[OSOBA_n]` style; all others `numbered is False` | unit |
| UC-5 | developer | constructs `Span(start=5, end=3, …)`, `Span(start=-1, end=2, …)`, `Span(start=3, end=3, …)` | each raises `ValueError`; the message carries offsets only, never text | unit |
| UC-6 | developer | constructs `Span` with `status` other than `"valid"` or `"suspect"` | raises `ValueError` | unit |

### How to verify

```sh
# unit tests (26)
uv run pytest -q -m "not integration"

# integration test (1)
uv run pytest -q -m integration

# type check
uv run mypy src

# lint / format
uv run ruff check . && uv run ruff format --check .
```

### Review here first

- `src/piitier/labels.py` — 39-member `Label` enum with Polish-diacritic placeholders and `numbered` flags; a wrong placeholder corrupts every downstream detector
- `src/piitier/spans.py` — half-open `[start, end)` offset validation and `status` whitelist (`"valid"` / `"suspect"`); the shared data contract all future slices (PII-1-b through PII-1-f) depend on
- `tests/test_labels.py:test_uc2_taxonomy_label_sync_passes` — the only guard against enum/taxonomy drift; verify the parsing logic matches the actual `docs/TAXONOMY.md` table format

### Not covered

Nothing. All 6 UCs are covered by automated tests and all pass.
