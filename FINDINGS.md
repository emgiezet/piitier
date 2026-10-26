# Findings so far (as of 2026-10-26)

Results and decisions in one place. Detailed documents are linked, not repeated.

## Model

| Finding | Evidence |
|---|---|
| `pii-5-v3` (fine-tuned `bardsai/eu-pii-anonimization-multilang-v2`) leaks **0/40** gold values on `bench/v1/dev`; the base model leaks 2/40 | [`eval/reports/2026-10-25-trening-pii-5.md`](eval/reports/2026-10-25-trening-pii-5.md) |
| `pii-5-v1` was rejected: 100% augmented (uppercased) training text leaked 22/40 on the hand-written bench while looking perfect on synthetic dev | same report |
| Synthetic dev is not a substitute for the gold set: strict F1 there is ~0.9, against ~0.6 on `bench/v1/dev` | same report |
| FP32 ONNX on synthetic dev (2 363 docs, per-document matching): F1 0.912, recall 0.944 | `training.export_onnx` run, PII-7 |
| **Dynamic INT8 quantisation is not usable as is:** recall 0.926 (−0.018 > tolerance 0.01), so the export is blocked | PII-7, [`specs/PII-7/spec.md`](specs/PII-7/spec.md) |
| Threshold calibration with a strict-recall target of 0.98 cannot succeed for `pii-5-v3` (best strict recall 0.944 synthetic, 0.636 bench), so the threshold stays 0.0; partial recall on synthetic dev is 0.982 | PII-7 investigation |
| The decoder can split one word across two entity types (`Wiśniew` NAZWISKO + `ska` OSOBA) | local tracker issue #2 |

## Pipeline

| Finding | Evidence |
|---|---|
| Rules + NER fusion: a checksum-valid rule span beats any overlapping model span; otherwise TAXONOMY risk weight, then length, then start; coverage is the union of the inputs | [`specs/PII-6-a/spec.md`](specs/PII-6-a/spec.md), `src/piitier/fusion.py` |
| The first fusion version never applied rule precedence on real input (detectors emit `source="rule"`, the code checked `"rule:"`); the unit tests used the wrong source and missed it | PII-6-a review (PR #11) |
| A NaN or out-of-range threshold silently dropped every NER span (fail-open); it is now rejected | PII-6-a review |
| The INT8 gate compared INT8 with INT8 (a directory holding `model_int8.onnx` was scored as ONNX), so it could never trip | PII-7 (PR #10), local issue #1 |
| Corpus metrics matched spans across documents; the error was ≤ 0.001 F1, but matching is now per document | PII-7 |
| The payment-card rule matches Luhn-valid 16-digit runs inside decimals (`0.9937050359712231`) and lock-file hashes | found while building `piitier scan` (PII-8); not fixed yet |

## Data

| Decision | Why |
|---|---|
| Templates derived from internal policy PDFs and commission statements stay local (gitignored) and were filtered out of the git history | they kept literal source dates; CLAUDE.md invariant 2 (PR #9, [`docs/DATASET_CARD.md`](docs/DATASET_CARD.md)) |
| A clean clone builds its corpus from hand-written templates only, so it differs from `data/synthetic/v0.3` | same |
| New checksum-valid identifiers must be allowlisted on purpose (`.pii-allowlist`, `piitier scan` hook) | PII-8 |
| Training templates annotate full names two ways: 23 occurrences in 16 templates as IMIE + NAZWISKO, 45 as OSOBA; `bench/v1` uses OSOBA throughout | likely part of the strict-F1 gap on the bench; the labelling guidelines follow `bench/v1`; unifying the templates needs a retrain (open ticket) |
| Doctor titles (`dr`, `lek. med.`) are inside the LEKARZ span in the corpus (`src/piitier/datagen/render.py`) | the labelling guidelines follow the corpus |

## Process

| Finding | Consequence |
|---|---|
| Independent review caught a BLOCKER in two of the last three feature batches that all tests had passed | keep a review before every merge |
| Tests written alongside a bugfix passed on the buggy code | bugfix tests must be shown to fail on the pre-fix code |
| Subagents wrote into the owner's checkout instead of their worktree three times | absolute paths under the worktree, and check the owner's `git status` after every run |
| In PII-9, PII-10 and PII-11 the reviewers' injected bugs (mutations) survived the first test suites | each fix round had to prove the new tests catch the reviewer's mutations |

## Compared with warda

[`pawelkiszczak/warda`](https://github.com/pawelkiszczak/warda) is a local allow/redact/ask/block decision model for
coding-agent tool calls, not a span anonymiser. What piitier adopted and what is still open:

| Practice | Where | Status |
|---|---|---|
| Licence files, CI on every PR, pre-commit with gitleaks and `piitier scan` | PII-8 | done |
| Evaluation protocol: counts with every metric, zero denominator = undefined, control systems `none` / `mask-all`, report provenance | PII-9, [`docs/bench/PROTOCOL.md`](docs/bench/PROTOCOL.md) | done |
| Calibration on a separate split, minimum support, Wilson interval, write-on-success | PII-10 | done; no calibration split exists yet, so existing run configs (e.g. `pii-5-v3`) need a `calibration_file` before `training.calibrate` runs |
| Labelling guidelines, gold-set schema v2 with two annotators and twins, agreement with a kappa floor of 0.7 | PII-11, [`docs/labelling/GUIDELINES.md`](docs/labelling/GUIDELINES.md) | tooling done; writing and double-labelling the documents needs human annotators |
| CONTRIBUTING and PR template | PII-12 | done |
| Gate evaluators that refuse undefined metrics (the INT8 gate computes deltas from 0.0) | PROTOCOL.md, rule 1 | open |
| Redaction hook for coding agents (`PreToolUse` / `PostToolUse`) | — | idea, not specced |
