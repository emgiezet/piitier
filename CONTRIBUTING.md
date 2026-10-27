# Contributing to piitier

Rules for humans and agents. The binding versions are [`CLAUDE.md`](CLAUDE.md) (invariants, task
router) and [`.claude/rules/python.md`](.claude/rules/python.md) (code conventions). This page is the
short path through them.

## Workflow

1. **Ticket.** Every change has a ticket id (`PII-<n>`). Bugs go to the tracker first; a human
   labelling the issue `bug` approves the fix.
2. **Spec.** Write `specs/<TICKET>/spec.md`: Problem, Scope (`In:` / `Out:`, change budget), Context,
   a UC table with observable results, no open questions. A human sets `status: approved`; nothing is
   implemented before that.
3. **Branch.** `ai/<TICKET>-<slug>` off `main`. Never commit to `main`.
4. **Pull request.** Label `ai-sdlc`, fill in the template, link the spec. CI must be green.
5. **Review.** Get an independent review before merging. It has caught a blocker that tests missed in two of the last three feature batches (see [`FINDINGS.md`](FINDINGS.md)).
6. **Merge**, then record new results or decisions in `FINDINGS.md`.

One spec is one pull request. Budgets live in [`.claude/sdlc.md`](.claude/sdlc.md) ("Change budget").

## Hooks and verification

```bash
uv sync --frozen
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
uv run pre-commit run --all-files          # gitleaks, private keys, ruff, mypy, piitier scan
uv run pytest -q -m "not integration"      # unit tests, no network (also on push and in CI)
uv run pytest -q -m integration            # touches model loading, training or export
```

Commits use conventional messages: `type(scope): description`. Do not bypass hooks with
`--no-verify`; fix the finding instead.

## Data and privacy

- Only synthetic documents enter the repository. Employer or client documents never do, not even as
  templates derived from them (`raw_data/` and derived templates stay local and gitignored).
- A new checksum-valid identifier (PESEL, NIP, REGON, IBAN, ID card, payment card) fails the
  `piitier-scan` hook. If it is synthetic, add its fingerprint:
  `uv run piitier scan --allowlist .pii-allowlist --write-allowlist .pii-allowlist <file>`.
- Never log or print document text or PII values, including in exceptions and reports.
- `bench/<version>/test/` is only for final numbers: never for training, calibration or prompt
  examples.

## Tests

- Every acceptance criterion's `UC-<n>` appears in a test name (`test_uc142_...`).
- Tests for a bug fix must fail on the code before the fix. Show it in the PR.
- Unit tests never touch the network; anything that downloads a checkpoint is
  `@pytest.mark.integration`.
- Never delete, skip or weaken a test to get green.

## Results

- Benchmark runs: `uv run python -m eval.run …` writes `eval/reports/`; metric definitions and gates
  are in [`docs/bench/PROTOCOL.md`](docs/bench/PROTOCOL.md).
- Model, pipeline, data and process findings go to [`FINDINGS.md`](FINDINGS.md), with a link to the
  evidence.
- Large artefacts (corpora, checkpoints, ONNX) go under `data/` or `training/out/`, never into git.
