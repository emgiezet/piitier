# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `.xlsx` input masking, `-o out.xlsx` workbook output and `--skip-columns` selection.
  Output retains masked values, supported cell styles, column widths, row heights, merges and
  freeze panes; comments/authors, hyperlinks, defined names, headers/footers, charts, images and
  other unsupported objects are deliberately dropped, and document properties are reset.
  Detected formulas become plain text with a CLI warning; TUI export shows the conversion count.
- Password-protected PDF extraction with user or owner credentials for RC4, AES-128 and AES-256, including empty-user restricted PDFs.
- `mask --password-stdin`, `mask --password` and bounded hidden terminal entry. Authentication failures preserve existing destinations and do not create new outputs.
- `mask-batch` with strict filename/password CSV mapping, isolated per-file failures, exclusive text outputs and a final success/failure summary.
- Masked credential entry before the existing comparison UI, with cancellation and Ctrl-C handling before model loading.
- `.json` input for `mask`, `mask-batch` and `compare`: string values are masked in place, keys, numbers and structure are left untouched (`src/piitier/jsonmask.py`). ([#24](https://github.com/emgiezet/piitier/pull/24))

### Changed

- A 16-digit number next to a comma, or glued to a word that is not a hex token, is reported as a `suspect` card number and masked. This includes Polish decimal-comma fractions with 16 digits.

### Fixed

- Rules-only masking (`piitier.mask`, `mask_csv`, `piitier mask`, `mask-batch`) deleted the text after a 14-digit number that has REGON-14 shape and passes the Luhn check: both detectors reported the same range and both replacements were applied. `render.mask` now resolves overlapping spans before replacing.
- The label chosen for two detections with the same range, status and risk weight depended on object identity, so the same input could be masked as `[REGON]` or `[NR_KARTY]`. The first detection in input order now wins.
- Card numbers next to a comma or glued to a word were not detected, so comma-delimited CSV files came back unmasked; a Luhn-invalid number in those positions was dropped instead of marked `suspect`.

## [0.1.0] - 2026-10-27

### Added

- `piitier --version` prints `piitier 0.1.0`; version is single-sourced from `piitier.__version__` via hatch dynamic versioning. ([d4ee335](https://github.com/emgiezet/piitier/commit/d4ee335))
- `--model` on `piitier mask` and `piitier compare`, and `piitier.Anonymizer(model=...)`, now accept a Hugging Face Hub repo id (`owner/name`) in addition to a local directory path. ([d4ee335](https://github.com/emgiezet/piitier/commit/d4ee335))
- `--revision` / `revision=` parameter for Hub branch, tag, or commit selection; ignored for local paths. ([d4ee335](https://github.com/emgiezet/piitier/commit/d4ee335))
- `src/piitier/ner/hub.py`: Hub resolution with local-directory-wins ordering and a clear `model error: could not download ...` message on failure (exit 2). ([d4ee335](https://github.com/emgiezet/piitier/commit/d4ee335))
- Packaging extras: `pip install piitier` installs rules only; `pip install 'piitier[ner]'` adds torch + transformers; `pip install 'piitier[onnx]'` adds ONNX Runtime. Hub resolution requires the `ner` extra. ([d4ee335](https://github.com/emgiezet/piitier/commit/d4ee335))
- `pyproject.toml` metadata: readme, authors, classifiers, and project URLs. ([d4ee335](https://github.com/emgiezet/piitier/commit/d4ee335))
- CI: `release/**` branches and `v*` tags are now covered; a new `build` job builds the wheel, installs it in a clean venv, and runs `--version` plus a rules-only mask smoke test. ([d4ee335](https://github.com/emgiezet/piitier/commit/d4ee335))
- `.github/workflows/integration.yml`: runs `pytest -m integration` weekly and on manual dispatch. ([d4ee335](https://github.com/emgiezet/piitier/commit/d4ee335))
- `piitier scan` hook now covers `eval/reports/*.json`. ([d4ee335](https://github.com/emgiezet/piitier/commit/d4ee335))
- Model card and publish checklist at `training/model_cards/pii-5-v4/README.md` and `PUBLISH.md`. ([d4ee335](https://github.com/emgiezet/piitier/commit/d4ee335))
- `piitier scan --write-allowlist <file>` writes discovered identifiers to an allowlist file. ([#22](https://github.com/emgiezet/piitier/pull/22))
- `piitier mask` and `piitier.Anonymizer` accept `--skip-columns` (header names or 1-based indices) and `--delimiter` to leave selected CSV columns unmasked. ([#22](https://github.com/emgiezet/piitier/pull/22))
- TUI (`piitier compare`) gained a CSV column selector and can export the anonymized file directly. ([#22](https://github.com/emgiezet/piitier/pull/22))
- `src/piitier/csvskip.py`: CSV field-range parser and delimiter sniffer. ([#22](https://github.com/emgiezet/piitier/pull/22))
- `pii-5-v4` NER model: six new medical training templates, threshold calibrated to 0.78 on a private split (strict recall 0.9866, 0/40 leaks on `bench/v1/dev`). ([#19](https://github.com/emgiezet/piitier/pull/19))
- Calibration sweep committed at `eval/reports/pii-5-v4/calibration_sweep.json`; `bench/v1/dev` report at `eval/reports/pii-5-v4/2026-10-27-ner-benchv1-dev.md`. ([#19](https://github.com/emgiezet/piitier/pull/19))
- Labelling guidelines, bench schema v2 validator, twin/mix annotation rules, and annotator agreement tooling. ([PII-11](https://github.com/emgiezet/piitier/pull/16))
- Evaluation protocol: per-document span matching, undefined-metric guards, control systems `none`/`mask-all`, report provenance. ([PII-9](https://github.com/emgiezet/piitier/pull/14))
- CONTRIBUTING and PR template. ([PII-12](https://github.com/emgiezet/piitier/pull/17))
- Dataset card (`docs/DATASET_CARD.md`) with Hugging Face front matter and per-corpus counts. ([d4ee335](https://github.com/emgiezet/piitier/commit/d4ee335), [#20](https://github.com/emgiezet/piitier/pull/20))
- Coreference numbering (`src/piitier/coref.py`): OSOBA, IMIE, NAZWISKO, ADRES and LEKARZ spans now carry a per-label entity index (`[OSOBA_1]`, `[OSOBA_2]`, etc.); same entity -- same index; mention matching uses Morfeusz 2 lemmas; a lone surname or initial+surname is merged with an earlier entity only when exactly one candidate exists. Labels without `numbered` (PESEL, IBAN, ...) are unaffected; rules-only `piitier.mask` output is unchanged. (PII-6-b)

### Changed

- NER decoder applies a first-subtoken rule so one word cannot be split across two entity types (e.g. `Wiśniew` NAZWISKO + `ska` OSOBA); `bench/v1/dev` numbers unchanged (strict F1 0.6897, 0/40 leaks). ([d4ee335](https://github.com/emgiezet/piitier/commit/d4ee335))
- All user-facing documentation translated to English; `eval/report.py` and `training/calibrate.py` emit English section headings. ([c19e24b](https://github.com/emgiezet/piitier/commit/c19e24b))
- `docs/PLAN.md` renamed from the Polish filename. ([c19e24b](https://github.com/emgiezet/piitier/commit/c19e24b))
- Insurer-report templates replaced commission-statement templates in `src/piitier/datagen/templates/`; the commission document type is no longer supported by the current generator. ([#20](https://github.com/emgiezet/piitier/pull/20))
- Rules + NER fusion: checksum-valid rule span beats any overlapping model span; otherwise TAXONOMY risk weight, then length, then start. ([PII-6-a / #11](https://github.com/emgiezet/piitier/pull/11))

### Fixed

- Payment-card rule no longer matches Luhn-valid digit runs that are embedded in decimal numbers (`0.9937050359712231`) or in lock-file hashes. ([d4ee335](https://github.com/emgiezet/piitier/commit/d4ee335))
- TUI: CSV column selection is applied before anonymization, not after. ([4434bbd](https://github.com/emgiezet/piitier/commit/4434bbd))
- Fusion rule-source comparison was checking `"rule:"` instead of `"rule"`, so rule precedence never fired on real input; unit tests used the wrong source string and missed it. ([PII-6-a / #11](https://github.com/emgiezet/piitier/pull/11))
- A NaN or out-of-range NER threshold now raises immediately instead of silently dropping all NER spans. ([PII-6-a / #11](https://github.com/emgiezet/piitier/pull/11))
- INT8 gate compared INT8 output with INT8 instead of with FP32; the quality delta could never trip. ([PII-7 / #10](https://github.com/emgiezet/piitier/pull/10))
- Corpus metrics matched spans across documents; now per-document; error was ≤ 0.001 F1. ([PII-7 / #10](https://github.com/emgiezet/piitier/pull/10))
- Calibration sweep now filters window spans at the candidate threshold before merging windows, matching `NerPredictor.predict` exactly. ([#19](https://github.com/emgiezet/piitier/pull/19))

### Known limitations

- `uv.lock` is excluded from `piitier scan` because NIP/PESEL/REGON rules fire inside package hashes; no fix yet.
- No frozen `bench/v1/test` split: the full test set needs human annotators.
- INT8 ONNX passes the recall gate for `pii-5-v4` (delta 0.0054) but had failed for `pii-5-v3`; the gate is still the single arbiter per checkpoint.
- TUI button labels are Polish (`Maskuj kolumny`, `Anonimizuj`).

---

[0.1.0]: https://github.com/emgiezet/piitier/compare/605dacbc3e1ca4560c4a9094d773ca45827a472e...v0.1.0
[Unreleased]: https://github.com/emgiezet/piitier/compare/v0.1.0...release/0.1.0
