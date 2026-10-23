# Spec PII-4-a — Inferencja NER (`src/piitier/ner/`)

## Przegląd

Moduł inferencji modelu NER dla biblioteki piitier: nazwy tagów BIO z enuma `Label`,
czysty (bez sieci) dekoder tokenów → spany, oraz `NerPredictor` z oknem przesuwnym
dla długich dokumentów. To jedyny moduł PII-4, który ląduje w `src/piitier`
(paczka wheel); ciężkie importy (transformers, torch) leniwie.

## Pliki

- `src/piitier/ner/__init__.py` — re-exporty publicznego API.
- `src/piitier/ner/inference.py` — cała logika.
- `tests/ner/__init__.py` (puste), `tests/ner/test_inference.py` — testy UC-67..UC-70
  (jednostkowe, bez transformers), UC-71 (`@pytest.mark.integration`).

## API (dokładne sygnatury)

```python
BIO_O: str = "O"


def bio_tag_names() -> list[str]:
    """['O'] + dla każdego Label w kolejności definicji enuma: 'B-<name>', 'I-<name>'.
    1 + 39*2 = 79 nazw; deterministyczna kolejność (kolejność członków enuma)."""


def spans_to_token_labels(spans: list[Span], offset_mapping: list[tuple[int, int]]) -> list[int]:
    """Identyfikatory tagów BIO dla tokenów. Token (offsety w oryginalnym tekście)
    dostaje B-<label> jeśli jest pierwszym tokenem w spanie, I-<label> dla kolejnych;
    warunek: token MUSI być w całości wewnątrz spana (tok_start >= span.start and
    tok_end <= span.end); tokeny częściowo nachodzące lub poza spanami → O.
    Offsety (0, 0) → O. Identyfikatory wg bio_tag_names() — indeks nazwy na liście."""


def decode_spans(
    text: str,
    offset_mapping: list[tuple[int, int]],
    probs: list[list[float]],
    id2label: dict[int, str],
    threshold: float = 0.0,
) -> list[Span]:
    """Dekoduje sekwencję dystrybucji per token na spany.
    - predicted tag = argmax po probs; B-/I- rozpoczyna encję; I- bez otwartej B- tej
      samej etykiety jest ignorowane (zaczyna nową encję tylko gdy poprzedni token miał
      tę samą etykietę B lub I — klasyczna naprawa BIO).
    - score encji = średnia prawdopodobieństwa wybranego tagu po tokenach encji.
    - encja o score < threshold jest odrzucana (threshold domyślnie 0.0 = bez filtracji).
    - tokeny z offsetem (0,0) pomijane; etykieta mapowana przez `Label[<name>]`
      (nazwa bez prefiksu B-/I-).
    - Span(source='model:ner', status='valid'); start/end z offsetów pierwszego/ostatniego
      tokenu encji. Sortowanie po (start, end)."""


class NerPredictor:
    def __init__(
        self,
        checkpoint: str | Path,
        threshold: float = 0.0,
        device: str = "cpu",
        window: int = 512,
        stride: int = 256,
    ) -> None:
        """Leniwie ładuje AutoTokenizer + AutoModelForTokenClassification (import
        transformers wewnątrz; brak biblioteki → ImportError z komunikatem o `uv sync`).
        Wymaga stride < window. id2label z configu modelu."""

    def predict(self, text: str) -> list[Span]:
        """Dzieli text na okna (window tokenów, przeskok stride, ostatnie okno wyrównane
        do końca), batch per okno, softmax, decode_spans per okno; wyniki okien scalane:
        encje o tej samej etykiet nachodzące się między oknami → wyższy score wygrywa
        (rozszerzenie zakresu do pokrycia); wynik posortowany, bez nakładania się.
        Pusty tekst → []."""
```

## Kryteria akceptacji

- **UC-67**: `bio_tag_names()` zwraca dokładnie 79 nazw, `['O']` pierwsze, potem
  B-/I- w kolejności enuma; `Label[białka]` — property test? nie: test porównuje z listą
  zbudowaną z `list(Label)` w teście.
- **UC-68**: `decode_spans` na ręcznym fixture (tekst "Jan Kowalski, PESEL 44051401359.",
  offsety tokenów, probs z jedną wyraźną encją OSOBA i jedną PESEL) → dokładnie 2 spany
  z dokładnymi offsetami, score w (0,1], `status='valid'`, `source='model:ner'`;
  tekst bez encji (samo O) → `[]`.
- **UC-69**: threshold odcina encję o score < threshold i zostawia wyższą; wartość
  graniczna (score == threshold) zostaje.
- **UC-70**: scalanie okien: dwa okna z encją tej samej etykiety pokrywające się
  (symulacja przez wywołanie wewnętrznej funkcji sklejającej — test jednostkowy
  funkcji pomocniczej `merge_windows(spans: list[Span]) -> list[Span]`):
  nakładające się ta sama etykieta → jeden span (wyższy score, pokryty zakres),
  różne etykiety nakładające się → wygiera wyższy score; wynik posortowany i rozłączny.
- **UC-71** (integration): `NerPredictor("hf-internal-testing/tiny-random-BertForTokenClassification")`
  + predict na polskim zdaniu z PESEL → lista dobrze uformowanych spanów (offsety w
  granicach tekstu, label w enumie); `spans_to_token_labels` + `bio_tag_names` zgodne
  (round-trip: dekodowane nazwy tagów istnieją w bio_tag_names()).

## Ograniczenia

- `mypy --strict` przechodzi: mypy overrides dla `transformers.*`, `torch.*` dodane w
  pyproject przez integratora; kod modułu w pełni annotowany.
- Nie modyfikować `piitier/__init__.py` (re-exporty ner nie wchodzą do top-level API w
  tym slocie) ani `docs/TAXONOMY.md`.
- `merge_windows` jest funkcją modułową (testowalna bez modelu) wywoływaną przez `predict`.

## Weryfikacja

Wszystkie UC + blok weryfikacyjny z reguł Python (ruff, mypy, pytest bez integration),
dodatkowo `uv run pytest -q -m integration tests/ner`.