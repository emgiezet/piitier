# Playbook — Entity type, label, or placeholder change

Task-scoped. Reached from the Task Router in `CLAUDE.md`. Do not read sibling playbooks.
Conventions for the code live in `.claude/rules/python.md`.

`docs/TAXONOMY.md` is the single source of entity types. Every other place that names a type
follows it. A type that exists in code but not in the taxonomy is a defect.

## Sequence

1. **Edit `docs/TAXONOMY.md` first.** For each type record: group (identity, state IDs,
   contact/location, finance, insurance, health art. 9, other art. 9/10, quasi-identifiers),
   the placeholder (`[PESEL]`, `[OSOBA_n]` for numbered types), the detection method (rule,
   NER, or both), and its risk weight for risk-weighted recall.
2. **Update the label enum** in `src/piitier/labels.py` to match. The NER label space is
   derived from this enum as BIO tags. Nothing else may hard-code a label string.
3. **Update the renderer's placeholder table** in `src/piitier/render.py`.
4. **Update the baseline label mappings** in `eval/baselines/` (bards.ai's 35 classes,
   Presidio, OpenAI Privacy Filter's 8 categories). A type with no mapping counts as a
   miss for that baseline, and the mapping file says so explicitly.
5. **Add an injector** to the synthetic generator in `src/piitier/datagen/` so the type
   appears in training data. For a rule-detected type, also follow the detector steps in the
   spec (the detector itself is a separate task).
6. **Rename or removal** changes the NER label space. Say in the spec that the model must be
   retrained, and do not edit the existing model card.
7. **Gold-set annotations** for a renamed or removed type move to a new bench version under
   `bench/`. Never edit annotations in an existing `test/` split in place.

## Test requirements

- A test asserts the label enum and the types listed in `docs/TAXONOMY.md` are the same set,
  so the next drift fails CI.
- The renderer produces the new placeholder for a span of the new type.
- The generator emits at least one span of the new type at a fixed seed.
- One test per acceptance criterion, named with its `UC-<n>` id when working from a spec.

## Verify

Run the verification block from `.claude/rules/python.md`.

## Done when

Taxonomy, label enum, renderer, baseline mappings, and generator all name the type
identically; any retraining need is stated in the spec; the verification block is green.
