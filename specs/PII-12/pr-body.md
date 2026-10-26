## PII-12 — docs(repo): CONTRIBUTING and pull request template

Adopted from pawelkiszczak/warda (see FINDINGS.md, last section). Spec: `specs/PII-12/spec.md`.

- `CONTRIBUTING.md`: workflow (ticket → approved spec → branch → PR → review → merge), hooks and verification, data and privacy rules, test rules, where results go.
- `.github/PULL_REQUEST_TEMPLATE.md`: spec/UC coverage, verification, privacy and data checklist, model and benchmark impact.

### Verification
- `uv run pre-commit run --all-files`: all hooks pass; `uv run pytest -q -m "not integration"`: green on the branch; CI on this PR.
- Docs-only slice (no runtime code); no independent review. `tests/test_contributing.py` pins the sections and checks that the verification commands match `.claude/rules/python.md`.
