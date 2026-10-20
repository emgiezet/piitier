# Project: piitier

Polish PII anonymiser for regulated sectors (fintech, insurtech, medtech), published as a model
and dataset on the Hugging Face Hub. The design is a hybrid:
deterministic checksum validators (PESEL, NIP, REGON, IBAN, …) plus a ~300M encoder NER model
plus a deterministic placeholder renderer with consistent numbering. It ships with PL-PII-Bench,
a Polish benchmark. Python 3.12, managed with uv. Training uses HF Transformers; export is ONNX
INT8. Design and roadmap: `docs/Plan MVP polskiego modelu do anonimizacji danych wrażliwych dla
fintech, insurtech i medtech.md`.

## Task Router

Find the row matching your task and read **only** the files it names. Do not preload other
playbooks or rules — loading everything degrades instruction following and burns context you
will need for the code.

| Your task | Read |
|-----------|------|
| Add or fix a regex/checksum detector for an entity type already listed in `docs/TAXONOMY.md` (PESEL, NIP, REGON, IBAN, ID card, Luhn card, policy/claim-number pattern) | `.claude/playbooks/rule-detector.md` |
| Add, rename, or remove an entity type, label, or placeholder, whatever the detection method | `.claude/playbooks/taxonomy-change.md` |
| Change span fusion, coreference/numbering (`[OSOBA_1]` across inflections), or the `mask`/`pseudonymize` renderer | `.claude/playbooks/pipeline-core.md` |
| Generate or change synthetic training documents: templates, Faker injection, OCR/dirt augmentation, hard negatives | `.claude/playbooks/synthetic-data.md` |
| Fine-tune the NER model, calibrate its recall threshold, export it to ONNX, or publish model/dataset to the Hugging Face Hub | `.claude/playbooks/model-training.md` |
| Add a metric or a baseline, or run the benchmark on the gold set | `.claude/playbooks/evaluation.md` |
| Write or fix tests, chase coverage | `.claude/playbooks/testing.md` |
| Deliver an approved spec end-to-end | run `/sdlc:implement <TICKET>` |
| Turn a ticket into a spec | run `/sdlc:spec <TICKET>` |
| Review a pull request | run `/sdlc:review <pr#>` |
| Anything else | this file plus the `.claude/rules/` file for the paths you touch |

`.claude/rules/*.md` are **path-scoped** — they attach automatically to the files you edit, so
you never need to open them from here. Playbooks are **task-scoped**: this table is the only way
in. Keep this table under 12 rows; past that the rows stop being distinguishable and the wrong
one gets picked, which is worse than picking none.

## Layout

Planned layout. Create each directory the first time a task needs it.

- `src/piitier/` — the library: `normalize.py`, `rules/` (validators and detectors), `ner/`
  (model inference), `fusion.py`, `coref.py`, `render.py`, `datagen/` (synthetic documents)
- `tests/` — pytest suite, mirroring `src/piitier/`
- `training/` — fine-tuning, calibration, and ONNX export scripts plus their configs
- `eval/` — metrics, baseline runners, and the benchmark report generator
- `bench/` — the PL-PII-Bench gold set (versioned; the `test/` split is frozen)
- `data/` — generated or downloaded corpora and checkpoints; gitignored, never committed
- `docs/` — the plan; `docs/TAXONOMY.md` is the single source of entity types and placeholders
- `specs/<TICKET>/` — agent-facing specs: `spec.md`, `qa-report.md`, `qa/`, `mockup/`
- `specs/briefs/` — discovery artefacts that precede a spec
- `.claude/sdlc.md` — this project's AI SDLC profile; `.claude/trackers/` — the tracker descriptor

## Invariants

1. Conventional commits: `type(scope): description`.
2. Never commit to `main`. Never commit secrets, `.env` files, or credentials. Never commit real
   personal data: only synthetic documents enter the repo, and employer or client documents never do.
3. All new functionality requires tests. Never delete, skip, or weaken a test to get green.
4. Text fidelity: output may differ from input only inside detected `[start, end)` spans. The
   fidelity test must report exactly 0 changed characters outside spans.
5. No generative output: an LLM never produces the masked text. It may only flag spans, and code
   decides what happens to them.
6. Recall first: a structured ID that fails its checksum is marked `suspect`, never dropped.
7. The gold `bench/**/test/` split is never used for training, threshold calibration, or prompt
   examples.
8. Run the verification commands for every stack you touched before calling a task done. They
   live in the `.claude/rules/` file for that stack.

## Commands

- `uv sync` — install the environment
- `uv run pytest -q` — tests
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src` — lint, format, types
