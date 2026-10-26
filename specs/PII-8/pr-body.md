## PII-8 — repo hygiene: licence, CI, pre-commit, `piitier scan`

Adopted from the comparison with pawelkiszczak/warda (see `FINDINGS.md`, last section).

- **`LICENSE`** (canonical Apache-2.0 text, SHA-256 `cfc7749b…3d30`, checked by a test) and **`NOTICE`**. Until now `pyproject.toml` declared Apache-2.0 but no licence file existed.
- **`piitier scan [--allowlist F] [--write-allowlist F] <path>…`** reports checksum-valid identifiers (PESEL, NIP, REGON, IBAN, ID card, payment card) as `path:line:column: LABEL`, never the value. Exit 1 if any are outside the allowlist. Rules only, no torch import.
- **`.pii-allowlist`**: SHA-256 fingerprints of the 53 synthetic values in the tree today. A new checksum-valid value now has to be allowlisted on purpose.
- **`.pre-commit-config.yaml`**: detect-private-key, large files, merge conflicts, gitleaks, ruff format/check, mypy, `piitier scan` on commit; unit tests on push. Python tools run via `uv run`, so `uv.lock` stays the single source of versions (`pre-commit==4.7.0` added to the dev group). Install: `uv run pre-commit install --hook-type pre-commit --hook-type pre-push`.
- **`.github/workflows/ci.yml`**: every PR and every push to `main` → `uv sync --frozen`, all hooks, unit tests. Unlike warda it gates PRs. Integration tests stay on the GPU workstation.
- **`FINDINGS.md`**: model, pipeline, data and process findings to date, with sources.

### Verification
- `uv run pre-commit run --all-files`: all 8 hooks pass; 754 unit tests pass; mypy clean.
- Negative check (UC-131): appending a freshly computed checksum-valid PESEL to a file fails `piitier-scan` with `specs/PII-8/spec.md:73:20: PESEL` and exit 1, without printing the value.
- UC-132: this PR's own `ci` run.

### Found along the way, not fixed here
The payment-card rule matches Luhn-valid 16-digit runs inside decimals (`0.9937050359712231` in report JSON) and in `uv.lock` hashes, so those generated files are excluded from the scan. Recorded in `FINDINGS.md`.
