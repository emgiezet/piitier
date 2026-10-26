---
ticket: PII-9
title: Protokół ewaluacji — liczniki, wartości nieokreślone, systemy kontrolne, metadane raportu
status: approved
stacks: [python]
---

# PII-9 — Protokół ewaluacji

<!-- approved: owner instruction in session, 2026-10-26 ("adopt the good things from warda"). -->

## Problem

Raport `eval.run` podaje P/R/F1 bez liczników, a dzielenie przez zero zwraca 0,0 — nie da się
odróżnić „system nic nie znalazł” od „w zbiorze nie ma takich encji”. Nie ma zapisanego protokołu:
który split służy do wyboru modelu, który do kalibracji, a który do liczb końcowych, ani jakie
progi są bramkami. Brak systemów kontrolnych, więc nie widać, czy metryki w ogóle odróżniają
systemy. Raport nie zapisuje commita ani wersji pliku benchmarku.

## Scope

In:
- `eval/metrics.py::EntityPRF` dostaje liczniki `tp`, `fp`, `fn` (int); wszystkie funkcje
  zwracające `EntityPRF` (jedno- i wielodokumentowe) je wypełniają.
- Raport markdown i JSON `eval.run`: każda metryka encji z licznikami; metryka o zerowym
  mianowniku wypisana jako `undefined (0/0)` w markdown i `null` w JSON — nigdy 0,0.
  Dotyczy precision, recall, F1, risk-weighted recall i leak rate.
- Systemy kontrolne w rejestrze `eval/baselines`: `none` (zero spanów) i `mask-all` (jeden span
  na każdy ciąg znaków bez białych znaków, etykieta `OSOBA`).
- Metadane raportu (markdown i JSON): commit (`git rev-parse HEAD`, a gdy niedostępny `unknown`),
  SHA-256 każdego pliku benchmarku, liczba dokumentów, próg, split.
- `docs/bench/PROTOCOL.md`: definicje metryk ze wzorami, rola każdego splitu, bramki (nazwa →
  metryka → próg), zasady raportowania.

Out:
- Kalibracja i jej split (PII-10); schemat złotego zbioru i zgodność anotatorów (PII-11).
- Zmiana logiki dopasowania spanów, detektorów, modelu, `src/piitier/`.
- `eval/compare.py` poza dopasowaniem do nowego pola liczników, jeśli konstruuje `EntityPRF`.

Change budget: 400 added lines, 10 files, 3 modules

## Context

- `eval/metrics.py::EntityPRF`, `entity_metrics`, `entity_metrics_by_label`,
  `corpus_entity_metrics*`, `corpus_risk_weighted_recall`, `leak_rate` / `LeakRate`.
- `eval/run.py::run_benchmark`, `::main` (sekcja metryk, JSON sidecar), `eval/report.py::write_report`.
- `eval/baselines/__init__.py` — rejestr systemów; `eval/baselines/piitier_systems.py` — wzorzec.
- `.claude/playbooks/evaluation.md`; `CLAUDE.md` niezmiennik 7 (split `test` tylko do liczb końcowych).
- Bramki znane dziś: wierność = 0 zmienionych znaków; wyciek dokumentów z identyfikatorem
  bezpośrednim < 1% na złotym `test` (plan MVP, sekcja metryk); spadek recall INT8 ≤ 0,01
  (`training/export_onnx.py`); cel recall kalibracji 0,98 (`training/calibrate.py`).

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-133 | metryki | `corpus_entity_metrics` na znanym zbiorze (2 dokumenty) | `tp`, `fp`, `fn` równe ręcznemu rachunkowi; P/R/F1 bez zmian względem obecnych wartości | unit |
| UC-134 | ewaluator | raport dla zbioru bez żadnego spanu gold etykiety X, gdzie system nic nie przewiduje | precision, recall, F1 tej etykiety: `undefined (0/0)` w markdown i `null` w JSON; nie `0.0000` | unit |
| UC-135 | ewaluator | raport z leak rate przy 0 dokumentach z identyfikatorem bezpośrednim | leak rate dokumentów `undefined (0/0)` / `null`; risk-weighted recall przy 0 gold → `undefined` | unit |
| UC-136 | ewaluator | `eval.run --system none --bench v1 --split dev` | exit 0; recall 0,0 (z licznikami `tp=0`); leak rate wartości = 1,0; wierność 0 | unit |
| UC-137 | ewaluator | `eval.run --system mask-all --bench v1 --split dev` | exit 0; leak rate wartości = 0,0; wierność 0; precision < 0,1 | unit |
| UC-138 | ewaluator | dowolny przebieg `eval.run` | markdown i JSON zawierają commit (40 znaków hex albo `unknown`), SHA-256 każdego pliku bench, liczbę dokumentów, split i próg | unit |
| UC-139 | ewaluator | czyta `docs/bench/PROTOCOL.md` | zawiera wzory P/R/F1 (strict, partial), risk-weighted recall, leak rate (dokumenty i wartości), wierność, numerację; tabelę splitów (synthetic dev: wybór; cal: kalibracja; bench dev: rozwój; bench test: wyłącznie liczby końcowe); tabelę bramek z progami z sekcji Context; regułę „zerowy mianownik = undefined, nigdy PASS” | unit (test sprawdza obecność sekcji i nazw bramek) |

## Non-functional

- Raporty nadal bez treści dokumentów i wartości PII (tylko id, liczniki, metryki).
- `none` i `mask-all` nie importują torch/transformers.

## Open questions

Brak.
