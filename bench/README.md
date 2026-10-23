# PL-PII-Bench v1

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

## Splits Policy

- `dev/`: Development split used for model tuning, threshold calibration, and baseline evaluation. Visible during development.
- `test/`: Test split frozen once version published. Created strictly at publication time to prevent data leakage and overfitting (CLAUDE.md invariant 7).

## License

This dataset and benchmark corpus are released under the **Creative Commons Attribution 4.0 International (CC BY 4.0)** license.
