---
ticket: PII-3-b
title: Generatory danych medycznych (ICD10, LEK, ROZPOZNANIE, PLACOWKA, LEKARZ, NPWZ)
status: approved
stacks: [python]
depends-on: PII-3-a
---

# PII-3-b — generatory danych medycznych (art. 9 RODO)

## Problem

Etykiety zdrowotne (`ICD10`, `LEK`, `ROZPOZNANIE`, `PLACOWKA`, `LEKARZ`, `NPWZ`) istnieją
w `docs/TAXONOMY.md` i enumie `Label`, ale nie mają generatorów; dokumenty medyczne
(`wypis_szpitalny`, `skierowanie`) nie zawierają danych art. 9, więc model nie ma na czym
się uczyć.

## Scope

In:
- W `src/piitier/datagen/values.py` (lub nowym `src/piitier/datagen/medical.py` rejestrującym
  się w `_GENERATORS`/`_VALIDATORS` — jeśli plik `values.py` zrobiłby się dłuższy niż
  ~450 linii):
  - `ICD10`: kod z małej, w repo autorskiej listy ~25 powszechnych kodów (fakty medyczne,
    np. `I10`, `J06.9`, `E11.9`) + warianty pisowni (z/bez kropki); walidator
    `^[A-Z]\d{2}(\.\d{1,2})?$`. Bez kopiowania tabeli ICD-10 (licencjonowane przez WHO) —
    wyłącznie pojedyncze kody jako fakty.
  - `LEK`: lista ~40 międzynarodowych nazw niezastrzeżonych (paracetamol, ibuprofen,
    amoksycylina…) autorska w repo; EVIDENCE: nazwy pospolite, nie podlegają licencji.
  - `ROZPOZNANIE`: ~20 autorskich fraz rozpoznań (np. „nadciśnienie tętnicze”).
  - `PLACOWKA`: komponowane nazwy „Szpital {Wojewódzki|Miejski} im. {Faker last_name}
    w {town}” — Faker `pl_PL`, zero słowników zewnętrznych.
  - `NPWZ`: 7 cyfr, pierwsza cyfra = kod zawodu (1 = lekarz); cyfrę kontrolną (jeśli
    publiczny opis formatu jej wymaga) zweryfikuj w publicznym źródle i zapisz link
    EVIDENCE w komentarzu; nie zgaduj formatu.
- `LEKARZ` (numbered): w `render.py` nowa grupa `_DOCTOR_LABELS = {Label.LEKARZ}` —
  osoba z `people.make_person` + prefix „dr”/„lek. med.” wg seed; infleksja jak dla
  `NAZWISKO` (rozszerzenie `_INFLECTABLE_LABELS` o `LEKARZ`), cache per entity.
- Nowe szablony: `templates/wypis_szpitalny/wypis_szpitalny_02.txt`
  (LEKARZ, ICD10, LEK, ROZPOZNANIE, PLACOWKA, NPWZ),
  `templates/skierowanie/skierowanie_02.txt` (LEKARZ, NPWZ, PLACOWKA).
- Prompty: informacyjna lista etykiet 21 → 27 w 8 plikach (po PII-3-a).
- Testy w `tests/datagen/test_values_medical.py` (UC-46…UC-53).

Out: `DANE_ZDROWOTNE` i `NR_DOKUMENTACJI` (poza odroczoną listą PII-2), detektory,
enum/taxonomy, zmiany LLM-owych zasad odrzucania, słowniki zewnętrzne (licencje!).

## Acceptance criteria

- UC-46: każdy generator zwraca wartość zgodną ze swoim walidatorem; determinizm seed.
- UC-47: `ICD10` z kropką i bez kropki przechodzi walidator; lista kodów ≥ 25.
- UC-48: `NPWZ` — format potwierdzony źródłem publicznym (EVIDENCE w komentarzu),
  100 losowań przechodzi walidator, wszystkie z pierwszą cyfrą 1.
- UC-49: `LEK` — 40 nazw, wszystkie niezastrzeżone (test porównuje z listą stałą).
- UC-50: `render` szablonu z 6 etykietami medycznymi: offsety dokładne,
  `text[start:end] == span.text`.
- UC-51: `LEKARZ#1:gen` infleksja działa (Morfeusz), fallback liczony jak dla `OSOBA`.
- UC-52: `build` + `check` przechodzą; `manifest.span_counts` zawiera etykiety medyczne.
- UC-53: prompt wymienia 27 etykiet zgodnie z `_SUPPORTED_LABELS`.

Change budget: 380 added lines, 8 files, 4 modules