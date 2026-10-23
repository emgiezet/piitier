# Dekompozycja PII-4 — Trening, kalibracja, eksport ONNX i ewaluacja

Nadrzędny plan: `local://pii-4-training-eval-plan.md` (zatwierdzony). Baza: `origin/main`
(PII-3 w PR #5 — niedotknięty). Gałąź integracyjna: `ai/pii-4-integration`.

## Wspólne kontrakty (obowiązują we wszystkich slice'ach)

- **Span**: frozen dataclass `piitier.spans.Span(start, end, label, source, score, status)`;
  offsety `[start, end)` w oryginalnym tekście; `status ∈ {"valid","suspect"}`. Nigdy drugiej
  struktury spanu.
- **Label**: enum `piitier.labels.Label` (39 typów). Etykieta modelu = `Label` (BIO w treningu,
  dekodowana do `Label` w inferencji). Zakaz string-literaly etykiet.
- **Rekord JSONL** (zestaw danych/bench, identyczny schemat jak datagen):
  `{"id": str, "doc_type": str, "text": str, "spans": [{"start": int, "end": int,
  "label": str, "text": str}]}` (`label` = nazwa enuma). Bench może mieć dodatkowe pola
  metadanych, ale te cztery pola obowiązkowe.
- **UC**: kryteria akceptacji UC-67..UC-92; nazwa testu zawiera id (`test_uc67_...`).
- **Zależności** (dev group, exact pin, dodane w pyproject przez integratora):
  `transformers==5.20.2`, `torch==2.14.1`, `seqeval==1.2.2`, `optimum==2.3.0`,
  `onnxruntime==1.31.0`, `presidio-analyzer==2.2.364`, `pyyaml==6.0.3`.
- **Importy ciężkie** (transformers/torch/presidio/optimum/onnxruntime): leniwie, wewnątrz
  funkcji/metodów, z czytelnym `ImportError`. Testy jednostkowe nigdy nie ściągają modeli;
  wszystko co pobiera checkpoint jest `@pytest.mark.integration`.
- **Weryfikacja slice'a** (z `.claude/rules/python.md`): `uv run ruff format --check .`,
  `uv run ruff check .`, `uv run mypy src`, `uv run pytest -q -m "not integration"`, plus
  `uv run pytest -q -m integration tests/<twoje>` dla plików integration.

## Slice'y

| Slice | Zakres | Zależy od | UC |
|---|---|---|---|
| PII-4-a | `src/piitier/ner/` — inferencja NER: tagi BIO, dekoder spanów, predyktor z oknem | — | UC-67..UC-71 |
| PII-4-b | `training/` — config loader (+guard test/), dataset BIO, trening (Trainer+seqeval) | a | UC-72..UC-74 |
| PII-4-c | `training/` — kalibracja progu, eksport ONNX + INT8, delty | a, b, d | UC-75..UC-78 |
| PII-4-d | `eval/metrics.py` — wszystkie metryki + wagi ryzyka w TAXONOMY.md | — | UC-79..UC-84 |
| PII-4-e | `eval/baselines/` — adaptery Presidio/bardsai/privacy-filter + rejestr | a | UC-85..UC-88 |
| PII-4-f | `eval/run.py` + `bench/v1/dev/` — runner benchmarku, fixture złotego zbioru | a, d, e | UC-89..UC-91 |

Fale: **1** — a, d równolegle; **2** — b, e (worktree powstaje z `ai/pii-4-integration`
po scaleniu fali 1); **3** — f, c (po scaleniu fali 2). Integrator scala każdy
ukończony slice do `ai/pii-4-integration` i dopiero wtedy tworzy worktree zależnych
slice'ów.
## Fakty zweryfikowane (2026-10-23)

- `bardsai/eu-pii-anonimization-multilang-v2`: ModernBERT 307M, Apache 2.0, BIO, 35 typów
  (`config.json` odczytany; pełne id2label w specyfikacji PII-4-e).
- `openai/privacy-filter`: token-classification, Apache 2.0, BILOU (BIES), 8 kategorii
  (`config.json` odczytany; 1.4B — nie ściągamy w testach).
- `hf-internal-testing/tiny-random-BertForTokenClassification` istnieje (BertForTokenClassification,
  z eksportem ONNX) — checkpoint smoke.
- Karty GPU na stacji: RTX 3090 Ti + RTX 3080 (trening: 3090 Ti; inferencja/ewaluacja: 3080;
  w testach CPU).
- `piitier.detect(text) -> list[Span]` i `piitier.mask(text) -> str` istnieją w top-level API.