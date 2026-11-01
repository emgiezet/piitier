---
ticket: PII-21-b
title: Live JSON jq selection preview and fidelity-preserving TUI export
status: approved
stacks: [python]
depends-on: PII-21-a
issue: https://github.com/emgiezet/piitier/issues/21
---

# PII-21-b — Live JSON field selection and export

## Problem

The existing JSON comparison opens immediately without a field-selection screen or JSON export. Users cannot see which original values are excluded before anonymization or save the result with original encoding and layout.

## Scope

In:
- JSON selection before existing comparison: original source left, scrollable jq-path checkboxes right, `Anonimizuj` button below. Checked means skip. Start with none skipped.
- Concrete indexed paths and deduplicated array-wildcard paths; canonical quoting for non-identifier keys. JSON keys and selector labels render literally, never as Rich markup.
- Every toggle immediately highlights/unhighlights only all matching original value ranges, including array matches; source text unchanged. Overlapping selections remain highlighted until all matching selections are cleared.
- `Anonimizuj` routes selected fields through slice a, then displays the existing before/after panes, numbering and arrow navigation. Numeric PII blocks transition/export even if selected to skip; show a safe error on the selection screen.
- JSON export beside source, default `<stem>_anonymised.json`, editable basename, exclusive creation; no source/existing/dangling-symlink overwrite. Preserve source encoding, BOM, key order, whitespace, line endings, skipped raw serialization. Remove only a newly created partial output on write failure.
- `compare --model` remains mandatory. Malformed JSON never opens selection/comparison. PDF/password and CSV flows remain unchanged.

Out:
- New viewers/commands, arbitrary jq execution, JSONL/NDJSON, key masking, numeric conversion, new dependencies, changes to CSV/PDF UX or model/training/benchmark work, pushes or PR creation.

Change budget: 600 added lines, 5 files, 3 modules; repository standing soft-line-budget policy applies, hard ceiling remains 5000.

## Context

- Issue #21 and approved slice a define supported jq paths and numeric safety. Preserve issue UC IDs.
- Worktree `/home/mgz/workspace/.aisdlc-worktrees/piitier-json`, branch `ai/PII-21-jq-json`; never edit the draft-authoring checkout.
- `src/piitier/tui.py`: `CsvSelectionScreen`, `AnonymizationDiffApp`, `compare_file`, `build_diff`; reuse rendering/export and model initialization conventions.
- Consume shared source ranges/path projection helpers from `src/piitier/jsonmask.py`; do not introduce a second JSON parser or selector grammar.
- Tests `tests/test_tui.py` and `tests/test_jsonmask.py`; existing `asyncio.run` + Textual Pilot pattern, no pytest-asyncio dependency.
- Source encoding detection belongs to existing JSON loader/output helpers from slice a; exported text is rendered once from accepted spans and numbering.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|---|---|---|---|---|
| UC-176 | TUI user | Toggle jq-path checkboxes before anonymizing | Original source remains exact; all and only matching values gain/lose skipped styling live, including arrays; keys/other values not marked; labels literal; selection list scrolls | e2e |
| UC-177 | TUI user | Select several paths and press Anonimizuj | Existing comparison displays exact preserved selected values and masked remaining PII; arrows navigate changes; detectable numeric PII blocks transition/export with no value disclosure | e2e |
| UC-178 | TUI user | Export default/edited basename with UTF-8/BOM/cp1250 and existing/source targets | Correct sibling file/bytes, encoding/BOM/CRLF/raw skipped values preserved; source/existing/symlink targets unchanged; no partial file on failure | e2e |

## Non-functional

- Actual checkbox events and rendered preview ranges must be exercised, not only helper forwarding or widget existence. Deterministic synthetic fixtures only.
- Keep document/selector data out of errors/logs. Preserve Ctrl-C/cancel, CSV selection/export, authenticated PDF comparison behavior.
- Run targeted TUI/JSON tests, full offline suite, formatting/lint/types. Smoke the actual terminal: toggle wildcard/index/quoted-key fields, observe highlighted values, anonymize, navigate, export; prove numeric blocking and original-byte fidelity. Use discovered local checkpoint; no network required.
- Update existing README/changelog only after behavior is verified. All temporary fixtures/scripts removed.

## Open questions

None.
