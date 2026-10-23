# Spec PII-4-e — Adaptery baseline'ów (`eval/baselines/`)

## Przegląd

Rejestr systemów porównawczych z jednym interfejsem `predict(text) -> list[Span]`
i jawnymi mapowaniami etykiet. Trzy adaptery zewnętrzne (Presidio regex-only,
bardsai v2, OpenAI Privacy Filter) + dwa systemy własne (`rules` = `piitier.detect`,
`ner` = `NerPredictor`). Typ bazowego, którego adapter nie mapuje, jest jawnie
wyliczony jako nieobsługiwany (stała UNMAPPED) — w benchmarku liczony jako miss.

## Pliki

- `eval/baselines/__init__.py` — rejestr `get_system(name, **kwargs)`, protokół.
- `eval/baselines/presidio_pl.py`, `eval/baselines/bardsai_v2.py`,
  `eval/baselines/privacy_filter.py`, `eval/baselines/piitier_systems.py`.
- `tests/eval/test_baselines.py` (UC-85, UC-88 — jednostkowe),
  `tests/eval/test_baselines_integration.py` (UC-86, UC-87 — integration).

## Interfejs (dokładne sygnatury)

```python
# eval/baselines/__init__.py
class System(Protocol):
    name: str
    unmapped: frozenset[Label]     # typy TAXONOMY których NIGDY nie przewiduje
    def predict(self, text: str) -> list[Span]: ...

_REGISTRY: dict[str, Callable[..., System]]

def register_system(name: str) -> decorator? — NIE, statyczny słownik:
_SYSTEM_FACTORIES: dict[str, type[System]] = {
    "rules": ..., "ner": ..., "presidio": ..., "bardsai-v2": ..., "privacy-filter": ...
}

def get_system(name: str, **kwargs: object) -> System:
    """Unknown name → KeyError z listą dostępnych nazw."""

# eval/baselines/piitier_systems.py
class RulesSystem:
    """name='rules'; unmapped=typy NER-only wg docs/TAXONOMY.md kolumny Metoda
    (encje z metodą zawierającą 'NER' bez reguły); predict = piitier.detect(text)."""

class NerSystem:
    """name='ner'; wymaga kwargs checkpoint: str, threshold: float = 0.0;
    predict = NerPredictor(checkpoint, threshold).predict(text); lazy import."""

# eval/baselines/presidio_pl.py
PRESIDIO_LABEL_MAP: dict[str, Label] = {
    "EMAIL_ADDRESS": Label.EMAIL, "PHONE_NUMBER": Label.TELEFON,
    "IBAN_CODE": Label.IBAN, "CREDIT_CARD": Label.NR_KARTY,
    "IP_ADDRESS": Label.IP, "PERSON": Label.OSOBA, "LOCATION": Label.MIEJSCOWOSC,
    "DATE_TIME": Label.DATA_URODZENIA, "PL_PESEL": Label.PESEL,
    "PL_NIP": Label.NIP, "PL_REGON": Label.REGON,
}
class PresidioSystem:
    """name='presidio'; AnalyzerEngine z registry zawierającym WYŁĄCZNIE
    rozpoznawacze bez-NLP (spacy nie wymagane): EmailRecognizer, PhoneRecognizer,
    CreditCardRecognizer, IbanRecognizer, IpRecognizer + własne PatternRecognizer
    dla PL_PESEL (11 cyfr + suma), PL_NIP, PL_REGON (wzorce z piitier.rules —
    re-użycie wyrażeń), nlp_engine=None. predict(text): analyzer.analyze(text,
    language='pl') → Span(source='baseline:presidio', score=result.score,
    status='valid'). Leniwy import presidio_analyzer."""

# eval/baselines/bardsai_v2.py
BARDSAI_LABEL_MAP: dict[str, Label] = {
    "PERSON_NAME": Label.OSOBA, "DATE_OF_BIRTH": Label.DATA_URODZENIA,
    "BANK_ACCOUNT_IDENTIFIER": Label.IBAN, "PAYMENT_CARD": Label.NR_KARTY,
    "PAYMENT_CARD_SECURITY": Label.CVV, "PHONE_NUMBER": Label.TELEFON,
    "EMAIL_ADDRESS": Label.EMAIL, "IP_ADDRESS": Label.IP, "LOCATION": Label.MIEJSCOWOSC,
    "POSTAL_ADDRESS": Label.ADRES, "HEALTH_DATA": Label.DANE_ZDROWOTNE,
    "VEHICLE_IDENTIFIER": Label.VIN, "FINANCIAL_AMOUNT": Label.KWOTA,
    "ORGANIZATION_NAME": Label.PLACOWKA, "DOCUMENT_REFERENCE": Label.NR_DOKUMENTACJI,
}
class BardsaiV2System:
    """name='bardsai-v2'; NerPredictor('bardsai/eu-pii-anonimization-multilang-v2')
    z id2label modelu; dekodowane etykiety modelu mapowane przez BARDSAI_LABEL_MAP
    (brak w mapie → span pomijany, nie zmyślimy etykiety). predict z NerPredictor.
    Konstruktor: leniwy (transformers w predict-path)."""

# eval/baselines/privacy_filter.py
PRIVACY_FILTER_LABEL_MAP: dict[str, Label] = {
    "private_person": Label.OSOBA, "private_address": Label.ADRES,
    "private_date": Label.DATA_URODZENIA, "private_email": Label.EMAIL,
    "private_phone": Label.TELEFON, "account_number": Label.NR_RACHUNKU,
}
def decode_bilou(
    offset_mapping: list[tuple[int,int]], probs: list[list[float]],
    id2label: dict[int, str],
) -> list[tuple[int, int, str, float]]:
    """Czysty dekoder BILOU (B/I/E/L/S-<type>) → (start, end, type, score);
    score = średnia prawdopodobieństwa tagów encji; tag spoza schematu (O) kończy
    encję; I/E bez otwartego B → ignorowane. Testowalny bez modelu."""

class PrivacyFilterSystem:
    """name='privacy-filter'; NerPredictor('openai/privacy-filter') z BILOU decode
    (predict przepisany: własne okno + decode_bilou, bo NerPredictor dekoduje BIO).
    UWAGA: model 1.4B — żadna integracja go nie pobiera (konstruktor leniwy);
    predykcja wymaga pełnego ściągnięcia — użycie ręczne/dokumentowane."""
```

