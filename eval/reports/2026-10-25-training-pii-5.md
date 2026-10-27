# Training report: pii-5-v1, pii-5-v2 and pii-5-v3 (2026-10-25)

## Summary

- Base model: `bardsai/eu-pii-anonimization-multilang-v2` (ModernBERT, 307M, Apache 2.0, revision `5e61416e`).
- **pii-5-v1: rejected.** On synthetic dev it looked nearly perfect, but on the hand-written `bench/v1/dev` 22 of 40 PII values leaked (base model: 2/40). Root cause: 100% of the training corpus was uppercased, and token labels were missing entity beginnings.
- **pii-5-v2: major progress, but partial regression.** Leak on bench dropped from 22/40 to 6/40, strict recall rose to 0.67 (base 0.33). However, `eval.compare` reported a regression on KWOTA (recall dropped to 0 due to missing currency in the span and missing decimal-point format).
- **pii-5-v3: goal achieved.** No regression, zero leaks on bench.
  - bench/v1/dev: leak **0/6 documents and 0/40 values** (base: 2/40, v1: 22/40, v2: 6/40).
  - bench/v1/dev strict F1: **0.646** on labels shared with the base model (base: 0.306, v1: 0.400, v2: 0.611).
  - `eval.compare` on bench: no regression (exit code 0; no recall drop above the 0.02 threshold).
  - Synthetic dev (2 363 docs): strict F1 **0.923**, leak **0/2363 documents**.

## Training runs

| | pii-5-v1 | pii-5-v2 | **pii-5-v3** |
|---|---|---|---|
| Config | `training/configs/pii-5-v1.yaml` | `training/configs/pii-5-v2.yaml` | `training/configs/pii-5-v3.yaml` |
| Corpus | `data/synthetic/v0.1` (`--augment` 100%) | `data/synthetic/v0.2` (no augmentation) | `data/synthetic/v0.3` (augmentation 25%, 32 prose templates) |
| Train / dev documents | 21 283 / 717 | 21 283 / 717 | 19 637 / 2 363 |
| Steps / epochs | 4000 / 3.0 | 1400 / 1.05 | 1300 / 1.06 |
| LR / batch / max_length | 2e-5 / 16 / 1024 | 1e-5 / 16 / 1024 | 1e-5 / 16 / 1024 |
| Hardware | RTX 3090 Ti, bf16 (~19.4 GB VRAM) | same as v1 | same as v1 |
| Training time | 1739 s (~29 min) | 610 s (~10 min) | 675 s (~11 min) |
| Final train loss | 0.0100 | 0.0470 | 0.0628 |
| seqeval on dev during training (P / R / F1) | 0.9925 / 0.9949 / 0.9937 | 0.9958 / 0.9988 / 0.9973 | 0.9267 / 0.9441 / 0.9353 |

## Evaluation (`eval.run`, span level, RTX 3080)

Strict: span boundaries and label must match exactly. Partial: prediction need only overlap with the gold span.

### bench/v1/dev (6 documents, 40 spans, hand-written)

| | Base model (bards v2) | pii-5-v1 | pii-5-v2 | **pii-5-v3** |
|---|---|---|---|---|
| Strict P / R / F1 (full taxonomy) | 0.282 / 0.275 / 0.279 | 0.500 / 0.250 / 0.333 | 0.489 / 0.550 / 0.518 | **0.656 / 0.636 / 0.646** |
| Partial P / R / F1 (full taxonomy) | 0.769 / 0.750 / 0.760 | 0.850 / 0.425 / 0.567 | 0.733 / 0.825 / 0.777 | **0.812 / 0.788 / 0.800** |
| Strict F1 (shared with base model) | 0.306 | 0.400 | 0.611 | **0.646** |
| **Leak: documents / values** | 1/6 / 2/40 | 5/6 / 22/40 | 2/6 / 6/40 | **0/6 / 0/40** |
| Regressions vs. base (`eval.compare`) | — | EMAIL, KWOTA | KWOTA | **NONE (exit code 0)** |

### Synthetic dev (templates unseen during training)

| | Base (v0.1) | pii-5-v1 (v0.1) | Base (v0.2) | pii-5-v2 (v0.2) | Base (v0.3) | **pii-5-v3 (v0.3)** |
|---|---|---|---|---|---|---|
| Strict P / R / F1 | 0.224 / 0.394 / 0.285 | 0.921 / 0.931 / 0.926 | 0.243 / 0.444 / 0.314 | 0.995 / 0.999 / 0.997 | 0.410 / 0.776 / 0.536 | **0.915 / 0.930 / 0.923** |
| Partial P / R / F1 | 0.440 / 0.776 / 0.562 | 0.988 / 1.000 / 0.994 | 0.433 / 1.000 / 0.604 | 0.997 / 1.000 / 0.999 | 0.499 / 0.945 / 0.653 | **0.965 / 0.982 / 0.974** |
| Leak: documents | 17/711 | 0/717 | 0/717 | 0/717 | 3/2363 | **0/2363** |

## Key bug fixes and changes

1. Uppercase and OCR augmentation (commit `4ae920e`, PII-3-d spec fix): `--augment` previously converted 100% of documents to uppercase without diacritics, so the model never saw normal text. We switched to `--augment-fraction 0.25`; only 25% of documents are corrupted with a random, non-empty subset of transforms (uppercase with probability 0.3, others 0.5). In corpus v0.3, 8% of documents are uppercase.
2. KWOTA and DOCHOD convention (commit `4ae920e`): the amount generator omitted currency from the span (`717 253,28`), while bench and PII annotations require `1500 PLN` / `250 zł`. The renderer now extends each amount span to include the adjacent currency token (`PLN`, `zł`, `EUR`, `€`); amounts come in 5 formats, including decimal-point. Documented in `TAXONOMY.md`.
3. New generators and formats (commit `4ae920e`): added generators for `DOCHOD` (income in various formats) and `DANE_ZDROWOTNE` (a curated list of 83 disease entities, injuries and symptoms in the nominative case). Damage and policy numbers gained slash formats (`SZK/YYYY/N`, `POL/YYYY/N`).
4. Prose templates (commit `4ae920e`): added 32 templates with entities in natural Polish sentences (4 per each of the 8 document types), with correct grammatical case usage and no duplication of address elements.
5. Token labelling and span decoder (commits `0597624`, `85811de`): BPE tokens with a leading space (`" CZ"`) are now correctly labelled `B-` based on overlap with the non-whitespace part. Tokens that are pure whitespace inside an entity are ignored during training (`-100`), and the evaluation decoder skips them, fixing the split of multi-word entities like `717 253,28`.
6. Model saving and GPU selection: `train.py` saves the trained model and tokenizer to `training/out/<run>/`. The start command includes `CUDA_DEVICE_ORDER=PCI_BUS_ID` to force execution on the RTX 3090 Ti and prevent OOM.

## Limitations and conclusions

- `bench/v1/dev` has 6 documents and 40 spans. That's enough to catch overfitting and generalisation errors, but real production validation needs the planned 300–500 documents.
- We left `bench/**/test/` untouched (invariant 7).
- Model `pii-5-v3` passes the bench with zero leaks and is ready for threshold calibration and ONNX export.
