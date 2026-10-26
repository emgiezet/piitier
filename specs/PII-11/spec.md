---
ticket: PII-11
title: Narzędzia złotego zbioru — wytyczne anotacji, schemat v2, zgodność anotatorów, bliźniaki
status: approved
stacks: [python]
---

# PII-11 — Narzędzia złotego zbioru PL-PII-Bench

<!-- approved: owner instruction in session, 2026-10-26 ("adopt the good things from warda"). -->

## Problem

`bench/v1/dev` ma 6 dokumentów jednego autora, bez drugiej anotacji i bez miary zgodności.
Plan zakłada 300–500 ręcznie pisanych dokumentów anotowanych przez dwie osoby, ale nie istnieją
wytyczne anotacji, format zapisu dwóch anotacji i adjudykacji, narzędzie do liczenia zgodności
ani reguła kontrolująca fałszywe alarmy (dokumenty bez PII o tej samej treści).

## Scope

In:
- `docs/labelling/GUIDELINES.md`: co anotujemy, definicja każdej grupy z `docs/TAXONOMY.md` z
  ≥ 2 przykładami pozytywnymi i ≥ 2 negatywnymi na grupę (fikcyjne, po polsku), reguły granic
  spanów (waluta w KWOTA/DOCHOD zgodnie z `docs/TAXONOMY.md`; tytuł `dr`/`lek. med.` należy do
  spana LEKARZ, jak w korpusie treningowym — `src/piitier/datagen/render.py`; pełne imię i
  nazwisko → jeden span OSOBA, jak w `bench/v1`; samo imię → IMIE, samo nazwisko → NAZWISKO;
  zagnieżdżenia), czego nie anotujemy (quasi-identyfikatory poza MVP), procedura sporów
  (niezależne anotacje, adjudykacja z jednozdaniowym uzasadnieniem), budżet czasu.
- Schemat rekordu bench v2 (`bench/README.md`): pola v1 (`id`, `doc_type`, `text`, `spans` =
  złota wersja po adjudykacji) plus `annotations` (lista `{annotator, spans}`, ≥ 2),
  `adjudicated_by`, `twin_of` (id albo `null`), `notes`.
- `eval/bench_schema.py` + CLI `python -m eval.bench_schema <plik>...`: walidacja v2 (offsety =
  wycinki tekstu, etykiety z enuma, ≥ 2 anotatorów, adjudykacja obecna, `twin_of` wskazuje
  istniejący rekord); reguła bliźniaka: każdy rekord ze spanem z `DIRECT_IDENTIFIERS` ma
  bliźniaka (`twin_of`) tego samego `doc_type` bez żadnego takiego spanu; kontrola miksu
  (każdy `doc_type` ≤ 30% rekordów). Exit 0 / 1 (z listą błędów po id, bez treści) / 2 (brak pliku).
- `eval/agreement.py` + CLI `python -m eval.agreement <plik>`: zgodność dwóch pierwszych
  anotatorów: span F1 (strict i partial, per etykieta i łącznie) oraz kappa Cohena na etykietach
  znaków (`O` dla znaków poza spanami); próg akceptacji 0,7 (exit 1 poniżej).

Out:
- Napisanie i anotacja dokumentów (wymaga ludzi); migracja `bench/v1` (zostaje v1).
- Zmiany w `eval/run.py` i metrykach (PII-9), aplikacja do anotacji z interfejsem.
- Ujednolicenie szablonów `datagen`: 23 wystąpienia w 16 szablonach anotują pełne imię i nazwisko
  jako IMIE + NAZWISKO zamiast OSOBA (niespójne z `bench/v1`); wymaga retreningu — osobny ticket.

Change budget: 500 added lines (bez wytycznych), 8 files, 3 modules

## Context

- `docs/TAXONOMY.md` — etykiety, grupy, konwencja waluty w KWOTA/DOCHOD.
- `bench/README.md`, `bench/v1/dev/docs.jsonl` — obecny format v1.
- `eval/metrics.py::DIRECT_IDENTIFIERS` (tylko odczyt).
- `eval/run.py::_parse_spans` — istniejąca walidacja offsetów (wzorzec; bez zmian w tym pliku).
- Plan MVP, sekcja 4: złoty zbiór 500–1000 dokumentów, dwóch anotatorów, zgodność kappa/F1.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-146 | anotator | czyta `docs/labelling/GUIDELINES.md` | każda z 6 grup ma ≥ 2 przykłady pozytywne i ≥ 2 negatywne; są sekcje: granice spanów, czego nie anotujemy, spory, budżet czasu | unit (test parsuje nagłówki i liczy przykłady) |
| UC-147 | kurator | `python -m eval.bench_schema` na poprawnym pliku v2 (fixture 4 rekordy: 2 z PESEL + 2 bliźniaki) | exit 0 | unit |
| UC-148 | kurator | jw. z rekordem: offset ≠ wycinek, nieznana etykieta, 1 anotator, brak adjudykacji, `twin_of` do nieistniejącego id | exit 1; każdy błąd wypisany z id rekordu i nazwą reguły, bez treści dokumentu | unit |
| UC-149 | kurator | rekord z IBAN bez bliźniaka; bliźniak zawierający PESEL; bliźniak innego `doc_type` | exit 1, reguła `twin` dla każdego przypadku | unit |
| UC-150 | kurator | plik, w którym jeden `doc_type` to > 30% rekordów | exit 1, reguła `mix` z podaniem udziału | unit |
| UC-151 | kurator | `python -m eval.agreement` na fixture, gdzie anotatorzy zgadzają się w 3 z 4 spanów (jeden inny zakres) | span F1 strict i partial oraz kappa znakowa równe ręcznemu rachunkowi (do 4 miejsc); exit 0 gdy kappa ≥ 0,7 | unit |
| UC-152 | kurator | jw. przy kappa < 0,7 | exit 1, komunikat z wartością kappa i progiem | unit |

## Non-functional

- Komunikaty walidatora i narzędzia zgodności zawierają id, reguły i liczby — nigdy treść ani wartości.
- Fixture'y wyłącznie z fikcyjnymi danymi; nowe wartości o ważnej sumie dodane do `.pii-allowlist`.

## Open questions

Brak.
