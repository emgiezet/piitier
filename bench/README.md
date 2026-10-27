# PL-PII-Bench

PL-PII-Bench v1 is the benchmark corpus for evaluating PII anonymisation and detection systems on Polish text across fintech, insurtech, and medtech domains.

## Record format

Each line in `docs.jsonl` is a JSON object with the following schema:

```json
{
  "id": "doc_id_str",
  "doc_type": "polisa | zgloszenie_szkody | umowa_kredytowa | wyciag | mail_klienta | wypis_szpitalny",
  "text": "Full document text in Polish...",
  "spans": [
    {
      "start": 0,
      "end": 10,
      "label": "LABEL_NAME",
      "text": "entity_substring"
    }
  ]
}
```

- `start` and `end`: Half-open character offsets `[start, end)` in `text`.
- `label`: Exact member name of `piitier.labels.Label` enum.


---

# PL-PII-Bench v2

v2 adds double annotation, adjudication, and twin records (documents without
any direct identifiers that are paired with their PII-bearing counterparts).
v1 records stay unchanged in `bench/v1/`; v2 lives in `bench/v2/`.

## Record format v2

Each line in `docs.jsonl` is a JSON object extending the v1 schema:

```json
{
  "id": "doc_id_str",
  "doc_type": "polisa | zgloszenie_szkody | umowa_kredytowa | wyciag | mail_klienta | wypis_szpitalny",
  "text": "Full document text in Polish...",
  "spans": [
    {
      "start": 0,
      "end": 10,
      "label": "LABEL_NAME",
      "text": "entity_substring"
    }
  ],
  "annotations": [
    {
      "annotator": "annotator_id",
      "spans": [
        { "start": 0, "end": 10, "label": "LABEL_NAME", "text": "entity_substring" }
      ]
    }
  ],
  "adjudicated_by": "curator_id",
  "twin_of": "id_of_paired_record_or_null",
  "notes": "Optional free-text annotation notes."
}
```

### Additional v2 fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `annotations` | list | yes | Raw annotations from individual annotators, ≥ 2 per record. Each item: `{annotator, spans}`. |
| `adjudicated_by` | string | yes | ID of the curator who resolved disagreements and produced the gold `spans`. |
| `twin_of` | string \| null | yes | ID of a paired "twin" record, or `null`. Every record with a span whose label is in `DIRECT_IDENTIFIERS` (see `eval/metrics.py`) must have a twin of the same `doc_type` that contains no `DIRECT_IDENTIFIERS` spans. |
| `notes` | string | yes | Free text: adjudication decisions, boundary rationale, etc. Empty string when unused. |

### Twin invariant

A twin record is a document of the same type and comparable structure, but with
all direct identifiers removed or replaced by non-PII content. The pair lets
evaluation tools measure false-positive rate on near-identical clean documents.

### Validator: bench_schema

`python -m eval.bench_schema <file>...` validates v2 JSONL files. Each error
is printed as `line <N>: <rule>: <description>` — no file-supplied value
(label text, annotator id, doc_type, etc.) appears in output.

Exit codes: 0 = valid, 1 = validation errors, 2 = input problem (file not
found, malformed JSON, non-object line, or no arguments).

### Mix rule

No single `doc_type` may exceed 30 % of the records in a file. The rule is
enforced by `bench_schema` on every validation run. A twin pair contributes
two records of the same `doc_type`, so a file needs at least 7 records for
a twin pair to stay at or below 30 % (2/7 ≈ 28.6 %).

### Agreement tool

`python -m eval.agreement <file>` computes inter-annotator agreement from the
first two annotators per record:

- Span F1 strict and partial (overall and per entity label)
- Cohen's kappa over per-character labels (`O` = outside spans), pooled
  across all records. An acceptance gate of kappa ≥ 0.7 is applied.

Output: one `key: value` line per metric, 4 decimal places. No file-supplied
value appears in output; unknown labels cause exit 2.

Exit codes: 0 = kappa ≥ 0.7, 1 = kappa < 0.7, 2 = input error (see above).


## Splits policy

- `dev/`: Development split used for model tuning, threshold calibration, and baseline evaluation. Visible during development.
- `test/`: Test split frozen once version published. Created strictly at publication time to prevent data leakage and overfitting (CLAUDE.md invariant 7).

## License

This dataset and benchmark corpus are released under the **Creative Commons Attribution 4.0 International (CC BY 4.0)** license.
