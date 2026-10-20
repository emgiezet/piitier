## PII-1-e — Mask ID-card numbers and payment-card numbers
**QA verdict: PASS** · UC coverage: 6/6 automated · Tests: 118 → 179 · Skipped: 0

Implemented from `specs/PII-1-e/spec.md`. Existing detectors, public API, labels and renderer are unchanged.

### What the spec asked for

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-22 | developer | `mask` on each of `ABA300000`, `ABA 300000`, `XYZ712345` | each becomes `[NR_DOWODU]`; `status="valid"` | integration |
| UC-23 | developer | `mask("nr ABA400000")` (wrong check digit, no keyword) | `"nr [NR_DOWODU]"`; `status="suspect"` | unit |
| UC-24 | developer | `mask` on each of `4111111111111111`, `4111 1111 1111 1111`, `4111-1111-1111-1111` | each becomes `[NR_KARTY]`; `status="valid"` | integration |
| UC-25 | developer | `mask("4111 1111 1111 1112")` (16 digits, fails Luhn, no keyword) | `"[NR_KARTY]"`; `status="suspect"` | unit |
| UC-26 | developer | `detect` on `aba300000`, `ABCD300000` and `ABA3000001` | no `NR_DOWODU` span for any of them (lowercase, 4 letters, 7 digits) *(added)* | unit |
| UC-27 | developer | `detect` on a Luhn-valid 12-digit run, a Luhn-valid 20-digit run, a Luhn-invalid 15-digit run, and the PESEL `90051512340` | no `NR_KARTY` span for any of them; the PESEL is still detected as `PESEL` only *(added)* | unit |

### How to verify

```sh
uv sync --frozen
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest -q
```

All checks passed; the full suite includes the marked integration cases: 179 passed,
zero skipped. Public-API smoke verified the specified card formats, suspect masking and
unchanged PESEL behavior.

### Review here first

- `src/piitier/rules/id_card.py`: fourth-character checksum placement and uppercase boundaries.
- `src/piitier/rules/payment_card.py`: Luhn checks and distinct candidate rules for 16 digits versus other lengths.
- `src/piitier/rules/__init__.py`: detector registration.

### Conditional size approval

Waived: over change budget: added lines (871 vs 540; 270 + 100% tolerance) — Standing owner approval in `.claude/sdlc.md` permits added-line overruns up to 5000, conditional on QA/verification passing, all UCs covered and no other unwaived findings. All five changed code/test paths are declared. — @local-user

### Not covered

No card-brand lookup, passports, CVV or expiry-date detection; all are outside the approved scope.
