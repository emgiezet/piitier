---
ticket: PII-33
title: Preserve surrounding text when rule detections overlap
kind: bugfix
status: draft
stacks: [python]
---

# PII-33 — Preserve surrounding text when rule detections overlap

## Problem

Rules-only masking can replace the same original-input range twice when REGON-14 and
payment-card detectors both match it. The second replacement uses stale offsets and deletes
following text, violating text fidelity in the public API, CSV masking, CLI and batch output.
Direct renderer callers can encounter the same loss with identical or partially overlapping spans.

## Scope

In:
- Resolve overlapping renderer inputs with the existing fusion precedence and full coverage.
- Preserve every character outside the union of supplied original-input spans.
- Regression coverage for public masking, CSV selection, CLI, batch and direct rendering.
- Inspect the TUI comparison/export span sources without changing the TUI implementation.

Out:
- Detector patterns, checksum rules, recall, public `detect` semantics and fusion precedence.
- Changes to CLI/TUI source files, dependencies, lockfiles or the changelog.
- New numbering or coreference policy for fragmented overlapping entities.

Change budget: 350 added lines, 3 files, 3 modules

## Context

- `src/piitier/rules/__init__.py::detect_all`, `src/piitier/__init__.py::detect`, `::mask`,
  `::mask_csv`: combined rule detections can overlap; detection remains unchanged.
- `src/piitier/render.py::mask`: common replacement boundary for rules-only API/CSV and export.
- `src/piitier/fusion.py::fuse`, `::_priority_key`: existing priority and coverage contract.
- `src/piitier/cli.py::mask_file`, `src/piitier/batch.py::mask_batch`: rules-only entrypoints.
- `src/piitier/tui.py::CsvSelectionScreen.on_button_pressed`,
  `::AnonymizationDiffApp.on_button_pressed`, `::compare_file`: CSV selection/export flow.
- `tests/test_render.py`, `tests/test_tui.py`, `.claude/playbooks/pipeline-core.md`.
- Decision: resolve overlaps at the renderer boundary using `fusion.fuse` only when the sorted
  input overlaps. This covers every rendering caller without changing detector results, copying
  fusion's priority rules or running another event sweep for already-disjoint inputs. Fusing only
  in public masking wrappers would leave direct renderer/TUI callers exposed; fusing inside
  `detect_all` would unnecessarily change the detection API.
- TUI reachability: the shipped `compare` command requires a model and passes fused
  `Anonymizer.detect` results. Direct `AnonymizationDiffApp(..., detector=piitier.detect)` CSV
  selection (already used by tests) passes unfused detections to the export renderer at line 383.
- Numbering decision: each fused fragment uses its own `(start, end)` key from `numbering`.
  A fragment without an exact key retains the existing template fallback (`[OSOBA_n]`, etc.);
  no index is inferred from its parent span. Shipped `Anonymizer` paths fuse before numbering.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-250 | library caller | Mask the allow-listed 14-digit collision in surrounding text | `Nr 30569309025904 KONIEC.` becomes `Nr [NR_KARTY] KONIEC.`; `100;30569309025904;200` becomes `100;[NR_KARTY];200` | unit |
| UC-251 | CLI caller | Run rules-only `mask` on the reported sentence | Exit 0 and exact stdout `Nr [NR_KARTY] KONIEC.` | integration |
| UC-252 | CSV caller | Mask a collision row with no skipped columns, an unrelated skipped column or the identifier column skipped | Non-identifier bytes remain identical; identifier becomes `[NR_KARTY]` unless its column is explicitly protected | unit |
| UC-253 | library caller | Mask random digit runs of every length 8–26 embedded in Unicode text | Exactly zero changed UTF-8 bytes outside the union of detected spans, including known collision examples | unit |
| UC-254 | renderer caller | Render two identical-range rule spans in either input order | Exactly one placeholder chosen by existing fusion precedence; all surrounding text preserved | unit |
| UC-255 | renderer caller | Render partial, nested, adjacent or disjoint spans | Entire covered union masked, no surrounding or intervening character changed, precedence identical to fusion | unit |
| UC-256 | batch caller | Run rules-only batch masking on collision-containing text and CSV files | Exit 0 and exact output files preserving suffixes and delimiters | integration |
| UC-257 | TUI caller | Select CSV columns and export with the rules-only detector callback | Exported bytes contain one winning placeholder per collision and preserve trailing cells, CRLFs and source bytes | integration |
| UC-258 | renderer caller | Render overlapping numbered spans with an original-range index | Fragments with an exact `numbering` key use that index; fragments absent from the mapping use their template placeholder; disjoint mapped spans retain their assigned index | unit |
| UC-259 | renderer caller | Render two same-range spans whose fusion priority is exactly equal (both suspect, same risk weight), in either input order, repeatedly | The first input span wins every time; the result never depends on object identity. For the rule detectors this means registry order (REGON before NR_KARTY) | unit |

## Non-functional

- Original-input half-open offsets and detector provenance remain unchanged.
- No new dependencies; reuse the existing fusion priority rather than defining a second order.
- Already non-overlapping spans retain the existing rendering and numbering behavior.
- All existing tests remain unmodified; synthetic fixtures only.

## Open questions

None. Human approval remains required before an unattended SDLC implementation run.
