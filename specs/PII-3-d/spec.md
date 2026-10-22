---
ticket: PII-3-d
title: Twarde negatywy, duży deterministyczny bieg i karta datasetu
status: approved
stacks: [python]
depends-on: PII-3-b, PII-3-c
---

# PII-3-d — twarde negatywy, duży bieg, karta datasetu

## Problem

Playbook (krok 6) wymaga twardych negatywów (słowa-poszukiwacze wyglądające jak PII,
które PII nie są, „labelled for exactly what it is”). Nie ma też przepisu na pełny bieg
10–20k dokumentów ani karty datasetu z licencjami (playbook, krok 8) — bez tego nie da
się opublikować zbioru na HF.

## Scope

In:
- Nowy moduł `src/piitier/datagen/hard_negatives.py`:
  `make_hard_negative_docs(seed: int, n: int) -> list[Document]` — dokumenty kodowane
  (nie szablony .txt — playbook zabrania wartości w szablonach), wartości z generatorów:
  - „numer referencyjny” o kształcie PESEL z błędną sumą kontrolną → **bez** spana PESEL
    (to nie identyfikator osoby),
  - nazwisko-rzeczownik (Kowal, Wróbel, Zima) jako zawód/ptak/drzewo → bez spana OSOBA,
  - ulica od nazwiska (`ul. Kowalskiego`) wewnątrz spana ADRES → **tylko** ADRES,
  - łańcuch 17-znakowy wyglądający na VIN z błędną cyfrą kontrolną w kontekście
    „numer protokołu” → bez spana VIN,
  - każdy dokument `doc_type` z istniejącego zbioru `DOC_TYPES`, id `hn_{i:07d}`.
- `build.py` + `__main__.py`: opcje CLI `--augment` (aplikuje `augment.augment` do
  każdego dokumentu z `random.Random(doc_seed)`) i `--hard-negatives N` (dokłada
  `make_hard_negative_docs` do zbioru treningowego, split dev zależny od seed jak zwykle);
  `manifest.json` zapisuje `augment: bool` i `hard_negatives: int`. Determinizm:
  ten sam seed + te same flagi → bajt identyczny output.
- `docs/DATASET_CARD.md`: schemat pól JSONL, generatory i ich źródła (Faker MIT,
  Morfeusz 2 BSD-2-Clause, listy autorskie w repo), licencja wyjścia CC BY 4.0,
  seed/`version`, przepis na pełny bieg (10–20k), statystyki z przykładowego biegu.
- Testy w `tests/datagen/test_hard_negatives.py` + rozszerzenie `test_build.py`
  (UC-60…UC-66).

Out: upload na HF (tylko karta), NER/baselines (PII-4), zmiany detektorów w
`src/piitier/rules/`, generowanie zbioru w CI (bieg testowy ≤ 2k dokumentów; pełny bieg
udokumentowany w karcie, wykonywany lokalnie do `data/`, gitignored).

## Acceptance criteria

- UC-60: każdy twardy negatyw ma spany wyłącznie dla encji, które naprawdę są (asercja
  per przypadek: brak PESEL, brak OSOBA, ADRES tylko raz itd.); `check` przechodzi.
- UC-61: `--hard-negatives 100` daje 100 dodatkowych dokumentów o id `hn_*`;
  `manifest.hard_negatives == 100`.
- UC-62: `--augment` — wszystkie offsety dokładne po augmentacji (check (0,"")),
  `manifest.augment == true`; bez flagi `augment == false` i wynik identyczny z PII-2-d.
- UC-63: determinizm: dwa biegi `--augment --hard-negatives 50 --seed 42` → identyczne
  pliki bajt w bajt (sha256).
- UC-64: bieg 2000 dokumentów z augmentacją i negatywami w teście (integration):
  `check` (0, ""), `span_counts` sumuje się z manifestu.
- UC-65: karta datasetu istnieje, wymienia wszystkie źródła z licencjami i CC BY 4.0.
- UC-66: pełny bieg (10k+, lokalnie, poza testem) — zapisz w karcie seed, rozmiar i
  sha256 plików (EVIDENCE w `qa-report.md`).

Change budget: 380 added lines, 8 files, 4 modules