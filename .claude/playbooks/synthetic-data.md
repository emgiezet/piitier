# Playbook — Synthetic training documents

Task-scoped. Reached from the Task Router in `CLAUDE.md`. Do not read sibling playbooks.
Conventions for the code live in `.claude/rules/python.md`.

Labels in synthetic data are correct by construction **only** because code injects every
value and records its offsets. Any step that lets text change without updating offsets
destroys that.

## Sequence

1. **Templates carry placeholders, never values.** Document types: policy, claim report,
   credit agreement, bank statement, customer email, call-centre transcript, hospital
   discharge, referral, commission statement. Templates live in `src/piitier/datagen/templates/`.
2. **A local LLM (Bielik, PLLuM, Qwen) may write template text** with placeholders in place
   of PII. It never writes a value and never assigns a label. Discard any LLM output that
   contains a value where a placeholder belongs.
3. **Values come from Faker `pl_PL` and the in-repo generators.** A PESEL matches its birth
   date and sex. NIP, REGON, IBAN and card numbers carry valid checksums: assert each
   generated value with the validators in `src/piitier/rules/` before injecting it. Addresses
   come from TERYT-shaped data. Names come from Faker only, never from LLM output.
4. **Inflection:** inject names in the grammatical case the slot needs (Morfeusz 2
   generation), and record the injected surface form as the span text.
5. **Augmentation** (typos, missing diacritics, OCR confusions 0/O and 1/l, digit groups
   split by spaces, uppercase, tables, email signatures) runs **after** injection and
   **recomputes every offset** it shifts.
6. **Hard negatives:** common-noun surnames (Kowal, Wróbel, Zima), streets named after
   people, PESEL-shaped technical numbers with bad checksums, public figures. Each one is
   labelled for exactly what it is.
7. **Output:** JSONL in the span schema, written to `data/synthetic/<version>/` (gitignored).
   Commit the generator, its config, and the seed, never the generated corpus. Same seed and
   config → byte-identical output.
8. **Licences:** record every source corpus and its licence in the dataset card draft. The
   output is CC BY 4.0, and CC BY sources (ai4privacy, KPWr) need attribution. Never use
   `bench/**/test/` documents as templates (CLAUDE.md invariant 7).

## Test requirements

- For every span of every generated document, after augmentation:
  `doc.text[span.start:span.end] == span.text`.
- Two runs with the same seed produce identical output; a different seed produces different output.
- Every injected structured ID passes its validator.
- Each augmentation gets its own case asserting offsets stay correct.
- One test per acceptance criterion, named with its `UC-<n>` id when working from a spec.

## Verify

Run the verification block from `.claude/rules/python.md`. Then generate a 100-document
sample at a fixed seed and run the offset-integrity check over it.

## Done when

Offsets are exact after augmentation, output is seed-deterministic, no LLM-written values
or labels reach the corpus, sources are recorded, and the verification block is green.
