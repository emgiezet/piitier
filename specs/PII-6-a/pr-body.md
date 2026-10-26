## PII-6-a — rule + NER span fusion in the library API and CLI

**QA: PASS** · UC-102..UC-110 9/9 · tests: 734 passed (`-m "not integration"`), 48 passed (`-m integration`) · independent review: CHANGES_REQUESTED (1 BLOCKER, 2 MAJOR) → all fixed.

### What changes for the user
- `piitier mask <file> --model <checkpoint dir> [--threshold T]` masks rule identifiers **and** model entities. Without `--model` the output is byte-identical to before.
- `piitier.Anonymizer(model=... | predictor=..., threshold=..., device=...)` with `.detect()` / `.mask()`; the model loads once. `piitier.detect` / `piitier.mask` stay rules-only and never import torch/transformers.
- New `src/piitier/fusion.py`: a valid rule span beats an overlapping NER span; otherwise TAXONOMY risk weight → longer span → earlier start; NER spans below the threshold are dropped (== kept); output is non-overlapping, coverage equals the union of the inputs, and the loser keeps its fragments with its own label and source. O(n log n) sweep (20k spans < 2 s).

### Real-model smoke test (pii-5-v3, CPU)
```
rules only : Poszkodowana Anna Wiśniewska, zam. ul. Lipowa 14/3, 30-001 Kraków, PESEL [PESEL], tel. 512 345 678, ...
--model    : Poszkodowana [IMIĘ_n] [NAZWISKO_n], zam. [ADRES_n], PESEL [PESEL], tel. [TELEFON], e-mail [EMAIL].
             Rozpoznanie: [ROZPOZNANIE]. Kwota roszczenia: [KWOTA]. Lekarz prowadzący: [LEKARZ_n].
```
`[OSOBA_n]`-style placeholders get numbered in PII-6-b (coref), as scoped.

### Review findings fixed
- **BLOCKER:** precedence tested `source.startswith("rule:")`, but detectors emit `source="rule"`, so "valid rule beats NER" never fired on real input (`PESEL 90051512340 x` + a longer KWOTA NER span → `[KWOTA]`). Fixed and covered by a test using real `detect_all` output (now `[KWOTA][PESEL][KWOTA]`); `Span.source` docstring corrected.
- **MAJOR:** O(n²) fusion → heap sweep. **MAJOR:** NaN / out-of-range threshold silently dropped every NER span (fail-open) → `ValueError` in the API; the CLI exits 2 with `invalid threshold: ...`.
- **MINOR:** an invalid or empty model dir, or missing torch, → exit 2, one line, no traceback; `Anonymizer(model=<nonexistent>)` raises before any HF Hub lookup; overwrite check before model load; property-based fidelity test on fused output; 3-way and rule-vs-rule overlap tests; Label→group mapping sync test.

Spec: [specs/PII-6-a/spec.md](https://github.com/emgiezet/piitier/blob/ai/PII-6-a-fusion/specs/PII-6-a/spec.md) · Decomposition: [specs/PII-6/decomposition.md](https://github.com/emgiezet/piitier/blob/ai/PII-6-a-fusion/specs/PII-6/decomposition.md)
