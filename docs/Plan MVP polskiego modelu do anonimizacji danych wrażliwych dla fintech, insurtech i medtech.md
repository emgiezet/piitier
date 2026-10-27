# Plan MVP polskiego modelu do anonimizacji danych wrażliwych (fintech / insurtech / medtech)

**Rekomendacja: na MVP zbuduj hybrydę – deterministyczne walidatory (PESEL, NIP, REGON, IBAN, dowód, nr polisy itd.) + mały enkoderowy model klasyfikacji tokenów (ok. 300M parametrów, fine-tuning na polskich danych domenowych) + deterministyczny „renderer” placeholderów ze spójną numeracją. Nie trenuj generatywnego LLM, który przepisuje tekst.** Generatywny Bielik/Qwen przydaje się w tym projekcie do trzech rzeczy: generowania danych syntetycznych, opcjonalnego „drugiego przebiegu” przy trudnych przypadkach i red teamingu. Nie powinien być silnikiem maskowania. Rynek przez ostatnie 12 miesięcy zmienił się mocno – OpenAI wypuściło otwarty Privacy Filter, a bards.ai polski model PII – więc przewagi trzeba szukać w polskim benchmarku, taksonomii branżowej i gwarancji wierności tekstu, a nie w samym fakcie, że istnieje „polski model PII”.

## TL;DR

- **Podejście:** hybryda regex/sumy kontrolne + enkoder NER (np. mmBERT/XLM-R/HerBERT, start z gotowego checkpointu PII) + deterministyczne podstawianie placeholderów. Ma najwyższy osiągalny recall, nie halucynuje, nie zmienia tekstu poza encjami i działa na CPU. Generatywny LLM traktuj jako narzędzie do danych i ewaluacji.
- **Dane i sprzęt:** na MVP wystarczy rząd 5–20 tys. syntetycznych, automatycznie oznaczonych polskich dokumentów i ręcznie zweryfikowany złoty zbiór 500–1000 dokumentów. Trening enkodera zajmie godziny na samym RTX 3090 Ti, więc trzecia karta nie jest teraz potrzebna. Duże przebiegi rób w chmurze (RTX 4090 od 0,34 USD/h, A100 80 GB ok. 1,39–1,59 USD/h na RunPod) albo przez PLGrid z partnerem akademickim.
- **Finansowanie i przewaga:** najmocniejszym argumentem dla grantodawców i inwestorów będzie pierwszy otwarty **polski benchmark PII dla sektorów regulowanych** razem z modelem, który mierzalnie bije OpenAI Privacy Filter, Presidio i bards.ai na polskich dokumentach branżowych (leak rate, recall, wierność). Plan: 12 tygodni po godzinach do publikacji na Hugging Face (model + dataset + Space), potem wniosek grantowy i open-core (on-prem, wsparcie, pakiety domenowe).

## Key Findings

1. **Generatywny LLM to złe narzędzie do samego maskowania.** Musi przepisać cały tekst token po tokenie, więc może zgubić, zmienić albo dopisać fragmenty, a jego wyniki różnią się między uruchomieniami. Protecto zauważa w swoim porównaniu, że „LLM-based redactors may hallucinate, redact too much or too little, and do not provide consistency across runs”.\[1\] Nawet OpenAI zbudowało Privacy Filter jako **dwukierunkowy klasyfikator tokenów** (pochodna gpt-oss, MoE: 1,5B parametrów łącznie, 50M aktywnych, licencja Apache 2.0), a nie model generatywny. Na PII-Masking-300k osiąga F1 96% (precision 94,04%, recall 98,04%).\[2\]\[3\]\[4\]
2. **Pole konkurencyjne w polskim jest już zajęte – częściowo.** bards.ai opublikowało `bardsai/eu-pii-anonimization`: polski klasyfikator tokenów na XLM-RoBERTa-base, 35 klas, samodzielnie raportowany „Global F1 95%” bez opisanego zbioru testowego.\[5\] Wersja `eu-pii-anonimization-multilang-v2` (mmBERT-base, 307M parametrów, kontekst 8k, Apache 2.0) ma strict span F1 0,973 na 455 realnych spanach (precision 0,966, recall 0,980).\[6\] **Żadna z tych prac nie podaje wyników osobno dla polskiego.** Karta modelu OpenAI Privacy Filter w ogóle nie raportuje polskiego, a GLiNER2-PII (fastino) obsługuje tylko 7 języków bez polskiego.\[2\]\[7\]
3. **Luka rynkowa:** brakuje (a) publicznego polskiego benchmarku PII z dokumentami branżowymi, (b) encji domenowych insurtech/medtech/fintech (nr polisy, nr szkody, nr umowy kredytowej, ICD-10, nr księgi wieczystej, nr rejestracyjny pojazdu, VIN), (c) spójnej numeracji encji z uwzględnieniem polskiej fleksji („Kowalski”/„Kowalskiego” → ten sam `[OSOBA_1]`), (d) twardej gwarancji, że tekst poza encjami jest bajt w bajt identyczny.
4. **Prawo:** placeholdery z mapą de-anonimizacji to **pseudonimizacja, nie anonimizacja**. Dla administratora, który trzyma mapę, dane pozostają osobowe (EDPB, Wytyczne 01/2025).\[8\] TSUE w wyroku C-413/23 P (EDPS v SRB, 4.09.2025) przyjął jednak podejście relatywne: dane spseudonimizowane nie są osobowe „in all cases and for every person”.\[9\]\[10\] Dla odbiorcy bez realnych środków reidentyfikacji – np. zewnętrznego dostawcy LLM – mogą nie być danymi osobowymi.\[11\] To mocny argument sprzedażowy, ale warunkiem jest skuteczne usunięcie także quasi-identyfikatorów.
5. **Twój sprzęt wystarcza na MVP.** Enkoder ok. 300M trenujesz na RTX 3090 Ti w godzinach. QLoRA Bielika 4.5B zmieści się na 24 GB. Zakup karty w 2026 r. jest nieopłacalny: RTX 5090 kosztował w Polsce we wrześniu 2026 od 24 999 zł do ponad 33 tys. zł przy cenie premierowej 10 299 zł.\[12\]

## 1. Architektura – porównanie podejść

### Tabela porównawcza

