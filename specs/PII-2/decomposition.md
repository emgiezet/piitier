# Decomposition — PII-2

Source: session reply "after PII-1, generate training data with local models on my GPU", plus
`specs/briefs/polish-pii-anonymizer.md` (Decisions) and `.claude/playbooks/synthetic-data.md`.
No `PII-2/spec.md` was ever written; this plan replaces it.

Estimate: ~1700 added lines · ~25 files · ~8 modules (budget 400/15/3)
Seam: walking skeleton. `-a` renders one labelled document from a template, which is the thinnest
path that yields correct training data. `-b` and `-c` widen the value generators, `-d` turns rendering
into a reproducible dataset build, and `-e` lets the local LLM write the templates.

| Slice | Outcome a user or operator can see | UCs | Budget | Depends on |
|---|---|---|---|---|
| `PII-2-a` | `render(template, seed)` returns a document whose spans are exact, for the 6 rule-detected identifiers | UC-1…UC-8 | 350 lines | PII-1-a…e |
| `PII-2-b` | people, addresses, phones and emails from Faker `pl_PL`; one person's PESEL agrees with their birth date and sex | UC-9…UC-14 | 330 lines | `-a` |
| `PII-2-c` | `{{NAZWISKO#1:gen}}` → `Kowalskiego` / `Kowalskiej` via Morfeusz 2 | UC-15…UC-21 | 280 lines | `-b` |
| `PII-2-d` | `python -m piitier.datagen build` writes reproducible `train.jsonl` / `dev.jsonl` / `manifest.json`, split by template | UC-22…UC-29 | 380 lines | `-a` |
| `PII-2-e` | `python -m piitier.datagen write-templates` asks local Bielik (Ollama, loopback only) for templates and rejects any that leak a value | UC-30…UC-37 | 380 lines | `-d` |

Order: -a → (-b → -c) and (-d → -e). The two branches are independent.
After `-d` the build already produces a valid dataset from hand-written templates; `-e` scales templates up,
and `-b`/`-c` widen the labels. Each slice merges on its own.

Recorded design decisions (inferred, confirm on review):
- Template placeholder syntax: `{{LABEL}}`, `{{LABEL#k}}` (entity `k` within one document), and
  `{{LABEL#k:case}}` with case ∈ `nom gen dat acc inst loc voc`. `LABEL` is the `Label` member name.
- The LLM writes templates only. Every value comes from code, so labels are exact by construction
  (CLAUDE.md invariant 5, `synthetic-data.md` step 2).
- LLM-written templates go to `data/templates/<version>/` (gitignored) with a manifest. The dataset build
  is deterministic from templates + seed. LLM output is not reproducible, so it is pinned by storing it,
  not by re-running it.
- The train/dev split is by `template_id`, so no template is in both halves.

Deferred to PII-3 (not written here): generators for insurance and finance IDs (`NR_POLISY`, `NR_SZKODY`,
`NR_UMOWY`, `NR_REJESTRACYJNY`, `VIN`); generators for medical data (`ICD10`, `LEK`, `ROZPOZNANIE`,
`PLACOWKA`, `LEKARZ`, `NPWZ`, which need dictionary sources and licence checks); OCR/diacritic augmentation
with offset recomputation; hard negatives; the full 10–20k-document run; the HF dataset card.
