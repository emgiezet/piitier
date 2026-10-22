# Scope Report — PII-2-b

## Scope Summary
- **In-scope files (5 native, 6 total — excluding specs; `uv.lock` is the 6th changed file):**
  - `pyproject.toml` (added `faker==40.43.0` runtime dependency)
  - `src/piitier/datagen/people.py` (new: PersonRecord, AddressRecord, make_person, make_address, generate_telefon, generate_email)
  - `src/piitier/datagen/render.py` (edited: person-group and address-group routing, anonymous entity allocation)
  - `src/piitier/datagen/values.py` (edited: TELEFON/EMAIL generator registration)
  - `tests/datagen/test_people.py` (new: 15 acceptance + regression tests)
- **Undeclared files:** 0
- **Out of bounds (OOB):** 0
- **Native modules (first 2 path segments):** 3 (`pyproject.toml`, `src/piitier`, `tests/datagen`), excluding `uv.lock`.

## Size & Budget Findings

- **Added lines:** 782 excluding `uv.lock`.
- **Budget limit:** 330 added lines + 100% tolerance = 660 added lines soft ceiling.
- **Files budget:** spec declared 4 native files; 5 native files changed (≤ 8 with 100% tolerance) — **file-budget finding retracted by `PeopleReview`; no file waiver required**.

## GAPS

Native finding (exact):
`over budget: 782 added lines > 660 (330 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)`

- The spec declared 330 added lines / 4 files / 3 modules; actual outcome is 782 added / 5 native files / 3 modules (6 files total including `uv.lock`).
- The excess is concentrated in `tests/datagen/test_people.py` (427+ lines after UC-11 house-number gap fix) and `src/piitier/datagen/render.py` (+76 lines for person/address group routing).
- Module count (3) is within spec. Hard ceiling (5000) is not breached. File count (5 native) ≤ 8 (4 + 100% tolerance) — retracted.
- Waiver: `Waived: over budget: 782 added lines > 660 (330 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)` activated under standing approval by @local-user (2026-10-20); `PeopleReview` APPROVED (zero unwaived findings, 2026-10-21).