| Kryterium | A. Generatywny LLM (text-to-text, np. Bielik 1.5B/4.5B/11B, Qwen, Gemma, PLLuM) | B. Klasyfikacja tokenów / NER (HerBERT, XLM-R, mmBERT, GLiNER, Privacy Filter) | C. Hybryda: walidatory + NER + deterministyczny renderer (**rekomendacja**) |
|---|---|---|---|
| Recall na identyfikatorach strukturalnych (PESEL, IBAN) | średni–wysoki; myli cyfry, nie liczy sum kontrolnych | wysoki, ale gubi nietypowe formaty | **bardzo wysoki** – regex + suma kontrolna daje praktycznie 100% na poprawnych numerach |
| Recall na imionach, adresach, kontekście | wysoki (rozumie kontekst) | wysoki po fine-tuningu domenowym | wysoki (NER) + opcjonalny 2. przebieg LLM |
| Ryzyko halucynacji / modyfikacji tekstu | **wysokie** – przepisuje cały tekst | brak – zwraca tylko offsety | **brak** – tekst zmieniany wyłącznie w zakresach spanów |
| Spójna numeracja `[IMIĘ_1]` | trzeba ją wytrenować, zawodna przy długich dokumentach | wymaga postprocessingu | deterministyczny moduł (lematyzacja + dopasowanie) |
| Szybkość / koszt inferencji | wolny (generacja ~długości wejścia), wymaga GPU | szybki, działa na CPU (INT8 ONNX) | szybki, CPU; LLM tylko dla niepewnych fragmentów |
| Wyjaśnialność / audyt | słaba | dobra (span + etykieta + score) | **najlepsza** (każda decyzja ma źródło: reguła / model / próg) |
| Dane potrzebne na MVP | dziesiątki tys. par wejście–wyjście | tysiące–kilkanaście tys. oznaczonych dokumentów | jak B; reguły nie potrzebują danych |
| Atrakcyjność dla inwestorów | „sexy”, ale trudno obronić niezawodność | solidna, „nudna” | **najlepsza historia:** „gwarantowana wierność + mierzalny leak rate + działa on-prem na CPU” |

### Uzasadnienie wyboru

- **Recall to metryka nadrzędna.** W anonimizacji jeden przeoczony PESEL oznacza incydent. Walidatory sum kontrolnych dają deterministyczną pewność dla identyfikatorów, a model ML zajmuje się tym, czego regex nie złapie: imionami w odmianie, adresami w luźnej formie, opisami zdrowia.
- **Wierność tekstu.** W architekturze C wyjście powstaje z oryginału przez podmianę zakresów `[start, end)`. Tekst poza encjami nie może się zmienić z definicji, co da się udowodnić testem automatycznym. Tego LLM nie zagwarantuje.
- **Koszt.** Model ok. 300M w INT8 ONNX zajmuje ok. 0,3 GB (tyle podaje bards.ai dla v2: 1,2 GB FP32 → 0,3 GB INT8, przy F1 spadającym z 0,973 do 0,968).\[6\]\[13\] Działa na CPU w banku czy szpitalu bez GPU, a w sektorach regulowanych to warunek wejścia.
- **Dla inwestorów i grantodawców** „LLM do anonimizacji” brzmi atrakcyjniej, więc w narracji pokaż komponent AI uczciwie: (1) własny model NER trenowany na danych syntetycznych generowanych lokalnie przez Bieliki, (2) opcjonalny „LLM verifier” – Bielik 1.5B/4.5B sprawdza fragmenty o niskiej pewności, (3) roadmapa, w której finansowanie idzie na większy model kontekstowy, quasi-identyfikatory i odporność na ataki inferencyjne LLM. Reprezentatywność generatywnego LLM nie jest tu potrzebna; potrzebna jest mierzalna przewaga.

### Docelowy pipeline MVP

1. **Normalizacja wejścia** (Unicode NFC, zachowanie oryginalnych offsetów).
2. **Warstwa reguł:** PESEL (11 cyfr, suma kontrolna, poprawna data), NIP (10 cyfr, wagi), REGON (9/14), IBAN PL (mod 97), nr dowodu osobistego (3 litery + 6 cyfr, suma kontrolna), paszport, karty płatnicze (Luhn), telefony, e-maile, kody pocztowe, nr rejestracyjne, VIN, nr KW, a także konfigurowalne wzorce klienta (nr polisy, nr szkody, nr umowy). Liczby bez poprawnej sumy kontrolnej nie są odrzucane, tylko oznaczane jako „podejrzane” – literówka w PESEL nadal jest PESEL-em.
3. **Model NER** (BIO/BIOES, okno 512–8k tokenów): osoby, adresy, lokalizacje, organizacje, daty urodzenia, dane zdrowotne, stanowiska, kwoty i inne kategorie kontekstowe.
4. **Fuzja:** reguła z poprawną sumą kontrolną wygrywa, a przy konflikcie typów obowiązuje priorytet. Próg modelu ustawiasz pod recall, np. tak, by osiągnąć ≥0,98 na zbiorze walidacyjnym.
5. **Koreferencja i numeracja:** lematyzacja (Morfeusz 2 / spaCy pl) i normalizacja wielkości liter, dzięki czemu „Jan Kowalski”, „Kowalskiego”, „J. Kowalski” → `[OSOBA_1]`. Ten sam IBAN → `[IBAN_1]`.
6. **Renderer:** tryb `mask` (placeholdery), `pseudonymize` (placeholdery + zaszyfrowana mapa, np. AES-GCM, z TTL) i `synthetic` (realistyczne dane z Faker pl_PL z poprawnymi sumami kontrolnymi i zgodną odmianą – rozszerzenie po MVP).
7. **(Opcjonalnie) LLM verifier:** Bielik 1.5B/4.5B dostaje *już zamaskowany* tekst i odpowiada, czy zostały w nim dane identyfikujące. Model wskazuje fragment, a decyzję podejmuje kod, więc LLM nigdy nie generuje wyjścia.

**Wybór enkodera:** zacznij od fine-tuningu `bardsai/eu-pii-anonimization-multilang-v2` (Apache 2.0, kontekst 8k, polskie przykłady już w treningu) albo `openai/privacy-filter` (Apache 2.0, 128k kontekstu, ale tylko 8 kategorii).\[2\]\[6\] Jako polski baseline „od zera” użyj HerBERT-large lub Polish RoBERTa. Na polskim NER (PolEval 2018/NKJP) HerBERT large uzyskał wynik 92,1 i F1 exact 89,9, a Polish RoBERTa base 91,4 (PolDeepNer2, CLARIN-PL).\[14\] Sprawdź licencje checkpointów przed publikacją.

## 2. Ile danych treningowych

Punkty odniesienia z istniejących prac:

