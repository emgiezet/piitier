# Playbook — Regex/checksum detector

Task-scoped. Reached from the Task Router in `CLAUDE.md`. Do not read sibling playbooks.
Conventions for the code live in `.claude/rules/python.md`; this file is the order of operations.

## Sequence

1. **Confirm the type exists.** Open `docs/TAXONOMY.md` and find the entity type, its placeholder
   and its method. If it is not there, stop: the task belongs to `taxonomy-change.md`.
2. **Write the validator first** in `src/piitier/rules/<type>.py`: a pure function
   `is_valid(value: str) -> bool` that implements the official checksum (PESEL weights 1-3-7-9 and
   a valid date, NIP weights mod 11, REGON 9/14, IBAN mod 97, ID card letters+digits, Luhn).
   No I/O, no globals, no regex inside the validator.
3. **Then the detector** in the same module: `find(text: str) -> list[Span]`. Offsets are into
   the string it was given (`text[span.start:span.end]` is the matched value). Accept the format
   variants the plan lists: spaces, dashes or dots between digit groups, a `PL` prefix where the
   format allows one, uppercase/lowercase letters, a value inside a URL or table cell.
4. **A checksum failure marks the span `status="suspect"`. It never drops the span.** A
   typo in a PESEL is still a PESEL (CLAUDE.md invariant 6).
5. **Register the detector** in `src/piitier/rules/__init__.py` so the pipeline runs it. A
   detector that is not registered never runs.
6. **Client-configurable patterns** (policy number, claim number, contract number) take their
   regex from configuration, not a hard-coded string. Ship one example pattern in the tests only.

## Test requirements

In `tests/rules/test_<type>.py`:

- Property-based (`hypothesis`): a generator of valid values → `is_valid` is `True`; the same
  values with the check digit altered → `is_valid` is `False`.
- The detector finds every generated valid value embedded at random positions in Polish
  filler text, and `text[start:end]` equals the embedded value for every span.
- Each format variant from step 3 gets its own parameterised case.
- Checksum-failing values come back as `suspect`, never missing.
- Hard negatives: digit runs of the right length in technical context (invoice line numbers,
  timestamps) come back `suspect`, not `valid`.
- Target 50–200 cases per validator. Never use a real person's number. Generate them.
- One test per acceptance criterion, named with its `UC-<n>` id when working from a spec.

## Verify

Run the verification block from `.claude/rules/python.md`.

## Done when

Validator and detector exist, the detector is registered, checksum failures are `suspect`,
the property tests pass, and the full verification block is green.
