# PL-PII-Bench — Evaluation Protocol

Version: 1.0 · Status: active

This document defines the metrics, split roles, quality gates, and reporting rules
for all benchmark runs on PL-PII-Bench.  Every published number **must** follow
these rules; non-conforming runs may not appear in model cards or release notes.

---

## Metric Definitions

All metrics are computed span-by-span on character offsets `[start, end)`.
Gold spans come from the benchmark annotations; predicted spans come from
the system under test.

### Entity Precision, Recall, F1

Two match modes are defined:

- **Strict**: a predicted span matches a gold span iff they share the same label
  and identical `[start, end)` offsets.
- **Partial**: a predicted span matches a gold span iff they share the same label
  and their character ranges overlap (i.e. `max(start_g, start_p) < min(end_g, end_p)`).

Matching is greedy and per-document (a span in document B cannot match a gold
span in document A even at identical offsets).

For a given match mode, let TP, FP, FN be the micro-aggregated span counts
across the corpus:

```
Precision  P = TP / (TP + FP)      [undefined when TP + FP = 0]
Recall     R = TP / (TP + FN)      [undefined when TP + FN = 0]
F1           = 2·TP / (2·TP + FP + FN)  [undefined when 2·TP + FP + FN = 0]
```

Both strict and partial variants are reported for every run.

### Risk-Weighted Recall

Entities are assigned to risk groups with the following weights (from `docs/TAXONOMY.md`):

| Grupa | Waga |
|---|---|
| Identyfikatory państwowe | 1.0 |
| Finanse | 1.0 |
| Ubezpieczenia | 0.9 |
| Kontakt i lokalizacja | 0.8 |
| Zdrowie — art. 9 RODO | 0.8 |
| Identyfikacja osoby | 0.6 |

For each document, let `w(g)` be the weight of gold span `g`.  A gold span
is *matched* when there is a strict-match predicted span for it.

```
RWR = Σ w(g) [matched g] / Σ w(g) [all g]

[undefined when the corpus contains no gold spans]
```

### Leak Rate

Two leak-rate metrics are reported:

**Document leak rate** — the share of documents that contain at least one
direct-identifier gold span whose value string-matches the rendered output:

```
Leak_docs = docs_leaked / docs_with_direct_id

[undefined when docs_with_direct_id = 0]
```

where `docs_with_direct_id` is the count of documents that contain at least
one gold span whose label is a direct identifier (PESEL, NIP, REGON, NR_DOWODU,
NR_PASZPORTU, NR_PRAWA_JAZDY, IBAN, NR_RACHUNKU, NR_KARTY, TELEFON, EMAIL, IP,
NR_UMOWY, NR_POLISY, NR_SZKODY, NR_REJESTRACYJNY, VIN, NR_KW, NPWZ, NR_DOKUMENTACJI).

**Value leak rate** — the share of gold PII values that string-match the rendered output:

```
Leak_values = values_leaked / values_total

[undefined when values_total = 0]
```

### Fidelity

Fidelity counts character mismatches *outside predicted spans* between the original
document and the rendered (masked) output:

```
Fidelity = chars changed outside predicted spans
```

The invariant is `Fidelity = 0` for any correctly-implemented system (output
differs from input only inside detected `[start, end)` spans).

### Numbering Consistency

For every label marked `numbered` in `docs/TAXONOMY.md`:

- **Same-entity consistency**: pairs of mentions of the same original value that
  received the same placeholder → fraction consistent.
- **Different-entity distinctness**: pairs of mentions of different original values
  that received different placeholders → fraction distinct.

---

## Split Roles

| Split | Rola | Dozwolone operacje |
|---|---|---|
| `synthetic dev` | Wybór modelu i wstępna ocena | Trening, iteracja, tuning, przegląd wyników |
| `cal` | Kalibracja progu | Wybór progu metodami kalibracyjnymi; nie do tuningu architektury |
| `bench dev` | Rozwój | Ewaluacja w trakcie pracy; raportowanie postępów |
| `bench test` | **Wyłącznie liczby końcowe** | Używany tylko do raportu końcowego lub karty modelu; nigdy do kalibracji ani tuningu |

`bench test` is frozen once a benchmark version is published.
CLAUDE.md invariant 7 applies: the `test` split is never used for training,
threshold calibration, or prompt examples.

---

## Quality Gates

The following gates define minimum standards for a system to be considered
production-ready.  Each gate is evaluated on the designated split.

| Gate name | Metric | Threshold | Split | Condition |
|---|---|---|---|---|
| fidelity-zero | Fidelity | = 0 changed chars | bench test | MUST pass; any non-zero is a blocker |
| doc-leak-rate | Document leak rate | < 1 % (0.01) | bench test | MUST pass; any higher value is a blocker |
| int8-recall-drop | Recall drop FP32 → INT8 | ≤ 0.01 | synthetic dev | MUST pass; larger drop blocks ONNX export |
| calibration-recall | Recall after calibration | ≥ 0.98 | cal | Target; calibration must achieve this on the cal split |

---

## Reporting Rules

1. **Zero denominator = undefined, never PASS.**  When a metric's denominator
   is zero (no predictions, no gold spans, or no documents with direct identifiers),
   the metric is reported as `undefined (0/0)` in Markdown and `null` in JSON.
   An undefined metric **never** satisfies a gate; the gate status is `SKIP`
   (not enough data) rather than PASS or FAIL.

2. **Every report must include provenance metadata:**
   - Git commit SHA (40 hex characters, or `unknown` if git is unavailable).
   - SHA-256 digest of every benchmark file read, keyed by filename.
   - Document count, split name, and detection threshold.

3. **Counts alongside rates.**  Every precision/recall/F1 value in a report must be
   accompanied by the underlying TP, FP, FN counts so that readers can verify
   the arithmetic and aggregate across reports.

4. **`bench test` is final.**  Numbers from `bench test` are the authoritative
   numbers for a model version.  They must not be cherry-picked or re-run after
   seeing them.

5. **Control systems bound the range.**  Every published evaluation should include
   or reference runs of the `none` (zero spans) and `mask-all` (every non-whitespace
   word masked as OSOBA) control baselines so that readers can interpret the scale
   of the reported metrics.