| Praca / zbiór | Skala | Wniosek |
|---|---|---|
| GLiNER2-PII (fastino) | **4 910** syntetycznych przykładów z adnotacjami PII, 42 typy encji w 7 kategoriach (arXiv 2605.09973) | według autorów mały, dobrze zaprojektowany zbiór syntetyczny wystarczył do najwyższego span F1 na SPY wśród pięciu porównywanych systemów, w tym OpenAI Privacy Filter |
| gliner2-PII-basque (tknika) | 2 842 zdania NER + 6 000 syntetycznych zdań PII (14 typów z poprawnymi sumami kontrolnymi) | adaptacja do nowego języka: micro F1 na PII z 0,742 → 0,845 (v1) → 0,905 (v2)\[15\] |
| NVIDIA Nemotron-PII | 100 000 rekordów (50k/50k), 55+ typów, CC BY 4.0 | skala „produkcyjna” dla jednego języka\[16\]\[17\]\[18\] |
| ai4privacy pii-masking-400k | 406 896 wpisów, 20,6 mln tokenów, 2,36 mln tokenów PII\[19\] | skala wielojęzyczna |
| KPWr (PolEval 2019) | 1 629 dokumentów, >24 tys. adnotacji\[20\] | ręczny polski korpus NER – mały, ale realny |

**Rekomendowane wolumeny (szacunki autora na podstawie powyższych punktów odniesienia):**

| Podejście | MVP | Produkcja |
|---|---|---|
| NER/hybryda (rekomendacja) | 5–20 tys. dokumentów syntetycznych (ok. 2–10 mln tokenów) + 500–1000 dokumentów złotego zbioru (min. ~100 wystąpień każdego typu encji w teście) | 50–150 tys. dokumentów, w tym min. kilka tysięcy realnych, spseudonimizowanych dokumentów od partnerów (zgodnie z RODO), min. ~1 000 wystąpień na typ w treningu |
| Generatywny LLM (dla porównania) | 20–50 tys. par wejście → wyjście z maską | 100–300 tys. par + dane do preferencji (DPO) karzące modyfikację tekstu |
| Reguły | 0 danych treningowych, ale ~50–200 przypadków testowych na walidator | jw. + testy property-based (generator poprawnych i błędnych numerów) |

## 3. Źródła danych dla polskiego

**Gotowe zbiory (sprawdzaj licencje!):**
- **ai4privacy `pii-masking-openpii-1.5m`** (CC BY 4.0, 1,64 mln wierszy, 30 języków, w tym polski) i `openpii-1m` (1 428 143 przykładów, 23 języki europejskie, 19 typów).\[21\]\[22\] Dokładna liczba polskich próbek nie jest publikowana; sprawdź ją filtrem `language='pl'` w Data Studio. Zestawy branżowe ai4privacy (np. `pii-masking-financial-pfi-400k`, `pii-masking-health-phi-400k`) wymagają akceptacji warunków, a `phi-masking-100k` w pełnej wersji jest komercyjny („All Rights Reserved”).\[23\]\[24\]
- **NVIDIA Nemotron-PII** (CC BY 4.0, angielski) – nadaje się do tłumaczenia lub adaptacji struktury dokumentów i taksonomii.\[25\]
- **KPWr-NER** (`clarin-pl/kpwr-ner`, CC BY 3.0, 82 klasy)\[26\] i **NKJP / PolEval 2018** – realne polskie nazwy własne w odmianie; zmapuj je do własnej taksonomii (osoba, lokalizacja, organizacja).
- **Orzeczenia (SAOS / portale orzeczeń)** – teksty sądowe są już zanonimizowane, więc nie dostarczają „złotych” danych osobowych. Przydają się jako realistyczne szablony języka prawnego, w które wstrzykujesz syntetyczne dane w miejsce znaczników anonimizacji.
- **Medyczne:** publiczne polskie zbiory kliniczne z danymi osobowymi praktycznie nie istnieją. Generuj syntetyczną dokumentację (karty informacyjne, skierowania, epikryzy) z kodami ICD-10 i nazwami leków z publicznych rejestrów.

**Generowanie syntetyczne (główne źródło):**
1. **Szablony + Faker pl_PL:** imiona i nazwiska z odmianą (Morfeusz do generowania form przypadków), adresy z TERYT, PESEL zgodny z datą urodzenia i płcią, NIP/REGON/IBAN z poprawnymi sumami kontrolnymi. Etykiety są tu z definicji idealne, bo znasz offsety wstrzykniętych wartości.
2. **LLM lokalnie (Bielik 11B/4.5B, PLLuM, Qwen) jako pisarz dokumentów:** generuje treść polisy, zgłoszenia szkody, umowy kredytowej, wyciągu, korespondencji z klientem, wypisu ze szpitala, czatu z infolinią – **z placeholderami w miejscu PII**. Potem kod wstrzykuje wartości z Fakera i zna dokładne offsety. Nie pozwalaj LLM-owi samodzielnie oznaczać encji – to źródło szumu.
3. **Augmentacja „brudu”:** literówki, brak polskich znaków, OCR-owe błędy (0/O, 1/l), numery rozbite spacjami, wielkie litery, tabele, maile z podpisami.
4. **Hard negatives:** nazwiska będące rzeczownikami pospolitymi (Kowal, Wróbel, Zima), nazwy ulic od nazwisk, numery techniczne o wyglądzie PESEL-u bez poprawnej sumy, osoby publiczne. Dzięki nim precision nie spada.

**Licencje i RODO:**
- Dane w 100% syntetyczne nie są danymi osobowymi, więc publikacja datasetu na HF jest bezpieczna. Nadal sprawdzaj, czy LLM nie „wyrecytował” prawdziwych osób; filtruj nazwiska znanych osób lub losuj je wyłącznie z Fakera.
- Dane od pracodawcy lub klientów: **nie używaj bez umowy i podstawy prawnej**. Bezpieczna ścieżka to zbiór ewaluacyjny przetwarzany wyłącznie on-prem u partnera (model jedzie do danych, nie odwrotnie), z umową powierzenia lub NDA i bez publikacji.
- Licencja wyjściowego datasetu musi być zgodna ze źródłami (CC BY 4.0 wymaga atrybucji; CC BY 3.0 KPWr – także). Licencja modelu bazowego (Apache 2.0 vs licencje Bielika/PLLuM) determinuje licencję modelu pochodnego.

## 4. Taksonomia encji i ramy prawne

### Proponowana taksonomia MVP (ok. 30 typów, 6 grup)

