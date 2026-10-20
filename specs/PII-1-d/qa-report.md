# QA Report — PII-1-d

**Verdict: GAPS (2 blocking findings, 1 minor)**

## UC Coverage

| UC | Requirement | Test | Status | Notes |
|-------|---|---|---|---|
| UC-19 | 4 PL IBAN/NRB forms → `[IBAN]`, span covers whole value | `test_uc19_pl_iban_with_prefix_spaced`, `test_uc19_pl_iban_with_prefix_compact` (boundary+), `test_uc19_nrb_bare_spaced` (boundary+), `test_uc19_nrb_bare_compact` (boundary+) | ✅ Automated | All 4 forms tested with boundary assertions |
| UC-20 | `PL…2875` fails mod 97 → `suspect` | `test_uc20_invalid_checksum_status_suspect`, `test_uc20_suspect_span_never_dropped` | ✅ Automated | — |
| UC-21 | 1 spaced IBAN + 1 contiguous IBAN + 1 PESEL → 3 non-overlapping spans | `test_uc21_iban_and_pesel_no_overlap` (rewritten) | ✅ Automated (non-overlapping case) | Test passes when PESEL doesn't naturally overlap; **blocking finding when PESEL overlaps** |
| UC-38 | DE IBAN (valid) → `[IBAN]` `status="valid"` | `test_uc38_de_iban_spaced_valid`, `test_uc38_de_iban_compact_valid` | ✅ Automated | — |
| UC-39 | DE IBAN (fails mod 97) → `status="suspect"` | `test_uc39_de_iban_invalid_checksum` | ✅ Automated | — |

## Test Suite Output

```
uv run pytest -q -m "not integration"
1 failed, 148 passed, 1 deselected (1.10s)
```

### By file
- `tests/rules/test_iban.py`: 34 passed
- `tests/test_render.py`: 1 failed (UC-13), 78 passed (includes other UC tests)
- Other: 36 passed

## Findings

### 1. [**BLOCKING**] UC-13 regression: overlapping spans break render.mask()
- **Location:** `tests/test_render.py::test_uc13_fidelity_mask_outside_spans_unchanged`
- **Failing case:** `'AA01010100005AA'`
- **Issue:** Foreign IBAN detector matches `AA01010100005AA` (2 letters + 2 digits + 13 chars, fails mod 97 → suspect). PESEL detector matches `01010100005` (valid PESEL) inside it. `piitier.detect()` returns overlapping spans:
  - `Span(start=0, end=15, label='[IBAN]', status='suspect')`
  - `Span(start=2, end=13, label='[PESEL]', status='valid')`
- **Why it fails:** `render.mask()` assumes non-overlapping spans; overlapping input causes corruption: input `'AA01010100005AA'` → output `'[IBAN]'` (AA guards destroyed).
- **Spec requirement violated:** UC-21 explicitly states "none overlapping; no PESEL span inside either IBAN"
- **Root cause:** No overlap resolution in `piitier.detect()` (currently just concatenates and sorts spans from all detectors). Spec acknowledges this is future work ("Fusion is a later pipeline ticket") **but UC-21 requires it anyway.**
- **Status:** Blocking—this test passed on main; the branch breaks UC-13.

### 2. [**BLOCKING**] UC-21 acceptance criterion contradicts spec's "Out:" section
- **Location:** Spec `In:` / `Out:` sections vs UC-21 row
- **Issue:** UC-21 requires non-overlapping spans ("none overlapping; no PESEL span inside either IBAN"). The `Out:` section says "Overlap resolution between detector types beyond what UC-21 states" is future work, implying UC-21's requirement is in scope. But the current implementation does no overlap resolution at all, and Finding 1 shows a case where this breaks UC-13.
- **Clarification needed:** Should UC-21 be downgraded to "when inputs don't naturally overlap" (current behavior), or should overlap resolution be implemented?
- **Test written:** `test_uc21_iban_and_pesel_no_overlap` (added) passes when PESEL doesn't naturally overlap; reveals Finding 1 when it does.
- **Status:** Blocking—spec and implementation don't align on the overlap requirement.

### 3. [minor] UC-19 marked "integration" in spec, but tests are unit tests with no `@pytest.mark.integration`
- **Location:** `specs/PII-1-d/spec.md`, line 54; `tests/rules/test_iban.py`, lines 42-73
- **Issue:** Spec table lists UC-19 as `integration` (last column). Tests use `find()` directly (unit level); none carry `@pytest.mark.integration`. Integration suite runs only 1 UC-1 test.
- **Fix applied:** Boundary assertions added to UC-19 tests (new assertions at lines 57-58, 66-67, 75-76) cover the "span covers whole value" requirement. Tests remain unit-level.
- **Resolution:** Either move UC-19 tests to integration (mark + move to integration suite) OR update spec table to `unit`. No blocker—tests pass, requirement verified.

## Not Verified

- **UC-19 runtime integration:** Spec marks UC-19 as integration test, but no integration harness runs it. Tests are unit-level (call `find()` on isolated strings). Verified by unit tests only.
- **UC-21 overlap resolution:** Only tested when PESEL doesn't naturally overlap. When PESEL and IBAN patterns naturally overlap (as in UC-13 case), tests reveal the regression but don't exercise the full overlap-filtering logic (which doesn't exist yet).
- **Verification map:** `none` per .claude/sdlc.md; no runtime harness (Gradio Space not deployed yet).

## Actions Required

**Blocking:** Findings 1 and 2 must be resolved before `PASS` verdict:
- Either implement overlap resolution (`piitier.detect()` must filter overlapping spans to satisfy UC-21), OR
- Downgrade UC-21 to allow overlapping spans and update spec language, AND fix UC-13 regression by other means (e.g., change IBAN pattern to be more conservative).

**Minor:** Finding 3 (UC-19 integration mark) can be waived if scope permits test-only verification.
