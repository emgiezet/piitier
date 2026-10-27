---
license: apache-2.0
base_model: bardsai/eu-pii-anonimization-multilang-v2
language:
  - pl
pipeline_tag: token-classification
library_name: transformers
tags:
  - pii
  - anonymization
  - gdpr
  - ner
  - polish
  - modernbert
model-index:
  - name: emgiezet/piitier-pl
    results:
      - task:
          type: token-classification
          name: Named Entity Recognition
        dataset:
          name: PL-PII-Bench v1 dev
          type: pl-pii-bench
          split: dev
        metrics:
          - type: precision
            value: 0.6383
            name: Strict Micro Precision
          - type: recall
            value: 0.7500
            name: Strict Micro Recall
          - type: f1
            value: 0.6897
            name: Strict Micro F1
          - type: f1
            value: 0.7586
            name: Partial Micro F1
          - type: recall
            value: 0.7744
            name: Risk-weighted Recall
          - type: other
            value: 0
            name: Leaked docs (bench/v1/dev)
          - type: other
            value: 0
            name: Leaked values (bench/v1/dev)
---

# piitier-pl — Polish PII Anonymisation (pii-5-v4)

## Model description

**piitier-pl** is a `ModernBertForTokenClassification` fine-tuned for Polish PII detection
and anonymisation. It recognises **39 entity types** encoded as **79 BIO tags** (78 B-/I-
tags + O).

### Entity types

`ADRES`, `CVV`, `DANE_ZDROWOTNE`, `DATA_URODZENIA`, `DOCHOD`, `EMAIL`, `GEO`, `IBAN`,
`ICD10`, `IMIE`, `IP`, `KOD_POCZTOWY`, `KWOTA`, `LEK`, `LEKARZ`, `MIEJSCOWOSC`,
`NAZWISKO`, `NIP`, `NPWZ`, `NR_DOKUMENTACJI`, `NR_DOWODU`, `NR_KARTY`, `NR_KW`,
`NR_PASZPORTU`, `NR_POLISY`, `NR_PRAWA_JAZDY`, `NR_RACHUNKU`, `NR_REJESTRACYJNY`,
`NR_SZKODY`, `NR_UMOWY`, `OSOBA`, `PESEL`, `PLACOWKA`, `PLEC`, `REGON`, `ROZPOZNANIE`,
`TELEFON`, `VIN`, `WIEK`

### Lineage

| Stage | Checkpoint | Data | Steps |
|---|---|---|---|
| Base | `bardsai/eu-pii-anonimization-multilang-v2` rev `5e61416e77675881185767fc0c67759d48b35592` | — | — |
| pii-5-v3 | local `training/out/pii-5-v3` | `data/synthetic/v0.3/train.jsonl` (19 637 docs) | 1 300 |
| pii-5-v4a | local `training/out/pii-5-v4a` | `data/synthetic/v0.3-medical/train.jsonl` (19 637 + 4 000 medical docs) | 2 200 |
| **pii-5-v4** | **this model** | `data/synthetic/v0.3-medical-contrast/train.jsonl` (23 637 + 4 000 contrastive docs) | 2 200 |

Source: `training/configs/pii-5-v3.yaml`, `training/configs/pii-5-v4a.yaml`,
`training/configs/pii-5-v4.yaml`.

### Weights checksum

SHA-256 of `model.safetensors` (shipped):
`94d43a6effabd3c3b1500d8f20f9d136aa77b39f2f4fb01fcf51dedd062fc94c`

Source: `eval/reports/pii-5-v4/2026-10-27-ner-benchv1-dev.md`.

The intermediate `pii-5-v4a` checkpoint is local-only and not distributed; its
`model.safetensors` was not available at release time (no sha256 recorded).

### Formats

- **safetensors** (FP32): primary.
- **FP32 ONNX** (`onnx/model.onnx` + `onnx/model.onnx.data`): strict F1 0.9832, recall 0.9868
  on `data/synthetic/v0.3/dev.jsonl` (2 363 documents) at threshold 0.78.
