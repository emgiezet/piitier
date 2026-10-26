# Raport: ner na bench/v1/dev

## System
- Name: ner
- Wersja: 0.1.0
- Data: 2026-10-25T11:00:58.522543
- Próg: brak — system bez progu

## Benchmark
- Wersja: v1
- Split: dev
- Liczba dokumentów: 6
- Liczba spanów gold: 40

## Sprzęt
- Platforma: Linux-7.0.0-38-generic-x86_64-with-glibc2.43
- Procesor: N/A
- GPU: NVIDIA GeForce RTX 3080
- Peak RAM: 2586570752 bytes

## Encje (strict)
- Micro Precision: 0.5000
- Micro Recall: 0.2500
- Micro F1: 0.3333

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| DANE_ZDROWOTNE | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| DOCHOD | 0.0000 | 0.0000 | 0.0000 |
| EMAIL | 0.0000 | 0.0000 | 0.0000 |
| IBAN | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 0.0000 | 0.0000 | 0.0000 |
| LEKARZ | 0.0000 | 0.0000 | 0.0000 |
| NIP | 1.0000 | 1.0000 | 1.0000 |
| NPWZ | 0.0000 | 0.0000 | 0.0000 |
| NR_KARTY | 1.0000 | 1.0000 | 1.0000 |
| NR_POLISY | 0.0000 | 0.0000 | 0.0000 |
| NR_RACHUNKU | 0.0000 | 0.0000 | 0.0000 |
| NR_SZKODY | 0.0000 | 0.0000 | 0.0000 |
| NR_UMOWY | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |
| PLACOWKA | 0.0000 | 0.0000 | 0.0000 |
| ROZPOZNANIE | 0.0000 | 0.0000 | 0.0000 |
| TELEFON | 0.6667 | 0.6667 | 0.6667 |

## Encje (partial)
- Micro Precision: 0.8500
- Micro Recall: 0.4250
- Micro F1: 0.5667

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 1.0000 | 0.2000 | 0.3333 |
| DANE_ZDROWOTNE | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| DOCHOD | 0.0000 | 0.0000 | 0.0000 |
| EMAIL | 0.5000 | 0.5000 | 0.5000 |
| IBAN | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 1.0000 | 0.3333 | 0.5000 |
| LEKARZ | 0.0000 | 0.0000 | 0.0000 |
| NIP | 1.0000 | 1.0000 | 1.0000 |
| NPWZ | 0.0000 | 0.0000 | 0.0000 |
| NR_KARTY | 1.0000 | 1.0000 | 1.0000 |
| NR_POLISY | 0.0000 | 0.0000 | 0.0000 |
| NR_RACHUNKU | 0.0000 | 0.0000 | 0.0000 |
| NR_SZKODY | 0.0000 | 0.0000 | 0.0000 |
| NR_UMOWY | 0.5000 | 1.0000 | 0.6667 |
| OSOBA | 1.0000 | 0.1429 | 0.2500 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |
| PLACOWKA | 0.0000 | 0.0000 | 0.0000 |
| ROZPOZNANIE | 1.0000 | 1.0000 | 1.0000 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 |

## Porównywalna podtaksonomia (bardsai_v2)
- Etykiety: ADRES, CVV, DANE_ZDROWOTNE, DATA_URODZENIA, EMAIL, GEO, IBAN, IP, KWOTA, MIEJSCOWOSC, NIP, NR_DOKUMENTACJI, NR_DOWODU, NR_KARTY, NR_RACHUNKU, OSOBA, PESEL, PLACOWKA, TELEFON, VIN
- Strict Micro Precision: 0.5882
- Strict Micro Recall: 0.3030
- Strict Micro F1: 0.4000
- Partial Micro Precision: 0.8824
- Partial Micro Recall: 0.4545
- Partial Micro F1: 0.6000

## Recall ważony ryzykiem
- Risk-weighted recall: 0.2561

## Leak rate
- Docs leaked: 5 / 6
- Values leaked: 22 / 40
- Leaked doc IDs: doc_polisa_01, doc_szkoda_02, doc_umowa_03, doc_wyciag_04, doc_szpital_06

## Wierność
- Changed chars outside spans: 0

## Numeracja
- Same entity consistent: 0 / 0
- Different entity distinct: 0 / 0

## Throughput
- Throughput: 31.84 docs/s
- P95 latency: 0.1065 s

## Podział wg doc_type

### mail_klienta
- Strict Micro Precision: 0.5000
- Strict Micro Recall: 0.3333
- Strict Micro F1: 0.4000

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| EMAIL | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 0.0000 | 0.0000 | 0.0000 |
| NR_KARTY | 1.0000 | 1.0000 | 1.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 |

### polisa
- Strict Micro Precision: 0.5000
- Strict Micro Recall: 0.2222
- Strict Micro F1: 0.3077

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| EMAIL | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 0.0000 | 0.0000 | 0.0000 |
| NR_POLISY | 0.0000 | 0.0000 | 0.0000 |
| NR_UMOWY | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |
| TELEFON | 0.0000 | 0.0000 | 0.0000 |

### umowa_kredytowa
- Strict Micro Precision: 0.5000
- Strict Micro Recall: 0.1667
- Strict Micro F1: 0.2500

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| DOCHOD | 0.0000 | 0.0000 | 0.0000 |
| IBAN | 0.0000 | 0.0000 | 0.0000 |
| NR_UMOWY | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |

### wyciag
- Strict Micro Precision: 0.0000
- Strict Micro Recall: 0.0000
- Strict Micro F1: 0.0000

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| IBAN | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 0.0000 | 0.0000 | 0.0000 |
| NR_RACHUNKU | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |

### wypis_szpitalny
- Strict Micro Precision: 0.5000
- Strict Micro Recall: 0.2857
- Strict Micro F1: 0.3636

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| LEKARZ | 0.0000 | 0.0000 | 0.0000 |
| NPWZ | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |
| PLACOWKA | 0.0000 | 0.0000 | 0.0000 |
| ROZPOZNANIE | 0.0000 | 0.0000 | 0.0000 |

### zgloszenie_szkody
- Strict Micro Precision: 1.0000
- Strict Micro Recall: 0.4286
- Strict Micro F1: 0.6000

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| DANE_ZDROWOTNE | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| NIP | 1.0000 | 1.0000 | 1.0000 |
| NR_SZKODY | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 |