## Kryteria akceptacji

- **UC-85**: `get_system('rules')` zwraca system z `predict` = `piitier.detect`
  (porównanie listy spanów na dokumencie z PESEL+IBAN); nieznana nazwa → KeyError
  z dostępnymi nazwami; każda mapa `*_LABEL_MAP` ma wartości będące członkami enuma
  (test iteruje po mapach); UNMAPPED każdego systemu to podzbiór `set(Label)`
  i pokrywa dokładnie `set(Label) - set(map values)` dla adapterów zewnętrznych.
- **UC-86** (integration): `PresidioSystem().predict` na polskim dokumencie
  (PESEL 44051401359, IBAN PL61 1090 1014 0000 0712 1981 2874, email) → ≥3 spany,
  etykiety zgodne z mapą, offsety w tekście; importy presidio zainstalowane w dev env.
- **UC-87** (integration): `BardsaiV2System().predict` na polskim zdaniu
  ("Nazywam się Jan Kowalski, mój numer PESEL to 44051401359.") → lista spanów
  (model 307M, BIO; pobranie ~1.2 GB — jednorazowe, cache HF); test asercje tylko
  strukturalne (offsety w granicach, etykieta w mapie), nie jakości detekcji.
- **UC-88**: `decode_bilou` na ręcznym fixture (sekwencja S-XXX / B..E / B..L
  znanymi offsetami i probs) → dokładne (start,end,type,score); I- bez B ignorowane;
  wszystkie 6 typów mapowanych przez PRIVACY_FILTER_LABEL_MAP to członkowie enuma.

## Ograniczenia

- Fala 1, ale zależy od PII-4-a: worktree powstaje z `ai/pii-4-integration` PO
  scaleniu PII-4-a (BardsaiV2System i NerSystem re-używają `NerPredictor`).
- Presidio: bez spaCy — jeśli AnalyzerEngine(nlp_engine=None) w wersji 2.2.364
  wymusza NLP, użyć AnalyzerEngine(nlp_engine=None, registry=...) z
  `AnalyzerEngine.supported_languages` — implementator czyta zainstalowane
  site-packages i dopasowuje; cel: brak modelu spaCy.
- Testy UC-85/UC-88 bez sieci; UC-86/87 integration (pytest -m integration).
- Nie modyfikować `src/piitier/`.

## Weryfikacja

UC-85..88 + blok weryfikacyjny; `uv run pytest -q -m integration tests/eval/test_baselines_integration.py`.