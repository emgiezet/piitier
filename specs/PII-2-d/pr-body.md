## PII-2-d — `python -m piitier.datagen build`: reproducible JSONL dataset split by template
**QA verdict: PASS** · **Code review: APPROVED** · UC coverage: 8/8 automated · Tests: 340 → 361 (+21) · Skipped: 0

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

Waived: over budget: 1085 added lines > 760 (380 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing) — Standing owner approval in `.claude/sdlc.md` permits added-line overruns up to 5000, conditional on QA/verification passing, all UCs covered and no other unwaived findings. All changed code/test paths are declared. DatasetReview approved; zero unwaived findings. — @local-user (2026-10-20)

---

## Combined integration — PII-2-b + PII-2-d

**QA verdict: PASS** · **DatasetReview: APPROVED · PeopleReview: PENDING**  
UC coverage: 14/14 automated · Tests: 340 → 376 (+36, 5.76 s) · Skipped: 0

This PR is stacked onto `ai/pii-1g-2a-integration` (PR#2, open). Base: `18c6a6b`. Do not rebase onto main until PR#2 merges.

### What both specs asked for

**PII-2-b — Person, address and contact generators**

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-9 | data author | `render` of OSOBA/PESEL/DATA_URODZENIA over 200 seeds | PESEL date digits decode to birth date; digit-10 parity matches sex | `test_uc9_pesel_date_matches_data_urodzenia`, `test_uc9_sex_digit_matches_personrecord_sex` |
| UC-10 | data author | `render` of IMIE/NAZWISKO/OSOBA | OSOBA == IMIE + " " + NAZWISKO; consistent when OSOBA appears first; two entities independent | `test_uc10_osoba_equals_imie_space_nazwisko`, `test_uc10_osoba_consistency_when_osoba_first`, `test_uc10_entity_scope_two_people` |
| UC-11 | data author | `render` of ADRES/KOD_POCZTOWY/MIEJSCOWOSC | three spans; postcode `\d{2}-\d{3}`; house number present; record shared across labels and seeds | `test_uc11_address_fields_and_format`, `test_uc11_address_record_shared_across_labels`, `test_uc11_address_shared_across_seeds` |
| UC-12 | data author | `render` of TELEFON; then `piitier.detect` | matches accepted phone shape; no false PESEL or NIP inside it | `test_uc12_telefon_accepted_shapes_and_no_false_detect` |
| UC-13 | data author | `render` of EMAIL | exactly one `@`; dot in domain; no whitespace | `test_uc13_email_syntax` |
| UC-14 | data author | `render` of OSOBA#1 and OSOBA#2 over 200 seeds | never the same full name | `test_uc14_two_explicit_people_distinct` |

**PII-2-d — `python -m piitier.datagen build`** (UC-22 – UC-29 as in the component section above)

### How to verify
```bash
uv run pytest -q -m "not integration"
uv run pytest -q
uv run ruff format --check . && uv run ruff check .
uv run mypy src
python -m piitier.datagen build --out /tmp/ds1
python -m piitier.datagen check /tmp/ds1
```

### Runtime evidence (manually observed by parent, isolated installed environment)

- 200 identity documents rendered; 2200 spans produced; anonymous 4-person + 3-address fresh IDs verified
- 2 byte-identical 100-doc default datasets; exact manifest counts, SHA256 hash-split, corrupted-offset rejection and bench/non-empty protection confirmed
- Combined custom templates: 100 people / address / contact documents exported and checked
- Existing 4 PDF CLI smokes: PASS; existing 27 API/text CLI smokes: PASS
- Final combined wheel built and tested (default + people CLI) in isolated installed environment away from source; Faker dependency and locale resources included
- No generated corpus committed

### What this batch does and does not include

Default 8 templates still use 6 structured labels (PESEL, NR_DOWODU, NIP, REGON, IBAN, NR_KARTY).  
All 9 new labels (OSOBA, IMIE, NAZWISKO, DATA_URODZENIA, ADRES, KOD_POCZTOWY, MIEJSCOWOSC, TELEFON, EMAIL) are functional and proven in custom templates.  
No LLM-written templates, no model training, no inflection, no BIO conversion, no production corpus in this batch.

### Combined size approval

Waived: over budget: 1851 added lines > 800 (400 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing) — Standing owner approval in `.claude/sdlc.md` permits added-line overruns up to 5000, conditional on QA/verification passing, all UCs covered and no other unwaived findings. All changed code/test paths are declared.

Component waivers (each independently granted):
- PII-2-b: over budget: 766 added lines > 660 (330 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)
- PII-2-d: over budget: 1085 added lines > 760 (380 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)

DatasetReview approved. Conditional until PeopleReview closes. — @local-user (2026-10-20)
