# Spec PII-4-b — Rdzeń treningu (`training/`)

## Przegląd

Pipeline treningu NER czytający WYŁĄCZNIE plik YAML konfiguracji (zero ukrytych
domyślnych wartości CLI), dataset JSONL w schemacie wspólnym (dekomp. PII-4), tagowanie
BIO z `src/piitier/ner/inference.py` (re-use z PII-4-a), trening HF Transformers
`Trainer` z metrykami seqeval. Walidator konfiguracji odrzuca ścieżki do złotego
splitu `test/` (CLAUDE.md inwariant 7).

## Pliki

- `training/__init__.py` (puste).
- `training/config.py` — loader + walidacja konfiguracji.
- `training/train.py` — dataset + trening (`python -m training.train <config.yaml>`).
- `training/configs/pii-4-smoke.yaml` — konfiguracja smoke (committed).
- `tests/training/__init__.py` (puste), `tests/training/fixtures/smoke_docs.jsonl`
  — 5 syntetycznych dokumentów w schemacie wspólnym (komitujemy; dane syntetyczne).
- `tests/training/test_config.py` (UC-72), `tests/training/test_train.py`
  (UC-73 jednostkowy, UC-74 integration).

## Konfiguracja YAML (dokładny schemat; wszystkie klucze obowiązkowe poza `threshold`)

```yaml
run: pii-4-smoke                  # nazwa uruchomienia = podkatalog training/out/<run>/
base_checkpoint: hf-internal-testing/tiny-random-BertForTokenClassification
base_revision: main
train_file: tests/training/fixtures/smoke_docs.jsonl
eval_file: tests/training/fixtures/smoke_docs.jsonl
seed: 42
max_steps: 1
per_device_batch_size: 2
learning_rate: 5e-5
max_length: 128
output_dir: training/out/pii-4-smoke
threshold: null                   # opcjonalny; wpisuje kalibracja (PII-4-c)
```

## API (dokładne sygnatury)

```python
# training/config.py
@dataclass(frozen=True)
class TrainingConfig:
    run: str
    base_checkpoint: str
    base_revision: str
    train_file: Path
    eval_file: Path
    seed: int
    max_steps: int
    per_device_batch_size: int
    learning_rate: float
    max_length: int
    output_dir: Path
    threshold: float | None


class ConfigError(Exception): ...


def load_config(path: Path) -> TrainingConfig:
    """PyYAML safe_load; brakujący klucz / klucz nieznany → ConfigError z nazwą klucza;
    train_file/eval_file muszą istnieć; odrzucenie gdy resolved ścieżka zawiera część
    'test' POD katalogiem 'bench' (bench/**/test/) → ConfigError;
    wartości: max_steps>0, per_device_batch_size>0, learning_rate>0, 0<max_length<=8192,
    threshold is None or 0<=threshold<=1."""


# training/train.py
def read_jsonl(path: Path) -> list[dict[str, object]]: ...


def build_dataset(records, tokenizer, max_length, label2id) -> torch.utils.data.Dataset:
    """Tokenizuje z return_offsets_mapping=True, truncation=max_length; etykiety z
    piitier.ner.spans_to_token_labels (B-/I- poza zakresem → -100); przechowuje
    input_ids, attention_mask, labels."""


def compute_metrics_factory(label_names: list[str]) -> Callable[[EvalPrediction], dict]:
    """seqeval: precision/recall/f1 na poziomie encji, tryb strict; klucze:
    'precision','recall','f1' (zaokrąglone 4 miejsca)."""


def main(argv: list[str] | None = None) -> int:
    """argv = [config_path] (dokładnie 1; inaczej → exit 2). Ładuje config, ustawia
    seed (random, numpy, torch), Trainer(max_steps z configu, save_strategy='no',
    use_cpu gdy brak CUDA — torch.cuda.is_available()), train, evaluate, zapis
    eval_results.json do output_dir; return 0/1."""
```

BIO labels modelu: `bio_tag_names()` z PII-4-a; model ładowany z
`num_labels=len(bio_tag_names())` przez `AutoModelForTokenClassification.from_pretrained(
checkpoint, revision=..., num_labels=...)` — konfiguracja modelu smoke ma 4 klasy,
nadpisujemy num_labels i label2id/id2label na nasze 79. seqeval w compute_metrics:
precision_score / recall_score / f1_score z seqeval (tryb domyślny strict),
tokeny -100 ignorowane.

## Kryteria akceptacji

- **UC-72**: `load_config` — pełny YAML → pola zgodne; brakujący klucz → ConfigError
  (nazwa klucza w komunikacie); nieznany klucz → ConfigError; nieistniejący plik →
  ConfigError; ścieżka `bench/v1/test/x.jsonl` i symlink do niej → ConfigError;
  ścieżka `bench/v1/dev/x.jsonl` → OK.
- **UC-73**: `build_dataset` test jednostkowy z tokenizerem-stubem o interfejsie
  `__call__(texts, return_offsets_mapping, truncation, max_length)` zwracającym
  deterministyczne offsety; etykiety: tokeny w spanie → B/I wg
  `spans_to_token_labels`, częściowe → O, tokeny ucięte przez max_length → -100
  (test sprawdza dokładne wartości na fixture).
- **UC-74** (integration): `main([smoke_config])` na CPU — 5 dokumentów, 1 krok;
  `eval_results.json` w output_dir ma klucze precision/recall/f1; exit code 0.
  Test kopiuje YAML do tmp z nadpisanym output_dir, żeby nie zostawiać artefaktów w repo.

## Ograniczenia

- Zero sieci w testach jednostkowych (UC-72, UC-73). UC-74 integration pobiera tiny
  checkpoint (~2 MB).
- Trening deterministyczny: seed z configu ustawiany w `main` (random/numpy/torch).
- Nie modyfikować `src/piitier/` — slice re-używa `piitier.ner.spans_to_token_labels`
  i `bio_tag_names` (PII-4-a scalone przed startem tego slice'a; patrz dekompozycja,
  fala 2).
- `mypy` bramka obejmuje tylko `src/`, ale kod `training/` i tak pełni typy.

## Weryfikacja

UC-72..74 + blok weryfikacyjny z reguł Python; `uv run pytest -q -m integration tests/training`.