# QA Report — PII-2-d

## Verdict: PASS

Every UC has a passing test carrying its id. Full suite: 361 passed, zero skipped.

## UC Coverage Map

| UC | actor | use case | automated test | status |
|----|-------|----------|----------------|--------|
| UC-22 | data author | `build --n 100 --seed 1 --out <tmp>` with packaged templates | `test_uc22_build_exit0_total_and_schema` | PASS |
| UC-23 | data author | `check <tmp>` on valid build output | `test_uc23_check_exit0_on_valid` | PASS |
| UC-24 | data author | `check` after one span's `start` shifted by 1 | `test_uc24_check_corrupted_exit1_names_doc_no_text` | PASS |
| UC-25 | data author | no `template_id` shared between train and dev | `test_uc25_template_ids_disjoint` | PASS |
| UC-26 | data author | same `build` command twice → byte-identical output | `test_uc26_deterministic_output` | PASS |
| UC-27 | data author | `build --out bench/x`; `build --out <non-empty dir>` | `test_uc27_bench_protection_exit2`, `test_uc27_nonempty_protection_exit2` | PASS |
| UC-28 | data author | `manifest.json` span/split/n/seed counts match JSONL | `test_uc28_manifest_counts_match_jsonl` | PASS |
| UC-29 | data author | every packaged template renders; all 8 doc types present | `test_uc29_packaged_templates_render_all_doc_types` | PASS |

All UCs present: 8/8 automated. All passing.

## Suite output

**Unit & Integration Tests:**
```
uv run pytest -q: 361 passed
```

- Baseline: 340 tests; feature branch: 361 tests (+21).
- Skipped: 0.
- Integration-marked tests require the wheel installed in the isolated environment; no model or network is needed.

**Static analysis (parent-run, isolated environment):**

- `uv run ruff format --check .` — exit 0
- `uv run ruff check .` — exit 0
- `uv run mypy src` — exit 0 (19 source files checked)

**Runtime verification (2× 100-doc runs, manually observed by parent):**

- `build --n 100 --seed 41 --out <dir1>` and `<dir2>`: both produced byte-identical corpora (100 documents, SHA256 rule verified)
- Both splits: exact schema, offsets and manifest counts per label/split/n/seed verified
- Reproducibility: `train.jsonl`, `dev.jsonl`, `manifest.json` byte-identical across both runs
- Corrupted-offset rejection: exit 1, doc id named in stderr, no document text
- Absolute bench path from unrelated cwd: exit 2, no writes (guards check resolved path and symlink aliases; no atomic TOCTOU guarantee)
- Symlink into bench/: exit 2, no writes
- Malformed UTF-8 in JSONL: exit 1, no traceback in stderr
- Non-empty output dir: exit 2, nothing written

**Earlier isolated-wheel packaging smoke also PASS.**

## Findings

The built-in 8 templates currently use 6 structured labels (PESEL, NR_DOWODU, NIP, REGON,
IBAN, NR_KARTY). No LLM-written templates, no inflection fallbacks triggered, no BIO
conversion, no production corpus, no HF upload in this slice.

## Not verified

- LLM-written templates (out of scope; PII-2-e)
- Augmentation, hard negatives, domain/medical labels, 10–20k production run (PII-3)
- HF dataset card (PII-3)
- Tokenisation and BIO conversion (model-training ticket)
- Any change to `render()` or the generators (out of scope)
