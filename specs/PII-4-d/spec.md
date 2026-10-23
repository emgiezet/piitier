# Spec PII-4-d — Metryki ewaluacji (`eval/metrics.py`)

## Przegląd

Wszystkie metryki benchmarku PL-PII-Bench jako czyste, w pełni typowane funkcje:
precision/recall encji (strict i partial), recall ważony ryzykiem (wagi w
`docs/TAXONOMY.md`), leak rate, wierność tekstu, spójność numeracji, throughput.
Każda sprawdzona przeciw ręcznie policzonemu fixture, w tym przypadki brzegowe
zero-pred i zero-gold.

## Pliki

- `eval/__init__.py` (puste).
- `eval/metrics.py` — wszystkie funkcje.
- `docs/TAXONOMY.md` — NOWA sekcja `## Wagi ryzyka` (6 grup; poniżej wartości).
- `tests/eval/__init__.py` (puste), `tests/eval/test_metrics.py` — UC-79..UC-84.

## Wagi ryzyka (sekcja do dopisania na końcu docs/TAXONOMY.md, dosłownie)

```markdown
## Wagi ryzyka

Wagi grup do recall ważonego ryzykiem (eval/metrics.py — test synchronizacji
`test_uc80` wymaga zgodności z tą tabelą):

| Grupa | Waga |
|-------|------|
| Identyfikatory państwowe | 1.0 |
| Finanse | 1.0 |
| Ubezpieczenia | 0.9 |
| Kontakt i lokalizacja | 0.8 |
| Zdrowie — art. 9 RODO | 0.8 |
| Identyfikacja osoby | 0.6 |
```

Uzasadnienie: sumy kontrolne identyfikatorów państwowych i finansowych są
bezpośrednim identyfikatorem (waga 1.0); dane kontaktowe i zdrowotne są
wrażliwe, ale rzadko same jednoznacznie identyfikują; imię/nazwisko/wiek to
quasi-identyfikatory (dopełniają reidentyfikację, nie prowadzą jej).

## API (dokładne sygnatury)

```python
@dataclass(frozen=True)
class EntityPRF:
    precision: float
    recall: float
    f1: float

def entity_metrics(
    gold: list[Span], pred: list[Span], match: Literal["strict", "partial"] = "strict",
) -> EntityPRF:
    """strict: ta sama etykieta i identyczne [start,end). partial: ta sama etykieta i
    dowolna niepusta nakładka [start,end). Micro. Zero-gold i zero-pred → P/R/F1 = 0.0
    (bez ZeroDivision; zero-gold & zero-pred → 0.0)."""

def entity_metrics_by_label(
    gold: list[Span], pred: list[Span], match: ... = "strict",
) -> dict[Label, EntityPRF]:
    """Per etykieta; tylko etykiety występujące w gold LUB pred."""

GROUP_WEIGHTS: dict[str, float]  # nazwa grupy -> waga (klucz: nazwa kolumny Grupa)

def group_for_label(label: Label) -> str: ...   # mapa Label -> nazwa grupy z TAXONOMY.md

def risk_weighted_recall(gold: list[Span], pred: list[Span]) -> float:
    """strict match; Σ w(label)*[gold złapany] / Σ w(label); zero-gold → 0.0."""

DIRECT_IDENTIFIERS: frozenset[Label]  # patrz lista niżej

def leak_rate(
    originals: list[str], gold_spans: list[list[Span]], rendered: list[str],
) -> LeakRate:
    """LeakRate(docs_leaked, docs_total, values_leaked, values_total, leaked_doc_ids).
    - values: wartość spana gold (oryginalny substring) występuje w rendered (find).
    - docs: dokument z co najmniej jednym niedomaskowanym spanem o etykietie w
      DIRECT_IDENTIFIERS. left; span 'suspect' którego wartość NIE występuje w
      rendered → nie liczy się (zmaskowany).
    - doc_ids przekazywane w `originals`? NIE — osobny parametr `doc_ids: list[str]`
      (kolejność zgodna)."""

def fidelity(original: str, rendered: str, spans: list[Span]) -> int:
    """Liczba znaków zmienionych POZA zakresami spanów. Implementacja: porównanie
    znak po znaku w regionach spoza spanów (offsety w oryginale); przed porównaniem
    rendered dzielony przez placeholder zgodnie z długościami wstawek — UWAGA: to
    wymaga odwrotnej mapy: iteruj oryginał z jednoczesnym śledzeniem pozycji w
    rendered; region poza spanem musi być identyczny co do bajta. Zwraca liczbę
    niedopasowań (0 = wierność zachowana)."""

def numbering_consistency(
    rendered: str, spans: list[Span], labels_numbered: set[Label],
) -> NumberingStats:
    """Placeholder wstawiony za i-ty span ekstrahowany z rendered (alignacja:
    iteruj oryginał+rendered jak w fidelity, zapisz string placeholdera per span).
    NumberingStats(same_entity_consistent, same_entity_total,
    different_entity_distinct, different_entity_total):
    - pary spanów tej samej etykiety w `labels_numbered` (OSOBA, IMIE, NAZWISKO,
      ADRES, LEKARZ) o IDENTYCZNEJ wartości (dokładny substring oryginału) → para
      ta sama encja: consistent gdy placeholder identyczny.
    - pary tej samej etykiety o różnej wartości → para różne encje: distinct gdy
      placeholder różny."""

@dataclass(frozen=True)
class ThroughputStats:
    docs_per_second: float
    p95_latency_seconds: float

def throughput_stats(latencies_seconds: list[float]) -> ThroughputStats:
    """docs/s = len/sum; p95 = metoda: nearest-rank (ceil(0.95*n)-ty element sorted);
    pusta lista → docs_per_second=0.0, p95=0.0."""

def peak_ram_bytes() -> int:
    """resource.getrusage(RUSAGE_SELF).ru_maxrss * 1024 (linux)."""
```

