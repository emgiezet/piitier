## PII-2-b — Person, address and contact generators with a consistent identity per entity

**QA verdict: PASS (355/355 passed, 3.19s)** · **Code Review: `PeopleReview` APPROVED (zero unwaived findings)** · UC coverage: 6/6 automated · Tests: 340 → 355 (+15) · Skipped: 0

### What this PR adds

Person, address, and contact generators that back the `OSOBA`, `IMIE`, `NAZWISKO`, `DATA_URODZENIA`, `ADRES`, `KOD_POCZTOWY`, `MIEJSCOWOSC`, `TELEFON`, and `EMAIL` placeholders.  Each entity `#k` shares one `PersonRecord` (sex, first name, surname, birth date, PESEL) and one `AddressRecord` (street, postcode, town) across all labels in the document.  The generated PESEL is validated by the existing `pisel.is_valid` rule before use; its birth-date digits decode to the rendered `DATA_URODZENIA` (format `DD.MM.RRRR`) and digit 10 parity agrees with the person's sex.

### Verification results

- `uv sync --frozen` — PASS
- `uv run ruff format --check . && uv run ruff check .` — PASS
- `uv run mypy src` (18 src files) — PASS
- `uv run pytest -q` — 355 passed (3.19s), 0 skipped
- Public API: 200 documents / 2200 spans PASS (exact offset/literal fidelity, PESEL date+validity, names and shared address coherence, phone/email syntax, seeded reproducibility, global RNG unchanged).
- Anonymous entity boundary: person group 4 slots → 4 distinct IDs; address group 3 slots → 3 distinct IDs.

### UC evidence summary

| UC | test(s) |
|----|---------|
| UC-9 — PESEL encodes birth date and sex | `test_uc9_pesel_date_matches_data_urodzenia`, `test_uc9_sex_digit_matches_personrecord_sex` |
| UC-10 — OSOBA = IMIE + space + NAZWISKO | `test_uc10_osoba_equals_imie_space_nazwisko`, `test_uc10_osoba_consistency_when_osoba_first`, `test_uc10_entity_scope_two_people` |
| UC-11 — shared address record; postcode format; house number | `test_uc11_address_fields_and_format`, `test_uc11_address_record_shared_across_labels`, `test_uc11_address_shared_across_seeds` |
| UC-12 — TELEFON shape; no false PESEL/NIP detect | `test_uc12_telefon_accepted_shapes_and_no_false_detect` |
| UC-13 — EMAIL syntax | `test_uc13_email_syntax` |
| UC-14 — two explicit people always distinct | `test_uc14_two_explicit_people_distinct` |

### How to verify

```bash
uv sync --frozen
uv run pytest -q                                    # 355 passed
uv run ruff format --check . && uv run ruff check . # no issues
uv run mypy src                                     # no issues
```

### Scope, sizing and constraints

- Native scope: 782 added lines, 5 native files, 3 modules (`pyproject.toml`, `src/piitier`, `tests/datagen`), excluding `uv.lock` (6th changed file, lock-only).
- Profile limit: 330 added lines, 4 files, 3 modules with 100% tolerance, hard ceiling 5000.
- File-budget finding retracted by `PeopleReview`: 5 native files ≤ 8 (4 + 100% tolerance); no file waiver required.
- `Waived: over budget: 782 added lines > 660 (330 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)` — standing approval by @local-user (2026-10-20), activated; `PeopleReview` APPROVED (zero unwaived findings, 2026-10-21).

### Limitations and dependencies

- **Faker 40.43.0 (MIT, pinned):** all names and addresses are Faker-generated synthetic data — no real personal data, no LLM, no scraping of real individuals.  `seed_instance()` is called per-call from the document `random.Random`; there is no shared module-level Faker state and no calls to `Faker.seed()` that would affect the global RNG.
- **Addresses use Faker's bundled locale data:** postcode-to-town pairs are not TERYT-accurate; accurate mapping is out of scope.
- **No inflected forms:** all rendered values are nominative case.  Inflection is deferred to PII-2-c.
- **Not a trained model:** this is a training-data building block only; no NER model, no dataset export.
