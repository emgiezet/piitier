# Dataset card: synthetic Polish PII corpus (piitier)

## Dataset purpose
Trains and evaluates NER and sensitive-data detection models (NER / PII anonymisation) for Polish across fintech, insurtech, and medtech domains. All data are 100% synthetic, generated from templates and code generators with augmentation and hard-negative sampling.

## JSONL schema
Each record in `train.jsonl` and `dev.jsonl` is a JSON object with the following fields:
- `id` (string): Unique document identifier (e.g. `doc_0000000` for template-based documents, `hn_0000000` for hard negatives).
- `doc_type` (string): Document type (e.g. `polisa`, `umowa_kredytowa`, `wypis_szpitalny`, `mail_klienta`, `wyciag`, `skierowanie`, `zgloszenie_szkody`, `transkrypcja_infolinii`, `raport_towarzystwa`).
- `template_id` (string): Identifier of the base template or unique negative identifier.
- `seed` (int): Random-generator seed (`random.Random`) used to render the document.
- `text` (string): Full text content of the document.
- `spans` (list of objects): List of matched spans, each containing:
  - `start` (int): Character-level start offset (inclusive).
  - `end` (int): Character-level end offset (exclusive).
  - `label` (string): PII label (e.g. `PESEL`, `ADRES`, `OSOBA`, etc.).
  - `entity` (string | null): Entity identifier for cross-span correlation (e.g. `"1"`).
  - `text` (string): Exact substring covered by the span (`text[start:end] == span["text"]`).

## Sources and licences
1. **Faker (`pl_PL`)**:
   - Used to generate first names, surnames, addresses, and cities.
   - Licence: **MIT**.
2. **Morfeusz 2**:
   - Used to inflect surnames and nouns in the appropriate grammatical cases.
   - Licence: **BSD-2-Clause**.
3. **In-repository authored lists**:
   - Curated list of ICD-10 codes, medical drugs (INN), diagnosis terms, and identifiers.
   - Licence: Original work (within the piitier project).
4. **Local language models (Ollama, local hardware only)**:
   - `SpeakLeash/Bielik-11B-v3.0-Instruct-GGUF` (`write-templates`) authored the text of templates for 8 original document types with PII placeholders. Output containing an actual value instead of a placeholder is rejected.
   - `qwen3-coder:30b` (`templatize`) is used solely as a span detector on the text of insurance-policy PDFs: it returns a JSON list of literal fragments with a label (`text`, `label`); the code verifies that each fragment appears verbatim and replaces it with a placeholder itself.
   - No LLM generates PII values or assigns span labels in the corpus; values are injected by code.
5. **Insurance-policy PDF files (layout donors)**:
   - Origin: internal document collection (wefox, PZU, Inter Partner Assistance/AXA policies) with **fictitious identities** (not real personal data, though they closely resemble it); approved for training by the data owner; never redistributed.
   - Text is extracted with `pypdf`, normalised (NBSP→space, fi/fl ligature substitution, multiple-space collapsing) and passed to a local LLM (`qwen3-coder:30b` via Ollama), which **only identifies spans** for replacement; code rules replace each value with a `{{LABEL}}` placeholder. The acceptance gate (`_gate`) rejects any fragment whose literals retain anything shaped like a PII value: it checks parsing, leaks (9+ digits, dates outside a birth-date context, card numbers, IBANs, postal codes), and label shape.
   - Derived templates (`templates/polisa/polisa_pdf_<hash>.txt`) **are not included in the repository** (`.gitignore`; CLAUDE.md invariant 2: employer and client documents never enter the repo): they are generated locally from legally permitted PDFs via `python -m piitier.datagen templatize`. A clean clone contains only the hand-written `polisa` templates; a corpus rebuilt without the derived local templates will differ from the historical `data/synthetic/v0.3`.
   - Source licence: **proprietary, not redistributed**. Derived templates are approved for training by the data owner and represent only the layout of the documents without any original values. The output synthetic dataset is published under **CC BY 4.0** solely as a product of code generators and generative models, not of the original PDFs.

