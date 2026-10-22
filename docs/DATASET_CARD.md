# Karta Datasetu: Syntetyczny Polski Korpus PII (piitier)

## Cel Datasetu
Zbiór danych służy do treningu i ewaluacji modeli rozpoznawania nazw własnych i danych wrażliwych (NER / anonimizacja PII) dla języka polskiego w domenach fintech, insurtech i medtech. Wszystkie dane są w 100% syntetyczne, generowane programowo przy użyciu zweryfikowanych generatorów, szablonów oraz technik augmentacji i twardych negatywów.

## Schemat JSONL
Każdy rekord w plikach `train.jsonl` oraz `dev.jsonl` jest obiektem JSON o następujących polach:
- `id` (string): Unikalny identyfikator dokumentu (np. `doc_0000000` dla szablonów, `hn_0000000` dla twardych negatywów).
- `doc_type` (string): Typ dokumentu (np. `polisa`, `umowa_kredytowa`, `wypis_szpitalny`, `mail_klienta`, `wyciag`, `skierowanie`, `zgloszenie_szkody`, `transkrypcja_infolinii`).
- `template_id` (string): Identyfikator szablonu bazowego lub unikalnego identyfikatora negatywu.
- `seed` (int): Ziarno generatora losowego (`random.Random`) użyte do wyrenderowania dokumentu.
- `text` (string): Pełna treść tekstu dokumentu.
- `spans` (lista obiektów): Lista dopasowanych spanów zawierających:
  - `start` (int): Początkowy offset znakowy (inkluzywny).
  - `end` (int): Końcowy offset znakowy (wykluczeniowy).
  - `label` (string): Etykieta PII (np. `PESEL`, `ADRES`, `OSOBA`, itp.).
  - `entity` (string | null): Identyfikator entity dla korelacji (np. `"1"`).
  - `text` (string): Dokładny podciąg tekstu pokryty przez span (`text[start:end] == span["text"]`).

## Źródła i Licencje
1. **Faker (`pl_PL`)**:
   - Używany do generowania imion, nazwisk, adresów i miast.
   - Licencja: **MIT**.
2. **Morfeusz 2**:
   - Używany do odmiany nazwisk i rzeczowników w odpowiednich przypadkach gramatycznych.
   - Licencja: **BSD-2-Clause**.
3. **Listy autorskie w repozytorium**:
   - Curated list of ICD-10 codes, medical drugs (INN), diagnosis terms, and identifiers.
   - Licencja: Twórczość własna (w ramach projektu piitier).
4. **Lokalny model językowy (Bielik)**:
   - Model `SpeakLeash/Bielik-11B-v3.0-Instruct-GGUF` używany wyłącznie lokalnie (przez Ollama) jako generator czystego tekstu szablonów z placeholderami. Żadne dane osobowe ani PII nie są generowane przez LLM; wartości są wstrzykiwane programowo przez kod.
   - Licencja modelu bazowego.

## Licencja Wyjściowa
Zbiór danych jest udostępniany na licencji **CC BY 4.0** (Creative Commons Attribution 4.0 International).

## Reprodukowalność
Zbiór jest w pełni deterministyczny. Użycie tego samego ziarna (`seed`), wersji biblioteki `piitier` oraz zestawu szablonów gwarantuje uzyskanie identycznych plików wynikowych (bajt w bajt, potwierdzone sumą kontrolną SHA-256).

## Pełny Bieg (Instrukcja dla Orchestratora)
Aby wykonać pełny bieg produkcyjny (20 000 dokumentów szablonowych + 2 000 twardych negatywów, z augmentacją), należy uruchomić następujące polecenie:

```bash
python -m piitier.datagen build \
  --templates src/piitier/datagen/templates \
  --n 20000 \
  --seed 42 \
  --augment \
  --hard-negatives 2000 \
  --out data/synthetic/v0.1/
```

## Statystyki Biegu (TODO)
> **TODO** (oczekuje na uruchomienie pełnego biegu przez orchestrator):
> - Liczba dokumentów treningowych i walidacyjnych: `TODO`
> - Liczba wystąpień poszczególnych etykiet (`span_counts`): `TODO`
> - Sumy kontrolne SHA-256 wygenerowanych plikόw (`train.jsonl`, `dev.jsonl`, `manifest.json`): `TODO`
