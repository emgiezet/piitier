---
paths:
  - "**/*.py"
  - "pyproject.toml"
---

# Python conventions

## Environment

- Python 3.12, managed with uv. The environment comes from `uv sync`; run tools as `uv run <tool>`.
- Add dependencies with an exact pin: `uv add <package>==<version>` (`--dev` for test and lint
  tools). Never use a floating range or `@latest`. Commit `pyproject.toml` and `uv.lock` together.
- `src/` layout: the importable package is `src/piitier/`. `training/` and `eval/` are
  top-level packages that import `piitier`. `piitier` never imports from them.

## Code

- Every public function and method is fully type-annotated; `uv run mypy src` must pass.
- One span type for the whole codebase, a frozen dataclass in `src/piitier/spans.py`:
  `Span(start, end, label, source, score, status)`. `[start, end)` is half-open and indexes
  characters of the **original input string**. Do not define a second span shape.
- Labels come from the enum in `src/piitier/labels.py`. Never use a bare label string literal.
- Validators in `src/piitier/rules/` are pure: no I/O, no globals, no logging.
- **Never log document text or PII values.** Logs carry document ids, offsets, labels and
  counts only. This applies to exceptions too: never put the matched value in an error message.
- Randomness is always seeded from config (`random.Random(seed)`, `numpy.random.default_rng(seed)`).
  Never use the global RNG.
- Secrets (the pseudonymisation key, HF tokens) come from the environment, are read once at
  startup, and never get a default value.
- Large artefacts (corpora, checkpoints, ONNX files) go under `data/` or `training/out/`.
  Never commit them, and never put them under `src/`.

## Tests

- pytest, in a `tests/` tree mirroring `src/piitier/` (`tests/rules/test_pesel.py` for
  `src/piitier/rules/pesel.py`). Files are named `test_*.py`.
- Every acceptance criterion's `UC-<n>` appears in a test name:
  `test_uc3_suspect_pesel_is_masked`.
- Property-based tests use `hypothesis`. When one finds a failure, keep the shrunk input as an
  explicit `@example`.
- Unit tests never touch the network. Anything that downloads a checkpoint or dataset is
  marked `@pytest.mark.integration` and excluded from the default run.
- Fixtures are synthetic. Never commit a real person's name, PESEL, IBAN, or address.

## Verification

Run from the repo root before calling a task done. A missing `pyproject.toml` means the
project has not been bootstrapped yet: say so and stop. Do not create one ad hoc.

```bash
uv sync
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest -q -m "not integration"
```

When the change touches model loading, training or export, also run:

```bash
uv run pytest -q -m integration
```
