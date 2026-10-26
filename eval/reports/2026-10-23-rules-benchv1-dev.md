# Raport: rules na bench/v1/dev

## System
- Name: rules
- Wersja: 0.1.0
- Data: 2026-10-23T18:34:26.994462
- Próg: brak — system bez progu

## Benchmark
- Wersja: v1
- Split: dev
- Liczba dokumentów: 6
- Liczba spanów gold: 40

## Sprzęt
- Platforma: Linux-7.0.0-38-generic-x86_64-with-glibc2.43
- Procesor: N/A
- GPU: NVIDIA GeForce RTX 3090 Ti
- Peak RAM: 39944192 bytes

## Encje (strict)
- Micro Precision: 0.8750
- Micro Recall: 0.1750
- Micro F1: 0.2917

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| DANE_ZDROWOTNE | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 0.0000 | 0.0000 | 0.0000 |
| DOCHOD | 0.0000 | 0.0000 | 0.0000 |
| EMAIL | 0.0000 | 0.0000 | 0.0000 |
| IBAN | 0.6667 | 1.0000 | 0.8000 |
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
| TELEFON | 0.0000 | 0.0000 | 0.0000 |

## Encje (partial)
- Micro Precision: 0.8750
- Micro Recall: 0.1750
- Micro F1: 0.2917

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| DANE_ZDROWOTNE | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 0.0000 | 0.0000 | 0.0000 |
| DOCHOD | 0.0000 | 0.0000 | 0.0000 |
| EMAIL | 0.0000 | 0.0000 | 0.0000 |
| IBAN | 0.6667 | 1.0000 | 0.8000 |
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
| TELEFON | 0.0000 | 0.0000 | 0.0000 |

## Recall ważony ryzykiem
- Risk-weighted recall: 0.2134

## Leak rate
- Docs leaked: 5 / 6
- Values leaked: 32 / 40
- Leaked doc IDs: doc_polisa_01, doc_szkoda_02, doc_umowa_03, doc_mail_05, doc_szpital_06

## Wierność
- Changed chars outside spans: 0

## Numeracja
- Same entity consistent: 0 / 0
- Different entity distinct: 0 / 0

## Throughput
- Throughput: 10357.29 docs/s
- P95 latency: 0.0001 s
