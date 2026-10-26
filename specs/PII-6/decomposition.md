# Dekompozycja PII-6 — model NER w pipeline biblioteki

Problem: `piitier.detect` / `piitier.mask` i CLI `piitier mask` używają tylko reguł
(`src/piitier/rules/`). Wytrenowany model (`training/out/pii-5-v3`, 0/40 wycieków na
`bench/v1/dev`) nie jest częścią biblioteki, więc kryterium nr 1 z briefu („szósty skrypt nie
powstaje”) jest spełnione tylko dla identyfikatorów z sumą kontrolną, nie dla imion, adresów
czy danych zdrowotnych.

Playbook `pipeline-core.md`: jeden etap pipeline'u na zadanie.

| Slice | Etap | Zależy od | Status |
|---|---|---|---|
| PII-6-a | `fusion` + podpięcie NER do API i CLI (walking skeleton) | — | spec: draft |
| PII-6-b | `coref` — numeracja `[OSOBA_1]` po lematach (Morfeusz 2), ten sam IBAN → ten sam indeks | a | do napisania |
| PII-6-c | renderer `pseudonymize` — mapa szyfrowana AES-GCM, klucz ze środowiska, TTL, round-trip | b | do napisania |

Poza PII-6 (osobne tickety, inne playbooki):
- Inferencja ONNX INT8 na CPU w `src/piitier/ner` (dziś `OnnxNerPredictor` żyje w `training/`).
- Pakowanie: `transformers`/`torch` są w grupie `dev`, więc `pip install piitier` nie ma NER.
- Kryterium kalibracji progu: dziś strict recall ≥ 0,98, nieosiągalny dla pii-5-v3
  (strict R 0,930 synth dev, 0,636 bench) → próg zawsze 0,0.
- Rozszerzenie `bench/v1` z 6 do 300–500 dokumentów.
