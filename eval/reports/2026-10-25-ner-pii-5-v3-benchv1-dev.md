# Raport: ner na bench/v1/dev

## System
- Name: ner
- Wersja: 0.1.0
- Data: 2026-10-25T12:51:54.500203
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
- Peak RAM: 2585063424 bytes

## Encje (strict)
- Micro Precision: 0.4561
- Micro Recall: 0.6500
- Micro F1: 0.5361

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.5714 | 0.8000 | 0.6667 |
| DANE_ZDROWOTNE | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| DOCHOD | 0.0000 | 0.0000 | 0.0000 |
| EMAIL | 1.0000 | 1.0000 | 1.0000 |
| IBAN | 0.6667 | 1.0000 | 0.8000 |
| IMIE | 0.0000 | 0.0000 | 0.0000 |
| KOD_POCZTOWY | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 0.3333 | 0.3333 | 0.3333 |
| LEKARZ | 1.0000 | 1.0000 | 1.0000 |
| MIEJSCOWOSC | 0.0000 | 0.0000 | 0.0000 |
| NAZWISKO | 0.0000 | 0.0000 | 0.0000 |
| NIP | 1.0000 | 1.0000 | 1.0000 |
| NPWZ | 1.0000 | 1.0000 | 1.0000 |
| NR_KARTY | 1.0000 | 1.0000 | 1.0000 |
| NR_POLISY | 1.0000 | 1.0000 | 1.0000 |
| NR_RACHUNKU | 0.0000 | 0.0000 | 0.0000 |
| NR_SZKODY | 1.0000 | 1.0000 | 1.0000 |
| NR_UMOWY | 1.0000 | 1.0000 | 1.0000 |
| OSOBA | 0.5000 | 0.1429 | 0.2222 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |
| PLACOWKA | 0.0000 | 0.0000 | 0.0000 |
| ROZPOZNANIE | 0.0000 | 0.0000 | 0.0000 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 |

## Encje (partial)
- Micro Precision: 0.5789
- Micro Recall: 0.8250
- Micro F1: 0.6804

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.5714 | 0.8000 | 0.6667 |
| DANE_ZDROWOTNE | 1.0000 | 1.0000 | 1.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| DOCHOD | 0.5000 | 1.0000 | 0.6667 |
| EMAIL | 1.0000 | 1.0000 | 1.0000 |
| IBAN | 0.6667 | 1.0000 | 0.8000 |
| IMIE | 0.0000 | 0.0000 | 0.0000 |
| KOD_POCZTOWY | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 1.0000 | 1.0000 | 1.0000 |
| LEKARZ | 1.0000 | 1.0000 | 1.0000 |
| MIEJSCOWOSC | 0.0000 | 0.0000 | 0.0000 |
| NAZWISKO | 0.0000 | 0.0000 | 0.0000 |
| NIP | 1.0000 | 1.0000 | 1.0000 |
| NPWZ | 1.0000 | 1.0000 | 1.0000 |
| NR_KARTY | 1.0000 | 1.0000 | 1.0000 |
| NR_POLISY | 1.0000 | 1.0000 | 1.0000 |
| NR_RACHUNKU | 0.0000 | 0.0000 | 0.0000 |
| NR_SZKODY | 1.0000 | 1.0000 | 1.0000 |
| NR_UMOWY | 1.0000 | 1.0000 | 1.0000 |
| OSOBA | 1.0000 | 0.2857 | 0.4444 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |
| PLACOWKA | 1.0000 | 1.0000 | 1.0000 |
| ROZPOZNANIE | 0.3333 | 1.0000 | 0.5000 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 |

## Porównywalna podtaksonomia (bardsai_v2)
- Etykiety: ADRES, CVV, DANE_ZDROWOTNE, DATA_URODZENIA, EMAIL, GEO, IBAN, IP, KWOTA, MIEJSCOWOSC, NIP, NR_DOKUMENTACJI, NR_DOWODU, NR_KARTY, NR_RACHUNKU, OSOBA, PESEL, PLACOWKA, TELEFON, VIN
- Strict Micro Precision: 0.6562
- Strict Micro Recall: 0.6364
- Strict Micro F1: 0.6462
- Partial Micro Precision: 0.8125
- Partial Micro Recall: 0.7879
- Partial Micro F1: 0.8000