| Grupa | Encje (placeholder) | Metoda |
|---|---|---|
| Identyfikacja osoby | `[OSOBA_n]`, `[IMIĘ_n]`, `[NAZWISKO_n]`, `[DATA_URODZENIA]`, `[WIEK]`, `[PŁEĆ]` | NER |
| Identyfikatory państwowe | `[PESEL]`, `[NR_DOWODU]`, `[NR_PASZPORTU]`, `[NR_PRAWA_JAZDY]`, `[NIP]` (osoby fizycznej), `[REGON]` | regex + suma kontrolna |
| Kontakt i lokalizacja | `[ADRES_n]`, `[KOD_POCZTOWY]`, `[MIEJSCOWOŚĆ]`, `[TELEFON]`, `[EMAIL]`, `[IP]`, `[GEO]` | regex + NER |
| Finanse (fintech) | `[IBAN]`, `[NR_RACHUNKU]`, `[NR_KARTY]`, `[CVV]`, `[NR_UMOWY]`, `[KWOTA]` (opcjonalnie), `[DOCHÓD]` | regex + Luhn/mod97 + NER |
| Ubezpieczenia (insurtech) | `[NR_POLISY]`, `[NR_SZKODY]`, `[NR_REJESTRACYJNY]`, `[VIN]`, `[NR_KW]` | konfigurowalne wzorce + NER |
| Zdrowie – art. 9 RODO (medtech) | `[DANE_ZDROWOTNE]`, `[ROZPOZNANIE]`, `[ICD10]`, `[LEK]`, `[NR_DOKUMENTACJI]`, `[PLACÓWKA]`, `[LEKARZ_n]`, `[NPWZ]` | NER + słowniki + regex |
| Pozostałe art. 9/10 | pochodzenie etniczne, poglądy, wyznanie, związki zawodowe, orientacja, biometria, dane o wyrokach | NER (trudne – roadmapa) |
| Quasi-identyfikatory | stanowisko, pracodawca, rzadkie zdarzenia, daty zdarzeń | NER + polityka (w MVP raportowane, nie zawsze maskowane) |

Taksonomia bards.ai (35 klas, m.in. HEALTH_DATA, CRIMINAL_OFFENCE_DATA, ORGANIZATION_IDENTIFIER dla NIP/REGON firm) jest dobrym punktem odniesienia.\[13\]\[27\] Mapowanie jej na Twoje etykiety ułatwi porównanie.\[6\]

### Ramy prawne – co trzeba wiedzieć (to nie jest porada prawna)

- **RODO, anonimizacja vs pseudonimizacja:** dane zanonimizowane (motyw 26) wychodzą poza RODO, dane spseudonimizowane (art. 4 pkt 5) nie. EDPB w Wytycznych 01/2025 podkreśla, że pseudonimizacja sama w sobie zwykle nie wystarcza do zgodności, ale wspiera minimalizację, privacy by design (art. 25) i bezpieczeństwo (art. 32). Wprowadza też pojęcie „domeny pseudonimizacji”.\[28\]\[29\]\[30\] Wyrok TSUE C-413/23 P (4.09.2025) potwierdził podejście relatywne: dla odbiorcy, który realistycznie nie może zidentyfikować osoby, dane mogą nie być osobowymi. Administrator nadal musi jednak informować o odbiorcach.\[11\]\[31\] **Wniosek produktowy:** tryb `mask` bez mapy, wspierany usuwaniem quasi-identyfikatorów, zbliża się do anonimizacji z perspektywy zewnętrznego LLM. Tryb `pseudonymize` to pseudonimizacja, a mapa musi zostać u administratora.
- **Art. 9 RODO:** dane o zdrowiu to kategoria szczególna, więc w medtech i w ubezpieczeniach zdrowotnych/życiowych recall na tej klasie jest krytyczny.
- **EU AI Act (rozporządzenie 2024/1689):** samo narzędzie do anonimizacji raczej nie jest systemem wysokiego ryzyka. Pomaga jednak klientom spełnić wymogi zarządzania danymi (art. 10) i ochrony prywatności w cyklu życia AI. Harmonogram obowiązków dla systemów wysokiego ryzyka był w 2025–2026 przedmiotem propozycji przesunięcia (pakiet „digital omnibus”) – zweryfikuj aktualny stan przed pisaniem wniosku.
- **DORA** (stosowane od 17.01.2025): w finansach i ubezpieczeniach zarządzanie ryzykiem ICT i dostawcami zewnętrznymi. Wysyłanie danych klientów do zewnętrznego LLM to ryzyko dostawcy ICT, a lokalny, otwarty filtr on-prem je ogranicza. To argument sprzedażowy dla CISO.
- **Tajemnice sektorowe:** tajemnica bankowa (art. 104 Prawa bankowego), tajemnica ubezpieczeniowa (art. 35 ustawy o działalności ubezpieczeniowej i reasekuracyjnej), tajemnica lekarska (art. 40 ustawy o zawodach lekarza i lekarza dentysty) oraz prawa pacjenta do poufności i dokumentacji (ustawa o prawach pacjenta i RPP). Obejmują one także informacje, które nie są „klasycznym PII” (np. fakt posiadania kredytu czy przebieg leczenia), dlatego taksonomia musi wykraczać poza imię i PESEL.

## 5. Trening na Twoim sprzęcie

**Co jest realne na RTX 3090 Ti 24 GB + RTX 3080 10 GB (szacunki):**

| Zadanie | Karta | Metoda | Szacowany czas |
|---|---|---|---|
| Enkoder ok. 300M (mmBERT/XLM-R base), 20k dokumentów × 512 tokenów, 3–5 epok | 3090 Ti | pełny fine-tuning, bf16 | ~1–4 h |
| HerBERT-large / XLM-R large (~560M) | 3090 Ti | pełny fine-tuning, bf16, gradient checkpointing | ~3–8 h |
| Bielik 1.5B (generator / verifier) | 3090 Ti | LoRA bf16 albo pełny FT z 8-bit Adam | kilka godzin na 10–30k przykładów |
| Bielik 4.5B | 3090 Ti | QLoRA 4-bit (Unsloth) | ~10–20 h na 30k przykładów ~1k tokenów |
| Bielik 11B | 3090 Ti | QLoRA 4-bit, krótki kontekst, mały batch | możliwe, ale na granicy; lepiej w chmurze |
| Inferencja Bielika 11B/4.5B do generowania danych | 3090 Ti (+3080) | vLLM / llama.cpp, kwantyzacja | dziesiątki tysięcy dokumentów na dobę – zależnie od długości |
| Ewaluacja, baseline'y, Presidio, demo | 3080 10 GB | inferencja | równolegle z treningiem na 3090 Ti |

**Frameworki:**
- Enkoder: **HF Transformers `Trainer` + `datasets` + `seqeval`** (lub biblioteka GLiNER / GLiNER2, jeśli idziesz w zero-shot). Eksport do ONNX z kwantyzacją INT8 (Optimum).
- LLM: **Unsloth** na pojedynczej karcie – darmowa wersja jest najszybsza na jednym GPU. Multi-GPU w Unsloth działa przez Accelerate/DDP, ale „enhanced multi-GPU” to wersja Pro.\[32\]\[33\]\[34\] **Axolotl** (FSDP/DeepSpeed ZeRO za darmo) lub **HF TRL + PEFT**, gdy potrzebujesz kilku kart.\[35\]
- **Nierówne karty:** DDP i FSDP synchronizują się do najwolniejszej i najmniejszej karty, więc 3080 10 GB ograniczy batch i model. Nie łącz ich w jeden trening. Używaj 3090 Ti do treningu, a 3080 do generowania danych, ewaluacji i demo. Ewentualnie model rozdziel warstwami (`device_map="balanced"`) tylko do inferencji dużych modeli.\[33\]

