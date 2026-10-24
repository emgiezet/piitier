# Raport: bardsai-v2 na bench/eval-sample/dev

## System
- Name: bardsai-v2
- Wersja: 0.1.0
- Data: 2026-10-25T00:00:22.712428
- Próg: brak — system bez progu

## Benchmark
- Wersja: eval-sample
- Split: dev
- Liczba dokumentów: 273
- Liczba spanów gold: 2329

## Sprzęt
- Platforma: Linux-7.0.0-38-generic-x86_64-with-glibc2.43
- Procesor: N/A
- GPU: NVIDIA GeForce RTX 3090 Ti
- Peak RAM: 2572210176 bytes

## Encje (strict)
- Micro Precision: 0.3424
- Micro Recall: 0.4058
- Micro F1: 0.3714

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.1961 | 0.2326 | 0.2128 |
| DATA_URODZENIA | 0.1333 | 1.0000 | 0.2353 |
| EMAIL | 0.0588 | 0.0588 | 0.0588 |
| IBAN | 0.5846 | 0.6032 | 0.5938 |
| IMIE | 0.0000 | 0.0000 | 0.0000 |
| KOD_POCZTOWY | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 0.1079 | 0.1279 | 0.1170 |
| MIEJSCOWOSC | 0.0100 | 0.1667 | 0.0189 |
| NAZWISKO | 0.0000 | 0.0000 | 0.0000 |
| NIP | 0.1331 | 0.1523 | 0.1421 |
| NR_DOKUMENTACJI | 0.0000 | 0.0000 | 0.0000 |
| NR_DOWODU | 0.0000 | 0.0000 | 0.0000 |
| NR_POLISY | 0.0000 | 0.0000 | 0.0000 |
| NR_REJESTRACYJNY | 0.0000 | 0.0000 | 0.0000 |
| NR_SZKODY | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.9062 | 0.9770 | 0.9403 |
| PESEL | 0.3822 | 1.0000 | 0.5530 |
| PLACOWKA | 0.0000 | 0.0000 | 0.0000 |
| REGON | 0.0000 | 0.0000 | 0.0000 |
| TELEFON | 0.3333 | 0.4815 | 0.3939 |
| VIN | 0.5000 | 0.2500 | 0.3333 |

## Encje (partial)
- Micro Precision: 0.5920
- Micro Recall: 0.7016
- Micro F1: 0.6422

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.8431 | 1.0000 | 0.9149 |
| DATA_URODZENIA | 0.1333 | 1.0000 | 0.2353 |
| EMAIL | 1.0000 | 1.0000 | 1.0000 |
| IBAN | 0.9692 | 1.0000 | 0.9844 |
| IMIE | 0.0000 | 0.0000 | 0.0000 |
| KOD_POCZTOWY | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 0.8438 | 1.0000 | 0.9153 |
| MIEJSCOWOSC | 0.0500 | 0.8333 | 0.0943 |
| NAZWISKO | 0.0000 | 0.0000 | 0.0000 |
| NIP | 0.3208 | 0.3672 | 0.3424 |
| NR_DOKUMENTACJI | 0.0000 | 0.0000 | 0.0000 |
| NR_DOWODU | 0.0000 | 0.0000 | 0.0000 |
| NR_POLISY | 0.0000 | 0.0000 | 0.0000 |
| NR_REJESTRACYJNY | 0.0000 | 0.0000 | 0.0000 |
| NR_SZKODY | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.9275 | 1.0000 | 0.9624 |
| PESEL | 0.3822 | 1.0000 | 0.5530 |
| PLACOWKA | 0.0000 | 0.0000 | 0.0000 |
| REGON | 0.0000 | 0.0000 | 0.0000 |
| TELEFON | 0.6923 | 1.0000 | 0.8182 |
| VIN | 0.5000 | 0.2500 | 0.3333 |

