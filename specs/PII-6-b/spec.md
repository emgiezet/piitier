---
ticket: PII-6-b
title: Numeracja placeholderów po koreferencji wzmianek
status: draft
stacks: [python]
---

# PII-6-b — Numeracja placeholderów po koreferencji wzmianek

## Problem

Po PII-6-a `piitier mask --model` zastępuje każdą osobę, adres i lekarza literalnym
`[OSOBA_n]`, `[ADRES_n]`, `[LEKARZ_n]`. Odbiorca zamaskowanego tekstu (np. zewnętrzny LLM
streszczający zgłoszenie szkody) nie odróżni poszkodowanej od sprawcy ani nie wie, że
„Jan Kowalski” i „Kowalskiego” to ta sama osoba — tekst traci sens, a metryka spójności
numeracji w `eval.run` nie może się poprawić.

## Scope

In:
- Moduł `src/piitier/coref.py`: każdemu spanowi etykiety z `Label.numbered == True`
  (OSOBA, IMIE, NAZWISKO, ADRES, LEKARZ) przypisuje indeks encji; ta sama encja → ten sam
  indeks, różne encje → różne indeksy, numeracja per etykieta od 1 w kolejności pierwszego
  wystąpienia.
- `Anonymizer.mask` i `piitier mask --model` wypisują placeholdery z indeksem
  (`[OSOBA_1]`, `[IMIĘ_2]`): sufiks `_n` z `Label.placeholder` zastąpiony numerem.
- Klucz encji: lematy Morfeusza 2 (zależność już w `[project.dependencies]`), case-fold;
  słowo nieznane słownikowi → forma case-fold. Tytuły (`dr`, `lek.`, `prof.`, `pan`, `pani`)
  nie należą do klucza. ADRES: case-fold i zwinięte białe znaki.
- Łączenie wzmianek OSOBA/LEKARZ: inicjał („J. Kowalski”) i samo nazwisko („Kowalskiego”)
  łączą się z wcześniejszą encją tej samej etykiety o tym samym lemacie nazwiska (i zgodnym
  inicjale), **tylko gdy kandydat jest dokładnie jeden**; przy zerze lub kilku — nowy indeks.

Out:
- Numeracja etykiet bez `numbered` (PESEL, IBAN, … zostają `[PESEL]`, `[IBAN]`) — źródłem
  placeholderów jest `docs/TAXONOMY.md`.
- Tryb `pseudonymize` i mapa wartości (PII-6-c); spójność numeracji między dokumentami.
- Zmiany w `fusion.py`, detektorach, modelu NER, `eval/`, `training/`, `datagen/`.
- `piitier.mask(text)` bez modelu (reguły nie produkują etykiet numerowanych — wynik bez zmian).
- Koreferencja zaimków („ona”, „jego”) i modele ML do koreferencji.

Change budget: 450 added lines, 6 files, 2 modules

## Context

- `.claude/playbooks/pipeline-core.md` krok 3 (Coreference) i kolejność etapów
  `fusion` → `coref` → `render`.
- `src/piitier/labels.py::Label.numbered`, `Label.placeholder` (`[OSOBA_n]` …).
- `src/piitier/fusion.py` — wejście etapu (rozłączne spany w offsetach oryginału).
- `src/piitier/render.py::mask` — renderer; wierność poza spanami = 0.
- `src/piitier/__init__.py::Anonymizer.mask`, `src/piitier/cli.py::mask_file`.
- `src/piitier/datagen/inflect.py` — istniejące użycie `morfeusz2` (wzorzec inicjalizacji).
- `eval/metrics.py::numbering_consistency` — metryka, którą ta zmiana ma poprawić.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-118 | integrator | `Anonymizer(predictor=<stub>).mask` na tekście ze spanami OSOBA „Jan Kowalski”, „Jana Kowalskiego”, „J. Kowalskiemu” | wszystkie trzy zastąpione `[OSOBA_1]`; w wyniku nie ma `_n` | unit |
| UC-119 | integrator | jw. dla OSOBA „Jan Kowalski” i „Anna Kowalska” | `[OSOBA_1]` i `[OSOBA_2]` w kolejności wystąpienia | unit |
| UC-120 | integrator | OSOBA „Jan Kowalski”, potem samo „Kowalskiego”; osobno: „Jan Kowalski”, „Adam Kowalski”, potem samo „Kowalskiego” | w pierwszym tekście oba `[OSOBA_1]`; w drugim „Kowalskiego” dostaje nowy indeks `[OSOBA_3]` (dwóch kandydatów → brak łączenia) | unit |
| UC-121 | integrator | osobne spany IMIE/NAZWISKO: „Jan” „Kowalski”, „Jana” „Kowalskiego”, „Anna” „Nowak” | `[IMIĘ_1] [NAZWISKO_1]` dwukrotnie, potem `[IMIĘ_2] [NAZWISKO_2]` | unit |
| UC-122 | integrator | tekst z OSOBA, ADRES, PESEL i IBAN (każdy dwukrotnie, ta sama wartość) | `[OSOBA_1]` i `[ADRES_1]` dwukrotnie (numeracja per etykieta); `[PESEL]` i `[IBAN]` bez indeksu | unit |
| UC-123 | integrator | LEKARZ „dr Marek Zieliński” i „lek. Marek Zieliński” | oba `[LEKARZ_1]` | unit |
| UC-124 | integrator | OSOBA ze słowem spoza słownika Morfeusza: „John Smithson” i „JOHN SMITHSON” | oba `[OSOBA_1]` | unit |
| UC-125 | integrator | dowolny tekst i rozłączne spany przez `Anonymizer.mask` | 0 zmienionych znaków poza spanami (property-based); `eval.metrics.numbering_consistency` na wyniku UC-118: spójne 1/1 | unit |

## Non-functional

- Indeksowanie deterministyczne: ten sam tekst i te same spany → ten sam wynik.
- Klucze encji i wartości nie trafiają do logów ani komunikatów błędów.
- Morfeusz 2 inicjalizowany raz na `Anonymizer`, nie per span.

## Open questions

Brak.
