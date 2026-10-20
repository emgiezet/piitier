---
ticket: PII-2-b
title: Person, address and contact generators with a consistent identity per entity
status: approved
stacks: [python]
depends-on: [PII-2-a]
---

# PII-2-b — Person, address and contact generators with a consistent identity per entity

## Problem

The NER model has to learn the entities that regexes cannot catch: names, addresses, contact details
[EVIDENCE: docs/Plan MVP … medtech.md, section 1, "Uzasadnienie wyboru"]. PII-2-a only generates
checksum identifiers, and the plan requires that a PESEL agrees with its owner's birth date and sex
[EVIDENCE: docs/Plan MVP … medtech.md, section 3, step 1].

## Scope

In:
- Generators for `OSOBA`, `IMIE`, `NAZWISKO`, `DATA_URODZENIA`, `ADRES`, `KOD_POCZTOWY`, `MIEJSCOWOSC`,
  `TELEFON` and `EMAIL`, backed by `faker==40.43.0` with locale `pl_PL`, seeded from the document's
  `random.Random`.
- A person record per entity `#k`: sex, first name, surname and birth date. Any of `OSOBA#k`, `IMIE#k`,
  `NAZWISKO#k`, `DATA_URODZENIA#k` and `PESEL#k` in one document describe the same person. `PESEL#k`
  encodes that birth date and sex, and still passes the validator.
- An address record per entity `#k`: `ADRES#k`, `KOD_POCZTOWY#k` and `MIEJSCOWOSC#k` belong together.
- `DATA_URODZENIA` is rendered as `DD.MM.RRRR`.

Out:
- Inflected forms (PII-2-c). Every value here is nominative.
- TERYT-accurate postcode-to-town mapping. Faker's pairs are used as they come.
- `PLEC`, `WIEK` and insurance, finance or medical labels (PII-3).
- Filtering names of public figures (PII-3, hard negatives).
- Any change to `render.py` beyond registering generators, and any change to PII-1 code.

Change budget: 330 added lines, 4 files, 3 modules

## Context

- `src/piitier/datagen/values.py` and `render.py`, from PII-2-a: register the new generators there.
- `src/piitier/rules/pesel.py` (validator), from PII-1-b.
- PESEL layout: `RRMMDD` + serial; digit 10 is even for women and odd for men; the month carries the
  century offset (see PII-1-b Context).
- New: `src/piitier/datagen/people.py`, `tests/datagen/test_people.py`; edit `values.py`, `pyproject.toml`, `uv.lock`.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-9 | data author | `render` of `"{{OSOBA#1}}, PESEL {{PESEL#1}}, ur. {{DATA_URODZENIA#1}}"` over 200 seeds | for every seed, the PESEL's date digits decode to the rendered birth date, and digit 10's parity matches the person's sex | unit |
| UC-10 | data author | `render` of `"{{IMIE#1}} {{NAZWISKO#1}} / {{OSOBA#1}}"` | the `OSOBA#1` value equals the `IMIE#1` value + `" "` + the `NAZWISKO#1` value | unit |
| UC-11 | data author | `render` of `"{{ADRES#1}}, {{KOD_POCZTOWY#1}} {{MIEJSCOWOSC#1}}"` | three spans; the postcode matches `\d{2}-\d{3}`; the `ADRES` span contains a house number | unit |
| UC-12 | data author | `render` of `"tel. {{TELEFON}}"` over 200 seeds, then `piitier.detect` | the phone matches `^(\+48 )?\d{3} \d{3} \d{3}$` or the contiguous 9-digit form; `detect` never reports a `PESEL` or `NIP` inside it *(added)* | integration |
| UC-13 | data author | `render` of `"{{EMAIL}}"` | exactly one `@`, a dot in the domain part, no whitespace | unit |
| UC-14 | data author | `render` of `"{{OSOBA#1}} i {{OSOBA#2}}"` over 200 seeds | `#1` and `#2` never have the same full name *(added)* | unit |

## Open questions

none
