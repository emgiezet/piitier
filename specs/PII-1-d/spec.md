---
ticket: PII-1-d
title: Mask IBAN and Polish NRB account numbers
status: approved
stacks: [python]
depends-on: PII-1-b
---

# PII-1-d — Mask IBAN and Polish NRB account numbers

## Problem

Bank account numbers turn up in the invoices and policies the author anonymises by hand
[EVIDENCE: session reply, specs/briefs/polish-pii-anonymizer.md], and they are a high-risk finance
identifier [EVIDENCE: docs/Plan MVP … medtech.md, section 6]. `piitier.mask()` does not detect them.

## Scope

In:
- IBAN PL validator (mod 97) and detector. Accepted forms: `PL` + 26 digits, or a bare 26-digit NRB,
  either contiguous or as `CC NNNN NNNN NNNN NNNN NNNN NNNN` with single spaces. The span covers the
  whole value, prefix and spaces included.
- A 26-digit value that fails mod 97 is detected as `status="suspect"`: 26 digits is distinctive
  enough that no keyword is needed (CLAUDE.md invariant 6).
- Foreign IBANs, matching what `trasti/complaint-classifier/scripts/scan_pii.py` already handles (rule
  `RACHUNEK`, line 91): 2 letters + 2 digits + 11–30 alphanumerics, contiguous or in groups of 4 separated
  by single spaces (the last group 1–4). They are validated with the same generic mod 97 and masked as `[IBAN]`.
- Registered with no API change.

Out:
- A per-country IBAN length table. Status comes from mod 97 alone.
- `[NR_RACHUNKU]`: account numbers in non-IBAN formats.
- PESEL/NIP/REGON/ID-card/payment-card detectors and the CLI (PII-1-b, -c, -e, -f).
- Overlap resolution between detector types beyond what UC-21 states. Fusion is a later pipeline ticket.

Change budget: 240 added lines, 3 files, 2 modules

## Context

- `src/piitier/rules/__init__.py` and `src/piitier/rules/pesel.py`, from PII-1-b.
- `.claude/playbooks/rule-detector.md`.
- mod 97: move the 2 country letters + 2 check digits to the end, map letters A=10 … Z=35, and the
  integer mod 97 must equal 1. A bare NRB is checked as `PL` + NRB.
- Prior art: `tests/test_scan_pii.py::test_polish_identifiers_with_and_without_checksums` (line 393, the
  `DE89 3704 0044 0532 0130 00` case). Read it for behaviour. Do not copy code from that repository.
- New: `src/piitier/rules/iban.py`, `tests/rules/test_iban.py`; edit `src/piitier/rules/__init__.py`.

## Acceptance criteria

All example numbers are synthetic or public sample values.

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-19 | developer | `mask` on each of `PL61109010140000071219812874`, `PL61 1090 1014 0000 0712 1981 2874`, `61109010140000071219812874`, `61 1090 1014 0000 0712 1981 2874` | each becomes exactly `[IBAN]`; one span, `status="valid"`, covering prefix and spaces | integration |
| UC-20 | developer | `mask` on `PL61109010140000071219812875` (fails mod 97) | `[IBAN]`; `status="suspect"` | unit |
| UC-21 | developer | `detect` on text containing one spaced IBAN, one contiguous IBAN and one PESEL | exactly three spans, one per value, sorted by `start`, none overlapping; no PESEL span inside either IBAN *(added)* | integration |
| UC-38 | developer | `mask` on `DE89 3704 0044 0532 0130 00` and `DE89370400440532013000` | each becomes exactly `[IBAN]`; `status="valid"` *(added from prior art)* | unit |
| UC-39 | developer | `mask` on `DE89 3704 0044 0532 0130 01` (fails mod 97) | `[IBAN]`; `status="suspect"` | unit |

## Open questions

none
