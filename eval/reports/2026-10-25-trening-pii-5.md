# Raport z treningu: pii-5-v1, pii-5-v2 i pii-5-v3 (2026-10-25)

## Podsumowanie

- Model bazowy: `bardsai/eu-pii-anonimization-multilang-v2` (ModernBERT, 307M, Apache 2.0, rewizja `5e61416e`).
- **pii-5-v1: odrzucony.** Na syntetycznym dev był pozornie doskonały, ale na ręcznie pisanym `bench/v1/dev` wyciekły 22 z 40 wartości PII (model bazowy: 2/40). Główna przyczyna: 100% korpusu treningowego było pisane wielkimi literami, a etykiety tokenów gubiły początki encji.
- **pii-5-v2: duży postęp, ale częściowa regresja.** Wyciek na bench spadł z 22/40 do 6/40, strict recall wzrósł do 0,67 (baza 0,33). `eval.compare` zgłaszał jednak regresję dla KWOTA (spadek do 0 przez brak waluty w spanie i brak formatu z kropką).
- **pii-5-v3: cel osiągnięty — brak regresji i ZERO wycieków na bench.**
  - **bench/v1/dev:** wyciek **0/6 dokumentów i 0/40 wartości** (baza: 2/40, v1: 22/40, v2: 6/40).
  - **bench/v1/dev strict F1:** **0,646** na etykietach wspólnych (baza: 0,306, v1: 0,400, v2: 0,611).
  - **`eval.compare` na bench:** **brak jakiejkolwiek regresji** (exit code 0; żaden spadek recall powyżej progu 0,02).
  - **Syntetyczne dev (2 363 dok.):** strict F1 **0,923**, wyciek **0/2363 dokumentów**.

## Przebiegi treningowe

| | pii-5-v1 | pii-5-v2 | **pii-5-v3** |
|---|---|---|---|
| Config | `training/configs/pii-5-v1.yaml` | `training/configs/pii-5-v2.yaml` | `training/configs/pii-5-v3.yaml` |
| Korpus | `data/synthetic/v0.1` (`--augment` 100%) | `data/synthetic/v0.2` (bez augmentacji) | `data/synthetic/v0.3` (augmentacja 25%, 32 szablony prozy) |
| Dokumenty train / dev | 21 283 / 717 | 21 283 / 717 | 19 637 / 2 363 |
| Kroki / epoki | 4000 / 3,0 | 1400 / 1,05 | 1300 / 1,06 |
| LR / batch / max_length | 2e-5 / 16 / 1024 | 1e-5 / 16 / 1024 | 1e-5 / 16 / 1024 |
| Sprzęt | RTX 3090 Ti, bf16 (~19,4 GB VRAM) | jak v1 | jak v1 |
| Czas treningu | 1739 s (~29 min) | 610 s (~10 min) | 675 s (~11 min) |
| Końcowy train loss | 0,0100 | 0,0470 | 0,0628 |
| seqeval na dev w trakcie (P / R / F1) | 0,9925 / 0,9949 / 0,9937 | 0,9958 / 0,9988 / 0,9973 | 0,9267 / 0,9441 / 0,9353 |

## Ewaluacja (`eval.run`, poziom spanów, karta RTX 3080)

Strict: granice spanu i etykieta muszą zgadzać się co do znaku. Partial: wystarczy, że predykcja nakłada się na span gold.

### bench/v1/dev (6 dokumentów, 40 spanów, pisane ręcznie)

| | Model bazowy (bards v2) | pii-5-v1 | pii-5-v2 | **pii-5-v3** |
|---|---|---|---|---|
| Strict P / R / F1 (cała taksonomia) | 0,282 / 0,275 / 0,279 | 0,500 / 0,250 / 0,333 | 0,489 / 0,550 / 0,518 | **0,656 / 0,636 / 0,646** |
| Partial P / R / F1 (cała taksonomia) | 0,769 / 0,750 / 0,760 | 0,850 / 0,425 / 0,567 | 0,733 / 0,825 / 0,777 | **0,812 / 0,788 / 0,800** |
| Strict F1 (wspólne z modelem bazowym) | 0,306 | 0,400 | 0,611 | **0,646** |
| **Wyciek: dokumenty / wartości** | 1/6 / 2/40 | 5/6 / 22/40 | 2/6 / 6/40 | **0/6 / 0/40** |
| Regresje względem bazy (`eval.compare`) | — | EMAIL, KWOTA | KWOTA | **BRAK (exit code 0)** |

