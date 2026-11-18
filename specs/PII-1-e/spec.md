---
ticket: PII-1-e
title: Mask ID-card numbers and payment-card numbers
status: approved
stacks: [python]
depends-on: PII-1-b
---

# PII-1-e — Mask ID-card numbers and payment-card numbers

## Problem

Claim reports and customer correspondence carry ID-card numbers and payment-card numbers
[EVIDENCE: docs/Plan MVP … medtech.md, section 4 taxonomy table]. The author's current scripts mask them
case by case [EVIDENCE: session reply, specs/briefs/polish-pii-anonymizer.md]. `piitier.mask()` does not
detect either.

## Scope

In:
- ID-card (dowód osobisty) validator and detector. Any 3 **uppercase** letters + optional single space
  + 6 digits is a candidate by shape, with no keyword needed. The 4th character is the check digit.
- Payment-card validator (Luhn) and detector. 16 digits, contiguous or in 4 groups of 4 separated by
  single spaces or dashes, are a candidate by shape. Contiguous runs of 13–15 or 17–19 digits are a
  candidate only when they pass Luhn. The span covers the separators.
- The checksum decides only `status`: `"valid"` or `"suspect"`. A failed checksum never removes a
  candidate (CLAUDE.md invariant 6).
- Shape rules are carried over from an earlier private script `scan_pii.py`: rules `DOWOD`
  (line 101) and `KARTA` (line 104).
- Registered with no API change.

Out:
- Passports, driving licences, CVV, expiry dates: later taxonomy work.
- Card brand detection (BIN ranges).
- Lowercase ID-card numbers (`aba300000`). Prior art requires uppercase too.
- Other detectors and the CLI (PII-1-b, -c, -d, -f).

Change budget: 270 added lines, 5 files, 2 modules

## Context

- `src/piitier/rules/__init__.py` and `src/piitier/rules/pesel.py`, from PII-1-b.
- `.claude/playbooks/rule-detector.md`.
- ID card: letters map A=10 … Z=35. Weights 7,3,1 on the letters and 7,3,1,7,3 on digits 5–9.
  Check digit = weighted sum mod 10, stored at position 4.
- New: `src/piitier/rules/id_card.py`, `src/piitier/rules/payment_card.py`,
  `tests/rules/test_id_card.py`, `tests/rules/test_payment_card.py`; edit `src/piitier/rules/__init__.py`.
- Prior art: `scan_pii.py` lines cited under Scope. Read them for behaviour. Do not copy code from that repository.

## Acceptance criteria

All example numbers are synthetic or public test values.

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-22 | developer | `mask` on each of `ABA300000`, `ABA 300000`, `XYZ712345` | each becomes `[NR_DOWODU]`; `status="valid"` | integration |
| UC-23 | developer | `mask("nr ABA400000")` (wrong check digit, no keyword) | `"nr [NR_DOWODU]"`; `status="suspect"` | unit |
| UC-24 | developer | `mask` on each of `4111111111111111`, `4111 1111 1111 1111`, `4111-1111-1111-1111` | each becomes `[NR_KARTY]`; `status="valid"` | integration |
| UC-25 | developer | `mask("4111 1111 1111 1112")` (16 digits, fails Luhn, no keyword) | `"[NR_KARTY]"`; `status="suspect"` | unit |
| UC-26 | developer | `detect` on `aba300000`, `ABCD300000` and `ABA3000001` | no `NR_DOWODU` span for any of them (lowercase, 4 letters, 7 digits) *(added)* | unit |
| UC-27 | developer | `detect` on a Luhn-valid 12-digit run, a Luhn-valid 20-digit run, a Luhn-invalid 15-digit run, and the PESEL `90051512340` | no `NR_KARTY` span for any of them; the PESEL is still detected as `PESEL` only *(added)* | unit |

## Open questions

none
