# Decomposition — PII-1

Source: `specs/briefs/polish-pii-anonymizer.md` (Decisions, third bullet), refined against the author's
prior script `scan_pii.py` (private). No `PII-1/spec.md`
was ever written; this plan replaces it.

Estimate: ~2200 added lines (≈ 400 of them `uv.lock`) · ~32 files · ~12 modules (budget 400/15/3)
Seam: walking skeleton. `-a` lays the typed core and `-b` is the thinnest working path
(`piitier.mask()` on one identifier). `-c`…`-e` widen detection, `-f` puts the CLI on top, and `-g` adds PDF input.

| Slice | Outcome a user or operator can see | UCs | Budget | Depends on |
|---|---|---|---|---|
| `PII-1-a` | `uv sync` installs `piitier`; `docs/TAXONOMY.md` and the `Label` enum agree, enforced by a test | UC-1…UC-6 | 610 lines (380 lockfile) | — |
| `PII-1-b` | `piitier.mask(text)` replaces PESEL (spaced or not) with `[PESEL]`; text outside spans is byte-identical | UC-7…UC-13, UC-36, UC-37 | 360 lines | `-a` |
| `PII-1-c` | NIP and REGON masked, formatted and keyword-labelled variants included | UC-14…UC-18 | 330 lines | `-b` |
| `PII-1-d` | IBAN (PL and foreign) and bare NRB masked | UC-19…UC-21, UC-38, UC-39 | 240 lines | `-b` |
| `PII-1-e` | ID-card numbers and payment-card numbers masked | UC-22…UC-27 | 270 lines | `-b` |
| `PII-1-f` | `piitier mask <file>` on `.txt`, `.md`, `.csv` (UTF-8 or cp1250): the "no sixth script" outcome | UC-28…UC-30, UC-33…UC-35, UC-40, UC-41 | 260 lines | `-b` |
| `PII-1-g` | `piitier mask <file>.pdf` for text-layer PDFs | UC-31, UC-32, UC-42 | 200 lines | `-f` |

Order: -a → -b → (-c, -d, -e, -f in any order) → -g after -f. Each merges on its own.
Once `-f` is merged, the CLI already replaces the author's text-format scripts for PESEL. Every
detector slice merged later widens it with no CLI change.

Not sliced out: the `Label` enum and `docs/TAXONOMY.md` stay together in `-a`, because the sync test
that keeps them identical is meaningless with only one side. Validators and their detectors stay together
per identifier, because a validator nobody calls ships nothing.

Candidate rule (from prior art, `scan_pii.py` line 73): candidates are found by **shape**, and the
checksum decides only `status`. A keyword is required only where the bare shape is mostly something
else: REGON-9 (phone numbers). Explicit exclusions: a `+`/`00` phone is never a PESEL, and a `KRS`
number is never a NIP.

Harness note: `uv.lock` is not in `aisdlc`'s `_SIZE_EXCLUDE`, so it counts as added lines. `-a`
declares it in its own budget line. `-g` adds ~20 lockfile lines for `pypdf`.
