# Karta Datasetu: Syntetyczny Polski Korpus PII (piitier)

## Cel Datasetu
Zbiór danych służy do treningu i ewaluacji modeli rozpoznawania nazw własnych i danych wrażliwych (NER / anonimizacja PII) dla języka polskiego w domenach fintech, insurtech i medtech. Wszystkie dane są w 100% syntetyczne, generowane programowo przy użyciu zweryfikowanych generatorów, szablonów oraz technik augmentacji i twardych negatywów.

## Schemat JSONL
Każdy rekord w plikach `train.jsonl` oraz `dev.jsonl` jest obiektem JSON o następujących polach:
- `id` (string): Unikalny identyfikator dokumentu (np. `doc_0000000` dla szablonów, `hn_0000000` dla twardych negatywów).
- `doc_type` (string): Typ dokumentu (np. `polisa`, `umowa_kredytowa`, `wypis_szpitalny`, `mail_klienta`, `wyciag`, `skierowanie`, `zgloszenie_szkody`, `transkrypcja_infolinii`, `zestawienie_prowizyjne`).
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
4. **Lokalne modele językowe (Ollama, tylko na lokalnym sprzęcie)**:
   - `SpeakLeash/Bielik-11B-v3.0-Instruct-GGUF` (`write-templates`) pisał tekst szablonów 8 pierwotnych typów dokumentów z placeholderami w miejscu PII. Wyjście zawierające wartość zamiast placeholdera jest odrzucane.
   - `qwen3-coder:30b` (`templatize`) służy wyłącznie jako detektor spanów w tekście polis PDF: zwraca w JSON listę dosłownych fragmentów z etykietą (`text`, `label`); kod sprawdza, że fragment występuje dosłownie, i sam podmienia go na placeholder.
   - Żaden LLM nie generuje wartości PII ani nie nadaje etykiet spanom w korpusie; wartości wstrzykuje kod.
5. **Pliki PDF polis ubezpieczeniowych (dawcy układu)**:
   - Pochodzenie: wewnętrzny zbiór dokumentów (polisy wefox, PZU, Inter Partner Assistance/AXA) z **fikcyjnymi tożsamościami** (nie są to dane osobowe, ale łudząco je przypominają); zatwierdzony do treningu przez właściciela danych; nigdy nie jest redystrybuowany.
   - Tekst jest ekstrahowany za pomocą `pypdf`, normalizowany (zamiana NBSP→spacja, ligatur fi/fl, wielokrotnych spacji) i przekazywany do lokalnego LLM (`qwen3-coder:30b` via Ollama), który **wyłącznie wskazuje spany** do zastąpienia; reguły kodu zamieniają każdą wartość na placeholder `{{LABEL}}`. Bramka akceptacji (`_gate`) odrzuca każdy fragment, w którego literałach pozostaje cokolwiek o kształcie wartości PII: sprawdza parsowanie, przecieki (cyfry 9+, daty poza kontekstem daty urodzenia, numery kart, IBAN, kody pocztowe) i kształt etykiet.
   - Szablony pochodne (`templates/polisa/polisa_pdf_<hash>.txt`) **nie trafiają do repozytorium** (`.gitignore`, CLAUDE.md niezmiennik 2 — dokumenty pracodawcy i klientów nigdy nie wchodzą do repo): powstają lokalnie z `raw_data/poland-policy-parser/pdf/` (katalog w `.gitignore`) przez `python -m piitier.datagen templatize`. Czysty klon zawiera tylko ręcznie pisane szablony `polisa`; korpus odtworzony bez lokalnych szablonów pochodnych różni się od `data/synthetic/v0.3`.
   - Licencja źródłowa: **zastrzeżona — nie jest redystrybuowana**. Szablony pochodne są zatwierdzone do treningu przez właściciela danych i stanowią wyłącznie odwzorowanie układu dokumentów bez oryginalnych wartości. Wyjściowy syntetyczny dataset jest publikowany na **CC BY 4.0** wyłącznie jako produkt generatorów kodu i modeli generatywnych, nie oryginalnych PDF-ów.

6. **Zestawienia prowizyjne (dawcy układu)**:
   - Pochodzenie: wewnętrzne zestawienia prowizyjne z **fikcyjnymi tożsamościami** (dane syntetyczne, zatwierdzone do treningu przez właściciela danych). Służą wyłącznie jako dawcy układu (layoutu) szablonów `zestawienie_prowizyjne`.
   - Przetwarzanie: `python -m piitier.datagen templatize-tables` mapuje nagłówki kolumn na etykiety PII (mapowanie nagłówek→`{{LABEL}}`); kolumny identyfikatorów (loginy agentów, identyfikatory agentów i podobne) są pomijane i nie trafiają do szablonów; nie jest używany żaden LLM. Bramka akceptacji odrzuca każdy szablon zawierający w literałach wartości o kształcie PII.
   - Szablony pochodne (`templates/zestawienie_prowizyjne/zestawienie_prowizyjne_<hash>.txt`) **nie trafiają do repozytorium** (`.gitignore`): powstają lokalnie z `raw_data/poland-commission-settlement/` przez `python -m piitier.datagen templatize-tables`. Repozytorium zawiera trzy ręcznie pisane szablony syntetyczne `zestawienie_prowizyjne_01..03.txt` (zmyślone daty i układ).
   - Licencja źródłowa: **zastrzeżona — nie jest redystrybuowana**. Szablony pochodne zatwierdzone do treningu przez właściciela danych.

