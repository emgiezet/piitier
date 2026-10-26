## PII-7 — INT8 export gate and per-document corpus metrics (bugfix, issue #1)

**QA: PASS** · UC-111..UC-117 7/7 · tests: 698 passed (`-m "not integration"`), 47 passed (`-m integration`) · independent review: CHANGES_REQUESTED → all findings fixed.

### Bugs fixed
1. **BLOCKER — the INT8 tolerance gate could never trip.** `score_checkpoint` treated any directory containing `*.onnx` as an ONNX model; `main` quantises first, so "FP32" was INT8 scored twice and `recall_delta` was always 0. Dispatch is now explicit (an existing `.onnx` *file* → ONNX; a directory → PyTorch), and the FP32 baseline is scored with the same `OnnxNerPredictor` on the exported FP32 ONNX, so the delta isolates quantisation.
2. **Corpus metrics matched spans across documents.** `eval.run`, `score_checkpoint` and `calibrate_threshold` flattened all documents before `entity_metrics`. New `corpus_entity_metrics`, `corpus_entity_metrics_by_label` and `corpus_risk_weighted_recall` match only within a document; the flattened `BenchResult.gold_spans/pred_spans` are removed (no alias). Numerically small (≤ 0.001 F1 on pii-5-v3), but wrong in principle; leak rate, fidelity and numbering were already per-document.

### Real-model evidence (pii-5-v3, data/synthetic/v0.3/dev, 2,363 docs)
| | FP32 ONNX | INT8 ONNX | delta |
|---|---|---|---|
| strict F1 | 0.912 | 0.887 | 0.026 |
| strict recall | 0.944 | 0.926 | **0.018** |

`python -m training.export_onnx training/configs/pii-5-v3.yaml` now exits **1** (`recall_delta 0.018 > tolerance 0.01`): the INT8 export is blocked, as model-training.md step 6 requires. Before the fix it reported delta 0.0.

### Tests that would have caught it
Every new test fails on the pre-fix code (checked against an `origin/main` extract): UC-114 collision (flat recall 1.0 vs per-doc 0.0), UC-116/117 assert that `main` scores `onnx/model.onnx` and then `model_int8.onnx`, UC-113 runs `run_benchmark` on a cross-document offset collision, UC-115 compares a checkpoint dir with and without a junk `model_int8.onnx`.

Spec: [specs/PII-7/spec.md](https://github.com/emgiezet/piitier/blob/ai/PII-7-int8-gate/specs/PII-7/spec.md)
