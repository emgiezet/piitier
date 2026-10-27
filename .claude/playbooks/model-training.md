# Playbook — Fine-tune, calibrate, export, publish the NER model

Task-scoped. Reached from the Task Router in `CLAUDE.md`. Do not read sibling playbooks.
Conventions for the code live in `.claude/rules/python.md`.

## Sequence

1. **Pick the base checkpoint and check its licence first.** Candidates:
   `bardsai/eu-pii-anonimization-multilang-v2` (Apache 2.0, 8k context), HerBERT-large, and
   XLM-R. The base licence decides the derived model's licence, so write it into the run config.
2. **One config per run** in `training/configs/<run>.yaml`: base checkpoint and revision,
   dataset version (`data/synthetic/<version>/`), label enum version, seed, epochs, learning
   rate, and max length. `training/train.py` reads only the config. No hidden CLI defaults.
3. **Train** with HF Transformers `Trainer`, scoring with `seqeval`. BIO tags come from
   `src/piitier/labels.py`. Train on the synthetic train split and validate on `bench/**/dev/`.
   **Never load `bench/**/test/`** (CLAUDE.md invariant 7).
4. **Hardware:** train on the RTX 3090 Ti (bf16). Never combine it with the RTX 3080 in
   one DDP/FSDP job, because the smaller card caps both. Use the 3080 for inference and evaluation.
5. **Calibrate the threshold** on a dedicated **calibration split** (not `dev/`).
   Set `calibration_file` in the run config to the calibration JSONL; without it
   `python -m training.calibrate` exits 2.  The split must not overlap `bench/**/test/`,
   `eval_file`, or `train_file`.  Set `calibration_min_support` (default 100 gold spans)
   and `calibration_target_recall` (default 0.98).  The calibration writes the threshold
   into the config and MODEL_CARD **only on success**; a failed run leaves both unchanged.
   Threshold choice is recall-first; use `calibration_match: partial` when the target
   is not achievable under strict matching.
6. **Export** to ONNX with INT8 quantisation (Optimum). Re-score the INT8 model on `dev/` and
   record the F1 and recall deltas against FP32. A recall drop beyond the spec's tolerance
   blocks the export.
7. **Publish** to the Hugging Face Hub. The model card source lives in
   `training/model_cards/<run>/README.md` (committed to git). Before uploading, copy it
   into the output directory:
   ```bash
   cp training/model_cards/<run>/README.md training/out/<run>/README.md
   ```
   Then upload (human-run only — the agent never pushes to the Hub):
   ```bash
   hf upload emgiezet/piitier-pl training/out/<run> . --repo-type model
   ```
   (`--repo-type dataset` for the synthetic corpus or PL-PII-Bench.)
   The card must contain:
   - Metrics per entity type and per domain, taken from the evaluation report on the frozen
     test split (produced by the evaluation task, not here).
   - Intended use, known limitations (quasi-identifiers, colloquial art. 9 data), base model
     and licence, calibrated threshold.
   - The sentence "This is not a certificate of anonymisation."
   See `training/model_cards/<run>/PUBLISH.md` for the pre-upload checklist.

## Test requirements

- `training/train.py` passes a smoke run on a 5-document fixture with a tiny checkpoint,
  for 1 step on CPU, in a test marked `integration` (it downloads a checkpoint).
- The config loader rejects a config that points at a `test/` split.
- Threshold calibration picks the highest threshold that meets the target recall on a
  hand-built score/label fixture.
- One test per acceptance criterion, named with its `UC-<n>` id when working from a spec.

## Verify

Run the verification block from `.claude/rules/python.md`, plus
`uv run pytest -q -m integration tests/training`.

## Done when

The run config is committed, `calibration_file` points to the calibration split,
the threshold is calibrated on the dedicated split (not `dev/`), INT8 deltas are
recorded, the model card is complete, the upload command has been printed (not run), and
the verification block is green.
