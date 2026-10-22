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

## Statystyki Biegu (pełny bieg, 2026-10-23, piitier 0.1.0, seed 42)
> - Dokumenty: 22 000 łącznie (20 000 szablonowych + 2 000 twardych negatywów), split: `train` 20 252, `dev` 1 748; `augment: true`.
> - `span_counts`: PESEL 20 000, IBAN 20 000, NIP 15 385, NR_DOWODU 15 386, REGON 10 769, NR_KARTY 6 153, ADRES 3 577, KOD_POCZTOWY 3 077, MIEJSCOWOSC 3 077, OSOBA 3 077, LEK 3 076, LEKARZ 3 077, NPWZ 3 077, PLACOWKA 3 077, DATA_URODZENIA 1 538, ICD10 1 538, ROZPOZNANIE 1 538, NR_POLISY 1 539, NR_SZKODY 1 538, NR_UMOWY 1 538, NR_REJESTRACYJNY 1 538, VIN 1 538.
> - SHA-256: `train.jsonl` `2f05f7186b00cabe5aa0c23a700effb2b24e61f2cc49e09972f0c83e7561f773`, `dev.jsonl` `bba47a4dbc7807d5c3aa3d7dc6c02a3fe4a1fa4fefdb40faa2ee34c8e6107ca3`; offsety zweryfikowane (`check` → 0).
