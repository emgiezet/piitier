---
ticket: PII-30
title: Restore payment-card recall at field delimiters and OCR-glued words
kind: bugfix
status: draft
stacks: [python]
---

# PII-30 — Payment-card context boundaries

## Problem

The boundary guards introduced in d4ee335 suppress real payment cards beside commas and
OCR-glued words. This leaks both checksum-valid cards and checksum-invalid 16-digit card
shapes through `mask` and comma-delimited `mask_csv`.

## Scope

In:
- Restore delimiter-adjacent and non-hex word-adjacent card detection, preserving exact offsets.
- Retain checksum-invalid 16-digit candidates as `suspect`; mark ambiguous comma-numeric
  and word-glued contexts `suspect` even when the checksum passes.
- Keep narrowly defined decimal and hexadecimal false-positive suppression.
- Add regression tests through the detector and public masking APIs.

Out:
- Other detectors, CSV parsing, rendering, Luhn validation, dependencies and allowlist changes.
- Changing the existing Luhn-only eligibility of contiguous 13–15 and 17–19 digit candidates.
- Changelog edits, commits and release operations.

Change budget: 280 added lines, 3 files, 3 modules

## Context

- `src/piitier/rules/payment_card.py::_CARD_16_RE`, `::_CARD_LONG_RE`, `::find`.
- `tests/rules/test_payment_card.py` existing checksum, boundary and masking coverage.
- `src/piitier/__init__.py::mask`, `::mask_csv` exercise the registered detector end to end.
- `.claude/playbooks/rule-detector.md`, `docs/TAXONOMY.md` (`NR_KARTY`).
- Depends on PII-33, already on this branch: public masking fuses overlapping REGON/card
  spans before rendering. Exact-priority ties use detector input order, so REGON wins over
  payment cards when both are suspect on the same range; valid spans still beat suspect
  spans. This fix does not change fusion.
- Only an ungrouped run immediately beside a digit-separated dot is suppressed as a decimal
  fragment (`digit + '.' + candidate` or `candidate + '.' + digit`). Grouped cards are not
  decimal fragments. Commas are ambiguous CSV delimiters/decimal punctuation and therefore
  never suppress a candidate; a comma immediately connecting it to another digit means
  `suspect` rather than a dropped span.
- Only an ungrouped run embedded in a complete alphanumeric token consisting exclusively
  of ASCII hexadecimal characters (optionally prefixed with `0x`/`0X`), with at least one
  adjacent letter, is suppressed as a hex token. This includes one-sided `abc` prefixes and
  two-sided `cc...ff`; non-hex words, including Polish letters and suffixes, instead make
  the candidate `suspect`.
- These exclusions prevent decimal report metrics and hexadecimal hashes from becoming
  cards. Digit-boundary guards still prevent extracting a card from a longer digit run.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-218 | text caller | Mask `Jan,4111111111111111,100` and delimiter variants | Exactly the card becomes `[NR_KARTY]`; surrounding fields and delimiters are unchanged | integration |
| UC-219 | text caller | Find and mask `100,4111111111111112,200` | Exactly one card span, exact offsets, `status='suspect'`; masking produces `100,[NR_KARTY],200` | integration |
| UC-220 | OCR caller | Find and mask a valid or invalid 16-digit card glued to a non-hex word on either side | Exactly the card is found as `suspect` and replaced; words remain unchanged, including `karta4111111111111111 wydana` | integration |
| UC-221 | CSV caller | Mask comma-delimited CSV containing valid or invalid 16-digit cards and the synthetic 14-digit card `30569309025904` | Header, commas, neighboring cells and line endings remain unchanged; 16-digit card cells become `[NR_KARTY]`, and the overlapping 14-digit value becomes `[REGON]` through fusion | integration |
| UC-222 | text caller | Find and mask space/dash-grouped valid or invalid cards next to numeric comma fields | One exact span including card separators, `suspect`, masked without touching field delimiters | integration |
| UC-223 | report caller | Find and mask dot-decimal fragments, including `0.9937050359712231` and report floats | No card spans and unchanged masked text; a trailing sentence period and grouped cards next to dots remain detectable | integration |
| UC-224 | hash caller | Find and detect complete hex tokens, including `cc4111111111111111ff` and a one-sided hex prefix | No `NR_KARTY` spans; non-hex alphanumeric context is not silently dropped (other detectors, including IBAN, are outside this criterion) | integration |
| UC-225 | text caller | Find and mask supported 14/15-digit Luhn-valid cards beside commas or non-hex words | One exact card span, `suspect` in ambiguous contexts; public masking replaces only the number using fusion's winning label (`[REGON]` for comma-adjacent and word-glued `30569309025904`, `[NR_KARTY]` for the 15-digit card); existing invalid-length eligibility is unchanged | integration |

## Non-functional

- Text outside detected half-open spans must be byte-for-byte unchanged.
- Existing tests are retained; the non-hex `xyz` suffix in the existing hex-suffix test is
  corrected to `ff` with its zero-span assertion unchanged, as explicitly authorized.
- Full non-integration pytest, Ruff formatting/lint, mypy and all-files pre-commit must pass,
  including scanning tracked float-heavy reports with no allowlist additions.
- PII-33 overlap resolution is a prerequisite for the 14-digit public-mask and CSV
  regressions; both are tested end to end with exact surrounding-text preservation.

## Open questions

None.
