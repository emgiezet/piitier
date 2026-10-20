---
ticket: PII-2-c
title: Inflect names into the grammatical case the template asks for (Morfeusz 2)
status: approved
stacks: [python]
depends-on: [PII-2-b]
---

# PII-2-c — Inflect names into the grammatical case the template asks for (Morfeusz 2)

## Problem

Polish names change form with grammatical case ("Kowalski" → "Kowalskiego"), and the market gap the
plan targets includes recognising inflected names [EVIDENCE: docs/Plan MVP … medtech.md, Key Findings 3(c)].
A model trained only on nominative names will miss "Pani Kowalskiej". The plan says to generate case forms
with Morfeusz 2 [EVIDENCE: docs/Plan MVP … medtech.md, section 3, step 1].

## Scope

In:
- `{{LABEL#k:case}}` for `OSOBA`, `IMIE` and `NAZWISKO`, with case ∈ `nom gen dat acc inst loc voc`.
- Inflection via `morfeusz2==1.99.15` generation: singular, agreeing with the person's sex from PII-2-b.
  `OSOBA` inflects first name and surname independently.
- The span text is the inflected surface form. The span keeps the person's `entity` id, so all case forms
  of one person share it.
- Fallback: when Morfeusz has no form for a name, the nominative is used and the document records
  `inflection_fallbacks` (a count).

Out:
- Inflecting `ADRES`, `MIEJSCOWOSC` and organisation names.
- Plural forms, diminutives, and vocative-only spellings (red-teaming variants, PII-3).
- Any change to PII-1 code or to the PII-2-b generators beyond adding the case argument.

Change budget: 280 added lines, 4 files, 3 modules

## Context

- `src/piitier/datagen/template.py` (the case is parsed, and currently rejected, in PII-2-a) and
  `src/piitier/datagen/people.py` (person sex), from PII-2-a and PII-2-b.
- Morfeusz 2 tags: `subst:sg:gen:m1` and similar. Verified locally: `generate("Kowalski")` yields
  `Kowalskiego` (gen) and `Kowalskiemu` (dat); `generate("Anna")` yields `Annie` (dat.loc).
- New: `src/piitier/datagen/inflect.py`, `tests/datagen/test_inflect.py`; edit `template.py`,
  `pyproject.toml`, `uv.lock`.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-15 | data author | `inflect("Kowalski", case="gen", sex="m")` and `inflect("Kowalska", case="gen", sex="f")` | `"Kowalskiego"` and `"Kowalskiej"` | unit |
| UC-16 | data author | `inflect("Anna", case="dat", sex="f")` and `inflect("Jan", case="inst", sex="m")` | `"Annie"` and `"Janem"` | unit |
| UC-17 | data author | `render` of `"{{OSOBA#1}} … rozmowa z {{OSOBA#1:inst}}"` where person 1 is fixed to Jan Kowalski | the second span text is `"Janem Kowalskim"`; both spans have `entity="1"` and `label=OSOBA` | unit |
| UC-18 | data author | `render` of `"{{NAZWISKO#1:xyz}}"` | `TemplateError` naming the unknown case *(added)* | unit |
| UC-19 | data author | `render` of `"{{PESEL#1:gen}}"` and `"{{ADRES#1:loc}}"` | `TemplateError`: case not allowed for this label *(added)* | unit |
| UC-20 | data author | `render` with a surname Morfeusz cannot generate (fixture surname `Xqzwy`) in `:gen` | span text `"Xqzwy"`; `doc.inflection_fallbacks == 1` *(added)* | unit |
| UC-21 | data author | the PII-2-a offset property test, rerun with case suffixes on name placeholders | it still holds: `doc.text[start:end]` equals each span's surface form | unit (property) |

## Open questions

none
