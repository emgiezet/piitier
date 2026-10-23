# Spec PII-4-c — Kalibracja progu i eksport ONNX INT8 (`training/`)

## Przegląd

Kalibracja progu detekcji (recall-first, tylko na `dev/`), eksport wytrenowanego
modelu do ONNX (Optimum), dynamiczna kwantyzacja INT8 (onnxruntime), ponowny scoring
INT8 vs FP32 na dev z zapisem delt. Próg zapisywany do konfiguracji uruchomienia
(mutowalny artefakt runa) i sekcji karty modelu.

## Pliki

- `training/calibrate.py` — czysta funkcja kalibracji + CLI
  (`python -m training.calibrate <config.yaml> <predictions.jsonl>`).
- `training/export_onnx.py` — eksport + kwantyzacja + rescore + raport
  (`python -m training.export_onnx <config.yaml>`).
- `tests/training/test_calibrate.py` (UC-75, UC-76 — jednostkowe),
  `tests/training/test_export_onnx.py` (UC-77, UC-78 — integration).

## Format predictions.jsonl (wejście kalibracji)

Rekord = dokument: `{"gold": [{"start": int, "end": int, "label": str}],
"pred": [{"start": int, "end": int, "label": str, "score": float}]}`.
(Produkuje go `training/predict.py`? NIE — w tym slocie predictions produkuje
`NerPredictor.predict` bezpośrednio w CLI calibrate: czyta eval_file z configu,
inferuje modelem `base_checkpoint` + `output_dir` checkpoint jeśli istnieje
(konfiguracyjne pole opcjonalne `predict_checkpoint: null` — jeśli null, używa
`base_checkpoint`). Zapis `predictions.jsonl` do output_dir przed kalibracją.)

## API (dokładne sygnatury)

```python
# training/calibrate.py
@dataclass(frozen=True)
class ThresholdResult:
    threshold: float
    recall: float
    precision: float
    target_met: bool          # czy recall >= target przy wybranym progu

def calibrate_threshold(
    docs: list[DocPrediction],          # (gold: list[Span], pred: list[Span]) — pred z score
    target_recall: float = 0.98,
) -> ThresholdResult:
    """Kandydaci: 0.0 + posortowane unikalne score predykcji (malejąco).
    Dla progu t: spany pred z score >= t; recall/precision strict (eval.metrics —
    re-use z PII-4-d: entity_metrics). Wybierz NAJWYŻSZY próg z recall >= target.
    Żaden próg nie spełnia → ThresholdResult(0.0, recall@0.0, precision@0.0, False).

def write_threshold(config_path: Path, result: ThresholdResult) -> None:
    """Aktualizuje klucz `threshold` w YAML konfiguracji (pozostałe klucze nietknięte,
    komentarze mogą zniknąć — dopuszczalne dla artefaktu runa) i dopisuje sekcję
    `## Kalibracja progu` do <output_dir>/MODEL_CARD.md (tworzy plik, jeśli brak):
    próg, recall, precision, target, liczba dokumentów."""

# training/export_onnx.py
def export_onnx(checkpoint: str | Path, output_dir: Path) -> Path:
    """optimum.onnxruntime.ORTModelForTokenClassification.from_pretrained(checkpoint,
    export=True).save_pretrained(output_dir/'onnx'); zwraca ścieżkę model.onnx.
    Import optimum leniwy."""

def quantize_int8(onnx_path: Path, output_path: Path) -> Path:
    """onnxruntime.quantization.quantize_dynamic(model_input, model_output,
    weight_type=QuantType.QInt8); zwraca output_path."""

def score_checkpoint(checkpoint_or_dir: str | Path, records, threshold: float | None)
    -> tuple[float, float]:   # (f1, recall) strict, przez NerPredictor + eval.metrics

def main(argv: list[str] | None = None) -> int:
    """argv = [config_path]; eksport FP32 z output_dir/checkpoint jeśli istnieje, w
    przeciwnym razie base_checkpoint (błąd jeśli brak — ConfigError); score FP32 vs
    score INT8 na eval_file; zapis export_report.json (fp32_f1, fp32_recall, int8_f1,
    int8_recall, f1_delta, recall_delta) do output_dir; gdy recall_delta >
    int8_recall_tolerance (nowy klucz YAML, domyślny 0.01 gdy absent w config —
    wyjątek: klucz deklarowany jako opcjonalny w schemacie) → exit 1."""
```

## Kryteria akceptacji

- **UC-75**: ręczny fixture (3 dokumenty, gold + pred ze score tak dobranymi, że
  recall 0.98+ osiągalny tylko poniżej pewnego progu) → `calibrate_threshold` zwraca
  dokładnie najwyższy próg spełniający target; weryfikacja arytmetycznie policzona
  w teście.
- **UC-76**: fixture gdzie nawet próg 0.0 daje recall < target → `target_met=False`,
  `threshold=0.0`, recall = osiągnięty (nigdy nie zmyśla sukcesu).
- **UC-77** (integration): `export_onnx` na tiny checkpoint → plik `onnx/model.onnx`
  istnieje i nie jest pusty.
- **UC-78** (integration): pełny `main` na smoke configu: quantize_int8 tworzy plik
  `model_int8.onnx`; `export_report.json` ma wszystkie 6 kluczy; wartości f1/recall
  w [0,1]; tolerance-breach: test jednostkowy `check_recall_delta` (funkcja czysta
  `def exceeds_tolerance(report: dict, tol: float) -> bool`) — delta > tol → True.

## Ograniczenia

- Fala 3: worktree zawiera scalone PII-4-a (NerPredictor) i PII-4-b (config) oraz
  PII-4-d (entity_metrics) — importy działają od startu.
- Kalibracja i rescore czytają WYŁĄCZNIE `eval_file` z configu (loader PII-4-b gwarantuje
  brak `bench/**/test/`).
- INT8 = dynamiczna kwantyzacja wag (QInt8) przez onnxruntime; optimum tylko do eksportu
  (API ORTQuantizer optimum 2.x niestabilne — decyzja: nie używać).
- Testy integration pobierają tiny checkpoint; nie pobieramy bardsai w tym slocie.
- Nie modyfikować `src/piitier/`.

## Weryfikacja

UC-75..78 + blok weryfikacyjny; `uv run pytest -q -m integration tests/training/test_export_onnx.py`.