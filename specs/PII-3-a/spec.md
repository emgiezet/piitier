---
ticket: PII-3-a
title: Generatory identyfikatorów ubezpieczeniowo-finansowych (NR_UMOWY, NR_POLISY, NR_SZKODY, NR_REJESTRACYJNY, VIN, NR_KW)
status: approved
stacks: [python]
depends-on: PII-2-a
---

# PII-3-a — generatory identyfikatorów ubezpieczeniowo-finansowych

## Problem

Sześć etykiet finansowych (`NR_UMOWY`, `NR_POLISY`, `NR_SZKODY`, `NR_REJESTRACYJNY`, `VIN`,
`NR_KW`) istnieje w `docs/TAXONOMY.md` i enumie `Label`, ale nie ma generatorów w
`src/piitier/datagen/values.py`, więc `render()` rzuca `TemplateError` i dane treningowe
nie zawierają tych encji.

## Scope

In:
- W `src/piitier/datagen/values.py` generator + walidator dla każdej z 6 etykiet
  (rejestracja w `_GENERATORS` i `_VALIDATORS`), deterministyczne z `random.Random`:
  - `NR_UMOWY`: `UM/{RRRR}/{7 cyfr}`, np. `UM/2026/0001234`; rok ze stałego zakresu 2015–2026.
  - `NR_POLISY`: `{2 wielkie litery}{10 cyfr}`; pierwsze litery ze zbioru {PL, UB}; np. `UB4839201756`.
  - `NR_SZKODY`: `{SZK|CLM}{8 cyfr}`, np. `SZK00348192`.
  - `NR_REJESTRACYJNY`: tablica rejestracyjna `^[A-Z]{2}[A-Z0-9]{3,5}$`, min. 2 cyfry,
    bez liter I, O, Q; np. `WX7421K`.
  - `VIN`: 17 znaków `^[A-HJ-NPR-Z0-9]{17}$` (bez I, O, Q), cyfra kontrolna na pozycji 9
    zgodna z ISO 3779 (transliteracja + wagi); WMI zaczyna się od `ZZ`, żeby nie kolidować
    z realnym producentem. Walidator przelicza cyfrę kontrolną — nie tylko regex.
  - `NR_KW`: `{2 wielkie litery}{1 cyfra}/{6 cyfr}/{RRRR}`, np. `PO4/001234/2026`.
- `render.py`: rozszerzenie `supported_labels` o te 6 etykiet.
- Nowe szablony pakowane (literal values are placeholders only):
  `src/piitier/datagen/templates/polisa/polisa_02.txt` (NR_POLISY),
  `src/piitier/datagen/templates/zgloszenie_szkody/zgloszenie_szkody_02.txt`
  (NR_SZKODY, NR_REJESTRACYJNY, VIN),
  `src/piitier/datagen/templates/umowa_kredytowa/umowa_kredytowa_02.txt` (NR_UMOWY).
- `src/piitier/datagen/prompts/*.txt`: aktualizacja wyłącznie informacyjnej listy
  obsługiwanych znaczników (15 → 21) w wszystkich 8 plikach; bez zmian struktury promptu.
  `_SUPPORTED_LABELS` w `llm.py` rozszerza się automatycznie przez `_GENERATORS`.
- Testy w `tests/datagen/test_values_finance.py` (UC-38…UC-45).

Out: detektory (rule-detector) tych formatów w `src/piitier/rules/`, zmiany enuma
`Label`, `docs/TAXONOMY.md`, generatorów `people.py`/`inflect.py`, bieżących szablonów
`*_01.txt`, LLM-owej listy odrzuceń.

## Acceptance criteria

- UC-38: każdy z 6 generatorów zwraca wartość przechodzącą swój walidator; 100 losowań
  z jednym `random.Random(42)` — 100 sukcesów, zero wyjątków.
- UC-39: `VIN`: wygenerowana wartość ma poprawną cyfrę kontrolną ISO 3779 (walidator
  przelicza sumę), brak znaków I/O/Q, prefiks `ZZ`.
- UC-40: ten sam seed → te same wartości; inny seed → inne (determinizm).
- UC-41: `render()` na szablonie z 6 nowymi etykietami zwraca dokument, w którym każdy
  `text[start:end] == span.text`, label zgodny, status `valid`.
- UC-42: szablon z etykietą spoza `supported_labels` nadal rzuca `TemplateError`.
- UC-43: `build` z katalogu zawierającego nowe szablony przechodzi; `check` zwraca (0, "");
  `manifest.span_counts` zawiera nowe etykiety.
- UC-44: `llm.write_templates` z fake serverem akceptuje szablon używający nowych etykiet
  (rozszerzenie fake-owej odpowiedzi), `rejected == {}`.
- UC-45: prompt dla każdego `doc_type` wymienia nową listę 21 etykiet (test porównuje listę
  z `_SUPPORTED_LABELS`).

Change budget: 380 added lines, 8 files, 4 modules