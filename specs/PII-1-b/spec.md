---
ticket: PII-1-b
title: Mask PESEL numbers through piitier.detect() and piitier.mask()
status: approved
stacks: [python]
depends-on: PII-1-a
---

# PII-1-b — Mask PESEL numbers through `piitier.detect()` and `piitier.mask()`

## Problem

Insurance developers fear leaking personal data when they send documents to an external LLM
[EVIDENCE: session reply, specs/briefs/polish-pii-anonymizer.md]. PESEL is the identifier whose leak
matters most, and the author currently strips it with a new script per project [EVIDENCE: session reply].
There is no library call that takes Polish text and returns it with PESEL numbers masked and everything
else untouched.

## Scope

In:
- `piitier.detect(text: str) -> list[Span]`: spans sorted by `start`, non-overlapping.
- `piitier.mask(text: str) -> str`: replaces each detected span with its label's placeholder.
- A PESEL validator and detector, plus the detector registry that `detect()` iterates.
- A checksum or date failure is detected with `status="suspect"` and masked like a valid PESEL
  (CLAUDE.md invariant 6).
- PESEL digits may be separated by single spaces, tabs or dashes; the span covers the separators.
  A run starting with `+` or `00` is a phone number and never a PESEL. Both rules are carried over
  from an earlier private script `scan_pii.py` (rule `PESEL`, line 86; phone exclusion, lines 318–324).

Out:
- NIP/REGON (PII-1-c), IBAN (PII-1-d), ID card and payment card (PII-1-e), the CLI and file loaders (PII-1-f).
- PESEL written in words, in base64, or split across lines (red-teaming variants, a later ticket).
- Phone-number detection as its own type (`[TELEFON]`). This slice only stops `+48…` from becoming a PESEL.
- Placeholder numbering (`[PESEL_1]`); repeated values each become `[PESEL]`. That is coreference, later.
- Unicode normalisation, NER, fusion between detector types, `pseudonymize` mode.
- Any change to `Label`, `Span`, or `docs/TAXONOMY.md` from PII-1-a.

Change budget: 360 added lines, 7 files, 4 modules

## Context

- `src/piitier/spans.py` (`Span`), `src/piitier/labels.py` (`Label.PESEL`, placeholder `[PESEL]`), from PII-1-a.
- `.claude/playbooks/rule-detector.md`: validator first, then detector, then registry; the test grid.
- `.claude/playbooks/pipeline-core.md`: right-to-left replacement and the fidelity property test.
- PESEL rule: weights 1,3,7,9,1,3,7,9,1,3 over digits 1–10, check digit = (10 − sum mod 10) mod 10.
  Month encodes the century (+80 → 1800s, +0 → 1900s, +20 → 2000s, +40 → 2100s, +60 → 2200s), and the
  date must exist.
- New: `src/piitier/rules/__init__.py`, `src/piitier/rules/pesel.py`, `src/piitier/render.py`,
  `tests/rules/test_pesel.py`, `tests/test_render.py`, `tests/test_api.py`; edit `src/piitier/__init__.py`.
- Prior art: an earlier private script `scan_pii.py` (rule `PESEL`, line 86)
  and `tests/test_scan_pii.py::test_phone_not_also_pesel_and_bad_check_digit_not_ignored` (line 50).
  Read them for behaviour. Do not copy code from that repository.

## Acceptance criteria

All example numbers are synthetic, computed for this spec.

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-7 | developer | `piitier.mask("PESEL: 90051512340, tel.")` | returns `"PESEL: [PESEL], tel."` | integration |
| UC-8 | developer | `piitier.detect("PESEL: 90051512340, tel.")` | exactly one span: `start=7, end=18, label=Label.PESEL, source="rule", score=1.0, status="valid"` | integration |
| UC-9 | developer | `mask`/`detect` on `90051512341` (wrong check digit) | masked to `[PESEL]`; span `status="suspect"` | integration |
| UC-10 | developer | `detect` on `90131512341` (checksum correct, month 13 does not exist) | one span, `status="suspect"` *(added)* | unit |
| UC-11 | developer | `detect` on `05250112343` (born 2005-05-01, month+20 encoding) | one span, `status="valid"` *(added)* | unit |
| UC-12 | developer | `detect` on a 10-digit run `9005151234`, a 12-digit run `900515123401`, and `x90051512340y` | no span for the 10- and 12-digit runs; for `x90051512340y` one span covering only the 11 digits: letters do not block a match, digits do *(added)* | unit |
| UC-13 | developer | `mask` on hypothesis-generated Polish text with 0–5 embedded PESELs at random positions, including `""` | every character outside the detected spans is identical, in order, to the input; text with no detections is returned unchanged; `""` returns `""` | unit (property) |
| UC-36 | developer | `mask` on `900 515 123 40`, `9005-1512-340` and `90051 512340` | each becomes exactly `[PESEL]`; the span covers the separators; `status="valid"` | unit |
| UC-37 | developer | `detect` on `Telefon: +48 501 234 567` and `tel. +48501234567` (both 11 digits after `+`) | no `PESEL` span in either *(added from prior art)* | unit |

## Non-functional

- `detect` and `mask` never log, print, or put text or matched values into an exception message.
- Validators are pure functions (`.claude/rules/python.md`).

## Open questions

none
