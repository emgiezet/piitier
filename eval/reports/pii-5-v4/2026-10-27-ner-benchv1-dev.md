# Report: ner on bench/v1/dev

## System
- Name: ner
- Version: 0.1.0
- Date: 2026-10-27T00:14:05.431108
- Threshold: 0.78

## Metadata
- Commit: e298debb2a8be324782f4114d60502db3edc4c0f
- Checkpoint: `training/out/pii-5-v4` (local, gitignored)
- SHA-256 wag (`model.safetensors`): `94d43a6effabd3c3b1500d8f20f9d136aa77b39f2f4fb01fcf51dedd062fc94c`
- Calibration config: `training/configs/pii-5-v4.yaml`
- Documents: 6
- Split: dev
- Threshold: 0.78
- SHA-256 bench:
  - docs.jsonl: 8c681e195f192df3a01fa6202cc0513e97e700b425b4b87355dfb927996dc6b0

## Benchmark
- Version: v1
- Split: dev
- Number of documents: 6
- Number of gold spans: 40

## Hardware
- Platform: Linux-7.0.0-38-generic-x86_64-with-glibc2.43
- CPU: N/A
- GPU: NVIDIA GeForce RTX 3080
- Peak RAM: 2596007936 bytes

## Entities (strict)
- Micro Precision: 0.6383 (TP=30, FP=17, FN=10)
- Micro Recall: 0.7500
- Micro F1: 0.6897

| Label | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| ADRES | 0.6667 | 0.8000 | 0.7273 | 4 | 2 | 1 |
| DANE_ZDROWOTNE | 0.0000 | 0.0000 | 0.0000 | 0 | 2 | 1 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 | 3 | 0 | 0 |
| DOCHOD | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| EMAIL | 1.0000 | 1.0000 | 1.0000 | 2 | 0 | 0 |
| IBAN | 0.6667 | 1.0000 | 0.8000 | 2 | 1 | 0 |
| IMIE | 0.0000 | undefined (0/0) | 0.0000 | 0 | 5 | 0 |
| KWOTA | 0.6667 | 0.6667 | 0.6667 | 2 | 1 | 1 |
| LEKARZ | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| MIEJSCOWOSC | 0.0000 | undefined (0/0) | 0.0000 | 0 | 1 | 0 |
| NAZWISKO | 0.0000 | undefined (0/0) | 0.0000 | 0 | 4 | 0 |
| NIP | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| NPWZ | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| NR_KARTY | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| NR_POLISY | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| NR_RACHUNKU | undefined (0/0) | 0.0000 | 0.0000 | 0 | 0 | 1 |
| NR_SZKODY | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| NR_UMOWY | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| OSOBA | 1.0000 | 0.2857 | 0.4444 | 2 | 0 | 5 |
| PESEL | 1.0000 | 1.0000 | 1.0000 | 3 | 0 | 0 |
| PLACOWKA | 0.0000 | 0.0000 | 0.0000 | 0 | 1 | 1 |
| ROZPOZNANIE | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 | 3 | 0 | 0 |

## Entities (partial)
- Micro Precision: 0.7021 (TP=33, FP=14, FN=7)
- Micro Recall: 0.8250
- Micro F1: 0.7586

| Label | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| ADRES | 0.6667 | 0.8000 | 0.7273 | 4 | 2 | 1 |
| DANE_ZDROWOTNE | 0.5000 | 1.0000 | 0.6667 | 1 | 1 | 0 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 | 3 | 0 | 0 |
| DOCHOD | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| EMAIL | 1.0000 | 1.0000 | 1.0000 | 2 | 0 | 0 |
| IBAN | 0.6667 | 1.0000 | 0.8000 | 2 | 1 | 0 |
| IMIE | 0.0000 | undefined (0/0) | 0.0000 | 0 | 5 | 0 |
| KWOTA | 1.0000 | 1.0000 | 1.0000 | 3 | 0 | 0 |
| LEKARZ | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| MIEJSCOWOSC | 0.0000 | undefined (0/0) | 0.0000 | 0 | 1 | 0 |
| NAZWISKO | 0.0000 | undefined (0/0) | 0.0000 | 0 | 4 | 0 |
| NIP | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| NPWZ | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| NR_KARTY | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| NR_POLISY | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| NR_RACHUNKU | undefined (0/0) | 0.0000 | 0.0000 | 0 | 0 | 1 |
| NR_SZKODY | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| NR_UMOWY | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| OSOBA | 1.0000 | 0.2857 | 0.4444 | 2 | 0 | 5 |
| PESEL | 1.0000 | 1.0000 | 1.0000 | 3 | 0 | 0 |
| PLACOWKA | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| ROZPOZNANIE | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 | 3 | 0 | 0 |