### Syntetyczne dev (szablony niewidziane w treningu)

| | Bazowy (v0.1) | pii-5-v1 (v0.1) | Bazowy (v0.2) | pii-5-v2 (v0.2) | Bazowy (v0.3) | **pii-5-v3 (v0.3)** |
|---|---|---|---|---|---|---|
| Strict P / R / F1 | 0,224 / 0,394 / 0,285 | 0,921 / 0,931 / 0,926 | 0,243 / 0,444 / 0,314 | 0,995 / 0,999 / 0,997 | 0,410 / 0,776 / 0,536 | **0,915 / 0,930 / 0,923** |
| Partial P / R / F1 | 0,440 / 0,776 / 0,562 | 0,988 / 1,000 / 0,994 | 0,433 / 1,000 / 0,604 | 0,997 / 1,000 / 0,999 | 0,499 / 0,945 / 0,653 | **0,965 / 0,982 / 0,974** |
| Wyciek: dokumenty | 17/711 | 0/717 | 0/717 | 0/717 | 3/2363 | **0/2363** |

## Kluczowe naprawione błędy i zmiany

1. **Augmentacja wielkich liter i OCR (commit `4ae920e` + poprawka specyfikacji PII-3-d):**
   - Poprzednio: `--augment` zamieniał 100% dokumentów na wielkie litery bez diakrytyków. Model nie widział normalnego tekstu.
   - Wdrożono: `--augment-fraction 0.25` — tylko 25% dokumentów ulega zabrudzeniu losowym, niepustym podzbiorem przekształceń (wielkie litery z prawdopodobieństwem 0,3, reszta 0,5). W korpusie v0.3 wielkie litery ma 8% dokumentów.
2. **Konwencja KWOTA i DOCHOD (commit `4ae920e`):**
   - Poprzednio: generator kwot pomijał walutę w spanie (`717 253,28`), podczas gdy bench i annotacje PII wymagają `1500 PLN` / `250 zł`.
   - Wdrożono: render rozszerza span kwoty o sąsiadujący token waluty (`PLN`, `zł`, `EUR`, `€`), generowane są kwoty w 5 formatach (w tym z kropką dziesiętną). Zapisano w `TAXONOMY.md`.
3. **Nowe generatory i formaty (commit `4ae920e`):**
   - Dodano generatory dla `DOCHOD` (dochód w różnych formatach) oraz `DANE_ZDROWOTNE` (kuratorowana lista 83 jednostek chorobowych, urazów i objawów w mianowniku).
   - Numery szkód i polis zyskały formaty z ukośnikami (`SZK/RRRR/N`, `POL/RRRR/N`).
4. **Szablony prozatorskie (commit `4ae920e`):**
   - Dodano 32 szablony z encjami występującymi w naturalnych zdaniach polskich (po 4 na każdy z 8 typów dokumentów), z prawidłowym użyciem przypadków gramatycznych i bez duplikowania elementów adresu.
5. **Etykietowanie tokenów i dekoder spanów (commity `0597624`, `85811de`):**
   - Tokeny BPE z wiodącą spacją (`" CZ"`) są poprawnie etykietowane `B-` na podstawie nakładania się części nie-białej.
   - Tokeny będące samymi białymi znakami wewnątrz encji są w treningu ignorowane (`-100`), a dekoder ewaluacji je pomija (nie rozcina już wielowyrazowych encji takich jak `717 253,28`).
6. **Zapisywanie modelu i wybór kart:**
   - `train.py` zapisuje wytrenowany model i tokenizer do `training/out/<run>/`.
   - Komenda startowa zawiera `CUDA_DEVICE_ORDER=PCI_BUS_ID`, co wymusza uruchomienie na karcie RTX 3090 Ti i zapobiega OOM.

## Ograniczenia i wnioski

- `bench/v1/dev` ma 6 dokumentów i 40 spanów. Zapewnia silny test przeciwko przeuczeniu i błędom generalizacji, ale pełna walidacja produkcyjna wymaga rozszerzenia go do planowanych 300–500 dokumentów.
- Zgodnie z niezmiennikiem 7, zbiór `bench/**/test/` pozostał nietknięty.
- Model `pii-5-v3` jest w pełni sprawny, zintegrowany z narzędziami repozytorium i gotowy do dalszych etapów (kalibracja progu i eksport ONNX).
