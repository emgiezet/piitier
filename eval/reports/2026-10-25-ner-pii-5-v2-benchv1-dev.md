# Raport: ner na bench/v1/dev

## System
- Name: ner
- Wersja: 0.1.0
- Data: 2026-10-25T11:37:02.742657
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
- Peak RAM: 2572734464 bytes

## Encje (strict)
- Micro Precision: 0.4889
- Micro Recall: 0.5500
- Micro F1: 0.5176

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.1111 | 0.2000 | 0.1429 |
| DANE_ZDROWOTNE | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| DOCHOD | 0.0000 | 0.0000 | 0.0000 |
| EMAIL | 0.2500 | 0.5000 | 0.3333 |
| IBAN | 0.6667 | 1.0000 | 0.8000 |
| KWOTA | 0.0000 | 0.0000 | 0.0000 |
| LEKARZ | 0.0000 | 0.0000 | 0.0000 |
| MIEJSCOWOSC | 0.0000 | 0.0000 | 0.0000 |
| NIP | 1.0000 | 1.0000 | 1.0000 |
| NPWZ | 0.0000 | 0.0000 | 0.0000 |
| NR_KARTY | 1.0000 | 1.0000 | 1.0000 |
| NR_POLISY | 0.0000 | 0.0000 | 0.0000 |
| NR_RACHUNKU | 0.0000 | 0.0000 | 0.0000 |
| NR_SZKODY | 0.0000 | 0.0000 | 0.0000 |
| NR_UMOWY | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 1.0000 | 1.0000 | 1.0000 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |
| PLACOWKA | 0.0000 | 0.0000 | 0.0000 |
| ROZPOZNANIE | 0.0000 | 0.0000 | 0.0000 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 |

## Encje (partial)
- Micro Precision: 0.7333
- Micro Recall: 0.8250
- Micro F1: 0.7765

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.5556 | 1.0000 | 0.7143 |
| DANE_ZDROWOTNE | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| DOCHOD | 0.0000 | 0.0000 | 0.0000 |
| EMAIL | 0.5000 | 1.0000 | 0.6667 |
| IBAN | 0.6667 | 1.0000 | 0.8000 |
| KWOTA | 0.3333 | 0.3333 | 0.3333 |
| LEKARZ | 1.0000 | 1.0000 | 1.0000 |
| MIEJSCOWOSC | 0.0000 | 0.0000 | 0.0000 |
| NIP | 1.0000 | 1.0000 | 1.0000 |
| NPWZ | 0.0000 | 0.0000 | 0.0000 |
| NR_KARTY | 1.0000 | 1.0000 | 1.0000 |
| NR_POLISY | 1.0000 | 1.0000 | 1.0000 |
| NR_RACHUNKU | 0.0000 | 0.0000 | 0.0000 |
| NR_SZKODY | 0.0000 | 0.0000 | 0.0000 |
| NR_UMOWY | 0.5000 | 1.0000 | 0.6667 |
| OSOBA | 1.0000 | 1.0000 | 1.0000 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |
| PLACOWKA | 1.0000 | 1.0000 | 1.0000 |
| ROZPOZNANIE | 0.5000 | 1.0000 | 0.6667 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 |

## Porównywalna podtaksonomia (bardsai_v2)
- Etykiety: ADRES, CVV, DANE_ZDROWOTNE, DATA_URODZENIA, EMAIL, GEO, IBAN, IP, KWOTA, MIEJSCOWOSC, NIP, NR_DOKUMENTACJI, NR_DOWODU, NR_KARTY, NR_RACHUNKU, OSOBA, PESEL, PLACOWKA, TELEFON, VIN
- Strict Micro Precision: 0.5641
- Strict Micro Recall: 0.6667
- Strict Micro F1: 0.6111
- Partial Micro Precision: 0.7436
- Partial Micro Recall: 0.8788
- Partial Micro F1: 0.8056

## Recall ważony ryzykiem
- Risk-weighted recall: 0.5183

## Leak rate
- Docs leaked: 2 / 6
- Values leaked: 6 / 40
- Leaked doc IDs: doc_szkoda_02, doc_szpital_06

## Wierność
- Changed chars outside spans: 0

## Numeracja
- Same entity consistent: 1 / 1
- Different entity distinct: 0 / 0

## Throughput
- Throughput: 33.02 docs/s
- P95 latency: 0.1010 s

## Podział wg doc_type

### mail_klienta
- Strict Micro Precision: 0.4286
- Strict Micro Recall: 0.5000
- Strict Micro F1: 0.4615

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| EMAIL | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 0.0000 | 0.0000 | 0.0000 |
| MIEJSCOWOSC | 0.0000 | 0.0000 | 0.0000 |
| NR_KARTY | 1.0000 | 1.0000 | 1.0000 |
| OSOBA | 1.0000 | 1.0000 | 1.0000 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 |

### polisa
- Strict Micro Precision: 0.6000
- Strict Micro Recall: 0.6667
- Strict Micro F1: 0.6316

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| EMAIL | 1.0000 | 1.0000 | 1.0000 |
| KWOTA | 0.0000 | 0.0000 | 0.0000 |
| NR_POLISY | 0.0000 | 0.0000 | 0.0000 |
| NR_UMOWY | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 1.0000 | 1.0000 | 1.0000 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 |

### umowa_kredytowa
- Strict Micro Precision: 0.5000
- Strict Micro Recall: 0.5000
- Strict Micro F1: 0.5000

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| DOCHOD | 0.0000 | 0.0000 | 0.0000 |
| IBAN | 1.0000 | 1.0000 | 1.0000 |
| NR_UMOWY | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 1.0000 | 1.0000 | 1.0000 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |

### wyciag
- Strict Micro Precision: 0.4286
- Strict Micro Recall: 0.6000
- Strict Micro F1: 0.5000

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 1.0000 | 1.0000 | 1.0000 |
| IBAN | 0.5000 | 1.0000 | 0.6667 |
| KWOTA | 0.0000 | 0.0000 | 0.0000 |
| NR_RACHUNKU | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 1.0000 | 1.0000 | 1.0000 |

### wypis_szpitalny
- Strict Micro Precision: 0.3333
- Strict Micro Recall: 0.4286
- Strict Micro F1: 0.3750

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| LEKARZ | 0.0000 | 0.0000 | 0.0000 |
| NPWZ | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 1.0000 | 1.0000 | 1.0000 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |
| PLACOWKA | 0.0000 | 0.0000 | 0.0000 |
| ROZPOZNANIE | 0.0000 | 0.0000 | 0.0000 |

### zgloszenie_szkody
- Strict Micro Precision: 0.6667
- Strict Micro Recall: 0.5714
- Strict Micro F1: 0.6154

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| DANE_ZDROWOTNE | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| NIP | 1.0000 | 1.0000 | 1.0000 |
| NR_SZKODY | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 1.0000 | 1.0000 | 1.0000 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 |
