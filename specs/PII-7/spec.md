---
ticket: PII-7
title: Bramka INT8 i metryki korpusowe liczone per dokument
kind: bugfix
status: approved
approved-by: issue #1 (label bug, @local-user)
stacks: [python]
---

# PII-7 — Bramka INT8 i metryki korpusowe liczone per dokument

## Problem

Eksport ONNX pii-5-v3 zgłosił `recall_delta = 0.0`, choć rzeczywisty spadek recall FP32 → INT8
to 0,016 (powyżej tolerancji 0,01). `score_checkpoint` traktuje katalog zawierający `*.onnx` jako
model ONNX, a `main` kwantyzuje przed scoringiem, więc „FP32” to INT8 liczony drugi raz: bramka
tolerancji nigdy nie zadziała. Dodatkowo `eval.run`, `score_checkpoint` i `calibrate_threshold`
łączą spany wszystkich dokumentów w jedną listę, więc predykcja z dokumentu B może trafić gold
z dokumentu A przy tych samych offsetach (issue #1).

## Scope

In:
- Dyspozycja `score_checkpoint`: plik `*.onnx` → ONNX; katalog → zawsze model PyTorch.
- `training.export_onnx.main`: baseline FP32 liczony tym samym predyktorem ONNX co INT8
  (na wyeksportowanym FP32 ONNX), żeby delta izolowała kwantyzację.
- Metryki korpusowe per dokument w `eval/metrics.py` i ich użycie we wszystkich wywołaniach
  korpusowych: `eval/run.py`, `eval/report.py`, `training/export_onnx.py`, `training/calibrate.py`.
- Usunięcie płaskich pól `BenchResult.gold_spans` / `pred_spans` (czysta zmiana, bez aliasów).

Out:
- Kryterium kalibracji (strict vs partial) i wartość tolerancji.
- Funkcje jednodokumentowe `entity_metrics`, `entity_metrics_by_label`, `risk_weighted_recall`
  (zostają bez zmian), `leak_rate`, `fidelity`, `numbering_consistency`.
- `src/piitier/`, `datagen/`, ponowny trening.

Change budget: 350 added lines, 8 files, 3 modules

## Context

- `training/export_onnx.py::score_checkpoint`, `::main`, `::OnnxNerPredictor`.
- `training/calibrate.py::calibrate_threshold`.
- `eval/metrics.py::entity_metrics`, `::entity_metrics_by_label`, `::risk_weighted_recall`.
- `eval/run.py::run_benchmark`, `::BenchResult`, sekcja metryk (`strict_micro` …,
  `comparable_labels`, JSON `gold_spans`); `eval/report.py::write_report` (`gold_count`).
- `.claude/playbooks/model-training.md` krok 6: spadek recall INT8 ponad tolerancję blokuje eksport.
- Issue #1 (`.aisdlc/tracker/issues/1.md`) — reprodukcja na `data/synthetic/v0.3/dev`.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-111 | metryki | `corpus_entity_metrics(gold_docs, pred_docs)` na dwóch dokumentach: gold `(10,20,PESEL)` tylko w A, predykcja `(10,20,PESEL)` tylko w B | brak trafienia: TP 0, P = R = 0,0; ten sam span w tym samym dokumencie → P = R = 1,0; wartości równe sumie TP/FP/FN liczonych osobno per dokument | unit |
| UC-112 | metryki | `corpus_entity_metrics_by_label` i `corpus_risk_weighted_recall` na tej samej kolizji między dokumentami | kolizja nie liczy się jako trafienie w żadnej etykiecie ani w recall ważonym | unit |
| UC-113 | ewaluator | `run_benchmark` + metryki raportu na dwóch dokumentach z kolizją offsetów jak w UC-111 | strict/partial P/R/F1 i tabela per etykieta w raporcie odpowiadają liczeniu per dokument; liczba spanów gold w raporcie = suma po dokumentach | unit |
| UC-114 | kalibracja | `calibrate_threshold` na dwóch dokumentach z kolizją offsetów | recall przy każdym progu liczony per dokument (kolizja nie podnosi recall); wybrany próg zgodny z ręcznym rachunkiem | unit |
| UC-115 | eksport | `score_checkpoint(<katalog checkpointu>)`, gdy w katalogu leży `model_int8.onnx` | scoring używa modelu PyTorch z katalogu (plik `.onnx` w katalogu nie zmienia wyniku); `score_checkpoint(<plik>.onnx)` używa ONNX | integration |
| UC-116 | eksport | `main` gdy wynik INT8 ma recall niższy od FP32 ONNX o więcej niż `int8_recall_tolerance` | exit 1; `export_report.json` zawiera FP32 liczone na FP32 ONNX, niezerowe `recall_delta` równe `fp32_recall - int8_recall` | unit |
| UC-117 | eksport | `main` gdy spadek recall ≤ tolerancji | exit 0; raport z tymi samymi kluczami i deltami | unit |

## Non-functional

- Metryki korpusowe liniowe względem liczby dokumentów (dopasowanie tylko w obrębie dokumentu).
- Raporty nadal nie zawierają treści dokumentów ani wartości PII.

## Open questions

Brak.
