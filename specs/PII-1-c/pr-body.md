## PII-1-c — Mask NIP and REGON numbers
**QA verdict: PASS** · UC coverage: 5/5 automated · Tests: 118 → 174 · Skipped: 0

Implemented from `specs/PII-1-c/spec.md`. No changes to PESEL, renderer, labels or spans.

### What the spec asked for

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-14 | developer | `mask` on each of `5260001246`, `526-000-12-46`, `526-00-01-246`, `PL5260001246`, `NIP: 526 000 12 46` | each value becomes `[NIP]` (`NIP: ` stays); span `status="valid"`; the span covers the prefix and separators | integration |
| UC-15 | developer | `mask("nr zamówienia 5260001247")` (10 digits, wrong check digit, no keyword) | `"nr zamówienia [NIP]"`; span `status="suspect"` | unit |
| UC-16 | developer | `mask` on `REGON: 123456785` (REGON-9) and on bare `12345678000012` (REGON-14) | each value becomes `[REGON]`; `status="valid"` | integration |
| UC-17 | developer | `mask` on `REGON 123456786` and bare `12345678000013` (wrong check digits) | each value becomes `[REGON]`; `status="suspect"` | unit |
| UC-18 | developer | `detect` on bare `123456785` and `tel. 600123457` (9 digits, no `REGON` keyword), and on `KRS 0000123456` | no `REGON` span for either 9-digit run; no `NIP` span for the KRS number *(added from prior art)* | unit |

### How to verify

```sh
uv sync --frozen
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest -q
```

All checks passed; 174 tests passed. Additional public-API smoke covered keyword formats,
KRS exclusion, the REGON remainder-10 case, and suspect masking.

### Review here first

- `src/piitier/rules/nip.py:39`: shape-only versus keyword-gated layouts and candidate boundaries.
- `src/piitier/rules/nip.py:107`: KRS exclusion applies to both detection paths.
- `src/piitier/rules/regon.py:40`: REGON-9 cannot be a prefix of a longer number; checksum remainder 10 maps to 0.

### Conditional size approval

Waived: over budget: 943 added lines > 660 (330 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing) — Standing owner approval in `.claude/sdlc.md` permits added-line overruns up to 5000, conditional on QA/verification passing, all UCs covered and no other unwaived findings. — @local-user (2026-10-20)

### Not covered

External GUS/BIR lookups are outside scope. Only synthetic identifiers were used.
