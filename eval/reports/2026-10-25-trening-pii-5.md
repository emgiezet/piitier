# Raport z treningu: pii-5-v1 i pii-5-v2 (2026-10-25)

## Podsumowanie

- Model bazowy: `bardsai/eu-pii-anonimization-multilang-v2` (ModernBERT, 307M, Apache 2.0, rewizja `5e61416e`).
- **pii-5-v1 odrzucony.** Na syntetycznym dev był lepszy od bazowego, ale na ręcznie pisanym `bench/v1/dev` wyciekło 22/40 wartości (bazowy: 2/40).
- **pii-5-v2: duży postęp, jeszcze niezaakceptowany.**
  - Syntetyczne dev: strict F1 0,997, bez żadnej regresji.
  - bench/v1/dev: strict recall 0,67 (bazowy 0,33), ale `eval.compare` zgłasza regresję KWOTA, a wyciek wynosi 6/40 (bazowy 2/40).
- Pozostałe różnice wynikają z luk w danych treningowych (formaty kwot z walutą, encje w prozie, DANE_ZDROWOTNE i DOCHOD bez przykładów). Naprawy są w toku i na nich powstanie v3.

## Przebiegi

| | pii-5-v1 | pii-5-v2 |
|---|---|---|
| Config | `training/configs/pii-5-v1.yaml` | `training/configs/pii-5-v2.yaml` |
| Korpus | `data/synthetic/v0.1` (`--augment`) | `data/synthetic/v0.2` (bez augmentacji) |
| Dokumenty train / dev | 21 283 / 717 | 21 283 / 717 |
| Kroki / epoki | 4000 / 3,0 | 1400 / 1,05 |
| LR / batch / max_length | 2e-5 / 16 / 1024 | 1e-5 / 16 / 1024 |
| Sprzęt | RTX 3090 Ti, bf16, ok. 19,4 GB VRAM | jak v1 |
| Czas treningu | 1739 s | 610 s |
| Końcowy train loss | 0,0100 | 0,0470 |
| seqeval na dev w trakcie (P / R / F1) | 0,9925 / 0,9949 / 0,9937 | 0,9958 / 0,9988 / 0,9973 |

seqeval jest liczony na poziomie tokenów w syntetycznym dev, czyli na tym samym rozkładzie danych co trening. Nie mierzy generalizacji.

## Ewaluacja (`eval.run`, poziom spanów, karta RTX 3080)

Strict: granice spanu muszą zgadzać się co do znaku. Partial: wystarczy, że predykcja nakłada się na span gold.

### bench/v1/dev (6 dokumentów, 40 spanów, pisane ręcznie)

| | Bazowy | pii-5-v1 | pii-5-v2 |
|---|---|---|---|
| Strict P / R / F1 (cała taksonomia) | 0,282 / 0,275 / 0,279 | 0,500 / 0,250 / 0,333 | 0,489 / 0,550 / 0,518 |
| Partial P / R / F1 (cała taksonomia) | 0,769 / 0,750 / 0,760 | 0,850 / 0,425 / 0,567 | 0,733 / 0,825 / 0,777 |
| Strict F1, etykiety wspólne z modelem bazowym | 0,306 | 0,400 | 0,611 |
| Wyciek: dokumenty / wartości | 1/6 / 2/40 | 5/6 / 22/40 | 2/6 / 6/40 |
| Regresje (`eval.compare`, spadek recall > 0,02) | – | EMAIL, KWOTA | KWOTA |

Wynik v1 policzono starszym dekoderem. Poprawki dekodera (opisane niżej) nie zmieniają tego, że v1 przegrywa z modelem bazowym na bench.

### Syntetyczne dev (717 dokumentów, szablony niewidziane w treningu)

| | Bazowy (v0.1) | pii-5-v1 (v0.1) | Bazowy (v0.2) | pii-5-v2 (v0.2) |
|---|---|---|---|---|
| Strict P / R / F1 | 0,224 / 0,394 / 0,285 | 0,921 / 0,931 / 0,926 | 0,243 / 0,444 / 0,314 | 0,995 / 0,999 / 0,997 |
| Wyciek: dokumenty | 17/711 | 0/717 | 0/717 | 0/717 |
| Regresje | – | MIEJSCOWOSC | – | brak |

Wyniki na syntetycznym dev zawyżają realną jakość, bo wartości pochodzą z tych samych generatorów, a układy dokumentów są podobne. O akceptacji modelu decyduje bench.

## Znalezione i naprawione błędy