## Porównywalna podtaksonomia (bardsai_v2)
- Etykiety: ADRES, CVV, DANE_ZDROWOTNE, DATA_URODZENIA, EMAIL, GEO, IBAN, IP, KWOTA, MIEJSCOWOSC, NIP, NR_DOKUMENTACJI, NR_DOWODU, NR_KARTY, NR_RACHUNKU, OSOBA, PESEL, PLACOWKA, TELEFON, VIN
- Strict Micro Precision: 0.3424
- Strict Micro Recall: 0.4657
- Strict Micro F1: 0.3947
- Partial Micro Precision: 0.5920
- Partial Micro Recall: 0.8053
- Partial Micro F1: 0.6824

## Recall ważony ryzykiem
- Risk-weighted recall: 0.3675

## Leak rate
- Docs leaked: 4 / 273
- Values leaked: 28 / 2329
- Leaked doc IDs: doc_0000493, doc_0000964, doc_0001213, doc_0001933

## Wierność
- Changed chars outside spans: 35248

## Numeracja
- Same entity consistent: 37 / 37
- Different entity distinct: 0 / 3173

## Throughput
- Throughput: 1.27 docs/s
- P95 latency: 0.7732 s

## Podział wg doc_type

### mail_klienta
- Strict Micro Precision: 0.4204
- Strict Micro Recall: 0.4204
- Strict Micro F1: 0.4204

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| IBAN | 0.5570 | 0.5695 | 0.5632 |
| NIP | 0.4167 | 0.1121 | 0.1767 |
| NR_DOWODU | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.0000 | 0.0000 | 0.0000 |
| PESEL | 0.3748 | 1.0000 | 0.5452 |

### polisa
- Strict Micro Precision: 0.1280
- Strict Micro Recall: 0.2816
- Strict Micro F1: 0.1760

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| ADRES | 0.1961 | 0.2326 | 0.2128 |
| DATA_URODZENIA | 0.6667 | 1.0000 | 0.8000 |
| EMAIL | 0.0588 | 0.0588 | 0.0588 |
| IBAN | 0.8000 | 0.8000 | 0.8000 |
| KOD_POCZTOWY | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 0.0649 | 0.0847 | 0.0735 |
| MIEJSCOWOSC | 0.0556 | 0.1667 | 0.0833 |
| NIP | 0.3333 | 0.8889 | 0.4848 |
| NR_DOKUMENTACJI | 0.0000 | 0.0000 | 0.0000 |
| NR_POLISY | 0.0000 | 0.0000 | 0.0000 |
| NR_REJESTRACYJNY | 0.0000 | 0.0000 | 0.0000 |
| NR_SZKODY | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.5417 | 0.5652 | 0.5532 |
| PESEL | 0.8182 | 1.0000 | 0.9000 |
| PLACOWKA | 0.0000 | 0.0000 | 0.0000 |
| REGON | 0.0000 | 0.0000 | 0.0000 |
| TELEFON | 0.4815 | 0.4815 | 0.4815 |
| VIN | 0.5000 | 0.2500 | 0.3333 |

### zestawienie_prowizyjne
- Strict Micro Precision: 0.3755
- Strict Micro Recall: 0.4186
- Strict Micro F1: 0.3959

| Etykieta | Precision | Recall | F1 |
|---|---|---|---|
| DATA_URODZENIA | 0.0000 | 0.0000 | 0.0000 |
| IBAN | 0.7778 | 0.8750 | 0.8235 |
| IMIE | 0.0000 | 0.0000 | 0.0000 |
| KWOTA | 0.1140 | 0.1333 | 0.1229 |
| MIEJSCOWOSC | 0.0000 | 0.0000 | 0.0000 |
| NAZWISKO | 0.0000 | 0.0000 | 0.0000 |
| NIP | 0.0191 | 0.1667 | 0.0343 |
| NR_POLISY | 0.0000 | 0.0000 | 0.0000 |
| NR_REJESTRACYJNY | 0.0000 | 0.0000 | 0.0000 |
| OSOBA | 0.9450 | 1.0000 | 0.9717 |
| PESEL | 0.0000 | 0.0000 | 0.0000 |
| PLACOWKA | 0.0000 | 0.0000 | 0.0000 |
| TELEFON | 0.0000 | 0.0000 | 0.0000 |
