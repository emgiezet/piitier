# QA Report — PII-2-b

## Verdict: PASS

Every UC has a passing test carrying its id. Full suite: 355 passed (3.19s), zero skipped.
Code Review: `PeopleReview` APPROVED (zero unwaived findings, 2026-10-21). File-budget major finding retracted: 5 native files ≤ 8 (4 + 100% tolerance). House-number test gap fixed and closed.

## UC Coverage Map

| UC | actor | use case | automated test(s) | status |
|----|-------|----------|-------------------|--------|
| UC-9 | data author | `render` of `"{{OSOBA#1}}, PESEL {{PESEL#1}}, ur. {{DATA_URODZENIA#1}}"` over 200 seeds; PESEL date digits decode to DATA_URODZENIA; digit 10 parity matches sex | `test_uc9_pesel_date_matches_data_urodzenia`, `test_uc9_sex_digit_matches_personrecord_sex` | pass |
| UC-10 | data author | `render` of `"{{IMIE#1}} {{NAZWISKO#1}} / {{OSOBA#1}}"` — OSOBA#1 equals IMIE#1 + `" "` + NAZWISKO#1; consistent regardless of placeholder order; two-entity scope | `test_uc10_osoba_equals_imie_space_nazwisko`, `test_uc10_osoba_consistency_when_osoba_first`, `test_uc10_entity_scope_two_people` | pass |
| UC-11 | data author | `render` of `"{{ADRES#1}}, {{KOD_POCZTOWY#1}} {{MIEJSCOWOSC#1}}"` — three spans; postcode matches `\d{2}-\d{3}`; ADRES contains house-number digit; shared record coherence across 200 seeds | `test_uc11_address_fields_and_format`, `test_uc11_address_record_shared_across_labels`, `test_uc11_address_shared_across_seeds` | pass |
| UC-12 | data author | `render` of `"tel. {{TELEFON}}"` over 200 seeds; phone matches accepted shape; `piitier.detect` never reports PESEL or NIP inside it | `test_uc12_telefon_accepted_shapes_and_no_false_detect` (integration) | pass |
| UC-13 | data author | `render` of `"{{EMAIL}}"` — exactly one `@`, dot in domain, no whitespace | `test_uc13_email_syntax` | pass |
| UC-14 | data author | `render` of `"{{OSOBA#1}} i {{OSOBA#2}}"` over 200 seeds — `#1` and `#2` never share the same full name | `test_uc14_two_explicit_people_distinct` | pass |

All UCs present: 6/6 automated. All passing.

## Suite output

**Unit & Integration Tests:**
```
uv run pytest -q: 355 passed (3.19s)
```

- Baseline: 340 tests; feature branch: 355 tests (+15 tests added).
- Ruff format/check, mypy (18 src files) PASS.
- Runtime verification: 200 documents / 2200 spans PASS (exact offset/literal fidelity, PESEL date+validity, names and shared address coherence, phone/email syntax, seeded reproducibility, global RNG unchanged).
- Anonymous entity boundary: person group 4 slots → 4 distinct IDs; address group 3 slots → 3 distinct IDs; anonymous placeholders never collide with explicit entity IDs.
- Verification attribution: parent manual execution (not native harness or CI).

## Additional regression tests (beyond UC scope)

| test | purpose | status |
|------|---------|--------|
| `test_anonymous_person_avoids_explicit_pesel_entity` | anonymous OSOBA does not receive entity `'1'` when PESEL#1 is explicit | pass |
| `test_anonymous_address_avoids_explicit_adres_entity` | anonymous KOD_POCZTOWY does not receive entity `'1'` when ADRES#1 is explicit | pass |
| `test_make_person_raises_on_collision_exhaustion` | `make_person` raises `RuntimeError` after 30 failed unique-name attempts (Faker mocked) | pass |
| `test_no_global_rng_state_leak_from_people_generators` | rendering people/address/contact documents leaves Python global `random.getstate()` unchanged | pass |

## Implementation Scope & Sizing
- Files changed: 6 total; 5 native (excluding `uv.lock`): `pyproject.toml`, `src/piitier/datagen/people.py`, `src/piitier/datagen/render.py`, `src/piitier/datagen/values.py`, `tests/datagen/test_people.py`.
- Native modules (first 2 path segments): 3 (`pyproject.toml`, `src/piitier`, `tests/datagen`).
- Added lines: 782 excluding `uv.lock`.
- Line finding: `over budget: 782 added lines > 660 (330 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)`.
- File finding: retracted — 5 native files ≤ 8 (4 + 100% tolerance); no file waiver required.
- Waiver: `Waived: over budget: 782 added lines > 660 (330 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)` activated under standing approval by @local-user (2026-10-20); all conditional checks satisfied (`PeopleReview` APPROVED, zero unwaived findings).
- Limitations: `faker==40.43.0` (MIT, pinned); per-call `seed_instance()`, no shared global Faker state; all names/addresses are synthetic — no real personal data, no LLM, no inflection; postcode-to-town pairs from Faker's bundled locale data, TERYT-accurate mapping out of scope.
