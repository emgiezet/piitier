---
ticket: PII-13
title: Plik kalibracyjny dla pii-5-v3
status: approved
stacks: [python]
---

# PII-13 — Plik kalibracyjny dla pii-5-v3

<!-- approved: owner instruction in session, 2026-10-26 ("pii-5-v3 a calibration file"). -->
<!-- scope extension prompted by owner request: "plz fix ... strict recall 0.9446 against the 0.98 target". -->

## Problem

Konfiguracja `pii-5-v3` nie wskazuje osobnego zbioru kalibracyjnego, więc kalibracja kończy się kodem 2. Pełny przebieg wymaga też ograniczenia liczby kandydatów progu i użycia GPU do predykcji.
Prawdziwy przebieg `pii-5-v3` osiągnął tylko 0,9446 strict recall. Kandydat z wysokim progiem dla poprawionego modelu może osiągnąć cel syntetyczny, a jednocześnie ujawniać wartości na ręcznie opisanym `bench/v1/dev`; taki próg nie może być zapisany jako bezpieczny.

## Scope

In:
- Osobny syntetyczny zbiór kalibracyjny, rozłączny z istniejącymi splitami, oraz klucz `calibration_file` w konfiguracji modelu.
- Siatka progów co 0,01, zapis krzywej precision/recall z licznikami do `calibration_sweep.json` na ścieżkach sukcesu i porażki.
- Konfigurowalne urządzenie predyktora podczas kalibracji (domyślnie CPU).
- Uruchomienie na prawdziwym checkpointcie i zapis zmierzonego wyniku w `FINDINGS.md`.
- Nowa wersja checkpointu wytrenowana tylko na dodatkowych szablonach medycznych przypisanych do treningu; istniejące splity dev i kalibracja bez zmian.
- Opcjonalny filtr bezpieczeństwa: spośród progów spełniających 0,98 strict recall wybierz najwyższy z zerem ujawnionych wartości na `bench/v1/dev`; filtruj predykcje **przed** scaleniem nakładających się okien, tak jak działający predyktor.

Out:
- Zmiany w `eval/metrics.py`, trybach dopasowania i `datagen`.
- Obniżenie celu recall, aby wymusić sukces kalibracji.
- Użycie `bench/v1/test` do doboru progu lub treningu; ręczne wpisanie progu bez pomiaru.

Change budget for the full PR: 900 authored lines (generated evaluation artifacts excluded), 20 files, 5 modules

## Context

Przed PII-13 `training/calibrate.py::calibrate_threshold` oceniał każdy unikatowy wynik predykcji, a `main()` nie przekazywał urządzenia do `NerPredictor`. `training/config.py` obsługiwał już osobny `calibration_file` i odmawiał zapisu progu na niepowodzeniu. Zbiór `bench/v1/dev` jest zbyt mały (40 spanów) dla minimum 100.
`training/templates/wypis_szpitalny/` zawiera tylko nowe szablony treningowe; `data/synthetic/v0.3-cal/dev.jsonl` i `bench/v1/dev` pozostają rozłączne z treningiem. `eval.metrics.leak_rate` ocenia ujawnione wartości po maskowaniu; wynik benchmarku ręcznego obejmuje tylko 40 spanów i nie dowodzi 0,98 recall na rzeczywistych dokumentach.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-155 | kalibracja | `calibrate_threshold` na predykcjach z 500 unikatowymi wynikami | Maksymalnie 101 progów; zwrócony próg jest wielokrotnością 0,01, a recall/precision są zmierzone przy zwróconym progu. | unit |
| UC-156 | kalibracja | Uruchomienie zakończone sukcesem oraz porażką | `<output_dir>/calibration_sweep.json` w obu przypadkach: malejące progi, recall, precision, tp, fp, fn przy każdym ocenionym progu; `chosen_threshold` null przy porażce, `reason`, `match`, `target_recall`, `gold_spans`, `docs`, `stopped_early`. | unit |
| UC-157 | trener | Klucz `calibration_device` w konfiguracji | Domyślnie `cpu`; pusty lub nie-tekstowy → `ConfigError`; wartość trafia do `NerPredictor(device=…)`. | unit |
| UC-158 | kalibracja | Kandydaty spełniają cel strict recall, lecz część ujawnia gold na safety dev | Wybrany zostaje najwyższy próg z zerem ujawnionych wartości; każdy punkt sweep ma licznik ujawnień, a config zawiera zmierzony próg. | unit |
| UC-159 | kalibracja | Żaden próg nie spełnia jednocześnie celu recall i safety | `reason=privacy_gate_not_met`, `chosen_threshold=null`, config pozostaje niezmieniony. | unit |
| UC-160 | trener | Nieistniejący lub testowy katalog safety | `ConfigError`; testowy split nie trafia do kalibracji. | unit |
| UC-161 | operator | Trenuje `pii-5-v4` i kalibruje na niezmienionym zbiorze | Strict recall ≥0,98 na 14 766 spanach; zapisany próg daje 0 ujawnionych wartości na `bench/v1/dev`; checkpoint pozostaje lokalny, mały sweep jest opublikowany jako raport. | integration |
| UC-162 | kalibracja | Span niskiej pewności łączy się ze spanem wysokiej pewności w oknach | Próg usuwa słabszy span przed `merge_windows`: zarówno strict recall, jak i licznik ujawnionych wartości odpowiadają predyktorowi używanemu w ewaluacji. | unit |

## Open questions

Brak.
