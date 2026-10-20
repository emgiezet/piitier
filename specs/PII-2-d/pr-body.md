## PII-2-d — `python -m piitier.datagen build`: reproducible JSONL dataset split by template
**QA verdict: PASS** · **Code review: APPROVED** · UC coverage: 8/8 automated · Tests: 340 → 362 (+22) · Skipped: 0

Written from `specs/PII-2-d/spec.md`. Review the spec's `Out:` scope first —
that is where an unattended run is most likely to have overstepped.

### What the spec asked for

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-22 | data author | `build --n 100 --seed 1 --out <tmp>` with packaged templates | exit 0; 100 lines total; every line has exact schema keys | `test_uc22_build_exit0_total_and_schema` |
| UC-23 | data author | `check <tmp>` on valid build output | exit 0 | `test_uc23_check_exit0_on_valid` |
| UC-24 | data author | `check` after one span's `start` shifted by 1 | exit 1; stderr names doc `id`; no document text in stderr | `test_uc24_check_corrupted_exit1_names_doc_no_text` |
| UC-25 | data author | read `template_id` across both files | no `template_id` in both `train.jsonl` and `dev.jsonl` | `test_uc25_template_ids_disjoint` |
| UC-26 | data author | same `build` command run twice into two empty dirs | three files byte-identical | `test_uc26_deterministic_output` |
| UC-27 | data author | `build --out bench/x`; `build --out <non-empty dir>` | exit 2 each; stderr `refusing to write into bench/` / `output directory not empty: <dir>`; nothing written | `test_uc27_bench_protection_exit2`, `test_uc27_nonempty_protection_exit2` |
| UC-28 | data author | read `manifest.json` | span counts per label, split counts, `n` and `seed` match JSONL | `test_uc28_manifest_counts_match_jsonl` |
| UC-29 | data author | render every packaged template at seed 0 | no `TemplateError`; all 8 doc types covered | `test_uc29_packaged_templates_render_all_doc_types` |

### How to verify
```bash
uv run pytest -q -m "not integration"         # unit tests only
uv run pytest -q                              # full suite including integration
uv run ruff format --check . && uv run ruff check .
uv run mypy src
```

Runtime verification (parent-run, 2× 100-doc runs):
- `build --n 100 --seed 41`: 100 documents, exact schema/split/manifest verified; SHA256 split rule confirmed
- Two identical runs: byte-identical `train.jsonl`, `dev.jsonl`, `manifest.json`
- Manifest span/split/n/seed counts match JSONL counts
- Corrupted offset → exit 1, doc id in stderr, no document text
- `bench/` path (resolved path and symlink aliases): exit 2, nothing written (no atomic TOCTOU guarantee)
- Non-empty output dir → exit 2, nothing written
- Malformed UTF-8 in JSONL → exit 1, no traceback in stderr
- Earlier isolated-wheel packaging smoke also PASS

### What this slice does and does not include

The 8 built-in templates use 6 structured labels (PESEL, NR_DOWODU, NIP, REGON, IBAN,
NR_KARTY). No LLM-written templates, no inflection fallbacks, no BIO conversion, no
production corpus, no HF upload. Those are explicitly out of scope (PII-2-e and PII-3).

### Review here first
- `src/piitier/datagen/build.py`: sha256 split, deterministic traversal, bench/non-empty guards
- `src/piitier/datagen/__main__.py`: CLI entry points for `build` and `check`
- `tests/datagen/test_build.py`: all 8 UC acceptance tests and regression cases

### Not covered
- LLM-written templates (PII-2-e)
- Augmentation, hard negatives, domain/medical labels, 10–20k production run (PII-3)
- HF dataset card (PII-3)
- Tokenisation and BIO conversion (model-training ticket)
- Any change to `render()` or the generators (out of scope)


### Size approval

Waived: over budget: 1148 added lines > 760 (380 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing) — Standing owner approval in `.claude/sdlc.md` permits added-line overruns up to 5000, conditional on QA/verification passing, all UCs covered and no other unwaived findings. All changed code/test paths are declared. DatasetReview APPROVED; zero unwaived findings. — @local-user (2026-10-20)