1. **Korpus v0.1 w 100% zabrudzony.**
   - Objaw: wszystkie 21 283 dokumenty treningowe miały wielkie litery, nie miały polskich znaków, miały zamiany 0/O i 1/l oraz cyfry porozbijane spacjami.
   - Przyczyna: `--augment` stosował wszystkie przekształcenia do każdego dokumentu, zgodnie z literą specyfikacji PII-3-d.
   - Skutek: model nie rozpoznawał normalnego tekstu (OSOBA, ADRES, EMAIL na bench).
   - Naprawa: v2 trenowany na v0.2 bez augmentacji. Docelowa zmiana (augmentacja tylko części dokumentów, losowy podzbiór przekształceń) jest w toku jako poprawka specyfikacji.
2. **Etykiety pierwszego tokenu encji (commit `0597624`).**
   - Przyczyna: tokeny BPE zaczynające się spacją (`" CZ"`) dostawały `O`.
   - Skutek: model gubił początek encji, np. `CZERWIONKA-LESZCZYNY` dawało `ERWIONKA-LESZCZYNY`.
   - Naprawa: etykieta wynika z tego, czy nie-biała część tokenu nakłada się na span.
3. **Rozcinanie encji na spacjach (commit `85811de`).**
   - Przyczyna: spacja wewnątrz encji to osobny token. Dostawała `O`, a dekoder zamykał na niej span.
   - Skutek: `717 253,28` dawało dwie encje.
   - Naprawa: w treningu takie tokeny są ignorowane (-100), dekoder je pomija.
   - Na v2 z tym samym checkpointem strict F1 na syntetycznym dev wzrósł z 0,357 do 0,997.
4. **`train.py` nie zapisywał modelu.** Teraz zapisuje model i tokenizer.
5. **Wybór karty.** Bez `CUDA_DEVICE_ORDER=PCI_BUS_ID` indeks 1 wskazuje RTX 3080, co kończyło się brakiem pamięci (OOM). Komenda w configu jest poprawiona.
6. **Ollama na 3090 Ti.** Ollama (`CUDA_VISIBLE_DEVICES=0,1`) trzymała `qwen3-coder:30b` (16,7 GB) na karcie treningowej, przez co trening przerywał się z OOM.
   - Trening uruchomiono po zwolnieniu karty.
   - Trwałe rozwiązanie wymaga `sudo`: w override usługi ustawić `CUDA_VISIBLE_DEVICES=0`.

## Co v2 jeszcze przepuszcza na bench

| Wartość | Etykieta | Przyczyna |
|---|---|---|
| `SZK/2026/12` | NR_SZKODY | Generator produkuje tylko format `SZK00348192` |
| `ból kręgosłupa i potłuczenia` | DANE_ZDROWOTNE | 0 przykładów w korpusie |
| `NPWZ 1234567` w zdaniu | NPWZ | W szablonach NPWZ występuje tylko jako `Etykieta: wartość` |
| `1500 PLN`, `12345.67 PLN` | KWOTA | Generator nie dołącza waluty do spanu; brak formatu z kropką dziesiętną |
| `8500 PLN` | DOCHOD | 0 przykładów w korpusie |

## Plan v3 (w toku)

- **Augmentacja:** obejmuje tylko 25% dokumentów, losowy podzbiór przekształceń (poprawka specyfikacji PII-3-d).
- **Konwencja KWOTA/DOCHOD:** span obejmuje sąsiednią walutę, tak jak w bench i w FINANCIAL_AMOUNT modelu bazowego. Do tego zróżnicowane formaty kwot.
- **Nowe generatory:** DOCHOD i DANE_ZDROWOTNE; numery szkód i polis w formacie z ukośnikami (`SZK/RRRR/N`, `POL/RRRR/N`).
- **Szablony prozatorskie:** 32 szablony z encjami w zdaniach (po 4 na 8 typów dokumentów).
- **Trening v3:** korpus `data/synthetic/v0.3`, poprawione etykiety białych znaków, ok. 1 epoki. Potem `eval.compare` z modelem bazowym na obu zbiorach.

## Ograniczenia oceny

- `bench/v1/dev` ma 6 dokumentów i 40 spanów: jeden span zmienia recall o 2,5 punktu. Do decyzji o publikacji potrzebny jest większy, ręcznie zweryfikowany dev (plan: 300 dokumentów).
- Próg nie jest skalibrowany: wszystkie przebiegi bez progu.
- Brak ewaluacji na `test/`, zgodnie z niezmiennikiem 7.

## Pliki

- Raporty: `eval/reports/2026-10-24-bardsai-v2-benchv1-dev.*`, `2026-10-25-bardsai-v2-v0.{1,2}-dev.*`, `2026-10-25-ner-pii-5-v{1,2}-*.*`.
- Modele (poza repozytorium): `training/out/pii-5-v1/`, `training/out/pii-5-v2/` (model, tokenizer, `train.log`, `eval_results.json`).
- Porównanie: `uv run python -m eval.compare <bazowy>.json <nowy>.json`.
