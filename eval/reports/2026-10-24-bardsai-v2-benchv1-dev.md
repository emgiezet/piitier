# Report: bardsai-v2 on bench/v1/dev

## System
- Name: bardsai-v2
- Version: 0.1.0
- Date: 2026-10-24T23:56:43.115491
- Threshold: none — threshold-free system

## Benchmark
- Version: v1
- Split: dev
- Number of documents: 6
- Number of gold spans: 40

## Hardware
- Platform: Linux-7.0.0-38-generic-x86_64-with-glibc2.43
- CPU: N/A
- GPU: NVIDIA GeForce RTX 3090 Ti
- Peak RAM: 2571923456 bytes

## Entities (strict)
- Micro Precision: 0.2821
- Micro Recall: 0.2750
- Micro F1: 0.2785

| Label | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| DANE_ZDROWOTNE | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| DOCHOD | 0.0000 | 0.0000 | 0.0000 |
| EMAIL | 0.5000 | 0.5000 | 0.5000 |
| IBAN | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 0.2500 | 0.3333 | 0.2857 |
| LEKARZ | 0.0000 | 0.0000 | 0.0000 |
| MIEJSCOWOSC | 0.0000 | 0.0000 | 0.0000 |
| NIP | 0.0000 | 0.0000 | 0.0000 |
| NPWZ | 0.0000 | 0.0000 | 0.0000 |
| NR_DOKUMENTACJI | 0.0000 | 0.0000 | 0.0000 |
| NR_KARTY | 1.0000 | 1.0000 | 1.0000 |
| NR_POLISY | 0.0000 | 0.0000 | 0.0000 |
| NR_RACHUNKU | 0.0000 | 0.0000 | 0.0000 |
| NR_SZKODY | 0.0000 | 0.0000 | 0.0000 |
| NR_UMOWY | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| PESEL | 0.7500 | 1.0000 | 0.8571 |
| PLACOWKA | 0.0000 | 0.0000 | 0.0000 |
| ROZPOZNANIE | 0.0000 | 0.0000 | 0.0000 |
| TELEFON | 0.6667 | 0.6667 | 0.6667 |

## Entities (partial)
- Micro Precision: 0.7692
- Micro Recall: 0.7500
- Micro F1: 0.7595

| Label | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 1.0000 | 1.0000 | 1.0000 |
| DANE_ZDROWOTNE | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| DOCHOD | 0.0000 | 0.0000 | 0.0000 |
| EMAIL | 1.0000 | 1.0000 | 1.0000 |
| IBAN | 0.6667 | 1.0000 | 0.8000 |
| KWOTA | 0.7500 | 1.0000 | 0.8571 |
| LEKARZ | 0.0000 | 0.0000 | 0.0000 |
| MIEJSCOWOSC | 0.0000 | 0.0000 | 0.0000 |
| NIP | 0.0000 | 0.0000 | 0.0000 |
| NPWZ | 0.0000 | 0.0000 | 0.0000 |
| NR_DOKUMENTACJI | 0.0000 | 0.0000 | 0.0000 |
| NR_KARTY | 1.0000 | 1.0000 | 1.0000 |
| NR_POLISY | 0.0000 | 0.0000 | 0.0000 |
| NR_RACHUNKU | 0.0000 | 0.0000 | 0.0000 |
| NR_SZKODY | 0.0000 | 0.0000 | 0.0000 |
| NR_UMOWY | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.8750 | 1.0000 | 0.9333 |
| PESEL | 0.7500 | 1.0000 | 0.8571 |
| PLACOWKA | 1.0000 | 1.0000 | 1.0000 |
| ROZPOZNANIE | 0.0000 | 0.0000 | 0.0000 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 |

## Comparable subtaxonomy (bardsai_v2)
- Labels: ADRES, CVV, DANE_ZDROWOTNE, DATA_URODZENIA, EMAIL, GEO, IBAN, IP, KWOTA, MIEJSCOWOSC, NIP, NR_DOKUMENTACJI, NR_DOWODU, NR_KARTY, NR_RACHUNKU, OSOBA, PESEL, PLACOWKA, TELEFON, VIN
- Strict Micro Precision: 0.2821
- Strict Micro Recall: 0.3333
- Strict Micro F1: 0.3056
- Partial Micro Precision: 0.7692
- Partial Micro Recall: 0.9091
- Partial Micro F1: 0.8333

## Risk-weighted recall
- Risk-weighted recall: 0.2805

## Leak rate
- Docs leaked: 1 / 6
- Values leaked: 2 / 40
- Leaked doc IDs: doc_szpital_06

## Fidelity
- Changed chars outside spans: 179

## Numbering
- Same entity consistent: 1 / 1
- Different entity distinct: 0 / 0

## Throughput
- Throughput: 0.59 docs/s
- P95 latency: 6.2566 s

## Breakdown by doc_type

### mail_klienta
- Strict Micro Precision: 0.4286
- Strict Micro Recall: 0.5000
- Strict Micro F1: 0.4615

| Label | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| EMAIL | 1.0000 | 1.0000 | 1.0000 |
| KWOTA | 0.0000 | 0.0000 | 0.0000 |
| MIEJSCOWOSC | 0.0000 | 0.0000 | 0.0000 |
| NR_KARTY | 1.0000 | 1.0000 | 1.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 |

### polisa
- Strict Micro Precision: 0.2222
- Strict Micro Recall: 0.2222
- Strict Micro F1: 0.2222

| Label | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| EMAIL | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 0.0000 | 0.0000 | 0.0000 |
| NR_DOKUMENTACJI | 0.0000 | 0.0000 | 0.0000 |
| NR_POLISY | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |
| TELEFON | 0.0000 | 0.0000 | 0.0000 |

### umowa_kredytowa
- Strict Micro Precision: 0.1667
- Strict Micro Recall: 0.1667
- Strict Micro F1: 0.1667

| Label | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| DOCHOD | 0.0000 | 0.0000 | 0.0000 |
| IBAN | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 0.0000 | 0.0000 | 0.0000 |
| NR_DOKUMENTACJI | 0.0000 | 0.0000 | 0.0000 |
| NR_UMOWY | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |

### wyciag
- Strict Micro Precision: 0.2000
- Strict Micro Recall: 0.2000
- Strict Micro F1: 0.2000

| Label | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| IBAN | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 1.0000 | 1.0000 | 1.0000 |
| NR_RACHUNKU | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |

### wypis_szpitalny
- Strict Micro Precision: 0.3333
- Strict Micro Recall: 0.2857
- Strict Micro F1: 0.3077

| Label | Precision | Recall | F1 |
|---|---|---|---|
| DANE_ZDROWOTNE | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| LEKARZ | 0.0000 | 0.0000 | 0.0000 |
| NPWZ | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |
| PLACOWKA | 0.0000 | 0.0000 | 0.0000 |
| ROZPOZNANIE | 0.0000 | 0.0000 | 0.0000 |

### zgloszenie_szkody
- Strict Micro Precision: 0.3333
- Strict Micro Recall: 0.2857
- Strict Micro F1: 0.3077

| Label | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| DANE_ZDROWOTNE | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| NIP | 0.0000 | 0.0000 | 0.0000 |
| NR_DOKUMENTACJI | 0.0000 | 0.0000 | 0.0000 |
| NR_SZKODY | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| PESEL | 0.0000 | 0.0000 | 0.0000 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 |
