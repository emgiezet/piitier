# Poprawka Specyfikacji: Augmentacja Ułamkowa (UC-62 / PII-3-d)

**Data:** 2026-10-25  
**Zatwierdzone przez:** użytkownika w czacie 2026-10-25

## Problem

Korpus v0.1 (piitier 0.1.0) był augmentowany w 100%: każdy dokument, wszystkie cztery transformacje (`uppercase`, `strip_diacritics`, `ocr_confusions`, `space_digit_groups`) naraz. Skutek: model pii-5-v1 dostrojony na tym korpusie osiągnął 22/40 poprawnych detekcji na ręcznie napisanym `bench/v1/dev`, podczas gdy model bazowy (bez fine-tuningu) osiągnął tylko 2/40. Nadmierne dopasowanie do stylu wieloliterowego spowodowało, że model klasyfikował tekst z małymi literami jako niezawierający PII.

## Zmiana

Oryginalne brzmienie UC-62 zakładało augmentację każdego dokumentu. Nowe brzmienie:

> Augmentacja jest stosowana do **ułamka** dokumentów wybranych losowo z prawdopodobieństwem `augment_fraction` (domyślnie 0,25). Dla wybranych dokumentów stosowany jest **losowy niepusty podzbiór** transformacji: każda transformacja jest włączana niezależnie (uppercase z prawdopodobieństwem 0,3; pozostałe z 0,5). Decyzja i wybór transformacji są deterministyczne — ziarno na poziomie dokumentu to `base_seed + i`. Hard-negative docs podlegają tej samej regule.

Nowy parametr CLI: `--augment-fraction F` (zakres: `(0, 1]`; domyślnie 0,25; wymagane `--augment`).

## Manifest

Trzy nowe pola w `manifest.json`:

| Klucz | Typ | Opis |
|---|---|---|
| `augment_fraction` | `float \| null` | Wartość użyta do augmentacji (null gdy `augment=false`) |
| `augmented_doc_count` | `int` | Łączna liczba dokumentów (szablonowych + HN) faktycznie zaugmentowanych |
| `transform_doc_counts` | `dict[str, int]` | Liczba dokumentów, w których zastosowano każdą transformację |

## Pełny Bieg — aktualizacja polecenia

```bash
python -m piitier.datagen build \
  --templates src/piitier/datagen/templates \
  --n 20000 \
  --seed 42 \
  --augment \
  --augment-fraction 0.25 \
  --hard-negatives 2000 \
  --out data/synthetic/v0.3/
```

## Uzasadnienie Wyboru Wartości Domyślnej

Frakcja 0,25 oznacza, że ~75% dokumentów zachowuje oryginalny (różnorodny) styl, a ~25% jest augmentowanych z losowym podzbiorem transformacji. Oczekiwany wynik: model uczy się PII niezależnie od stylu zapisu, bez przeuczenia się na jeden wariant.
