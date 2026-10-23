## PR: PII-4 — NER training, calibration, ONNX INT8 export and evaluation benchmark

**QA verdict: PASS (503/503 passed)** · **Code Review: 12 findings + 1 post-review defect all fixed** · **UC coverage: 26/26 (UC-67..UC-92)** · **Tests: 437 → 467 non-integration (+30) + 36 integration** · **Base branch: main**

### Executive Summary & Integration Scope
This PR delivers the complete PII-4 batch implementing fine-tuning, threshold calibration, ONNX INT8 export, evaluation metrics, baseline adapters, and benchmark runner for the ~300M encoder NER model.
- **PII-4-a**: NER Inference Core & Sliding Window (`src/piitier/ner`, UC-67..UC-71).
- **PII-4-b**: Training Pipeline & Config Handling (`training/train.py`, UC-72..UC-74).
- **PII-4-c**: Threshold Calibration & ONNX INT8 Export (`training/calibrate.py`, `training/export_onnx.py`, UC-75..UC-78).
- **PII-4-d**: Evaluation Metrics & Risk Weighting (`eval/metrics.py`, UC-79..UC-84).
- **PII-4-e**: Baseline Adapters & Registry (`eval/baselines/`, UC-85..UC-88).
- **PII-4-f**: Benchmark Runner & Reporting (`eval/run.py`, `bench/`, UC-89..UC-91).

### Observed Test & Verification Results
- `uv run ruff format --check . && uv run ruff check .` — PASS
- `uv run mypy src` (24 files) — PASS
- `uv run pytest -m "not integration"` — 467 passed, 0 skipped.
- `uv run pytest -m integration` — 36 passed, 0 skipped.
- Total suite: 503 passed, 0 skipped.

### Usage Examples
```bash
uv run python -m training.train training/configs/pii-4-smoke.yaml
uv run python -m training.calibrate training/configs/pii-4-smoke.yaml
uv run python -m training.export_onnx training/configs/pii-4-smoke.yaml
uv run python -m eval.run --system rules --bench v1 --split dev
```

### Scope, Sizing & Waiver
- **Native combined scope:** 4440 added lines, 37 files, 19 modules (excluding specs and `uv.lock`).
- **Size Finding:** `over budget: 4440 added lines > 800 (400 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)`
- **Waiver Status:** Waived under standing approval by @local-user (2026-10-20): batch total ≤ 5000 hard ceiling passes (4440 < 5000), all 26 UCs green, all review findings fixed.

### Accepted Deviations
1. **Optimum / ONNX Export:** Optimum 2.3.0 requires separate optimum-onnxruntime backend package; used `torch.onnx.export` opset 14 + `onnxruntime.quantization.quantize_dynamic` QInt8 (same INT8 dynamic-weights result, rescored both variants).
2. **Dataset API:** `build_dataset` label2id parameter removed (review finding #10, supersedes spec signature).
3. **Numbering Consistency:** Signature extended with `original` + `masked_spans` parameters for correct partial-masking alignment.
4. **Smoke Training:** Smoke train test may pick available GPUs on workstation (1-step smoke, harmless).
5. **Dependencies:** Heavy training/export deps in dev group with lazy imports in shipped `src/piitier/ner` (wheel stays lean: `faker`/`morfeusz2`/`pypdf` only).

### Slice Specifications and Reports
- **PII-4-a**: [Spec](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-a/spec.md) | [QA Report](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-a/qa-report.md) | [Verify Report](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-a/verify-report.md)
- **PII-4-b**: [Spec](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-b/spec.md) | [QA Report](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-b/qa-report.md) | [Verify Report](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-b/verify-report.md)
- **PII-4-c**: [Spec](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-c/spec.md) | [QA Report](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-c/qa-report.md) | [Verify Report](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-c/verify-report.md)
- **PII-4-d**: [Spec](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-d/spec.md) | [QA Report](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-d/qa-report.md) | [Verify Report](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-d/verify-report.md)
- **PII-4-e**: [Spec](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-e/spec.md) | [QA Report](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-e/qa-report.md) | [Verify Report](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-e/verify-report.md)
- **PII-4-f**: [Spec](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-f/spec.md) | [QA Report](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-f/qa-report.md) | [Verify Report](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4-f/verify-report.md)
- **Combined Scope Report**: [Scope Report](https://github.com/emgiezet/piitier/blob/ai/pii-4-integration/specs/PII-4/scope-report.md)
