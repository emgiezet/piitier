---
ticket: PII-1-c
title: Mask NIP and REGON numbers
status: approved
stacks: [python]
depends-on: PII-1-b
---

# PII-1-c — Mask NIP and REGON numbers

## Problem

Invoices and insurance policies, two of the formats the author has scripted by hand, carry NIP
and REGON numbers [EVIDENCE: session reply, specs/briefs/polish-pii-anonymizer.md]. A sole trader's NIP
identifies a person. `piitier.mask()` from PII-1-b does not detect either number.

## Scope

In:
- NIP validator and detector. Candidates by shape, with no keyword needed: 10 contiguous digits, or
  grouped `XXX-XXX-XX-XX` / `XXX-XX-XX-XXX`, optional `PL` prefix. After the keyword `NIP` or `VAT ID`
  (case-insensitive), any single space/tab/dash separators are also accepted. The span covers the
  prefix and the separators, never the keyword.
- REGON validator and detector. 14 contiguous digits are a candidate by shape. A 9-digit REGON is a
  candidate **only** after the keyword `REGON`, because a bare 9-digit run is usually a phone number.
- The checksum decides only `status`: `"valid"` or `"suspect"`. A failed checksum never removes a
  candidate (CLAUDE.md invariant 6).
- A 10-digit run preceded by the keyword `KRS` within 40 characters is not a NIP candidate.
- Both registered so `piitier.detect()` and `piitier.mask()` pick them up with no API change.
- Candidate rules are carried over from `trasti/complaint-classifier/scripts/scan_pii.py`: rules `NIP`
  and `REGON` at lines 99–100 and 113–114, and the KRS exclusion at lines 332–341.

Out:
- PESEL (PII-1-b, unchanged), IBAN (PII-1-d), ID card and payment card (PII-1-e), CLI (PII-1-f).
- Telling a company NIP from a sole-trader NIP. Every NIP is masked as `[NIP]`.
- Lookups against GUS/BIR or any network call.
- Any change to `Label`, `Span`, `render.py`, or the PESEL detector.
- KRS detection as its own type. KRS is not in `docs/TAXONOMY.md`; this slice only stops it becoming a NIP.

Change budget: 330 added lines, 5 files, 2 modules

## Context

- `src/piitier/rules/__init__.py` (registry) and `src/piitier/rules/pesel.py` (sibling to mirror), from PII-1-b.
- `.claude/playbooks/rule-detector.md`.
- NIP: weights 6,5,7,2,3,4,5,6,7; check = sum mod 11; a result of 10 is never valid.
- REGON-9: weights 8,9,2,3,4,5,6,7; REGON-14: weights 2,4,8,5,0,9,7,3,6,1,2,4,8; check = sum mod 11,
  where 10 → 0.
- New: `src/piitier/rules/nip.py`, `src/piitier/rules/regon.py`, `tests/rules/test_nip.py`,
  `tests/rules/test_regon.py`; edit `src/piitier/rules/__init__.py`.
- Prior art: `scan_pii.py` lines cited under Scope, and
  `tests/test_scan_pii.py::test_polish_identifiers_with_and_without_checksums` (line 393).
  Read them for behaviour. Do not copy code from that repository.

## Acceptance criteria

All example numbers are synthetic, computed for this spec.

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-14 | developer | `mask` on each of `5260001246`, `526-000-12-46`, `526-00-01-246`, `PL5260001246`, `NIP: 526 000 12 46` | each value becomes `[NIP]` (`NIP: ` stays); span `status="valid"`; the span covers the prefix and separators | integration |
| UC-15 | developer | `mask("nr zamówienia 5260001247")` (10 digits, wrong check digit, no keyword) | `"nr zamówienia [NIP]"`; span `status="suspect"` | unit |
| UC-16 | developer | `mask` on `REGON: 123456785` (REGON-9) and on bare `12345678000012` (REGON-14) | each value becomes `[REGON]`; `status="valid"` | integration |
| UC-17 | developer | `mask` on `REGON 123456786` and bare `12345678000013` (wrong check digits) | each value becomes `[REGON]`; `status="suspect"` | unit |
| UC-18 | developer | `detect` on bare `123456785` and `tel. 600123457` (9 digits, no `REGON` keyword), and on `KRS 0000123456` | no `REGON` span for either 9-digit run; no `NIP` span for the KRS number *(added from prior art)* | unit |

## Open questions

none
