---
ticket: PII-13
title: Plik kalibracyjny dla pii-5-v3
status: approved
stacks: [python]
---

# PII-13 — Plik kalibracyjny dla pii-5-v3

<!-- approved: owner instruction in session, 2026-10-26 ("pii-5-v3 a calibration file"). -->

## Problem

Konfiguracja `pii-5-v3` nie wskazuje osobnego zbioru kalibracyjnego, więc kalibracja kończy się kodem 2. Pełny przebieg wymaga też ograniczenia liczby kandydatów progu i użycia GPU do predykcji.

## Scope

In:
- Osobny syntetyczny zbiór kalibracyjny, rozłączny z istniejącymi splitami, oraz klucz `calibration_file` w konfiguracji modelu.
- Siatka progów co 0,01, zapis krzywej precision/recall z licznikami do `calibration_sweep.json` na ścieżkach sukcesu i porażki.
- Konfigurowalne urządzenie predyktora podczas kalibracji (domyślnie CPU).
- Uruchomienie na prawdziwym checkpointcie i zapis zmierzonego wyniku w `FINDINGS.md`.

Out:
- Zmiany w `eval/metrics.py`, trybach dopasowania i `datagen`.
- Obniżenie celu recall, aby wymusić sukces kalibracji.

Change budget: 300 added lines, 5 files, 2 modules

## Context

`training/calibrate.py::calibrate_threshold` ocenia obecnie każdy unikatowy wynik predykcji, a `main()` nie przekazuje urządzenia do `NerPredictor`. `training/config.py` obsługuje już osobny `calibration_file` i odmawia zapisu progu na niepowodzeniu. Zbiór `bench/v1/dev` jest zbyt mały (40 spanów) dla minimum 100.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-155 | kalibracja | `calibrate_threshold` na predykcjach z 500 unikatowymi wynikami | Maksymalnie 101 progów; zwrócony próg jest wielokrotnością 0,01, a recall/precision są zmierzone przy zwróconym progu. | unit |
| UC-156 | kalibracja | Uruchomienie zakończone sukcesem oraz porażką | `<output_dir>/calibration_sweep.json` w obu przypadkach: malejące progi, recall, precision, tp, fp, fn przy każdym ocenionym progu; `chosen_threshold` null przy porażce, `reason`, `match`, `target_recall`, `gold_spans`, `docs`, `stopped_early`. | unit |
| UC-157 | trener | Klucz `calibration_device` w konfiguracji | Domyślnie `cpu`; pusty lub nie-tekstowy → `ConfigError`; wartość trafia do `NerPredictor(device=…)`. | unit |

## Open questions

Brak.
