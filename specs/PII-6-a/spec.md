---
ticket: PII-6-a
title: Fuzja spanów reguł i modelu NER w API i CLI
status: approved
stacks: [python]
---

# PII-6-a — Fuzja spanów reguł i modelu NER w API i CLI

## Problem

`piitier.detect`, `piitier.mask` i `piitier mask <plik>` wykrywają tylko identyfikatory z reguł
(PESEL, NIP, REGON, IBAN, dowód, karta). Imiona, adresy, dane zdrowotne i kwoty przechodzą
niezamaskowane, mimo że model `pii-5-v3` ma 0/40 wycieków na `bench/v1/dev`. Autor musi pisać
własny kod łączący model z regułami — dokładnie ten „szósty skrypt”, którego ma nie być.

## Scope

In:
- Moduł `src/piitier/fusion.py`: łączy spany reguł i modelu w listę rozłącznych spanów według
  reguł pierwszeństwa z `.claude/playbooks/pipeline-core.md` (sekcja „Fusion precedence”).
- Publiczna klasa `piitier.Anonymizer(model: str | Path | None = None, *, predictor=None,
  threshold: float = 0.0, device: str = "cpu")` z metodami `detect(text) -> list[Span]` i
  `mask(text) -> str`, używająca fuzji. `model` (katalog checkpointu) i `predictor` (obiekt z
  `predict(text) -> list[Span]`) wykluczają się; podanie obu albo żadnego → `ValueError`.
- CLI: `piitier mask <plik> --model <katalog> [--threshold T]`.

Out:
- `coref` / numeracja `[OSOBA_1]` (PII-6-b) — placeholdery pozostają w obecnej postaci
  `Label.placeholder`.
- Tryb `pseudonymize` (PII-6-c), `normalize`/NFC, weryfikator LLM.
- Inferencja ONNX w `src/piitier` i zmiany w `training/`, `eval/`, `datagen/`.
- Zmiana zależności i pakowania (`transformers`/`torch` zostają w grupie `dev`).
- Zmiana zachowania `piitier.detect(text)` / `piitier.mask(text)` bez modelu.
- Zmiana detektorów w `src/piitier/rules/` i kryterium kalibracji progu.

Change budget: 550 added lines, 8 files, 3 modules

## Context

- `src/piitier/__init__.py` — `detect`, `mask`, `__all__`; tu dochodzi `Anonymizer`.
- `src/piitier/rules/__init__.py::detect_all` — spany reguł (`status` `valid` / `suspect`).
- `src/piitier/ner/inference.py::NerPredictor` — spany modelu (`source="model:ner"`, `score`).
- `src/piitier/render.py::mask` — renderer; przyjmuje wyłącznie spany rozłączne.
- `src/piitier/cli.py::main`, `mask_file` — podkomenda `mask`.
- `src/piitier/spans.py::Span`, `src/piitier/labels.py::Label` — jedyne typy spanu i etykiety.
- `docs/TAXONOMY.md`, sekcja „Wagi ryzyka” — wagi grup = tabela priorytetu typów w fuzji.
- `.claude/playbooks/pipeline-core.md` — kolejność etapów i reguły pierwszeństwa fuzji.
- Decyzja (PII-4, `specs/PII-4/decomposition.md`): ciężkie importy leniwe, z czytelnym `ImportError`.

Tabela priorytetu typów (reguła 2 pierwszeństwa): wygrywa span o wyższej wadze grupy etykiety
z „Wag ryzyka”; przy równej wadze dłuższy span; przy równej długości span o wcześniejszym
`start`. Przegrany zachowuje fragmenty poza zwycięzcą (reguła 4: żaden znak pokryty przez
którekolwiek wejście nie zostaje odsłonięty), każdy fragment ze swoją etykietą i `source`.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-102 | biblioteka | fuzja: span reguły `valid` PESEL wewnątrz spana NER `ADRES` | span PESEL ma dokładnie zakres reguły i `source` reguły; części ADRES przed i po PESEL zostają jako osobne spany ADRES z `source="model:ner"`; wynik rozłączny | unit |
| UC-103 | biblioteka | fuzja: span reguły `suspect` nakłada się częściowo na span NER innej etykiety | wygrywa etykieta o wyższej wadze grupy z TAXONOMY; przy równej wadze dłuższy span; przy równej długości wcześniejszy `start`; przegrany zachowuje fragmenty poza zwycięzcą | unit |
| UC-104 | biblioteka | fuzja z progiem `t`: spany NER o `score < t` i `score == t` | spany o `score < t` znikają z wyniku, spany o `score == t` zostają; spany reguł nie są filtrowane progiem | unit |
| UC-105 | biblioteka | fuzja dla kształtów nakładania: zagnieżdżony, częściowy, przyległy, identyczny | wynik rozłączny i posortowany po `start`; zbiór znaków pokrytych przez wynik równa się sumie znaków pokrytych przez wejście; spany przyległe nie są scalane; każdy span zachowuje `source` swojego wejścia | unit |
| UC-106 | integrator | `piitier.Anonymizer(predictor=<stub NER>, threshold=0.5).mask(text)` na tekście z imieniem (wykrytym tylko przez NER) i PESEL (reguła) | imię i PESEL zastąpione placeholderami; 0 zmienionych znaków poza spanami | unit |
| UC-107 | integrator | `import piitier; piitier.mask(text)` bez modelu | wynik identyczny z obecnym (tylko reguły); `"transformers"` i `"torch"` nie występują w `sys.modules` | unit |
| UC-108 | użytkownik CLI | `piitier mask <plik> --model <katalog> --threshold 0.5` na tiny checkpoincie (`hf-internal-testing/tiny-random-BertForTokenClassification` zapisanym lokalnie) | exit 0, wyjście zawiera placeholdery PESEL z reguł; bez `--model` wynik bajtowo identyczny z obecnym `piitier mask <plik>` | integration |
| UC-109 | użytkownik CLI | `piitier mask <plik> --model /nie/istnieje` | exit 2; stderr zawiera ścieżkę modelu i nie zawiera tracebacku ani treści dokumentu; nic nie zapisano do `-o` | unit |
| UC-110 | integrator | `piitier.Anonymizer()` bez argumentów oraz `piitier.Anonymizer(model=<katalog>, predictor=<stub>)` | oba wywołania kończą się `ValueError` przed załadowaniem czegokolwiek; `"transformers"` nie trafia do `sys.modules` | unit |

## Non-functional

- Spany wychodzące z fuzji są w offsetach oryginalnego wejścia (CLAUDE.md niezmiennik 4);
  test wierności renderera pozostaje zielony bez zmian.
- `Anonymizer` ładuje model raz w konstruktorze, nie przy każdym `mask`.
- Żaden log ani komunikat błędu nie zawiera treści dokumentu ani wartości PII.

## Open questions

Brak.
