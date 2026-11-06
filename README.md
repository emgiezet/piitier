# piitier

Polish PII anonymiser for regulated sectors (fintech, insurtech, medtech). It combines deterministic
checksum validators, a fine-tuned NER model and a placeholder renderer that never changes a character
outside the detected spans.

**Status: pre-release (0.1.0).** The library, CLI, training and evaluation pipeline work. The model is not
published yet. This is not a certificate of anonymisation.

## What it does

```text
$ piitier mask zgloszenie.txt --model training/out/pii-5-v3
Zgłoszenie szkody z dnia 12.03.2025.
Poszkodowana [IMIĘ_n] [NAZWISKO_n], zam. [ADRES_n], PESEL [PESEL],
tel. [TELEFON], e-mail [EMAIL]. Rozpoznanie: [ROZPOZNANIE].
Kwota roszczenia: [KWOTA]. Lekarz prowadzący: [LEKARZ_n].
```

Without `--model` only the deterministic rules run, and the same document becomes
`… Poszkodowana Anna Wiśniewska, zam. ul. Lipowa 14/3, 30-001 Kraków, PESEL [PESEL], …`.

Guarantees the code is built around (`CLAUDE.md`, "Invariants"):

- **Text fidelity.** The output differs from the input only inside `[start, end)` spans of the original
  string. A property-based test pins this at exactly 0 changed characters.
- **Recall first.** A structured identifier that fails its checksum is marked `suspect` and still masked,
  never dropped.
- **No generative output.** No LLM writes the masked text; models only propose spans.
- **Rules win on identifiers.** A checksum-valid rule span (PESEL, NIP, REGON, IBAN, ID card, payment
  card) beats any overlapping model span.

The 39 entity types in 6 risk groups, their placeholders and risk weights are defined in
[`docs/TAXONOMY.md`](docs/TAXONOMY.md), the single source of truth for labels.

## Installation