6. **Insurance-company reports (synthetic templates)**:
   - The repository contains three hand-written `raport_towarzystwa_01..03.txt` templates: a policy-portfolio report, a claims-settlement report, and a property-coverage review. The layout and dates are fictional; these are not documents received from insurers.
   - `python -m piitier.datagen templatize-tables` can locally convert approved XLSX/CSV reports into templates with placeholders. It maps column headers to PII labels; agent identifiers and logins are skipped, and the acceptance gate rejects literals shaped like PII values. Derived templates remain local (`.gitignore`); they are not part of the distributed dataset.

## Output licence
The output synthetic dataset (`train.jsonl` / `dev.jsonl`) is released under **CC BY 4.0** (Creative Commons Attribution 4.0 International). The licence covers only the synthetic data produced by code and language models. Derived templates from non-distributed PDFs/XLSX/CSV files are not redistributed; they remain local (`.gitignore`), never in the repository, neither as raw documents nor as extracted source text.

## Augmentation
When `--augment` is active, each document is augmented independently with a given probability (`augment_fraction`, default 0.25). For documents selected for augmentation, a random **non-empty** subset of transformations is applied:

| Transformation | Inclusion probability |
|---|---|
| `ocr_confusions` (swap 0↔O, 1↔l) | 0.5 |
| `space_digit_groups` (insert spaces in digit groups) | 0.5 |
| `strip_diacritics` (remove Polish diacritics) | 0.5 |
| `uppercase` (convert to upper case) | 0.3 |

Both choices are fully deterministic; the per-document seed is `seed + i`. The manifest records: `augment_fraction`, `augmented_doc_count` (number of documents actually augmented), and `transform_doc_counts` (number of documents to which each transformation was applied).

**Rationale:** corpus v0.1 was augmented 100% (every document, all transformations), which caused a style leak (the model learned to identify upper-case versions as PII even without context). Fractional augmentation with a random subset of transformations reduces this effect and keeps data diversity.

## Reproducibility
The dataset is fully deterministic. Using the same seed (`seed`), version of the `piitier` library, and set of templates guarantees identical output files (byte-for-byte, verified by SHA-256 checksum). The `build` command allocates templates via round-robin across document types (sorted lexicographically): iteration `i` selects type `doc_types[i % len(doc_types)]`, and within a type templates cycle in order.

Split rule: `sha256(template_id) % 10 == 0 → dev`, all others → `train`. Additional guarantee: if all templates of a given document type would be assigned to `dev`, the entire type is force-redirected to `train` (training-coverage guarantee). Types for which this correction was applied are recorded in `manifest.json` under the key `split_forced_train`. The mechanism is deterministic and independent of the `n` and `seed` parameters.

## Full run (orchestrator instructions)
To run a full production build (20,000 template documents + 2,000 hard negatives, fractional augmentation):

```bash
python -m piitier.datagen build \
  --templates src/piitier/datagen/templates \
  --n 20000 \
  --seed 42 \
  --augment \
  --augment-fraction 0.25 \
  --hard-negatives 2000 \
  --out data/synthetic/v0.3/
```

## Run statistics (full run, piitier 0.1.0, seed 42)
> - Documents: 22,000 total (20,000 template-based + 2,000 hard negatives), split: `train` 21,283, `dev` 717; `augment: true`.
> - `span_counts`: KWOTA 38920, OSOBA 28428, PESEL 18466, IBAN 17056, NR_POLISY 16725, NIP 11388, NR_DOWODU 11143, REGON 6771, ADRES 6003, NR_KARTY 4455, NR_REJESTRACYJNY 3252, MIEJSCOWOSC 3020, NAZWISKO 2840, IMIE 2705, KOD_POCZTOWY 2653, TELEFON 2468, VIN 2283, PLACOWKA 2222, LEKARZ 2222, NPWZ 2222, LEK 2222, EMAIL 1451, DATA_URODZENIA 1259, NR_SZKODY 1205, NR_UMOWY 1111, NR_KW 1111, ROZPOZNANIE 1111, ICD10 1111.
> - SHA-256: `train.jsonl` `1530afd5a5f5a2efb116cd3a12742165c88cdadd6cc878b5967b1ea9554c1a98`, `dev.jsonl` `36c757419e978b2ed8d1cf8450bb52edc95676d32a9778528316bc7b4df9c752`; offsets verified (`check` → 0).