**Czy kupować trzecią kartę? Nie teraz.**
- RTX 5090 (32 GB) kosztował w Polsce 14.09.2026 od 24 999 zł do 33 091 zł (mediana 27 872 zł) przy cenie premierowej 10 299 zł.\[12\] Za tę kwotę kupisz tysiące godzin RTX 4090 w chmurze.
- Jeśli już kupować, to używaną RTX 3090 24 GB: ta sama architektura co 3090 Ti, czyli symetryczna para 2×24 GB do DDP lub FSDP. Ceny rynku wtórnego zweryfikuj samodzielnie, bo ich nie sprawdzałem. Pamiętaj też o zasilaczu (≥1200–1600 W przy dwóch 3090) i przepływie powietrza.
- **Chmura (RunPod, 2026):** RTX 4090 – 0,34 USD/h (Community) / 0,69–0,74 USD/h (Secure); RTX 5090 – ok. 0,99 USD/h; A100 80 GB – 1,19–1,59 USD/h; H100 PCIe – 1,99–2,89 USD/h.\[36\]\[37\]\[38\] Przykład z rynku: 20-godzinny QLoRA na A100 to ok. 28 USD.\[39\] Vast.ai bywa tańszy (marketplace), Lambda droższa (H100 SXM ok. 3,99 USD/h).\[40\] **Budżet chmurowy na całe MVP: ~50–300 USD.**
- **PLGrid (Cyfronet):** Athena (węzły 8× A100 40 GB) i Helios (440× GH200 96 GB).\[41\]\[42\] O granty mogą wnioskować tylko osoby z afiliacją naukową (pracownik uczelni lub instytutu, doktorant), a grant pilotażowy daje 1000 godzin obliczeniowych.\[43\] **Wymaga partnera akademickiego** – to i tak dobry ruch pod granty B+R.

## 6. Ewaluacja

**Metryki (raportuj wszystkie, per typ encji i per domena):**
- **Recall i precision na poziomie encji** (strict i partial match; seqeval). **Recall ważony ryzykiem:** PESEL, IBAN i diagnoza ważą więcej niż miejscowość.
- **Leak rate:** odsetek dokumentów, w których po maskowaniu został *jakikolwiek* bezpośredni identyfikator, oraz odsetek „wartości PII” (string-match oryginałów na wyjściu). To metryka biznesowa numer 1. Cel MVP: <1% dokumentów z wyciekiem identyfikatora bezpośredniego na złotym zbiorze.
- **Wierność tekstu poza encjami:** po usunięciu spanów różnica znaków ma wynosić dokładnie 0 (test automatyczny). Dla porównania z LLM-ami: chrF/normalized edit distance.
- **Spójność numeracji:** odsetek par wzmianek o tej samej osobie, które dostały ten sam placeholder (i różnych osób – różne).
- **Użyteczność:** to samo zadanie downstream (streszczenie szkody, klasyfikacja reklamacji, ekstrakcja danych polisy) wykonane przez zewnętrzny LLM na oryginale i na wersji zamaskowanej, z porównaniem jakości.
- **Wydajność:** dokumenty/s na CPU i GPU, p95 latencji, RAM.

**Złoty zbiór testowy:** 500–1000 dokumentów w 6–8 typach (polisa, zgłoszenie szkody, umowa kredytowa, wyciąg, mail od klienta, transkrypcja infolinii, wypis szpitalny, skierowanie). Około 70% realistycznej syntetyki pisanej ręcznie lub przez LLM i ręcznie poprawionej, około 30% „trudnych” przypadków. Dwóch anotatorów, wytyczne anotacji, zgodność Cohen's kappa/F1 między anotatorami. Publikuj go jako **PL-PII-Bench** (odrębny dataset na HF) – to Twój najważniejszy aktyw marketingowy i grantowy.

**Red teaming i reidentyfikacja:**
- Ataki formatów: PESEL ze spacjami, słownie, w tabeli, w URL-u, w base64; imiona zdrobniałe i w wołaczu; adresy bez „ul.”.
- **Atak inferencyjny LLM:** daj silnemu LLM zamaskowany tekst i poproś o wywnioskowanie tożsamości, miejsca czy wieku. Staab, Vero, Balunović i Vechev (ETH Zurich) w pracy „Language Models are Advanced Anonymizers” (ICLR 2025), testując 13 LLM-ów oraz Presidio i Azure Language Services, stwierdzają, że „current industry-standard text anonymizers are largely insufficient at protecting users from such attacks, as they are unable to pick up on revealing yet complex and context-dependent cues”. Mierz to jako osobną metrykę „residual inference risk” – dobra przestrzeń na roadmapę grantową.
- Atak powiązań: kilka dokumentów tego samego klienta → czy z quasi-identyfikatorów da się złożyć tożsamość.

**Baseline'y do tabeli porównawczej:**
1. Microsoft Presidio (z polskim spaCy) – wariant „out of the box” i z polskimi recognizerami.
2. `anon-legal-pl` (Presidio + spaCy `pl_core_news_lg` + opcjonalnie Bielik przez Ollamę, walidacja PESEL/NIP/REGON, Apache 2.0).\[44\]\[45\]
3. `bardsai/eu-pii-anonimization` (PL) i `-multilang-v2`.
4. `openai/privacy-filter` (Apache 2.0, bez wyników dla polskiego).
5. GLiNER-PII (knowledgator, NVIDIA) – zero-shot z polskimi etykietami.
6. Zero-shot LLM: Bielik 11B v3 z promptem maskującym oraz GPT/Claude (tylko na danych syntetycznych!).
7. Opcjonalnie komercyjne: Limina (dawniej Private AI) – trial.

Kontekst z literatury: w benchmarku LLM-Anonymizer (Wiest i in., zespół J.N. Kathera, NEJM AI 2(4), marzec 2025, DOI 10.1056/AIdbp2400537; 250 realnych listów klinicznych, niemiecki) „CliniDeID and Presidio anonymized PII in the clinical letters with lower sensitivity (0.84 and 0.82, respectively) on a character-wise basis”, lokalny Llama-2 7B miał czułość ok. 0,84, a najlepszy lokalny Llama-3 70B – 99,24% (pominięte 0,76% PII). Generyczne narzędzia zostawiają więc ~16–18% identyfikatorów w dokumentach medycznych, co uzasadnia model domenowy.

## 7. Konkurencja i rynek