Python 3.12 and [uv](https://docs.astral.sh/uv/). Windows and Linux need x86-64: the pinned
`morfeusz2` wheels cover only `win_amd64`, macOS universal2 and manylinux x86-64, so Windows on ARM
and Linux on ARM cannot resolve the lockfile.

### Linux and macOS

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # if uv is missing
uv python install 3.12
uv sync                                           # runtime + dev dependencies (incl. torch/transformers for the NER)
uv run piitier --help
```

### Windows (PowerShell)

```powershell
winget install --id=astral-sh.uv -e
# or: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv python install 3.12
uv sync
uv run piitier --help
```

- Quote what PowerShell would otherwise consume: `--delimiter ";"`, `--skip-columns "PESEL,2"`.
  `--delimiter "\t"` reaches the CLI as the two literal characters it expects.
- Write results to a file (`-o out.txt`, `-o out.xlsx`). PowerShell's `>` re-encodes a command's
  stdout (UTF-16 in Windows PowerShell 5.1), and a legacy console code page cannot print every
  character a Polish document holds; for console output run `chcp 65001` or set
  `$env:PYTHONIOENCODING = "utf-8"` first.
- Development: `uv sync --frozen`, then
  `uv run pre-commit install --hook-type pre-commit --hook-type pre-push` and
  `uv run pytest -q -m "not integration"`, the gate CI runs. The gitleaks hook is a Go hook that
  pre-commit builds on first run; install Go if that step fails.
- `--device cuda` needs a CUDA build of torch. Check with
  `uv run python -c "import torch; print(torch.version.cuda)"` and install a CUDA wheel from the
  PyTorch index if it prints `None`. CI and the training workstation are Linux.

## Quick start

```bash
uv run piitier mask document.pdf          # rules only; .txt .md .csv .pdf (with a text layer) .xlsx
uv run piitier mask document.pdf -o out.txt --model <checkpoint-dir> --threshold 0.0
uv run piitier mask document.csv --skip-columns "PESEL,2"  # header names or 1-based indices
uv run piitier mask document.csv --skip-columns "ID" --delimiter ";"  # override auto-detection
uv run piitier compare document.csv --model <checkpoint-dir> --device cuda  # TUI: choose columns, mask, export
uv run piitier mask raport.xlsx                             # sheets rendered as text on stdout
uv run piitier mask raport.xlsx -o raport_anon.xlsx         # masked workbook, cell values only
uv run piitier mask raport.xlsx -o out.xlsx --skip-columns "Nr polisy,2"
uv run piitier compare raport.xlsx --model <checkpoint-dir> # TUI: columns, mask, export .xlsx
```

Exit code 2 means a usage or input error (missing file or model, invalid threshold). Errors name the path,
never document content.

Skipped CSV columns retain their original text; unknown columns emit a warning on stderr without
stopping masking. A detection spanning a skipped and an unskipped cell is still masked.
`--skip-columns` on files other than CSV and XLSX, and `--delimiter` on files other than CSV,
exit 2.

XLSX input reads every worksheet. `-o <name>.xlsx` writes a masked workbook: only cell values
change, so sheets, column widths, number formats and formulas stay; openpyxl drops charts, images,
pivot tables and VBA on save. Formulas and sheet names are never masked, a masked numeric cell
becomes text, and a detection spanning two cells is masked in both. `--skip-columns` matches row-1
headers of any sheet, or a 1-based index in every sheet. Any other output (stdout, `-o out.txt`)
is the rendered text: `# <sheet>` and one line per row with cells joined by ` | `. `piitier scan`
still skips binary files, so it does not look inside a workbook.

The `compare` TUI requires a local model. For CSV and XLSX it first shows a table preview (up to
50 rows; the first sheet of a workbook) on the left and per-column **Maskuj kolumny** checkboxes on
the right. All columns are selected for masking by default; uncheck any columns to leave them
unchanged (in every sheet of a workbook), then choose **Anonimizuj**. The comparison screen exports
alongside the source with an editable filename (default `<name>_anonymised.csv` or
`<name>_anonymised.xlsx`), without overwriting an existing file. Other files open the original
comparison view directly. The CLI `mask --skip-columns` still selects columns to leave unchanged.

`piitier scan <files>…` lists checksum-valid identifiers as `path:line:column: LABEL` without printing the
value, and exits 1 if any are not in `--allowlist`. Use it to check files before sharing them.

## Python API

```python
import piitier

text = "Poszkodowana Anna Wiśniewska, PESEL 44051401359."

# Rules only; importing piitier never loads torch.
piitier.mask(text)
# -> 'Poszkodowana Anna Wiśniewska, PESEL [PESEL].'
piitier.detect(text)
# -> [Span(start=36, end=47, label=<Label.PESEL: '[PESEL]'>, source='rule',
#          score=1.0, status='valid')]

# Rules + NER; the model is loaded once, in the constructor.
anon = piitier.Anonymizer(model="training/out/pii-5-v3", threshold=0.0)
anon.mask(text)
# -> 'Poszkodowana [IMIĘ_n] [NAZWISKO_n], PESEL [PESEL].'
```

For CSV text, `piitier.mask_csv(text, skip_columns=["ID"], delimiter=";")` masks detections
outside the selected column. Omit `delimiter` to auto-detect it; optional `detector` and
`on_unknown_column` callbacks customize detection and missing-column handling.

For workbooks, `piitier.xlsx.mask_workbook` writes the masked copy; `piitier/__init__.py` does not
re-export it, so `import piitier` stays free of openpyxl:

```python
from pathlib import Path

import piitier
from piitier.xlsx import mask_workbook

mask_workbook(Path("raport.xlsx"), Path("out.xlsx"), detector=piitier.detect)
```

It takes the same `skip_columns` and `on_unknown_column` arguments as `mask_csv`; pass
`detector=anon.detect` for rules + NER.

`Anonymizer` also accepts `predictor=` (any object with `predict(text) -> list[Span]`) instead of a model
directory. Fusion of rule and model spans is in [`src/piitier/fusion.py`](src/piitier/fusion.py).

## Model

| | |
|---|---|
| Current checkpoint | `pii-5-v3`, local only (`training/out/` is gitignored, not yet on the Hugging Face Hub) |
| Base | [`bardsai/eu-pii-anonimization-multilang-v2`](https://huggingface.co/bardsai/eu-pii-anonimization-multilang-v2), ModernBERT 307M, Apache-2.0, revision `5e61416e` |
| Training data | synthetic corpus `data/synthetic/v0.3` (19 637 train / 2 363 dev documents), see [`docs/DATASET_CARD.md`](docs/DATASET_CARD.md) |
| Config | [`training/configs/pii-5-v3.yaml`](training/configs/pii-5-v3.yaml) |

Results so far:

- `bench/v1/dev` (6 hand-written documents, 40 gold spans): **0/40 PII values leaked** (base model 2/40). See
  [`eval/reports/2026-10-25-trening-pii-5.md`](eval/reports/2026-10-25-trening-pii-5.md).
- Synthetic dev (2 363 documents), FP32 ONNX, strict matching per document: F1 0.912, recall 0.944.
- **INT8 export is blocked.** Dynamic INT8 quantisation drops recall to 0.926 (−0.018), above the 0.01
  tolerance, so `training.export_onnx` exits 1.

## Training and evaluation

```bash
uv run python -m piitier.datagen build --templates src/piitier/datagen/templates --n 20000 --seed 42 --out data/synthetic/<version>/
uv run python -m piitier.datagen check data/synthetic/<version>/

uv run python -m training.train      training/configs/<run>.yaml   # HF Trainer + seqeval; config is the only input
uv run python -m training.calibrate  training/configs/<run>.yaml   # recall-first threshold on dev
uv run python -m training.export_onnx training/configs/<run>.yaml  # FP32 + INT8 ONNX, blocks on recall drop

uv run python -m eval.run --system rules --bench v1 --split dev    # report in eval/reports/
```

Benchmark systems (`eval/baselines/`): `rules`, `ner` (`--checkpoint`), `presidio` (regex recognisers, no
spaCy model), `bardsai-v2`, `privacy-filter` (`openai/privacy-filter`). Reports cover strict and partial
P/R/F1 per label, risk-weighted recall, leak rate, fidelity, numbering consistency and throughput.

Train on the RTX 3090 Ti alone. `training.train` pins a single GPU when several are visible, because mixing
cards in one job is forbidden by `.claude/playbooks/model-training.md`.

## Data policy

- Only synthetic documents enter the repository. Employer or client documents never do.
- Templates derived from internal documents (`raw_data/`, `templatize`, `templatize-tables`) stay local and
  are gitignored. A clean clone builds its corpus from the hand-written templates only.
- `bench/<version>/test/` is the frozen gold split. It is never used for training, calibration or prompt
  examples, and the config loader rejects it. `bench/v1` currently has only `dev/`.

## Repository layout

| Path | Contents |
|---|---|
| `src/piitier/` | library: `rules/` (checksum validators), `ner/` (inference), `fusion.py`, `render.py`, `loaders.py`, `csvskip.py`, `xlsx.py`, `cli.py`, `tui.py`, `datagen/` |
| `training/` | fine-tuning, calibration and ONNX export, driven by `training/configs/*.yaml` |
| `eval/` | metrics, baseline adapters, benchmark runner and reports |
| `bench/` | PL-PII-Bench gold set (versioned) |
| `docs/` | plan, `TAXONOMY.md`, `DATASET_CARD.md` |
| `specs/` | one directory per ticket: `spec.md` with UC acceptance criteria, QA and PR records |

## Development

```bash
uv sync --frozen
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
uv run pre-commit run --all-files          # gitleaks, private keys, ruff, mypy, piitier scan
uv run pytest -q -m "not integration"      # unit tests, no network (also run on push)
uv run pytest -q -m integration            # downloads checkpoints from the Hugging Face Hub
```

CI (`.github/workflows/ci.yml`) runs the hooks and unit tests on every pull request and push to `main`.
A new checksum-valid identifier in any committed file fails the `piitier-scan` hook unless its fingerprint
is in `.pii-allowlist`; only synthetic values may be allowlisted.

Work is specced first: every change has a `specs/<TICKET>/spec.md` whose `UC-<n>` ids appear in test names.
Agents and humans follow [`CLAUDE.md`](CLAUDE.md) (task router, invariants) and
[`.claude/rules/python.md`](.claude/rules/python.md). Results and decisions so far are summarised in
[`FINDINGS.md`](FINDINGS.md).

## Known limitations

- Placeholders are not numbered yet: every person is `[OSOBA_n]` (coreference is PII-6-b).
- No `pseudonymize` mode with a reversible encrypted map yet (PII-6-c).
- The NER can split one word across two entity types (`[NAZWISKO_n][OSOBA_n]`), issue #2 in the local tracker.
- `bench/v1` has 6 documents; the planned gold set is 300–500 documents with a frozen `test/` split.
- Threshold calibration targets strict recall ≥ 0.98, which pii-5-v3 does not reach (strict recall 0.944 on
  synthetic dev), so the threshold stays at 0.0.
- `torch`/`transformers` are dev dependencies, so `pip install piitier` gives rules-only masking.
- Quasi-identifiers (job title, employer, event dates) and colloquial health data are outside the MVP
  taxonomy.

## License

Apache-2.0; see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE). The base model is Apache-2.0.