## Licencja Wyjściowa
Wyjściowy syntetyczny dataset (pliki `train.jsonl` / `dev.jsonl`) jest udostępniany na licencji **CC BY 4.0** (Creative Commons Attribution 4.0 International). Licencja ta odnosi się wyłącznie do syntetycznych danych wyjściowych generowanych przez kod i generatywne modele językowe. Szablony pochodne z polis PDF i zestawień prowizyjnych są zatwierdzone do treningu, lecz **nie są redystrybuowane** — pozostają wyłącznie lokalnie (`.gitignore`), nigdy w repozytorium ani jako surowe dokumenty czy wyekstrahowany tekst pierwotny.

## Augmentacja
Kiedy `--augment` jest aktywny, każdy dokument jest augmentowany niezależnie z zadanym prawdopodobieństwem (`augment_fraction`, domyślnie 0,25). Dla dokumentów wybranych do augmentacji stosowany jest losowy **niepusty** podzbiór transformacji:

| Transformacja | Prawdopodobieństwo włączenia |
|---|---|
| `ocr_confusions` (zamiana 0↔O, 1↔l) | 0,5 |
| `space_digit_groups` (spacje w cyfrach) | 0,5 |
| `strip_diacritics` (usunięcie polskich znaków diakrytycznych) | 0,5 |
| `uppercase` (zamiana na wielkie litery) | 0,3 |

Jeśli losowanie nie wybrałoby żadnej transformacji, wybierana jest jedna losowa (gwarancja niepustości). Zarówno decyzja o augmentacji danego dokumentu, jak i wybór transformacji są w pełni deterministyczne — ziarno na poziomie dokumentu pochodzi z `seed + i`. Manifest zapisuje: `augment_fraction`, `augmented_doc_count` (liczba dokumentów faktycznie zaugmentowanych) oraz `transform_doc_counts` (liczba dokumentów, do których zastosowano każdą transformację).

**Uzasadnienie:** korpus v0.1 był augmentowany w 100% (każdy dokument, wszystkie transformacje), co spowodowało wyciek stylu (model nauczył się identyfikować wersje wieloliterowe jako PII nawet bez kontekstu). Augmentacja ułamkowa z losowym podzbiorem transformacji redukuje ten efekt, zachowując różnorodność danych.

## Reprodukowalność
Zbiór jest w pełni deterministyczny. Użycie tego samego ziarna (`seed`), wersji biblioteki `piitier` oraz zestawu szablonów gwarantuje uzyskanie identycznych plików wynikowych (bajt w bajt, potwierdzone sumą kontrolną SHA-256). Polecenie `build` przydziela szablony metodą round-robin po typach dokumentów (posortowanych leksykograficznie): iteracja `i` wybiera typ `doc_types[i % len(doc_types)]`, a w obrębie typu szablony cyklicznie.

Reguła podziału: `sha256(template_id) % 10 == 0 → dev`, pozostałe → `train`. Dodatkowa gwarancja: jeśli wszystkie szablony danego typu dokumentu trafiłyby do `dev`, cały ten typ jest przymusowo kierowany do `train` (gwarancja pokrycia treningu). Typy, dla których zastosowano tę korektę, są zapisywane w `manifest.json` pod kluczem `split_forced_train`. Mechanizm jest deterministyczny i niezależny od parametrów `n` oraz `seed`.

## Pełny Bieg (Instrukcja dla Orchestratora)
Aby wykonać pełny bieg produkcyjny (20 000 dokumentów szablonowych + 2 000 twardych negatywów, z augmentacją ułamkową), należy uruchomić następujące polecenie:

```bash
python -m piitier.datagen build \
  --templates src/piitier/datagen/templates \
  --n 20000 \
  --seed 42 \
  --augment \
  --augment-fraction 0.25 \
  --hard-negatives 2000 \
  --out data/synthetic/v0.3/
```

## Statystyki Biegu (pełny bieg, piitier 0.1.0, seed 42)
> - Dokumenty: 22 000 łącznie (20 000 szablonowych + 2 000 twardych negatywów), split: `train` 21 283, `dev` 717; `augment: true`.
> - `span_counts`: KWOTA 38920, OSOBA 28428, PESEL 18466, IBAN 17056, NR_POLISY 16725, NIP 11388, NR_DOWODU 11143, REGON 6771, ADRES 6003, NR_KARTY 4455, NR_REJESTRACYJNY 3252, MIEJSCOWOSC 3020, NAZWISKO 2840, IMIE 2705, KOD_POCZTOWY 2653, TELEFON 2468, VIN 2283, PLACOWKA 2222, LEKARZ 2222, NPWZ 2222, LEK 2222, EMAIL 1451, DATA_URODZENIA 1259, NR_SZKODY 1205, NR_UMOWY 1111, NR_KW 1111, ROZPOZNANIE 1111, ICD10 1111.
> - SHA-256: `train.jsonl` `1530afd5a5f5a2efb116cd3a12742165c88cdadd6cc878b5967b1ea9554c1a98`, `dev.jsonl` `36c757419e978b2ed8d1cf8450bb52edc95676d32a9778528316bc7b4df9c752`; offsety zweryfikowane (`check` → 0).