| Rozwiązanie | Typ | Polski? | Uwagi |
|---|---|---|---|
| Microsoft Presidio | open source (MIT), framework | przez rozszerzenia | standard de facto; jakość zależy od dodanych modeli |
| OpenAI Privacy Filter | open-weight, Apache 2.0 | brak raportowanych wyników | 8 kategorii, 128k kontekstu, F1 96% (EN, PII-Masking-300k); OpenAI zastrzega, że to nie jest narzędzie certyfikowanej anonimizacji\[2\]\[3\]\[46\] |
| GLiNER2-PII (fastino), GLiNER-PII (knowledgator, NVIDIA) | open source | nie (7 języków) / zero-shot | knowledgator gliner-pii-base-v1.0: F1 80,99% (precision 79,28%, recall 82,78%) na synthetic-multi-pii-ner-v1 według karty HF, ale tylko 0,368 średniego span F1 na benchmarku SPY (arXiv 2605.09973) |
| bards.ai eu-pii-anonimization (PL, multilang, v2) | open source, Apache 2.0 (multilang) | **tak** | najbliższy konkurent; brak polskiego benchmarku i encji branżowych |
| pii.tools | open source, Apache 2.0, przeglądarka (WASM) | tak | 35 typów, oparte na modelach bards.ai\[47\] |
| anon-legal-pl, matematic-anonimizacja-pl, priv-masker (NASK spaCy) | open source | tak | reguły + spaCy; prawo i administracja |
| Bluur (BTC), Redactable | komercyjne | tak | anonimizacja dokumentów, głównie prawo/administracja\[48\] |
| Limina (dawniej Private AI) | komercyjne, on-prem kontener | 52 języki | 50+ typów encji, redakcja/pseudonimizacja/synteza; Series A w 2022 r.: 8 mln USD (10,7 mln CAD, BetaKit); zmiana nazwy na Limina ogłoszona 5.03.2026 bez wpływu na produkty i klientów (getlimina.ai) |
| Protecto | komercyjne, privacy vault | 50+ języków | 200+ typów PII/PHI/PCI\[49\] |
| Skyflow | komercyjne, vault + tokenizacja | – | mocne w fintech (PCI DSS)\[50\] |
| Nightfall | komercyjne, DLP | – | ochrona użycia AI przez pracowników\[51\] |

**Luki, w które warto celować:**
1. **Polskie dokumenty sektorów regulowanych** – encje insurtech/medtech/fintech, których nie ma w generycznych taksonomiach.
2. **Publiczny, rzetelny benchmark polski** – nikt go nie ma, a klienci i grantodawcy go potrzebują.
3. **Spójna pseudonimizacja z fleksją** i odwracalna mapa (round-trip: maskuj → zewnętrzny LLM → odmaskuj w poprawnej formie gramatycznej).
4. **Gateway on-prem dla LLM** (proxy OpenAI-compatible) z audytem: „udowodnij, że PII nie opuściło firmy”.\[52\]

## 8. Finansowanie

| Źródło | Dla kogo | Kwota / termin | Dopasowanie |
|---|---|---|---|
| **NLnet / NGI Zero Commons Fund** | osoby fizyczne i organizacje | 5–50 tys. EUR; **ostatni nabór zamknięty 1.06.2026**; NLnet prowadzi inne programy (następny termin 3.11.2026) | idealne dla open source – sprawdź aktualne programy NLnet\[53\]\[54\] |
| **FENG Ścieżka SMART (PARP, MŚP)** | MŚP z siedzibą w Polsce | nabór B+R 29.10–29.12.2026, budżet 500 mln zł; w naborze I/2026 min. 3 mln zł kosztów B+R, do 80% dofinansowania | za duże na MVP; realne dla spółki po MVP, z partnerem naukowym\[55\]\[56\]\[57\] |
| **NCBR** (programy B+R, konkursy tematyczne AI) | firmy, konsorcja z nauką | zmienne | monitoruj; mocny argument to konsorcjum z uczelnią (PLGrid!) |
| **EIC Accelerator / Horizon Europe (Cluster 4, AI & data)** | startupy / konsorcja | duże granty + equity | po walidacji rynkowej; „trustworthy AI” i suwerenność danych to pasujące tematy |
| Prototype Fund | – | – | program niemiecki, dla osób z Niemiec – raczej niedostępny |
| Akceleratory i VC w CEE (AI/regtech) | spółka | pre-seed/seed | potrzebne: MVP, benchmark, 2–3 LOI od firm z branży |
| **Ekosystem SpeakLeash/Bielik, PLLuM** | społeczność | nieformalnie | wiarygodność, dane, współautorzy, dostęp do mocy (współpraca z ACK Cyfronet) |

**Co musi zawierać MVP i demo, żeby przekonać:**
1. **Tabela benchmarku** na PL-PII-Bench: Twój model vs Presidio, OpenAI Privacy Filter, bards.ai, Bielik zero-shot – recall, leak rate, wierność, latencja na CPU.
2. **Live demo (HF Space):** wklejasz zgłoszenie szkody albo wypis → widzisz podświetlone encje → wersja zamaskowana → odpowiedź zewnętrznego LLM → odmaskowanie. Przy tym licznik „0 znaków zmienionych poza encjami”.
3. **Gateway w 5 minut:** `docker run`, endpoint zgodny z OpenAI API, który maskuje w locie.
4. **2–3 listy intencyjne** od firm z insurtech, fintech lub medtech (Twoja sieć kontaktów i Eskadra Bielika) oraz opis pilota.
5. **Roadmapa „na co pójdą pieniądze”:** większy model kontekstowy, quasi-identyfikatory, odporność na wnioskowanie LLM, OCR/PDF, kolejne języki CEE, certyfikacja/audyt zewnętrzny.

## 9. Plan działania (12 tygodni, 1 osoba po godzinach ~10–15 h/tydz.)

| Tydz. | Kamień milowy | Rezultat |
|---|---|---|
| 1 | Taksonomia + wytyczne anotacji + repo | `TAXONOMY.md`, schemat JSON spanów, decyzja o licencji (Apache 2.0) |
| 2 | Warstwa reguł + testy property-based | walidatory PESEL/NIP/REGON/IBAN/dowód/Luhn/wzorce polis; >200 testów |
| 3–4 | Generator danych syntetycznych | szablony 8 typów dokumentów, Faker pl_PL + Morfeusz, Bielik lokalnie jako pisarz; 10–20 tys. dokumentów |
| 4–5 | Złoty zbiór v0.1 | 300 dokumentów ręcznie zweryfikowanych (docelowo 500–1000), drugi anotator na próbce |
| 5 | Baseline'y | wyniki Presidio, anon-legal-pl, bards.ai, Privacy Filter, GLiNER, Bielik zero-shot |
| 6–7 | Trening modelu NER v1 | fine-tuning 2–3 kandydatów (mmBERT/bards v2, XLM-R, HerBERT), wybór, kalibracja progu pod recall |
| 8 | Fuzja + koreferencja + renderer | tryby `mask` i `pseudonymize` (mapa szyfrowana), test wierności = 0 zmian |
| 9 | Red teaming + iteracja danych | hard negatives, augmentacja OCR, v2 modelu; raport leak rate |
| 10 | Eksport i pakowanie | ONNX INT8, biblioteka `pip`, Docker gateway (OpenAI-compatible) |
| 11 | Publikacja na Hugging Face | model card (zastosowania, ograniczenia, metryki per encja, „to nie jest certyfikat anonimizacji”), dataset card (syntetyczność, licencje źródeł), PL-PII-Bench, Space (Gradio) |
| 12 | Materiały dla finansowania | one-pager, deck 10 slajdów, wpis techniczny, zgłoszenie do NLnet lub innego programu, rozmowy o LOI |

