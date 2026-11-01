---
ticket: PII-21-a
title: JSON jq path selection, public API and numeric PII rejection
status: approved
stacks: [python]
issue: https://github.com/emgiezet/piitier/issues/21
---

# PII-21-a — JSON path selection and fail-closed masking

## Problem

Existing JSON masking handles decoded string values but provides no field selection or public `piitier.mask_json` API. Numeric PII is currently left visible without an error. Operators need jq-style field exclusions without changing JSON syntax, formatting or numeric types.

## Scope

In:
- Repeated `mask --skip-fields PATH`, public `piitier.mask_json(text, skip_fields=..., ...)` and model-enabled JSON masking with document-local numbering.
- jq path projections: dotted identifiers, JSON-quoted key segments (including commas, spaces, dots and escapes), nonnegative integer array indices and `[]` wildcards, including root arrays/scalars. No comma splitting of CLI arguments.
- A selected object/array protects all descendant string values; numeric safety validation still applies everywhere, even inside skipped subtrees. Duplicate object keys remain serialized and all matching occurrences are handled.
- Numeric tokens are passed to the applicable detector independently; any detected PII raises a safe `ValueError`-derived error. Do not convert numbers or leak their contents.
- Unknown selectors produce a content-free warning while other values continue; unsupported syntax is a safe input error before output/model work.
- Source-range mapping for decoded string spans, preserving escapes outside replacements, whitespace, key order, line endings, BOM and source encoding (UTF-8, UTF-8 BOM, existing cp1250 fallback). JSON file outputs retain source encoding.
- Existing JSON batch callers consume shared numeric safety automatically; no new batch selection flags.

Out:
- Full jq execution, pipes/functions/filters/expressions/slices/negative indices, JSONL/NDJSON, key masking, numeric type conversion, new dependencies, detector changes, PDF/CSV behavior changes, model/training/benchmark changes, pushes or PR creation.

Change budget: 700 added lines, 10 files, 3 modules; repository standing soft-line-budget policy applies, hard ceiling remains 5000.

## Context

- Issue #21 is the behavioral source of truth. Preserve its UC IDs despite overlaps with historical unrelated tickets.
- Worktree: `/home/mgz/workspace/.aisdlc-worktrees/piitier-json`, branch `ai/PII-21-jq-json`, based on current `origin/release/0.1.0` (`d8bb0a6`). Do not edit the draft-authoring checkout `/home/mgz/workspace/piitier`.
- Existing `src/piitier/jsonmask.py`: `validate_json`, `_source_boundaries`, `detect_json`, `mask_json`.
- Existing `src/piitier/__init__.py`: `mask_csv`, `Anonymizer.detect/assign`; `src/piitier/cli.py`: `mask_file`, `_main`; `src/piitier/loaders.py`: `load_json`; `src/piitier/batch.py`: JSON masking caller.
- Tests: `tests/test_jsonmask.py`, `tests/test_cli.py`, `tests/test_loaders.py`, `tests/test_batch.py`. Historical tests allowing detectable numeric PII must be migrated to the newly required rejection contract while retaining formatting/numbering coverage using safe non-PII numbers.
- Existing shared renderer/coreference must remain the output path; JSON keys never reach detection. Errors/warnings contain categories, not document values or parser excerpts.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|---|---|---|---|---|
| UC-174 | CLI operator | Mask JSON while skipping `.klient.pesel` | Selected value unchanged; other PESEL string becomes `[PESEL]`; valid JSON with exact source formatting outside replacements | e2e |
| UC-175 | API caller | Use `.osoby[].email`, `.osoby[0].email`, quoted keys and repeated selectors | Wildcard selects all matching array values; index selects only the first; punctuation/escaped keys remain exact; no comma splitting; model numbering stays document-local | integration |
| UC-179 | operator/API caller | Mask a detectable numeric token, including a skipped field/subtree | Safe API error or CLI exit 2, no partial/new output, existing output unchanged, no credential/document-value/parser disclosure | integration |
| UC-180 | operator/API caller | Use unmatched selectors or unsupported jq syntax | Unmatched selector warns without leaking content and continues; unsupported syntax fails safely before output; no full jq evaluation | integration |
| UC-181 | operator/API caller | Use malformed JSON or --skip-fields on non-JSON | API rejects malformed JSON; CLI exit 2 with empty stdout and no output mutation; unsupported input options fail before inference | e2e |

## Non-functional

- All fixtures synthetic; no real data, credentials, parser excerpts or document values in diagnostics.
- No reserialization of the full JSON document; modify only mapped detected string spans. Never ignore numeric PII because of skip selection.
- Use existing Python/uv tools and fully typed public symbols. Tests must assert observable outputs and safety, not mock echoes/source text. No skipping/weakening tests for green.
- Run targeted JSON/CLI/loaders/batch tests, full offline suite, formatting/lint/types; execute subprocess API/CLI smoke with BOM/CRLF, quoted/wildcard/index selectors, unknown/invalid paths and numeric rejection.
- Scope completeness requires every listed UC boundary and all dependent callsites; no production fallbacks or placeholders.

## Open questions

None. The restricted jq grammar and supported encodings above are the explicit implementation contract.
