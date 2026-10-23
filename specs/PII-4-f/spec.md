# Spec PII-4-f — Runner benchmarku + fixture złotego zbioru (`eval/run.py`, `bench/v1/`)

## Przegląd

CLI benchmarku `python -m eval.run --system <name> --bench <version> --split <dev|test>`
piszące raport markdown z każdą metryką, wersjami, progiem i sprzętem, plus
pierwszy fixture złotego zbioru PL-PII-Bench v1 (tylko split `dev`; `test/` powstanie
przy publikacji wersji — niewidoczny dla tuningu, CLAUDE.md inwariant 7).

## Pliki

- `eval/run.py` — CLI + orkiestracja (wczytanie bench, predykcja, maskowanie,
  metryki, raport).
- `eval/report.py` — `write_report(...)` (czysty generator markdown z danych).
- `bench/v1/dev/docs.jsonl` — 6 syntetycznych dokumentów złotego zbioru (committed).
- `bench/README.md` — format bench, polityka zamrożenia `test/`, licencja CC BY 4.0.
- `tests/eval/test_bench_fixture.py` (UC-89), `tests/eval/test_run.py`
  (UC-90 jednostkowy z tmp-bench, UC-91 end-to-end na committowanym fixture).

## Fixture bench/v1/dev (dokumenty syntetyczne, pisane ręcznie)

6 dokumentów, po jednym na typ (polisa, zgłoszenie_szkody, umowa_kredytowa, wyciąg,
mail_klienta, wypis_szpitalny), każdy 3–8 zdań, po polsku, zawiera łącznie ≥15 spanów
gold z ≥8 różnych etykiet, w tym: PESEL (suma kontrolna poprawna), NIP, IBAN, NR_KARTY
(Luhn), OSOBA (2× ta sama osoba w jednym dokumencie — dla numbering), DATA_URODZENIA,
ADRES, EMAIL, TELEFON. Rekord = wspólny schemat JSONL (dekomp. PII-4). Wartości
fikcyjne, generowane przez implementatora zgodnie z checksumami (wzorce z
`tests/rules/`); zakaz prawdziwych danych.

## API (dokładne sygnatury)

```python
# eval/run.py
def read_bench(bench_dir: Path) -> list[BenchDoc]:
    """BenchDoc = (id: str, doc_type: str, text: str, gold: list[Span]).
    Czyta wszystkie *.jsonl w katalogu; walidacja offsetów: text[start:end] ==
    span['text'], etykieta w enumie — błąd → ValueError z id dokumentu."""

def run_benchmark(
    system: System, docs: list[BenchDoc], *, threshold: float | None,
) -> BenchResult:
    """Per dokument: pred = system.predict(text); rendered = piitier.render.mask(text, pred).
    Latencje: time.perf_counter per predict. BenchResult zawiera: wszystkie listy
    dla metryk eval.metrics (gold łączone, pred łączone, originals, rendered,
    doc_ids), latencies, threshold."""

def main(argv: list[str] | None = None) -> int:
    """argparse: --system (wymagane), --bench (domyślnie 'v1'), --split (domyślnie
    'dev', wybór dev|test), --checkpoint (dla systemu ner, inaczej błąd), --threshold
    (float, domyślnie 0.0), --out-dir (domyślnie 'eval/reports').
    - Ścieżka bench: bench/<version>/<split>/; brak katalogu → exit 1 z komunikatem.
    - --split test → dozwolone (liczby finalne), ale raport dostaje adnotację
      'final numbers' i ostrzeżenie w stdout.
    - Nazwa pliku raportu: <YYYY-MM-DD>-<system>-bench<v>-<split>.md.
    - exit 0."""

# eval/report.py
def write_report(
    path: Path, *, system_name: str, system_version: str, bench_version: str,
    split: str, threshold: float | None, result: BenchResult,
    metrics: dict[str, object],  # z eval.metrics — sekcje poniżej
) -> Path:
    """Sekcje raportu (kolejność obowiązkowa):
    # Raport: <system> na bench/<v>/<split>
    - System: name, wersja (piitier.__version__ lub identyfikator modelu), data,
      próg (lub 'brak — system bez progu').
    - Benchmark: wersja, split, liczba dokumentów, liczba spanów gold.
    - Sprzęt: platform.platform(), procesor, GPU (torch.cuda.is_available() →
      nazwa przez torch.cuda.get_device_name(0), inaczej 'CPU'), RAM peak
      (eval.metrics.peak_ram_bytes).
    - Encje (strict): precision/recall/f1 micro + tabela per etykieta.
    - Encje (partial): jw.
    - Recall ważony ryzykiem.
    - Leak rate: docs i values (z listą doc_ids wycieków).
    - Wierność: changed_chars_outside_spans (oczekiwane 0 dla reguł).
    - Numeracja: same_entity_consistent/total, different_entity_distinct/total
      (dla systemów bez coref adnotacja 'n/a — brak modułu coref' gdy total==0
      w obu kierunkach... NIE: liczymy zawsze; liczby mogą być 0/x — raport
      wypisuje liczby bez skrętów).
    - Throughput: docs/s, p95 latencji."""
```

## Kryteria akceptacji

- **UC-89**: fixture walidacyjny — `read_bench(bench/v1/dev)` zwraca 6 dokumentów;
  każdy span: offsety zgodne z text[start:end], etykieta członkiem enuma; ≥8 różnych
  etykiet łącznie; ≥1 dokument z 2 wzmiankami tej samej osoby (identyczny substring);
  PESEL w fixture przechodzi walidator `piitier.rules.pesel`; IBAN mod97; NIP suma.
- **UC-90**: `write_report` na syntetycznym BenchResult (tmp) → plik ma wszystkie 9
  sekcji nagłówkowych w kolejności (test sprawdza kolejność linii `#`/`##` i pola);
  metryki zero-gold → 0.0 bez wyjątku.
- **UC-91**: `python -m eval.run --system rules --bench v1 --split dev`
  (subprocess z repo root) → exit 0, raport w eval/reports/ (tmp copy dla testu:
  --out-dir tmp) zawiera sekcje i niezerowe metryki dla PESEL/IBAN/NIP
  (dla systemu rules: precision na tych etykietach = 1.0 — reguły wykrywają
  wszystkie checksumowe gold z fixture, jeśli wzorce się zgadzają; asercja: recall
  PESEL/IBAN/NIP == 1.0 w raporcie per etykieta strict).

## Ograniczenia

- Fala 2: worktree zawiera scalone PII-4-a (NerSystem), PII-4-d (metryki),
  PII-4-e (rejestr).
- `--split test` czyta bench/<v>/test/ jeśli istnieje (final numbers); tuningu tam
  nie ma (guard siedzi w config loaderze PII-4-b i kalibracji PII-4-c).
- Raport zapisuje TYLKO id dokumentów wycieków — nigdy tekst ani wartości PII.
- Testy bez sieci: UC-91 działa offline (system rules nie pobiera nic).
- Nie modyfikować `src/piitier/`.

## Weryfikacja

UC-89..91 + blok weryfikacyjny; UC-91 komenda dosłownie:
`uv run python -m eval.run --system rules --bench v1 --split dev --out-dir /tmp/eval-report-test`.