**Mały zespół (2–3 osoby):** ten sam zakres w ~6–8 tygodni, z dodatkowym anotatorem/ekspertem domenowym (ubezpieczenia/medycyna) i większym złotym zbiorem.

**Publikacja na HF – checklista:**
- Model: Apache 2.0 (jeśli baza na to pozwala), karta z tabelą metryk per typ encji i per domena, znane ograniczenia (quasi-identyfikatory, dane art. 9 w języku potocznym), przykłady użycia, wersje ONNX.
- Dataset: syntetyczny korpus treningowy (CC BY 4.0) + osobno PL-PII-Bench (z zablokowanym lub wersjonowanym testem, by uniknąć kontaminacji).
- Space: demo z trybami maskowania, wizualizacja spanów, przycisk „wyślij do LLM i odmaskuj”.

**Open-core i monetyzacja:**
- **Open source (Apache 2.0):** model bazowy, reguły, biblioteka, benchmark.
- **Enterprise:** pakiety domenowe (insurtech/medtech/bank) dotrenowane na danych klienta on-prem; gateway z audytem, RBAC, zarządzaniem mapami (vault, TTL, HSM); obsługa PDF/OCR; SLA i wsparcie; wdrożenia on-prem/air-gapped.
- **Usługi:** fine-tuning na danych klienta u klienta, audyt leak rate przed wdrożeniem AI, szkolenia (Twoja rola trenera Bielika to atut).
- **Certyfikacja:** zewnętrzny audyt metodologii (np. z kancelarią RODO lub ośrodkiem akademickim) jako produkt premium. Nie obiecuj „certyfikatu anonimizacji” – takiego formalnego certyfikatu RODO nie ma.

## Caveats

- **Szacunki:** wolumeny danych, czasy treningu i budżety chmurowe to szacunki inżynierskie na podstawie podobnych prac, a nie zmierzone wyniki. Zweryfikuj je pierwszym przebiegiem.
- **Wyniki konkurencji są w dużej mierze samodzielnie raportowane** (bards.ai „F1 95%”, OpenAI 96% na angielskim benchmarku). Nikt nie publikuje rzetelnych liczb dla polskiego, dlatego własny benchmark jest konieczny, a nie opcjonalny. Wyniki bards.ai v2 na Nemotron i OpenPII nie są held-out, bo te zbiory były w treningu.\[6\]
- **Ceny GPU** w Polsce były w 2026 r. ekstremalnie zmienne. Cen używanych RTX 3090 nie weryfikowałem. Ceny chmurowe różnią się zależnie od źródła i daty.
- **Finansowanie:** ostatni nabór NGI Zero Commons Fund jest zamknięty.\[53\] Ścieżka SMART wymaga spółki i dużego budżetu B+R. Szczegóły programów NCBR, EIC i inwestorów CEE wymagają aktualnej weryfikacji.
- **Prawo:** opis RODO, AI Act, DORA i tajemnic sektorowych jest orientacyjny i wymaga konsultacji z prawnikiem, zwłaszcza status wydłużenia terminów AI Act i to, czy konkretny tryb maskowania spełnia próg anonimizacji w danym kontekście.
- **Konflikt interesów:** upewnij się, że umowa o pracę nie przypisuje pracodawcy praw do projektu i że nie używasz danych ani zasobów firmy bez zgody.

## Sources

