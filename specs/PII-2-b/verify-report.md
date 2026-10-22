PASS
## Verification Summary (Parent Manual Execution — 2026-10-21)

- **Test Suite:** `uv run pytest -q` — 355 passed (3.19s), 0 skipped (baseline 340 tests + 15 added).
- **Static Analysis & Formatting:**
  - `uv run ruff format --check . && uv run ruff check .` — PASS
  - `uv run mypy src` (18 src files) — PASS
- **Runtime Verification:** 200 documents / 2200 spans verified (exact offset/literal fidelity, PESEL date+validity, names and shared address coherence, phone/email syntax, seeded reproducibility, global RNG unchanged).
- **Anonymous entity boundary:** person group 4 slots → 4 distinct IDs; address group 3 slots → 3 distinct IDs; anonymous placeholders never collide with explicit entity IDs.
- **Code Review:** `PeopleReview` APPROVED (zero unwaived findings, 2026-10-21). File-budget major finding retracted: 5 native files ≤ 8 (4 + 100% tolerance). House-number test gap fixed and closed.
- **Size & Budget Waiver:** Added lines (782) exceed soft limit (660). Line waiver activated under standing approval by @local-user (2026-10-20): `Waived: over budget: 782 added lines > 660 (330 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)`. File-budget finding retracted — no file waiver required.
- **Scope:** 6 files changed total; 5 native files (excluding `uv.lock`): `pyproject.toml`, `src/piitier/datagen/people.py`, `src/piitier/datagen/render.py`, `src/piitier/datagen/values.py`, `tests/datagen/test_people.py`.
- **Attribution:** All verification commands executed via parent manual execution (not native harness or CI).
