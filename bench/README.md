# PL-PII-Bench

PL-PII-Bench v1 is the gold-standard benchmark corpus for evaluating PII anonymisation and detection systems for Polish text in fintech, insurtech, and medtech domains.

## Record Format

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

# PL-PII-Bench v2 (planned)

v2 adds double annotation, adjudication, and twin records (documents without
any direct identifiers that are paired with their PII-bearing counterparts).
v1 records stay unchanged in `bench/v1/`; v2 lives in `bench/v2/`.

## Record Format v2

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
all direct identifiers removed or replaced by non-PII content.  The pair lets
evaluation tools measure false-positive rate on near-identical clean documents.

### Validator

`python -m eval.bench_schema <file>...` validates v2 JSONL files and reports
errors as `<id>: <rule>: <detail>` (no document text).  Exit 0 = valid,
exit 1 = errors, exit 2 = file not found.

## Splits Policy

- `dev/`: Development split used for model tuning, threshold calibration, and baseline evaluation. Visible during development.
- `test/`: Test split frozen once version published. Created strictly at publication time to prevent data leakage and overfitting (CLAUDE.md invariant 7).

## License

This dataset and benchmark corpus are released under the **Creative Commons Attribution 4.0 International (CC BY 4.0)** license.
