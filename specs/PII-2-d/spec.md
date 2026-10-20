---
ticket: PII-2-d
title: python -m piitier.datagen build — reproducible JSONL dataset split by template
status: approved
stacks: [python]
depends-on: [PII-2-a]
---

# PII-2-d — `python -m piitier.datagen build`: reproducible JSONL dataset split by template

## Problem

Training needs a dataset on disk: thousands of labelled documents across the plan's 8 document types,
reproducible from a seed, and with no template shared between train and validation, because shared
templates inflate the validation score [EVIDENCE: docs/Plan MVP … medtech.md, section 9, weeks 3–4;
.claude/playbooks/synthetic-data.md, step 7]. PII-2-a renders one document in memory and writes nothing.

## Scope

In:
- `python -m piitier.datagen build --templates <dir> --n <N> --seed <S> --out <dir>` writes
  `train.jsonl`, `dev.jsonl` and `manifest.json`.
- A template file is `<templates>/<doc_type>/<template_id>.txt`, UTF-8. `doc_type` is one of `polisa`,
  `zgloszenie_szkody`, `umowa_kredytowa`, `wyciag`, `mail_klienta`, `transkrypcja_infolinii`,
  `wypis_szpitalny` or `skierowanie`.
- Packaged templates: at least one hand-written template per doc type in `src/piitier/datagen/templates/`.
  They use only labels with generators at the time of writing. They are the default `--templates`.
- One JSONL line per document:
  `{"id","doc_type","template_id","seed","text","spans":[{"start","end","label","entity","text"}]}`.
- Split: `dev` gets every template whose `sha256(template_id)` mod 10 == 0. The rest go to `train`.
- `manifest.json`: `n`, `seed`, template count per doc type, span count per label, document count per
  split, `piitier.__version__`, and the summed `inflection_fallbacks`.
- `python -m piitier.datagen check <dir>` re-verifies every span's offsets. Exit 0 if all are correct,
  exit 1 naming the first bad document id.
- Exit 2 when `--out` is inside `bench/` (CLAUDE.md invariant 7) or already non-empty.

Out:
- LLM-written templates (PII-2-e). This slice reads whatever `.txt` files `--templates` holds.
- Augmentation, hard negatives, domain and medical labels, the 10–20k production run, the HF dataset card (PII-3).
- Tokenisation and BIO conversion for training (model-training ticket).
- Any change to `render()` or the generators.

Change budget: 380 added lines, 8 files, 3 modules

## Context

- `src/piitier/datagen/render.py` (`render`, `Document`, `TemplateError`), from PII-2-a.
- `.claude/playbooks/synthetic-data.md`: steps 7 and 8; output goes to `data/synthetic/<version>/`, which is gitignored.
- New: `src/piitier/datagen/__main__.py`, `src/piitier/datagen/build.py`,
  `src/piitier/datagen/templates/<doc_type>/*.txt` (8 or more files), `tests/datagen/test_build.py`.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-22 | data author | `build --n 100 --seed 1 --out <tmp>` with the packaged templates | exit 0; `train.jsonl` + `dev.jsonl` hold 100 lines in total; every line parses and has exactly the schema keys | integration |
| UC-23 | data author | `check <tmp>` on that output | exit 0 | integration |
| UC-24 | data author | `check` after one span's `start` is shifted by 1 in `train.jsonl` | exit 1; stderr names that document's `id` and no document text *(added)* | integration |
| UC-25 | data author | read `template_id` across both files | no `template_id` appears in both `train.jsonl` and `dev.jsonl` | integration |
| UC-26 | data author | the same `build` command run twice into two empty dirs | the three files are byte-identical | integration |
| UC-27 | data author | `build --out bench/x` and `build --out <non-empty dir>` | exit 2 each; stderr `refusing to write into bench/` / `output directory not empty: <dir>`; nothing written *(added)* | integration |
| UC-28 | data author | read `manifest.json` | span counts per label equal the spans counted in the JSONL files; `n`, `seed` and the per-split counts match | integration |
| UC-29 | data author | `render` every packaged template at seed 0 | no `TemplateError`; all 8 doc types are present | unit |

## Open questions

none
