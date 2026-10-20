# Playbook — Fusion, coreference/numbering, renderer

Task-scoped. Reached from the Task Router in `CLAUDE.md`. Do not read sibling playbooks.
Conventions for the code live in `.claude/rules/python.md`.

## The pipeline, in order

`normalize` (Unicode NFC plus an offset map back to the original) → `rules` → `ner` →
`fusion` → `coref` → `render`. Each stage takes the previous stage's output and returns
`Span`s or text; no stage reaches back into an earlier one. Change one stage per task.

## Sequence

1. **Keep the offset contract.** All spans leaving `fusion` are in **original-input**
   offsets. `normalize` owns the mapping; no other stage computes offsets.
2. **Fusion precedence** in `src/piitier/fusion.py`:
   1. A rule span with `status="valid"` beats any overlapping NER span.
   2. Otherwise the type-priority table decides.
   3. NER spans below the calibrated threshold are dropped.
   4. Overlaps resolve to non-overlapping spans and never leave a character uncovered that
      either input covered.
   5. Every output span keeps its `source` (rule, model, threshold) for the audit.
3. **Coreference** in `src/piitier/coref.py`: lemmatise (Morfeusz 2 or spaCy `pl`) and
   case-fold, so "Jan Kowalski", "Kowalskiego" and "J. Kowalski" share one canonical key and
   one index (`[OSOBA_1]`). The same IBAN string gets the same index. Different entities get
   different indices. Numbering is in order of first appearance.
4. **Renderer** in `src/piitier/render.py` builds output only by replacing `[start, end)`
   ranges of the original string, right to left. Modes:
   - `mask` — placeholders, no map.
   - `pseudonymize` — placeholders plus a map encrypted with AES-GCM under a key read from
     the environment, with a TTL. The map and the key are never logged or written unencrypted.
   - `synthetic` is post-MVP: do not implement it unless a spec asks.
5. **An LLM verifier, if present, returns spans only.** Code decides what happens to them
   (CLAUDE.md invariant 5).

## Test requirements

- **Fidelity (property-based):** for random text and random non-overlapping spans, every
  character outside the spans is byte-identical in the output. Changed characters outside
  spans must be exactly 0. Keep this test green; never loosen it.
- Fusion: one parameterised case per precedence rule and per overlap shape (nested, partial,
  adjacent, identical).
- Coreference: inflected forms of one person → one index; two people sharing a surname →
  two indices.
- `pseudonymize` round-trip: unmasking the masked text with its map returns the input exactly.
- NFC: input containing decomposed diacritics renders with spans at the correct original offsets.
- One test per acceptance criterion, named with its `UC-<n>` id when working from a spec.

## Verify

Run the verification block from `.claude/rules/python.md`.

## Done when

Precedence, numbering and renderer behaviour are covered case by case, the fidelity test
reports 0, the round-trip passes, and the verification block is green.
