## PII-2-b + PII-2-d — Person/address/contact generators and reproducible JSONL dataset build

**QA verdict: PASS** · **Both reviews: APPROVED** · UC coverage: 14/14 automated · Tests: 340 → 377 (+37, 5.15 s) · Skipped: 0

This PR is stacked onto `ai/pii-1g-2a-integration` (PR#2, open). Base: `18c6a6b`. Do not rebase onto main until PR#2 merges.

Written from `specs/PII-2-b/spec.md` and `specs/PII-2-d/spec.md`. Component evidence in `specs/PII-2-b/` and `specs/PII-2-d/` (qa-report, verify-report, scope-report). Review the `Out:` sections of both specs first.

### What both specs asked for

**PII-2-b — Person, address and contact generators** (UC-9 – UC-14)

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-9 | data author | `render` OSOBA/PESEL/DATA_URODZENIA over 200 seeds | PESEL date digits decode to birth date; digit-10 parity matches sex | `test_uc9_pesel_date_matches_data_urodzenia`, `test_uc9_sex_digit_matches_personrecord_sex` |
| UC-10 | data author | `render` IMIE/NAZWISKO/OSOBA | OSOBA == IMIE + " " + NAZWISKO; consistent when OSOBA appears first; two entities independent | `test_uc10_osoba_equals_imie_space_nazwisko`, `test_uc10_osoba_consistency_when_osoba_first`, `test_uc10_entity_scope_two_people` |
| UC-11 | data author | `render` ADRES/KOD_POCZTOWY/MIEJSCOWOSC | three spans; postcode `\d{2}-\d{3}`; house number present; record shared across labels and seeds | `test_uc11_address_fields_and_format`, `test_uc11_address_record_shared_across_labels`, `test_uc11_address_shared_across_seeds` |
| UC-12 | data author | `render` TELEFON; then `piitier.detect` | accepted phone shape; no false PESEL or NIP inside it | `test_uc12_telefon_accepted_shapes_and_no_false_detect` |
| UC-13 | data author | `render` EMAIL | exactly one `@`; dot in domain; no whitespace | `test_uc13_email_syntax` |
| UC-14 | data author | `render` OSOBA#1 and OSOBA#2 over 200 seeds | never the same full name | `test_uc14_two_explicit_people_distinct` |

**PII-2-d — `python -m piitier.datagen build`** (UC-22 – UC-29)

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
uv run ruff format --check . && uv run ruff check .         # 102 files, exit 0
uv run mypy src                                              # 20 source files, exit 0
uv run pytest -q -m "not integration"
uv run pytest -q                                             # 377 passed, 0 skipped
uv run python -m piitier.datagen build --n 100 --seed 41 --out /tmp/ds1   # fresh empty dir
uv run python -m piitier.datagen check /tmp/ds1
```

### Runtime evidence (manually observed by parent, isolated installed environment)

Final combined wheel built and installed outside the repo in an isolated uv process using cached deps (--offline after PyPI 502). All runtime checks PASS:

- Custom templates: 100 people / address / contact documents rendered and exported; check exit 0
- Custom loader probe: 3 CRLF sequences preserved verbatim through `read_bytes` decode
- Two byte-identical default 100-doc corpora (seed 41); exact manifest counts and SHA256 hash-split confirmed
- Corrupted-offset rejection: exit 1, doc id in stderr, no document text
- bench/ path (resolved path and symlink aliases): exit 2, nothing written (no atomic TOCTOU guarantee)
- Non-empty output dir: exit 2, nothing written
- No generated corpus committed

### What this batch does and does not include

Default 8 packaged templates use 6 structured labels (PESEL, NR_DOWODU, NIP, REGON, IBAN, NR_KARTY). Custom templates can use all 9 new person/address/contact labels (OSOBA, IMIE, NAZWISKO, DATA_URODZENIA, ADRES, KOD_POCZTOWY, MIEJSCOWOSC, TELEFON, EMAIL) — proven in integration tests. No LLM-written templates, no model training, no inflection, no BIO conversion, no production corpus in this batch.

### Size approval

Waived: over budget: 1930 added lines > 800 (400 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing) — Standing owner approval in `.claude/sdlc.md` permits added-line overruns up to 5000, conditional on QA/verification passing, all UCs covered and no other unwaived findings. All changed code/test paths are declared. Files/modules within 100% tolerance; no separate file waivers. Both reviews APPROVED; zero unwaived findings. — @local-user (2026-10-20)

Component findings covered by the same standing approval:

Waived: over budget: 782 added lines > 660 (330 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing) — PII-2-b; PeopleReview APPROVED. — @local-user (2026-10-20)

Waived: over budget: 1148 added lines > 760 (380 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing) — PII-2-d; DatasetReview APPROVED. — @local-user (2026-10-20)