## Recall ważony ryzykiem
- Risk-weighted recall: 0.6707

## Leak rate
- Docs leaked: 0 / 6
- Values leaked: 0 / 40
- Leaked doc IDs: brak

## Wierność
- Changed chars outside spans: 0

## Numeracja
- Same entity consistent: 1 / 1
- Different entity distinct: 0 / 0

## Throughput
- Throughput: 16.08 docs/s
- P95 latency: 0.1623 s

## Podział wg doc_type

### mail_klienta
- Strict Micro Precision: 0.3750
- Strict Micro Recall: 0.5000
- Strict Micro F1: 0.4286

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| EMAIL | 1.0000 | 1.0000 | 1.0000 |
| IMIE | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 0.0000 | 0.0000 | 0.0000 |
| MIEJSCOWOSC | 0.0000 | 0.0000 | 0.0000 |
| NAZWISKO | 0.0000 | 0.0000 | 0.0000 |
| NR_KARTY | 1.0000 | 1.0000 | 1.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 |

### polisa
- Strict Micro Precision: 0.5455
- Strict Micro Recall: 0.6667
- Strict Micro F1: 0.6000

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 1.0000 | 1.0000 | 1.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| EMAIL | 1.0000 | 1.0000 | 1.0000 |
| IMIE | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 0.0000 | 0.0000 | 0.0000 |
| NAZWISKO | 0.0000 | 0.0000 | 0.0000 |
| NR_POLISY | 1.0000 | 1.0000 | 1.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 |

### umowa_kredytowa
- Strict Micro Precision: 0.4000
- Strict Micro Recall: 0.6667
- Strict Micro F1: 0.5000

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 1.0000 | 1.0000 | 1.0000 |
| DOCHOD | 0.0000 | 0.0000 | 0.0000 |
| IBAN | 1.0000 | 1.0000 | 1.0000 |
| IMIE | 0.0000 | 0.0000 | 0.0000 |
| NAZWISKO | 0.0000 | 0.0000 | 0.0000 |
| NR_UMOWY | 1.0000 | 1.0000 | 1.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |

### wyciag
- Strict Micro Precision: 0.8000
- Strict Micro Recall: 0.8000
- Strict Micro F1: 0.8000

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 1.0000 | 1.0000 | 1.0000 |
| IBAN | 0.5000 | 1.0000 | 0.6667 |
| KWOTA | 1.0000 | 1.0000 | 1.0000 |
| NR_RACHUNKU | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 1.0000 | 1.0000 | 1.0000 |

### wypis_szpitalny
- Strict Micro Precision: 0.2857
- Strict Micro Recall: 0.5714
- Strict Micro F1: 0.3810

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| IMIE | 0.0000 | 0.0000 | 0.0000 |
| KOD_POCZTOWY | 0.0000 | 0.0000 | 0.0000 |
| LEKARZ | 1.0000 | 1.0000 | 1.0000 |
| NAZWISKO | 0.0000 | 0.0000 | 0.0000 |
| NPWZ | 1.0000 | 1.0000 | 1.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| PESEL | 1.0000 | 1.0000 | 1.0000 |
| PLACOWKA | 0.0000 | 0.0000 | 0.0000 |
| ROZPOZNANIE | 0.0000 | 0.0000 | 0.0000 |

### zgloszenie_szkody
- Strict Micro Precision: 0.5556
- Strict Micro Recall: 0.7143
- Strict Micro F1: 0.6250

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 1.0000 | 1.0000 | 1.0000 |
| DANE_ZDROWOTNE | 0.0000 | 0.0000 | 0.0000 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 |
| IMIE | 0.0000 | 0.0000 | 0.0000 |
| NAZWISKO | 0.0000 | 0.0000 | 0.0000 |
| NIP | 1.0000 | 1.0000 | 1.0000 |
| NR_SZKODY | 1.0000 | 1.0000 | 1.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| ROZPOZNANIE | 0.0000 | 0.0000 | 0.0000 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 |
