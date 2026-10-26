---
ticket: PII-10
title: Kalibracja progu na osobnym splicie, z minimalnym wsparciem i przedziałem ufności
status: approved
stacks: [python]
---

# PII-10 — Kalibracja progu: osobny split, minimalne wsparcie, przedział ufności

<!-- approved: owner instruction in session, 2026-10-26 ("adopt the good things from warda"). -->

## Problem

`training.calibrate` dobiera próg na tym samym `eval_file`, na którym wybiera się model, więc
próg jest dopasowany do zbioru selekcji. Liczy wyłącznie strict recall, którego pii-5-v3 nie
osiąga (0,944), i mimo nieosiągniętego celu zapisuje do configu próg 0,0 jak udaną kalibrację.
Wynik nie podaje liczności, przedziału ufności ani recall per grupa ryzyka, więc nie wiadomo,
na ilu przykładach oparto decyzję.

## Scope

In:
- Nowe klucze konfiguracji (`training/config.py`, opcjonalne): `calibration_file` (ścieżka),
  `calibration_target_recall` (domyślnie 0,98), `calibration_match` (`strict` | `partial`,
  domyślnie `strict`), `calibration_min_support` (domyślnie 100 spanów gold).
- Walidacja: `calibration_file` nie może wskazywać `bench/**/test/` (istniejąca reguła) ani być
  tym samym plikiem co `eval_file` (po `resolve()`); `calibration_match` spoza zbioru i
  `calibration_target_recall` spoza (0, 1] → `ConfigError`.
- `training.calibrate` kalibruje wyłącznie na `calibration_file`; brak klucza → exit 2 z
  komunikatem. Dopasowanie według `calibration_match`.
- Wsparcie: mniej spanów gold niż `calibration_min_support` → brak dopasowania progu.
- Próg trafia do configu **tylko** przy osiągniętym celu i wystarczającym wsparciu (exit 0);
  w przeciwnym razie config bez zmian, exit 1, przyczyna (`unsupported` / `target_not_met`).
- Raport (stdout i sekcja `## Kalibracja progu` w `MODEL_CARD.md`): próg, recall, precision,
  liczba spanów gold i dokumentów, 95% przedział Wilsona dla recall, tryb dopasowania, recall
  i liczność per grupa ryzyka z `docs/TAXONOMY.md` („Wagi ryzyka”).

Out:
- Progi per grupa / per etykieta (jeden próg globalny jak dziś).
- Zmiany w `datagen` (podział train/dev/cal) i w metrykach `eval/metrics.py`.
- Eksport ONNX, trening, `src/piitier/`.

Change budget: 350 added lines, 6 files, 2 modules

## Context

- `training/calibrate.py::calibrate_threshold`, `::write_threshold`, `::main`, `ThresholdResult`.
- `training/config.py::load_config`, `TrainingConfig`, `_OPTIONAL_KEYS`, `_check_test_split`.
- `eval/metrics.py::corpus_entity_metrics`, `group_for_label`, `GROUP_WEIGHTS` (tylko odczyt).
- `.claude/playbooks/model-training.md` krok 5 (kalibracja recall-first na dev, próg do configu i karty).
- `FINDINGS.md`, sekcja Model: strict recall pii-5-v3 0,944 vs partial 0,982.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-140 | trener | `load_config` z `calibration_file` równym `eval_file` | `ConfigError` z nazwą klucza; inny plik → OK; `calibration_match: fuzzy` lub `calibration_target_recall: 1.5` → `ConfigError` | unit |
| UC-141 | trener | `calibrate` bez `calibration_file` w configu | exit 2, komunikat wskazuje brakujący klucz, config bez zmian | unit |
| UC-142 | trener | kalibracja na zbiorze z 40 spanami gold przy `calibration_min_support: 100` | exit 1, przyczyna `unsupported`, config bez zmian, `MODEL_CARD.md` zapisuje liczność i przyczynę | unit |
| UC-143 | trener | kalibracja z wystarczającym wsparciem, cel nieosiągalny przy strict, osiągalny przy partial (ręcznie zbudowany fixture) | `strict`: exit 1, `target_not_met`, config bez zmian; `partial`: exit 0, wybrany najwyższy próg spełniający cel, zapisany w configu | unit |
| UC-144 | trener | udana kalibracja | raport zawiera recall z 95% przedziałem Wilsona równym ręcznemu rachunkowi (do 4 miejsc), liczbę spanów i dokumentów oraz recall i liczność per grupa ryzyka | unit |
| UC-145 | trener | kalibracja na dwóch plikach: `eval_file` A i `calibration_file` B | predykcje i metryki liczone tylko na B (A nie jest czytany) | unit |

## Non-functional

- Predykcje kalibracji (`predictions.jsonl`) bez treści dokumentów (jak dziś).
- Testy jednostkowe bez pobierania modeli (stub predyktora / gotowy plik predykcji).

## Open questions

Brak.