- **INT8 ONNX** (`model_int8.onnx`, dynamic quantisation, 310 MB): strict F1 0.9745, recall
  0.9814 on the same split. Recall delta against FP32 is 0.0054, inside the 0.01 tolerance,
  so the export gate passed for this checkpoint. The earlier `pii-5-v3` INT8 export failed
  the same gate (delta 0.018). Source: `training/out/pii-5-v4/export_report.json`, copied
  to this repository as `export_report.json`.

---

## Intended use and out-of-scope

**In scope:** detection and masking of personal data in Polish-language insurance, banking,
and medical documents, for GDPR-compliance workflows.

**Out of scope:**
- Languages other than Polish.
- Pseudonymisation (replacement with consistent surrogates) — the model masks only.
- Coreference numbering (same entity across a document gets the same mask token) — not
  implemented; all spans are numbered independently.
- Quasi-identifiers (combinations of non-PII attributes that identify a person together).
- Non-textual PII (images, scanned PDFs without OCR).
- Fully autonomous anonymisation pipelines without human review.

---

## How to use

### With `piitier` (recommended)

The `piitier` package adds a **rule layer** (checksum-valid identifiers: PESEL, IBAN, NIP,
NPWZ, NR_KARTY, …) on top of the NER output, a risk-weighted fusion strategy, and a
span renderer. Rules win over the NER model on any overlapping identifier span.

**CLI:**
```bash
piitier mask file.txt --model emgiezet/piitier-pl --threshold 0.78
```

**Python API:**
```python
from piitier import Anonymizer

anon = Anonymizer(model="emgiezet/piitier-pl", threshold=0.78)
result = anon.mask("Jan Kowalski, PESEL 44051401359, zam. Warszawa")
print(result.text)
```

### With plain `transformers`

> **Note:** using `transformers` directly bypasses the rule layer and renderer.
> The rule layer catches checksum-valid identifiers that NER may miss or mis-label.
> For production anonymisation use the `piitier` API above.

```python
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline

model_id = "emgiezet/piitier-pl"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForTokenClassification.from_pretrained(model_id)

ner = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")
spans = ner("Jan Kowalski, PESEL 44051401359, zam. Warszawa")
# Filter by score >= 0.78 to match the calibrated threshold
spans = [s for s in spans if s["score"] >= 0.78]
```

---

## Evaluation

### Synthetic calibration split

| Metric | Value | Source |
|---|---|---|
| Documents | 1 031 | `training/configs/pii-5-v4.yaml` |
| Gold spans | 14 766 | `eval/reports/pii-5-v4/calibration_sweep.json` |
| Threshold | 0.78 | `training/configs/pii-5-v4.yaml` |
| Strict Recall | **0.9866** | `eval/reports/pii-5-v4/calibration_sweep.json` |
| Strict Precision | **0.9711** | `eval/reports/pii-5-v4/calibration_sweep.json` |
| Wilson 95% CI (recall) | [0.9846, 0.9883] | `training/out/pii-5-v4/MODEL_CARD.md` |
| Leaked values | **0** | `eval/reports/pii-5-v4/calibration_sweep.json` |

Risk-group recall on calibration (source: `training/out/pii-5-v4/MODEL_CARD.md`):

| Group | Recall | Spans |
|---|---|---|
| State identifiers | 1.0000 | 1 167 |
| Finance | 1.0000 | 3 159 |
| Insurance | 0.9959 | 1 455 |
| Contact and location | 0.9896 | 3 185 |
| Health — Art. 9 GDPR | 0.9981 | 2 664 |
| Person identification | 0.9509 | 3 136 |

### bench/v1/dev

6 hand-written documents, 40 gold spans.
Source: `eval/reports/pii-5-v4/2026-10-27-ner-benchv1-dev.md`.

| Metric | Value |
|---|---|
| Strict Precision | 0.6383 (TP=30, FP=17, FN=10) |
| Strict Recall | 0.7500 |
| Strict F1 | 0.6897 |
| Partial F1 | 0.7586 |
| Risk-weighted Recall | 0.7744 |
| Leaked docs | 0 / 6 |
| Leaked values | 0 / 40 |
| Base model leaked values | 2 / 40 |

