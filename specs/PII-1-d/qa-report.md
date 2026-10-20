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

### ~~3. [minor] UC-19 integration marker~~ ✅ Resolved
- All four UC-19 tests now explicitly assert `spans[0].status == "valid"`: `test_uc19_pl_iban_with_prefix_spaced` (already present), `test_uc19_pl_iban_with_prefix_compact`, `test_uc19_nrb_bare_spaced`, `test_uc19_nrb_bare_compact`. Three assertions added; no other test or production code changed.

## Limitations

### Spaced foreign IBAN — greedy trailing 4-char groups
The spaced pattern `[A-Z]{2}[0-9]{2}(?: [A-Z0-9]{4})+(?: [A-Z0-9]{1,4})?` retains the longest
greedy match.  When subsequent prose words are themselves 4 alphanumeric characters (e.g.
`GB29 NWBK 6016 1331 9268 1919 text done`), those words may be consumed as additional groups.
No per-country IBAN length table is used (explicitly Out-of-scope per spec §Out).  No
checksum-based truncation heuristic is invented — the generic grouped-shape is preserved as
matched, which is the agreed contract for this ambiguous input class.  This affects only the
spaced form; the contiguous pattern is unaffected.

---

## Combined C/D/E/F Integration — `ai/pii-1-integration`

*Evidence from parent-observed gates on the integration branch. This section records the final
combined state; existing standalone sections above reflect D-branch-only evidence and remain
accurate for that branch context.*

### Scope differentiation from standalone D evidence

The sections above capture **D-branch state only**: 155 tests, with `detect_all` suppressing
only PESEL spans contained within an IBAN span (PESEL-only containment guard).

The integration branch (`ai/pii-1-integration`) merges all four features: C (NIP/REGON),
D (IBAN/NRB), E (ID-card/payment-card), F (CLI). The combined suite reached **295 tests
passed, zero skipped**. The containment filter in `detect_all` was broadened from PESEL-only
to any non-IBAN child span, to fix the BE68 trailing-token loss described below.

### BE68 bug — registry containment fix

**Observed symptom:** `mask('BE68539007547034 EUR')` returned `'[IBAN]'` — the trailing
` EUR` was silently dropped.

**Root cause:** After integrating C, `detect_all` collected both an IBAN span at `0:16`
and a REGON candidate at `2:16` (substring of the same bytes). The D-branch containment
guard was PESEL-only and did not suppress the REGON child. At render time, the surviving
REGON span's end-position 16 advanced the cursor to the same position as the IBAN end,
consuming the space before `EUR` and causing the trailing token to be dropped.

**Fix location:** `src/piitier/rules/__init__.py` — `detect_all()`. The containment predicate
was changed from `span.kind == "PESEL"` to any non-IBAN kind (i.e. `span.kind != "IBAN"`),
so REGON, NIP, NR_DOWODU, and NR_KARTY candidates wholly nested inside an IBAN span are all
suppressed before the span list is returned. No changes to the renderer, mask module, or any
fusion subsystem. Valid and suspect outer-span status and regression tests are unaffected.

**Regression coverage:** `test_regression_contiguous_be68_stops_before_prose` and
`test_regression_contiguous_at61_stops_before_prose` confirm IBAN outer spans are unaffected;
combined suite re-runs both.

### Full gate results (parent-observed)

| Gate | Result |
|---|---|
| `uv run ruff format .` | PASS |
| `uv run ruff check .` | PASS |
| `uv run mypy src` (13 source files) | PASS |
| `uv run pytest -q` | **295 passed, 0 skipped** |
| LSP registry | OK |
| API smoke (27 cases, parent-observed) | PASS |
| Installed CLI smoke | PASS |
| Six-label CRLF doc (exact mask / no-overlap / fidelity) | PASS |
| Independent 24-UC smoke (`/tmp/piitier-combined-smoke.py`, 133 assertions) | **PASS — exit 0** |

### API smoke — 27 cases (parent-observed)

Parent ran 27 distinct API and installed-CLI smoke cases covering:
- IBAN masking: compact and spaced forms, BE/AT/DE foreign IBANs, trailing-prose
  non-absorption (`BE68539007547034 EUR` → `[IBAN] EUR`), suspect/valid status
- NIP/REGON masking (valid and suspect), KRS non-confusion
- ID-card (`NR_DOWODU`) and payment-card (`NR_KARTY`) masking, Luhn verification
- PESEL suppression inside IBAN (UC-21), REGON/NIP containment inside IBAN (BE68 fix)
- CLI: UTF-8, cp1250, BOM, CRLF, Markdown, CSV, `-o` output file, same-input refusal,
  error-privacy (no PII in stderr)

*A separately prepared 656-line smoke script originally had one incorrect expected NIP prefix.
The corrected version (`/tmp/piitier-combined-smoke.py`) was run by parent and exited 0 with
133 successful assertions and output `PASS -- all assertions satisfied`. Exact NIP prefix,
Markdown and CSV byte output corrected per contract; six-label mixed-CRLF document and exact
span fragments verified. This result is recorded as independent 24-UC evidence alongside the
27 parent-observed API/CLI cases above.*

### Six output labels

All six PII mask labels declared across C/D/E/F are produced with correct spans, status,
and non-overlapping boundaries:
`[IBAN]`, `[PESEL]`, `[NIP]`, `[REGON]`, `[NR_DOWODU]`, `[NR_KARTY]`

CRLF document test verified exact mask text, no span overlap, and full-content fidelity
across all six labels.

### Aggregate added lines

3,133 lines of added code, tests, and configuration across 16 files (excluding specs and
lockfiles), below the hard 5,000-line cap. No soft 480-line per-file waiver exceeded
beyond the three declared paths documented in the integration scope report.

### UC coverage — all 24 use cases

| Feature | UC IDs | Count |
|---|---|---|
| C — NIP / REGON | UC-14, UC-15, UC-16, UC-17, UC-18 | 5 |
| D — IBAN / NRB | UC-19, UC-20, UC-21, UC-38, UC-39 | 5 |
| E — ID-card / payment-card | UC-22, UC-23, UC-24, UC-25, UC-26, UC-27 | 6 |
| F — CLI | UC-28, UC-29, UC-30, UC-33, UC-34, UC-35, UC-40, UC-41 | 8 |
| **Total** | | **24** |

All 24 UCs exercised by automated tests, parent-observed API/CLI smoke (27 cases), and the
independent corrected 24-UC smoke script (133 assertions, exit 0). No LLM training or
inference completion is claimed.

### Known limitation (carried forward)

The generic grouped spaced-IBAN pattern described in the `Limitations` section above applies
unchanged to the integration branch. No per-country IBAN length table was added; this remains
explicitly out of scope per spec §Out.

### Review approvals

| Scope | Review agent | Verdict |
|---|---|---|
| PII-1-c (C — NIP/REGON) | Independent code-reviewer | APPROVED |
| PII-1-d (D — IBAN/NRB) | DfinalReview (code-reviewer) | APPROVED |
| PII-1-e (E — ID-card/payment-card) | Independent code-reviewer | APPROVED |
| PII-1-f (F — CLI) | Independent code-reviewer | APPROVED |
| Combined integration (`ai/pii-1-integration`) | IntegrationReview (code-reviewer) | APPROVED |
