# Brief: polski anonimizator PII (piitier)

## Problem

Developerzy w firmie ubezpieczeniowej boją się wycieku danych przy wysyłaniu dokumentów do zewnętrznego
LLM [EVIDENCE: session reply — rozmowy autora z developerami]. Autor napisał już piąty jednorazowy
skrypt anonimizujący, za każdym razem dla innych danych: CSV, plain text, polisy ubezpieczeniowe,
faktury, PDF, markdown [EVIDENCE: session reply]. Każdy kolejny projekt zaczyna anonimizację od zera,
bo poprzednie skrypty były pisane pod konkretny format [EVIDENCE: session reply].

## Expected outcome

Kryterium nr 1: szósty skrypt nie powstaje [EVIDENCE: session reply — wybór „a”]. Obserwowalnie:
przy kolejnym projekcie autor instaluje jedno narzędzie (`pip install piitier` lub `docker run`),
podaje plik TXT/MD/CSV/PDF (z warstwą tekstową) i dostaje zamaskowany tekst, nie pisząc kodu
anonimizującego [ASSUMPTION]. Tekst poza wykrytymi encjami jest bajt w bajt identyczny (0 zmienionych
znaków) [EVIDENCE: docs/Plan MVP … medtech.md, sekcja 1]. Identyfikator strukturalny z błędną sumą
kontrolną jest maskowany jako „podejrzany”, a nie pomijany [EVIDENCE: docs/Plan MVP … medtech.md, pipeline krok 2].

Kryteria dalsze, kolejność nieustalona: (b) compliance akceptuje wysyłkę do LLM na podstawie raportu
leak rate/recall; (c) model mierzalnie bije Presidio, bards.ai i OpenAI Privacy Filter na PL-PII-Bench
i jest opublikowany na HF [EVIDENCE: session reply — lista opcji b, c; kolejność niejasna].

## Alternatives considered

| Opcja | Co robi | Nakład | Wartość |
|---|---|---|---|
| Nic nie budować | Szósty, siódmy… skrypt pod każdy format | — | — |
| Scalić 5 skryptów w bibliotekę (regex + walidatory + loadery formatów) | Usuwa powtarzanie pracy; bez NER i bez pomiaru | niski–średni | średnia: rozwiązuje kryterium a) dla identyfikatorów, nie dla imion/adresów |
| Presidio / anon-legal-pl / bards.ai + własne loadery | Gotowy NER, polskie recognizery | niski | średnia: brak encji branżowych i polskich liczb [EVIDENCE: docs/Plan MVP … medtech.md, sekcja 7] |
| Hybryda z planu: walidatory + NER ~300M + renderer + PL-PII-Bench | Pełny plan, 12 tygodni po godzinach | wysoki | wysoka: kryteria a), b), c) [EVIDENCE: docs/Plan MVP … medtech.md, sekcja 9] |
| Generatywny LLM przepisujący tekst | Maskowanie przez generację | wysoki | niska: halucynacje, brak wierności [EVIDENCE: docs/Plan MVP … medtech.md, Key Findings 1] |

Rekomendacja: hybryda z planu, ale w kolejności kryterium a). Najpierw rdzeń deterministyczny z
loaderami formatów, który od razu zastępuje skrypty; potem NER; benchmark i publikacja na końcu
[ASSUMPTION].

## Challenger

1. A 300M-parameter NER model fine-tuned on synthetic data will systematically miss adversarial and naturally-occurring PII variations that only appear in real regulated-sector documents, making it dangerous precisely where it needs to be safe.
2. Twelve weeks solo after hours is not enough time to build, validate, and publish both a production-grade anonymisation library and a credible benchmark dataset — one of them will be a façade.
3. You have already written this script five times because the inputs keep changing, and a model release does not fix the integration problem — every new document format will still require a one-off adapter.

Odpowiedź: zarzut 3 przesuwa loadery formatów do pierwszego wycinka; zarzut 1 to powód, dla którego
recall mierzy się na ręcznie zweryfikowanym złotym zbiorze, a nie na syntetyce; zarzut 2 to powód
kolejności: biblioteka najpierw, benchmark później [ASSUMPTION].

## Non-goals

- OCR skanów PDF w pierwszym wycinku; tylko PDF z warstwą tekstową [ASSUMPTION].
- Tryb `synthetic` (Faker zamiast placeholderów) — po MVP [EVIDENCE: docs/Plan MVP … medtech.md, pipeline krok 6].
- Gateway OpenAI-compatible — tydzień 10, osobny spec [EVIDENCE: docs/Plan MVP … medtech.md, sekcja 9].
- Użycie prawdziwych dokumentów pracodawcy lub klientów [EVIDENCE: docs/Plan MVP … medtech.md, sekcja 3].

## Decisions

- Kryterium sukcesu nr 1 = a) „szósty skrypt nie powstaje” — owner: autor (emgiezet) [EVIDENCE: session reply].
- Architektura hybrydowa, bez generatywnego maskowania — owner: autor [EVIDENCE: docs/Plan MVP … medtech.md].
- Pierwszy spec: `docs/TAXONOMY.md` + szkielet projektu uv + walidatory PESEL/NIP/REGON/IBAN/dowód/Luhn +
  renderer `mask` z testem wierności + loadery TXT/MD/CSV/PDF-tekst + CLI — owner: autor, do zatwierdzenia w specu [ASSUMPTION].
- Punkt wyjścia: wcześniejszy prywatny skrypt `scan_pii.py`. Kandydaci są wykrywani po kształcie
  numeru, a suma kontrolna nie odrzuca kandydata. Kodowanie: UTF-8, potem cp1250. Obsługiwane wejścia:
  MSG, EML, ZIP, OCR obrazów i skanów — owner: autor [EVIDENCE: session reply + scan_pii.py l. 73, 1058–1065].
- PII-1-a…g zatwierdzone na polecenie autora — owner: autor [EVIDENCE: session reply „zaakceptuj”].
- Następny krok po PII-1: PII-2, czyli generowanie danych treningowych lokalnymi modelami na własnym GPU
  — owner: autor [EVIDENCE: session reply]. Środowisko: RTX 3090 Ti 24 GB i RTX 3080 10 GB; Ollama ma
  Bielik 11B v3 (Q8_0/Q6_K), Bielik 4.5B v3, Bielik-Minitron 7B v3, Bielik 1.5B v3, qwen3:8b, gemma4
  [EVIDENCE: nvidia-smi, ollama list]. Ollama nasłuchuje na `*:11434`, czyli na wszystkich interfejsach
  [EVIDENCE: ss -ltn].

## Clarification (owner, 2026-10-20)

Cel nr 1 jest potrzebny do budowy danych treningowych. Rdzeń i loadery są etapem przygotowawczym
do PII-2, nie zamiennikiem celu modelowego. — owner: autor (emgiezet)
[EVIDENCE: session reply, 2026-10-20].

## Open questions

- Jaka kolejność b) i c)? Odpowiedź „a następnie a” jest niejednoznaczna. Nie blokuje pierwszego specu, bo oba kryteria wymagają tego samego rdzenia.
- Czy faktury i polisy z poprzednich skryptów to PDF z warstwą tekstową, czy skany? Nie blokuje: OCR jest poza pierwszym wycinkiem. Prior art zawiera już OCR (olmOCR przez lokalną Ollamę).
- Czy kod z wcześniejszego prywatnego skryptu `scan_pii.py` należy do autora? Jeśli nie, specy pozwalają go tylko czytać, nie kopiować. Nie blokuje.