## Risk-weighted recall
- Risk-weighted recall: 0.7744

## Leak rate
- Docs leaked: 0/6 (docs_with_direct_id=6, docs_total=6)
- Values leaked: 0/40
- Leaked doc IDs: none

## Fidelity
- Changed chars outside spans: 0

## Numbering
- Same entity consistent: 0 / 1
- Different entity distinct: 0 / 0

## Throughput
- Throughput: 31.18 docs/s
- P95 latency: 0.1085 s

## Breakdown by doc_type

### mail_klienta
- Strict Micro Precision: 0.4286 (TP=3, FP=4, FN=3)
- Strict Micro Recall: 0.5000
- Strict Micro F1: 0.4615

| Label | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| ADRES | undefined (0/0) | 0.0000 | 0.0000 | 0 | 0 | 1 |
| EMAIL | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| IMIE | 0.0000 | undefined (0/0) | 0.0000 | 0 | 1 | 0 |
| KWOTA | 0.0000 | 0.0000 | 0.0000 | 0 | 1 | 1 |
| MIEJSCOWOSC | 0.0000 | undefined (0/0) | 0.0000 | 0 | 1 | 0 |
| NAZWISKO | 0.0000 | undefined (0/0) | 0.0000 | 0 | 1 | 0 |
| NR_KARTY | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| OSOBA | undefined (0/0) | 0.0000 | 0.0000 | 0 | 0 | 1 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |

### polisa
- Strict Micro Precision: 0.8889 (TP=8, FP=1, FN=1)
- Strict Micro Recall: 0.8889
- Strict Micro F1: 0.8889

| Label | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| ADRES | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| EMAIL | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| IMIE | 0.0000 | undefined (0/0) | 0.0000 | 0 | 1 | 0 |
| KWOTA | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| NR_POLISY | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| OSOBA | 1.0000 | 0.5000 | 0.6667 | 1 | 0 | 1 |
| PESEL | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |

### umowa_kredytowa
- Strict Micro Precision: 0.7143 (TP=5, FP=2, FN=1)
- Strict Micro Recall: 0.8333
- Strict Micro F1: 0.7692

| Label | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| ADRES | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| DOCHOD | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| IBAN | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| IMIE | 0.0000 | undefined (0/0) | 0.0000 | 0 | 1 | 0 |
| NAZWISKO | 0.0000 | undefined (0/0) | 0.0000 | 0 | 1 | 0 |
| NR_UMOWY | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| OSOBA | undefined (0/0) | 0.0000 | 0.0000 | 0 | 0 | 1 |
| PESEL | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |

### wyciag
- Strict Micro Precision: 0.8000 (TP=4, FP=1, FN=1)
- Strict Micro Recall: 0.8000
- Strict Micro F1: 0.8000

| Label | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| ADRES | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| IBAN | 0.5000 | 1.0000 | 0.6667 | 1 | 1 | 0 |
| KWOTA | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| NR_RACHUNKU | undefined (0/0) | 0.0000 | 0.0000 | 0 | 0 | 1 |
| OSOBA | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |

### wypis_szpitalny
- Strict Micro Precision: 0.5000 (TP=5, FP=5, FN=2)
- Strict Micro Recall: 0.7143
- Strict Micro F1: 0.5882

| Label | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| ADRES | 0.0000 | undefined (0/0) | 0.0000 | 0 | 2 | 0 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| IMIE | 0.0000 | undefined (0/0) | 0.0000 | 0 | 1 | 0 |
| LEKARZ | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| NAZWISKO | 0.0000 | undefined (0/0) | 0.0000 | 0 | 1 | 0 |
| NPWZ | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| OSOBA | undefined (0/0) | 0.0000 | 0.0000 | 0 | 0 | 1 |
| PESEL | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| PLACOWKA | 0.0000 | 0.0000 | 0.0000 | 0 | 1 | 1 |
| ROZPOZNANIE | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |

### zgloszenie_szkody
- Strict Micro Precision: 0.5556 (TP=5, FP=4, FN=2)
- Strict Micro Recall: 0.7143
- Strict Micro F1: 0.6250

| Label | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| ADRES | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| DANE_ZDROWOTNE | 0.0000 | 0.0000 | 0.0000 | 0 | 2 | 1 |
| DATA_URODZENIA | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| IMIE | 0.0000 | undefined (0/0) | 0.0000 | 0 | 1 | 0 |
| NAZWISKO | 0.0000 | undefined (0/0) | 0.0000 | 0 | 1 | 0 |
| NIP | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| NR_SZKODY | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
| OSOBA | undefined (0/0) | 0.0000 | 0.0000 | 0 | 0 | 1 |
| TELEFON | 1.0000 | 1.0000 | 1.0000 | 1 | 0 | 0 |
