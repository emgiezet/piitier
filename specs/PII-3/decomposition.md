# Decomposition — PII-3

Source: `specs/PII-2/decomposition.md` (deferred list) + `specs/briefs/polish-pii-anonymizer.md`
+ `.claude/playbooks/synthetic-data.md`. Approved by owner command 2026-10-23 („pracuj dalej").

No `PII-3/spec.md`; this plan replaces it. All labels below already exist in
`docs/TAXONOMY.md` and the `Label` enum — PII-3 adds no new taxonomy entries, only
generators, augmentation, negatives, and run tooling.

Estimate: ~1440 added lines · ~20 files · ~6 modules (hard ceiling 5000).

| Slice | Outcome a user or operator can see | UCs | Budget | Depends on |
|---|---|---|---|---|
| `PII-3-a` | `render` injects valid `NR_UMOWY`, `NR_POLISY`, `NR_SZKODY`, `NR_REJESTRACYJNY`, `VIN`, `NR_KW` into insurance/finance templates | UC-38…UC-45 | 380 lines | PII-2-a |
| `PII-3-b` | `render` injects `ICD10`, `LEK`, `ROZPOZNANIE`, `PLACOWKA`, `LEKARZ`, `NPWZ` into medical templates | UC-46…UC-53 | 380 lines | `-a` (shared files) |
| `PII-3-c` | `augment(doc, rng)` strips diacritics / applies OCR confusions / spaces digit groups and every offset stays exact | UC-54…UC-59 | 300 lines | PII-2-a |
| `PII-3-d` | `build --augment --hard-negatives N` produces a large seed-deterministic corpus; `docs/DATASET_CARD.md` documents schema, sources, licences | UC-60…UC-66 | 380 lines | `-b`, `-c` |

Order: `-a` ∥ `-c` → `-b` → `-d`. `-a`/`-b` share `values.py`, `render.py`, prompts and
templates, so they serialize; `-c` is a standalone module and runs in parallel; `-d`
integrates everything into `build` and writes the card.

Deferred to PII-4 (not written here): NER fine-tuning, PL-PII-Bench baselines, ONNX export,
HF upload (only the card is written here), OCR of scans, MSG/EML/ZIP inputs.