DIRECT_IDENTIFIERS = {PESEL, NR_DOWODU, NR_PASZPORTU, NR_PRAWA_JAZDY, NIP, REGON,
IBAN, NR_RACHUNKU, NR_KARTY, TELEFON, EMAIL, IP, NR_UMOWY, NR_POLISY, NR_SZKODY,
NR_REJESTRACYJNY, VIN, NR_KW, NPWZ, NR_DOKUMENTACJI} — identyfikatory maszynowe
i dane kontaktowe; imiona/adresy to quasi-identyfikatory (pominięte).

## Kryteria akceptacji (każdy fixture policzony ręcznie w teście)

- **UC-79**: `entity_metrics` strict: 3 gold/2 pred (1 exact hit, 1 wrong offsets,
  1 miss) → P=1/2, R=1/3, F1 dokładnie (0.4, 1/3, 2*P*R/(P+R)); partial: pred
  nachodzący z gold → hit; zero-pred → (0,0,0); zero-gold+zero-pred → (0,0,0);
  `entity_metrics_by_label` per etykieta zgodna z ręcznym rachunkiem.
- **UC-80**: `risk_weighted_recall`: ręczny fixture z etykietami z 3 grup o różnych
  wagach → dokładna wartość ważona; test parsuje sekcję `## Wagi ryzyka` z
  docs/TAXONOMY.md i porównuje z `GROUP_WEIGHTS` (drift = fail).
- **UC-81**: `leak_rate`: dokument z niedomaskowanym PESEL (wartość widoczna w
  rendered) → docs_leaked=1; dokument gdzie wartość suspect spana została
  zastąpiona placeholderem → nie wyciek; wartość wycieka w dokumencie bez
  DIRECT_IDENTIFIER (np. MIEJSCOWOSC left) → values_leaked rośnie, docs_leaked NIE.
- **UC-82**: `fidelity` = 0 dla poprawnego maskowania (render.mask) i > 0 gdy
  rendered zmienia znak poza spanem (test przeciwko ręcznie zepsutej kopii).
- **UC-83**: `numbering_consistency` na rendered z `piitier.render.mask`: dwie
  wzmianki tej samej wartości → ten sam placeholder (consistent); dwie różne
  osoby (różna wartość) → oba dostają ten sam literalny placeholder → distinct=0
  (renderer bez coref — oczekiwane); drugi fixture: rendered z RĘCZNIE nadanymi
  placeholderami [OSOBA_1]/[OSOBA_2] → pełna zgodność (consistent i distinct).
- **UC-84**: `throughput_stats([0.1]*10)` → docs/s=10.0, p95=0.1; puste → (0.0, 0.0);
  p95 nearest-rank na liście o znanej kolejności → dokładna wartość elementu.

## Ograniczenia

- Funkcje czyste: bez I/O, bez globali; `peak_ram_bytes` jedyny wyjątek (resource).
- Spany `status='suspect'` traktowane w metrykach identycznie (to, że zmaskowane,
  widać przez rendered w leak_rate).
- Nie dotykać `src/piitier/` (import tylko `piitier.spans`, `piitier.labels`,
  `piitier.render` w testach).
- Test UC-80 parsuje tabelę wag z TAXONOMY.md (regex `| <Grupa> | <float> |`).

## Weryfikacja

UC-79..84 + blok weryfikacyjny z reguł Python (bez integration — brak sieci).