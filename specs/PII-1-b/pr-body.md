## PII-1-b — Mask PESEL numbers through `piitier.detect()` and `piitier.mask()`
**QA verdict: PASS** · UC coverage: 9/9 automated · Tests: 26 → 117 · Skipped: 0

🤖 Written by an agent from `specs/PII-1-b/spec.md`. Review the spec's `Out:` scope first —
that is where an unattended run is most likely to have overstepped.

### What the spec asked for

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-7 | developer | `piitier.mask("PESEL: 90051512340, tel.")` | returns `"PESEL: [PESEL], tel."` | integration |
| UC-8 | developer | `piitier.detect("PESEL: 90051512340, tel.")` | exactly one span: `start=7, end=18, label=Label.PESEL, source="rule", score=1.0, status="valid"` | integration |
| UC-9 | developer | `mask`/`detect` on `90051512341` (wrong check digit) | masked to `[PESEL]`; span `status="suspect"` | integration |
| UC-10 | developer | `detect` on `90131512341` (checksum correct, month 13 does not exist) | one span, `status="suspect"` | unit |
| UC-11 | developer | `detect` on `05250112343` (born 2005-05-01, month+20 encoding) | one span, `status="valid"` | unit |
| UC-12 | developer | `detect` on a 10-digit run `9005151234`, a 12-digit run `900515123401`, and `x90051512340y` | no span for the 10- and 12-digit runs; for `x90051512340y` one span covering only the 11 digits: letters do not block a match, digits do | unit |
| UC-13 | developer | `mask` on hypothesis-generated Polish text with 0–5 embedded PESELs at random positions, including `""` | every character outside the detected spans is identical, in order, to the input; text with no detections is returned unchanged; `""` returns `""` | unit (property) |
| UC-36 | developer | `mask` on `900 515 123 40`, `9005-1512-340` and `90051 512340` | each becomes exactly `[PESEL]`; the span covers the separators; `status="valid"` | unit |
| UC-37 | developer | `detect` on `Telefon: +48 501 234 567` and `tel. +48501234567` (both 11 digits after `+`) | no `PESEL` span in either | unit |

### How to verify

```
uv run ruff format --check . && uv run ruff check .
uv run mypy src
uv run pytest -q -m "not integration"
```

### Review here first

- `src/piitier/rules/pesel.py` — PESEL checksum weights, century-month encoding, separator-aware regex, and phone-number exclusion (`+`/`00` prefix); this is the only file where a subtle constant error produces silent misclassification
- `src/piitier/render.py` — right-to-left replacement enforcing the fidelity invariant (UC-13); every character outside a span must survive unchanged in order
- `src/piitier/__init__.py` — public API surface; `detect()` and `mask()` are the two new exported symbols

### Not covered

- No logging/printing/exception-leakage invariant: verified by code inspection only; no automated guard
- Validators are pure functions: verified by code inspection only; no automated purity guard
- Integration-marker gap: UC-7/8/9 are spec-marked `integration` but the tests carry no `@pytest.mark.integration` decorator; all pass under both `-m "not integration"` and bare `pytest`

### Conditional size approval

Waived: over change budget: added lines (1135 vs 720; 360 + 100% tolerance) — Owner approved a hard ceiling of 5000 added lines and conditional acceptance below it on 2026-10-20; QA and verification must pass, all UCs must remain covered, and all other unwaived findings must be resolved before approval. See `.claude/sdlc.md`, Change budget. — @local-user

This waives only the added-line overrun. The undeclared empty
`tests/rules/__init__.py` was removed before re-review; no test or assertion was
removed. Full-suite verification after removal: 118 passed, zero skipped;
ruff format/check and mypy passed.
