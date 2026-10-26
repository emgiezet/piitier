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
| Threshold calibration with a strict-recall target of 0.98 cannot succeed for `pii-5-v3` (best strict recall 0.944 synthetic, 0.636 bench); no threshold is written. Partial recall on synthetic dev is 0.982 | PII-7 investigation; PII-10 write-on-success |
| Dedicated calibration split (1 031 synthetic documents, 14 766 gold spans; 25 duplicate zero-gold rows removed against v0.3 train/dev): strict recall at threshold 0.0 is **0.9446** (13 948 TP, 818 FN), precision 0.8846 (1 819 FP). Target 0.98 not met; config unchanged | `training/out/pii-5-v3/calibration_sweep.json` (77 evaluated thresholds, local-only); `data/synthetic/v0.3-cal/dev.jsonl` (gitignored; built from local historical v0.3 templates with seed 900042) |
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

### Rebuild the local calibration split

`data/synthetic/v0.3` was trained with **338** templates (218 policy, 81 table). A clean
checkout has only 6 policy and 3 hand-written table templates; substituting that set would
change the split and invalidate the measured result. First restore the private, gitignored
historical template backup to `data/derived-templates/` (see `docs/DATASET_CARD.md` for its
origin), and the original `data/synthetic/v0.3/{train,dev}.jsonl`. Neither is distributed in git.
The following assembles the original 338 templates (the 3 newer hand-written table templates
were not part of v0.3), then runs the build command in `training/configs/pii-5-v3.yaml`:

```bash
uv run python - <<'PY'
from pathlib import Path
from shutil import copy2

packaged = Path("src/piitier/datagen/templates")
backup = Path("data/derived-templates")
target = Path("data/calibration-templates")
assert backup.is_dir() and not target.exists()
for source in (*packaged.rglob("*.txt"), *backup.rglob("*.txt")):
    if source.is_relative_to(packaged) and source.parent.name == "zestawienie_prowizyjne":
        continue
    base = packaged if source.is_relative_to(packaged) else backup
    dest = target / source.relative_to(base)
    dest.parent.mkdir(parents=True, exist_ok=True)
    copy2(source, dest)
assert len(list(target.rglob("*.txt"))) == 338
PY
uv run python -m piitier.datagen build --templates data/calibration-templates \
  --n 9000 --seed 900042 --augment --augment-fraction 0.25 --hard-negatives 900 \
  --out data/synthetic/v0.3-cal/
```

Seed separation alone is insufficient: 25 zero-gold hard negatives duplicate text in v0.3.
Filter those rows deterministically, updating the local manifest. This preserves every gold
span and yields 1 031 dev docs, 14 766 gold spans, and zero shared text hashes:

```bash
uv run python - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path("data/synthetic")
def digest(row):
    return hashlib.sha256(row["text"].encode()).digest()
old = set()
for name in ("train.jsonl", "dev.jsonl"):
    with (root / "v0.3" / name).open(encoding="utf-8") as f:
        old.update(digest(json.loads(line)) for line in f)
path = root / "v0.3-cal/dev.jsonl"
with path.open(encoding="utf-8") as f:
    rows = [json.loads(line) for line in f]
kept = [row for row in rows if digest(row) not in old]
assert len(rows) - len(kept) == 25
assert all(not row["spans"] for row in rows if digest(row) in old)
path.write_text(
    "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in kept),
    encoding="utf-8",
)
manifest_path = root / "v0.3-cal/manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
manifest["split_counts"]["dev"] = len(kept)
manifest["filtered_calibration_duplicates"] = len(rows) - len(kept)
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
uv run python -m piitier.datagen check data/synthetic/v0.3-cal/
```

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
| Calibration on a separate split, minimum support, Wilson interval, write-on-success | PII-10, PII-13 | done for local `pii-5-v3`: `data/synthetic/v0.3-cal/dev.jsonl` built from historical templates (see build command in run config); strict target 0.98 not met, so no threshold written |
| Labelling guidelines, gold-set schema v2 with two annotators and twins, agreement with a kappa floor of 0.7 | PII-11, [`docs/labelling/GUIDELINES.md`](docs/labelling/GUIDELINES.md) | tooling done; writing and double-labelling the documents needs human annotators |
| CONTRIBUTING and PR template | PII-12 | done |
| Gate evaluators that refuse undefined metrics (the INT8 gate computes deltas from 0.0) | PROTOCOL.md, rule 1 | open |
| Redaction hook for coding agents (`PreToolUse` / `PostToolUse`) | — | idea, not specced |