**Evaluation independence caveat:** `bench/v1/dev` was the **safety gate** for threshold
selection — the threshold 0.78 was chosen in part because it yields 0/40 leaked values on
this split (thresholds ≥ 0.98 leaked 8/40 values on the same split). No frozen test split
exists yet. These numbers are **not independent** of the threshold choice and should not
be treated as held-out test performance.

#### Per-label weak spots (strict, bench/v1/dev)

| Label | Issue |
|---|---|
| IMIE | 5 FP, 0 TP (0 gold) — false-positive hallucination |
| NAZWISKO | 4 FP, 0 TP (0 gold) — false-positive hallucination |
| OSOBA | Recall 0.2857 (2 TP, 5 FN) — multi-token full names frequently missed |
| DANE_ZDROWOTNE | 0 TP, 2 FP, 1 FN — no correct predictions |
| PLACOWKA | 0 strict TP (1 FN, 1 FP) — partial match only |

Note: IMIE/NAZWISKO FPs arise partly because training templates annotate full names both
ways (IMIE + NAZWISKO separately vs. OSOBA); the bench uses OSOBA throughout.
Source: `FINDINGS.md` (Data section).

### Throughput

31.18 docs/s, P95 latency 0.1085 s (NVIDIA RTX 3080, single-process inference).
Source: `eval/reports/pii-5-v4/2026-10-27-ner-benchv1-dev.md`.

---

## Training data and provenance

- **Synthetic corpus** (`data/synthetic/v0.3` and extensions): CC BY 4.0. Generated from
  publicly distributed templates shipped in this repository.
- **Layout-donor documents:** some templates were derived from insurance documents owned
  by the author (Max Małecki), who also owns and releases these weights. Those documents
  carried fictitious identities; the derived templates keep only layout, every value is a
  `{{LABEL}}` placeholder, and they are **not redistributed** (gitignored). No third-party
  data licence applies to the weights. A clean clone of this repository cannot exactly
  reproduce the `v0.3` corpus or the calibration split (see `FINDINGS.md`, "Rebuild the
  local calibration split" section).
- The calibration split (1 031 docs) was built with seed 900042 from 338 templates
  (218 policy, 81 table), with 25 zero-gold duplicate rows removed.

---

## Licence and attribution

Apache-2.0. Derived from
[bardsai/eu-pii-anonimization-multilang-v2](https://huggingface.co/bardsai/eu-pii-anonimization-multilang-v2)
(Apache-2.0, bards.ai).

See `NOTICE`:
> piitier — Copyright 2026 Max Małecki.
> Model checkpoints are fine-tuned from bardsai/eu-pii-anonimization-multilang-v2
> (Apache-2.0, bards.ai) and are distributed separately, each with its own model card.

---

## Known limitations

- **Split-name decoding:** the token decoder can split a single word across two entity
  types (e.g. `Wiśniew` as NAZWISKO + `ska` as OSOBA). Source: `FINDINGS.md`.
- **No coreference numbering:** the same entity appearing multiple times in a document
  receives independent mask tokens; consistent pseudonymisation is not supported.
- **No pseudonymise:** replacement with consistent surrogates is out of scope for v0.1.0.
- **Quasi-identifiers out of scope:** combinations of non-PII attributes (age, postcode,
  occupation) that jointly identify a person are not detected.
- **Polish only:** the base model is multilingual but this fine-tune was trained and
  evaluated on Polish text only.
- **Small bench:** bench/v1/dev contains 6 documents and 40 spans; per-label numbers are
  not statistically stable.
- **IMIE/NAZWISKO annotation mismatch:** training templates use IMIE + NAZWISKO for ~23
  occurrences across 16 templates; bench/v1 uses OSOBA. Unifying templates requires a
  retrain. Source: `FINDINGS.md`.
- **Payment-card false positives:** the rule layer can match Luhn-valid 16-digit runs
  inside decimals or lock-file hashes. Source: `FINDINGS.md`.

---

This is not a certificate of anonymisation.
