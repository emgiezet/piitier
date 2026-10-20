# Playbook — Tests and coverage

Task-scoped. Reached from the Task Router in `CLAUDE.md`. Do not read sibling playbooks.
Load the `dense-testing` skill — it holds the density floors, the per-stack recipes, and the rules
this playbook enforces. Test conventions live in `.claude/rules/python.md`.

## Sequence

1. **Find the gap before writing anything.** Which acceptance criteria (`UC-<n>` in
   `specs/<TICKET>/spec.md`) have no test carrying their id? Which public functions in
   `src/piitier/`, `eval/` or `training/` changed in the recent diff and have no test? That list
   is the work.
2. **End-to-end through the pipeline first.** One test per `UC-<n>`, named with its id, that
   runs real text through `normalize → rules → ner → fusion → coref → render` (or the eval
   runner) and asserts on the output text and spans. These catch a hallucinated implementation;
   unit tests only catch a wrong branch.
3. **Then fill the branch grid.** Every error path, validation rule, and conditional in the
   changed code gets its own case, parameterised with `pytest.mark.parametrize`.
4. **Property-based where an invariant exists.** Use `hypothesis` for validators (valid vs
   altered check digit), the fidelity guarantee (0 changed characters outside spans), and
   offset integrity (`text[start:end] == span.text`).
5. **Assert on observable behaviour**: rendered text, span offsets and labels, metric values,
   written report files. Never assert that a mock was called when the real effect is checkable.
6. **Run the full suite, not just the new file.** A new test that passes while breaking two
   existing ones is a net loss.

## Non-negotiable

- Never delete a test, mark it skipped, or loosen an assertion to make the suite green. If a test
  contradicts the spec, stop and report the contradiction — one of them is wrong, and deciding
  which is a human call, not a cleanup task.
- Never write a test that asserts current buggy behaviour just to get a green run.
- Never weaken the fidelity test, and never raise its tolerance above 0.
- Test fixtures are synthetic. Never paste real personal data into a test.
- A flaky test is a defect: fix the race or the fixture, never retry around it. `hypothesis`
  failures are real; add the shrunk example as an explicit `@example`.

The `Stop` hook enforces the first rule automatically and will block a session that removed tests
or added skips.

## Verify

Run the verification block from `.claude/rules/python.md`. Then report in the spec's terms:

- `UC-<n>` ids with at least one passing test, out of the total in the spec.
- Test count before and after, and the skip count — which must be zero.

## Done when

Every `UC-<n>` has a passing test carrying its id, every branch introduced by the change has a
case, nothing was skipped or weakened, and the verification block is green.