1. [Comparing Best NER Models For PII Identification](https://www.protecto.ai/blog/best-ner-models-for-pii-identification/)
2. <https://arxiv.org/html/2608.18274v1>
3. [Introducing OpenAI Privacy Filter](https://openai.com/index/introducing-openai-privacy-filter/)
4. [OpenAI Releases Privacy Filter: A 1.5B-Parameter Open-Source PII Redaction Model with 50M Active Parameters - MarkTechPost](https://www.marktechpost.com/2026/04/28/openai-releases-privacy-filter-a-1-5b-parameter-open-source-pii-redaction-model-with-50m-active-parameters/)
5. [bardsai/eu-pii-anonimization · Hugging Face](https://huggingface.co/bardsai/eu-pii-anonimization)
6. [bardsai/eu-pii-anonimization-multilang-v2 · Hugging Face](https://huggingface.co/bardsai/eu-pii-anonimization-multilang-v2)
7. [fastino/gliner2-privacy-filter-PII-multi · Hugging Face](https://huggingface.co/fastino/gliner2-privacy-filter-PII-multi)
8. [The new EDPB guidelines on pseudonymization - LEXIA](https://www.lexia.it/en/2025/02/26/edpb-guidelines-pseudonymization/)
9. [CJEU clarifies concept of personal data for a transfer of pseudonymised data to third parties](https://www.aoshearman.com/en/insights/ao-shearman-on-data/cjeu-clarifies-concept-of-personal-data-for-a-transfer-of-pseudonymised-data-to-third-parties)
10. [Personal Data or Not? CJEU Weighs In on Pseudonymisation in EDPS v. SRB](https://www.goodwinlaw.com/en/insights/publications/2025/09/alerts-technology-dpc-personal-data-or-not)
11. [EU Court of Justice Clarifies Definition of “Personal Data” in the Context of Pseudonymization](https://www.hunton.com/privacy-and-cybersecurity-law-blog/eu-court-of-justice-clarifies-definition-of-personal-data-in-the-context-of-pseudonymization)
12. [Dlaczego RTX 5090 kosztuje w Polsce 25 000 zł](https://devstockacademy.pl/blog/branza-it-i-nowe-technologie/rtx-5090-cena-polska-25-tysiecy-2026/)
13. [PII Anonymizer](https://eu-pii.bards.ai/)
14. [GitHub - CLARIN-PL/PolDeepNer2: An improved tool for named entity recognition for Polish based on deep learning. · GitHub](https://github.com/CLARIN-PL/PolDeepNer2)
15. [tknika/gliner2-PII-basque · Hugging Face](https://huggingface.co/tknika/gliner2-PII-basque)
16. [--- library\_name: gliner license: other license\_name: nvidia-open-model-license](https://huggingface.co/nvidia/gliner-PII/raw/main/README.md)
17. [GitHub - NVIDIA-NeMo/Nemotron: Developer Asset Hub for NVIDIA Nemotron — A one-stop resource for training recipes, usage cookbooks, datasets, and full end-to-end reference examples to build with Nemotron models · GitHub](https://github.com/NVIDIA-NeMo/Nemotron)
18. [🛡️ Nemotron PII: Synthesized Data for Privacy-Preserving AI](https://huggingface.co/blog/nvidia/nemotron-pii)
19. [ai4privacy/pii-masking-400k · Datasets at Hugging Face](https://huggingface.co/datasets/ai4privacy/pii-masking-400k)
20. [(PDF) PolEval 2019 - the next chapter in evaluating Natural Language Processing tools for Polish](https://www.researchgate.net/publication/334480247_PolEval_2019_-_the_next_chapter_in_evaluating_Natural_Language_Processing_tools_for_Polish)
21. [ai4privacy/pii-masking-openpii-1m · Datasets at Hugging Face](https://huggingface.co/datasets/ai4privacy/pii-masking-openpii-1m)
22. [ai4privacy/pii-masking-openpii-1.5m · Datasets at Hugging Face](https://huggingface.co/datasets/ai4privacy/pii-masking-openpii-1.5m)
23. [ai4privacy/pii-masking-digital-pdi-350k · Datasets at Hugging Face](https://huggingface.co/datasets/ai4privacy/pii-masking-digital-pdi-350k)
24. [README.md · ai4privacy/phi-masking-100k at main](https://huggingface.co/datasets/ai4privacy/phi-masking-100k/blob/main/README.md)
25. [nvidia/Nemotron-PII · Datasets at Hugging Face](https://huggingface.co/datasets/nvidia/Nemotron-PII)
26. [clarin-pl/kpwr-ner · Datasets at Hugging Face](https://huggingface.co/datasets/clarin-pl/kpwr-ner)
27. [GitHub - semprerudi/awesome-pii-redaction: A curated list of resources about PII · GitHub](https://github.com/semprerudi/awesome-pii-redaction)
28. [Guidelines 01/2025 on Pseudonymisation](https://www.edpb.europa.eu/system/files/2025-01/edpb_guidelines_202501_pseudonymisation_en.pdf)
29. [EDPB advises on pseudonymisation for GDPR compliance](https://www.hunton.com/insights/publications/edpb-advises-on-pseudonymisation-for-gdpr-compliance)
30. [EDPB's Draft Guidelines 01/2025 on Pseudonymisation](https://allegiance.law/news/edpbs-draft-guidelines-01-2025-on-pseudonymisation/)
31. [CJEU Ruling on Pseudonymisation: Landmark Case C-413/23 P (EDPS v SRB) and Its Impact on GDPR Compliance](https://sgklegal.gr/en/cjeu-clarifies-scope-of-pseudonymisation/)
32. [Axolotl vs Unsloth vs TorchTune: Best LLM Fine-Tuning Frameworks in 2026](https://www.spheron.network/blog/axolotl-vs-unsloth-vs-torchtune/)
33. [Multi-GPU Fine-tuning with Unsloth](https://unsloth.ai/docs/basics/multi-gpu-training-with-unsloth)
34. [Pricing](https://www.unsloth.ai/pricing)
35. [unsloth-vs-axolotl-2026 - DEV Community](https://dev.to/jovan_chan_9500711396d4e6/unsloth-vs-axolotl-2026-18e1)
36. [GPU Cloud Pricing Comparison: Runpod vs Vast.ai (2026)](https://www.spheron.network/blog/gpu-cloud-pricing-comparison-runpod-vs-vastai-2026/)
37. [Top 12 Cloud GPU Providers for AI and ML in 2026](https://www.runpod.io/articles/guides/top-cloud-gpu-providers)
38. [RunPod Pricing](https://www.usagepricing.com/blueprint/runpod)
39. [RunPod vs Glows.ai: 7 Numbers Before You Rent a GPU](https://glows.ai/article/runpod_vs_glows_ai_en)
40. [RunPod vs Lambda vs Vast.ai: GPU Pricing 2026 - Tech Insider](https://tech-insider.org/runpod-vs-lambda-vs-vast-ai-2026/)
41. [Athena - Maciej Pawlik - Confluence](https://docs.cyfronet.pl/display/~plgpawlik/Athena)
42. [Offer - PLGrid](https://www.plgrid.pl/offer)
43. [Granty PLGrid](https://guide.plgrid.pl/pl/grants/plgrid)
44. [anon-legal-pl — anonimizacja dokumentów prawnych offline](https://www.ktzr.pl/legal-tech/anon-legal-pl/)
45. [GitHub - apiotrowski-afk/anon-legal-pl: Local-first PII anonymizer for Polish legal documents — built on Microsoft Presidio + spaCy. PESEL/NIP/REGON checksums, court-signature patterns, optional Bielik (local LLM) + OCR. 100% offline. Apache 2.0. · GitHub](https://github.com/apiotrowski-afk/anon-legal-pl)
46. [OpenAI's Privacy Filter: Open-Weight PII Redaction Model — Xcelit](https://www.xcelit.co.in/news/openais-privacy-filter-open-weight-pii-redaction-model)
47. [pii.tools — anonimizacja PII w przeglądarce](https://pii.tools/)
48. [Systemy do anonimizacji dokumentów](https://bluur.ai/pl/bluur-vs-redactable)
49. [Data Privacy Vault For AI & PII Protection](https://www.protecto.ai/product/privacy-vault/)
50. [Best PII Tokenization Software for LLMs (2026)](https://www.enigmavault.io/blog/best-pii-tokenization-software-for-llms/)
51. [Best AI Data Security Software for Enterprises (2026)](https://www.enigmavault.io/blog/best-ai-data-security-software-for-enterprises/)
52. [privacy-kit/README.md at main · bards-ai/privacy-kit · GitHub](https://github.com/bards-ai/privacy-kit/blob/main/README.md)
53. [NLnet; NGI Zero Commons Fund](https://nlnet.nl/commonsfund/)
54. [NLnet; About NGI Zero](https://nlnet.nl/NGI0/)
55. [Ścieżka SMART 2026 dla MŚP](https://openconcept.pl/sciezka-smart-2026-dla-msp-nabor-ogloszony-jesli-chcesz-zdazyc-musisz-zaczac-teraz/)
56. [Ścieżka SMART 2026 dla MŚP: nabór PARP na projekty B+R](https://mdotacje.pl/sciezka-smart-parp-2026/)
57. [Nabór FENG 003/26 w Ścieżce SMART](https://www.innology.pro/czytelnia/czy-to-juz-ostatni-konkurs-na-prace-b-r-w-ramach-sciezki-smart)
