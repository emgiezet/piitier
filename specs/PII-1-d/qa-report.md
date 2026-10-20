# QA Report — PII-1-d

**Verdict: PASS**

## UC Coverage

| UC | Requirement | Test | Status | Notes |
|-------|---|---|---|---|
| UC-19 | 4 PL IBAN/NRB forms → `[IBAN]`, span covers whole value | `test_uc19_pl_iban_with_prefix_spaced`, `test_uc19_pl_iban_with_prefix_compact`, `test_uc19_nrb_bare_spaced`, `test_uc19_nrb_bare_compact` | ✅ Automated | All 4 forms tested with boundary assertions |
| UC-20 | `PL…2875` fails mod 97 → `suspect` | `test_uc20_invalid_checksum_status_suspect`, `test_uc20_suspect_span_never_dropped` | ✅ Automated | — |
| UC-21 | 1 spaced IBAN + 1 contiguous IBAN + 1 PESEL → 3 non-overlapping spans; no PESEL inside IBAN | `test_uc21_iban_and_pesel_no_overlap`, `test_uc21_regression_pesel_inside_suspect_iban_suppressed`, `test_uc21_regression_pesel_inside_valid_iban_suppressed` | ✅ Automated | Overlap-suppression implemented in `detect_all`; regression covers both suspect and valid IBAN containers |
| UC-38 | DE IBAN (valid) → `[IBAN]` `status="valid"` | `test_uc38_de_iban_spaced_valid`, `test_uc38_de_iban_compact_valid` | ✅ Automated | — |
| UC-39 | DE IBAN (fails mod 97) → `status="suspect"` | `test_uc39_de_iban_invalid_checksum` | ✅ Automated | — |

## Test Suite Output

```
uv run pytest -q
155 passed in 1.18s
```

Public API smoke: `mask('BE68539007547034 EUR')` → `'[IBAN] EUR'`; `mask('AT611904300234573201 payment received')` → `'[IBAN] payment received'`; `detect('AA01010100005AA')` → 1 suspect IBAN; `detect('AI01010100005AA')` → 1 valid IBAN; `find('DE89 3704 0044 0532 0130 01')` → 1 suspect; `find('DE89' + 'A'*31)` → no match.


## Correction Evidence

### Fix: UC-21 overlap suppression in `detect_all`
- **Location:** `src/piitier/rules/__init__.py` — `detect_all()`
- **Change:** After collecting and sorting spans, any `PESEL` span wholly contained within an `IBAN` span (valid or suspect) is removed before returning.
- **Scope:** One conditional filter; no general fusion subsystem; PESEL detector and renderer unchanged.

### Fix: `tests/rules/test_iban.py` linting / regression
- Removed unused `settings` import from `hypothesis`.
- Fixed import order (`import piitier` before `from piitier…`).
- Shortened UC-21 docstring from 107 to 80 chars (E501).
- Removed trailing blank lines at end of file.
- Added `test_uc21_regression_pesel_inside_suspect_iban_suppressed` — minimized hypothesis failure `'AA01010100005AA'`.
- Added `test_uc21_regression_pesel_inside_valid_iban_suppressed` — valid IBAN container `'AI01010100005AA'` (mod97=1).

### Fix: foreign IBAN regex — split compact and spaced patterns
- **Location:** `src/piitier/rules/iban.py` — replaced `_FOREIGN_IBAN_RE` with `_FOREIGN_IBAN_COMPACT_RE` and `_FOREIGN_IBAN_SPACED_RE`.
- **Root cause:** `(?:[ ]?[A-Z0-9]{4})*(?:[ ]?[A-Z0-9]{1,4})?` with optional separators at every group matched contiguous IBANs but then greedily absorbed adjacent words (e.g. `EUR`, `payment`) as optional trailing groups, corrupting the checksum and mislabelling valid IBANs as `suspect`.
- **Fix:** Compact pattern (`[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}`) stops exactly at the first non-alphanumeric after the account; spaced pattern (`[A-Z]{2}[0-9]{2}(?: [A-Z0-9]{4})+(?: [A-Z0-9]{1,4})?`) requires uniform single-space-separated 4-char groups.
- **Regressions:** `test_regression_contiguous_be68_stops_before_prose`, `test_regression_contiguous_at61_stops_before_prose`.

### Fix: property tests — replaced tautological assertions with independent check-digit generator
- **Removed:** `test_prop_is_valid_generated_iban_passes` (only asserted `isinstance(result, bool)`) and `test_prop_bare_nrb_26_digits_consistency` (imported production `_mod97` to recheck `is_valid`, circular verification).
- **Added:** `_iban_check_digits()` test-local helper (independent IBAN check digit computation using only `ord` arithmetic); `test_prop_generated_valid_nrb_detected_as_valid` (verifies span status and exact masking); `test_prop_mutated_check_digit_yields_suspect` (incremented check digit always fails mod 97).


### Verification commands run (parent gates, post-merge)
```
uv run ruff format .            → 1 file reformatted, 52 unchanged
uv run ruff check .             → All checks passed
uv run mypy src                 → Success: no issues found in 7 source files
uv run pytest -q                → 155 passed in 1.18s
```


## Findings (resolved)

### ~~1. [BLOCKING] UC-13 regression: overlapping spans break render.mask()~~ ✅ Fixed
- **Root cause:** `detect_all` concatenated spans without overlap filtering.
- **Fix:** `detect_all` now removes PESEL spans contained within IBAN spans (UC-21 requirement, in-scope per spec).
- **Evidence:** `piitier.detect('AA01010100005AA')` → 1 span `[IBAN]` suspect; `piitier.mask('AA01010100005AA')` → `'[IBAN]'`; UC-13 property test passes.

### ~~2. [BLOCKING] UC-21 contradicts Out section~~ ✅ Resolved
- **Resolution:** UC-21's "no PESEL inside IBAN" is implemented narrowly in `detect_all` without introducing a general fusion subsystem. Spec `Out:` excludes general overlap resolution; this single-rule suppression is within scope of UC-21's explicit requirement.

### 3. [minor] UC-19 integration marker
- Status unchanged: tests remain unit-level; requirement verified. No blocker.

## Limitations

### Spaced foreign IBAN — greedy trailing 4-char groups
The spaced pattern `[A-Z]{2}[0-9]{2}(?: [A-Z0-9]{4})+(?: [A-Z0-9]{1,4})?` retains the longest
greedy match.  When subsequent prose words are themselves 4 alphanumeric characters (e.g.
`GB29 NWBK 6016 1331 9268 1919 text done`), those words may be consumed as additional groups.
No per-country IBAN length table is used (explicitly Out-of-scope per spec §Out).  No
checksum-based truncation heuristic is invented — the generic grouped-shape is preserved as
matched, which is the agreed contract for this ambiguous input class.  This affects only the
spaced form; the contiguous pattern is unaffected.
