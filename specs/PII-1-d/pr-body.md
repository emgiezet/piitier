# PII-1-d — Mask IBAN and Polish NRB account numbers

Adds an IBAN/NRB detector to `piitier.mask()` and `piitier.detect()`.

## What changed

- **`src/piitier/rules/iban.py`** (new) — regex-based detector for Polish NRB (PL + 26 digits),
  foreign IBAN (2-letter CC + 2 check digits + 11–30 alphanumerics), both contiguous and
  space-separated forms; mod 97 validation; `status="valid"` or `status="suspect"`.
- **`src/piitier/rules/__init__.py`** — imports `iban` module; inserts `iban.find` into
  `_DETECTORS` after `regon.find`; `detect_all` applies a narrow filter removing any PESEL span
  wholly contained within an IBAN span (UC-21, valid or suspect); no general fusion subsystem.
- **`tests/rules/test_iban.py`** (new) — unit and integration tests covering all five UCs,
  property tests with independent check-digit helper.

## Use-case coverage

| UC | Action | Expected result | Status |
|----|--------|-----------------|--------|
| UC-19 | `mask` on each of `PL61109010140000071219812874`, `PL61 1090 1014 0000 0712 1981 2874`, `61109010140000071219812874`, `61 1090 1014 0000 0712 1981 2874` | each → `[IBAN]`; one span, `status="valid"`, prefix and spaces covered | ✅ |
| UC-20 | `mask` on `PL61109010140000071219812875` (fails mod 97) | `[IBAN]`; `status="suspect"` | ✅ |
| UC-21 | `detect` on text containing one spaced IBAN, one contiguous IBAN and one PESEL | exactly three spans, sorted by `start`, no PESEL span inside either IBAN | ✅ |
| UC-38 | `mask` on `DE89 3704 0044 0532 0130 00` and `DE89370400440532013000` | each → `[IBAN]`; `status="valid"` | ✅ |
| UC-39 | `mask` on `DE89 3704 0044 0532 0130 01` (fails mod 97) | `[IBAN]`; `status="suspect"` | ✅ |

## Verification

```
uv run ruff format .            → 1 file reformatted, 52 unchanged
uv run ruff check .             → All checks passed
uv run mypy src                 → Success: no issues found in 7 source files
uv run pytest -q                → 155 passed in 1.18s
```

Public API smoke: `mask('BE68539007547034 EUR')` → `'[IBAN] EUR'`;
`mask('AT611904300234573201 payment received')` → `'[IBAN] payment received'`;
`detect('AA01010100005AA')` → 1 suspect IBAN; `detect('AI01010100005AA')` → 1 valid IBAN;
`find('DE89 3704 0044 0532 0130 01')` → 1 suspect; `find('DE89' + 'A'*31)` → no match.

## Risks

- **Grouped-shape ambiguity (known grammar ambiguity):** The spaced foreign IBAN pattern
  `[A-Z]{2}[0-9]{2}(?: [A-Z0-9]{4})+(?: [A-Z0-9]{1,4})?` greedily consumes trailing 4-char
  alphanumeric prose tokens when they directly follow a valid IBAN group sequence
  (e.g. `GB29 NWBK 6016 1331 9268 1919 text done`). No per-country length table is in scope
  (spec §Out). No checksum-based truncation heuristic is introduced. The generic grouped shape
  is preserved as matched — agreed contract for this ambiguous input class. Contiguous pattern
  is unaffected.
- **PESEL suppression scope (narrow, by design):** `detect_all` removes only PESEL spans
  contained within IBAN spans. All other inter-detector overlaps remain unresolved until
  `fusion.py` is implemented (later ticket).

## Scope

Waived: over budget: 678 added lines > 480 (240 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing) — Standing owner approval in `.claude/sdlc.md` permits added-line overruns up to 5000, conditional on QA and verification passing, every UC covered and no other unwaived scope/correctness/security/test-integrity findings. — @local-user (2026-10-20)
