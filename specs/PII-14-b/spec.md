---
ticket: PII-14-b
title: Filename-password CSV mapping and directory batch anonymisation
status: approved
stacks: [python]
depends-on: PII-14-a
---

# PII-14-b — Filename-password CSV mapping and directory batch anonymisation

## Problem

Operators processing directories must currently invoke anonymisation separately for each file.
Per-document credentials cannot be supplied as a validated mapping, and one unreadable document
must not prevent other documents from being anonymised safely.

## Scope

In:
- `piitier mask-batch INPUT_DIR -o OUTPUT_DIR [--passwords FILE] [--model MODEL]
  [--threshold FLOAT] [--revision REV]`.
- Strict filename/password CSV parsing, deterministic nonrecursive selection, shared secure
  credential entry, one reusable model and non-destructive per-file text outputs.
- Per-file failure isolation, safe diagnostics, counts/exit codes, offline tests and usage docs.

Out:
- Recursive traversal, parallel batch processing, path-precedence mapping or credential caching.
- Batch CSV column-selection/delimiter flags, batch TUI, new comparison interface or PDF output.
- OCR, detector changes, credential persistence, alternate encodings for password maps, real
  secrets/maps in the repository, CI, benchmarks, corpora/checkpoints or tracker mutations.

Change budget: 400 added lines, 8 files, 3 modules.

This is a review estimate, not a waiver of `.claude/sdlc.md` file/module limits. Permitted scope:
new `src/piitier/batch.py` and `src/piitier/passwords.py`, `src/piitier/cli.py`, new
`tests/test_passwords.py` and `tests/test_batch.py`, `tests/test_cli.py`, and existing `README.md`
usage sections. Reuse PII-14-a's loader and hidden terminal callback without duplicating them.
No dependency or lockfile change is needed in this slice.

## Context

- Baseline: `release/0.1.0` at `69c9d1b946069ed19a5a31a4f49bd08f391fd6e0`, or a descendant
  retaining Textual comparison, model integration and CSV selection/export, with approved
  [PII-14-a](../PII-14-a/spec.md) implemented and verified first. Implement after human approval
  in an isolated branch/worktree, not the draft-authoring `feat/polisa-pdf-templates` checkout.
  Parent: [PII-14 decomposition](../PII-14/decomposition.md).
- `src/piitier/cli.py`: `main`, `mask_file` and its model/threshold/revision defaults.
- `src/piitier/loaders.py`: `_LOADERS`, `get_loader`, and PII-14-a's `load_with_password` and
  typed `ValueError` authentication errors; `PdfNoTextError` remains a per-file failure.
- `piitier.Anonymizer.mask` and `piitier.mask`: reuse existing masking and document-local numbering.
- Neither `src/piitier/batch.py` nor `src/piitier/passwords.py` exists on the baseline. Batch
  execution belongs in the former; credential-map parsing belongs in the latter.
- Existing synthetic builders in `tests/test_loaders_pdf.py` and existing CLI test conventions
  are the fixture/testing anchors; no additional PDF fixture library is required.

### Credential-map contract

- `--passwords FILE` is optional. Parse the entire file before processing any documents or
  creating outputs. Encoding is UTF-8 with optional BOM, without encoding guesses/fallbacks.
- Require exactly the two header columns `filename` and `password`, in that order. Select comma
  or semicolon separation from the header only; never sniff credential data. Use standard strict
  CSV parsing, including quoting rules and embedded newlines. No value stripping or comments.
- Each nonblank record has exactly two fields. Blank records are skipped, not records containing
  whitespace or an empty filename. Preserve password whitespace, quoted commas/semicolons,
  quoted embedded newlines and an empty second field exactly. Header-only is a valid empty map;
  empty files (including BOM-only files) are invalid.
- Filename is an exact case-sensitive basename, not a path. Reject empty names, `.` and `..`,
  any slash or backslash, and duplicates. Do not normalise case or strip filename whitespace.
- Report malformed headers, decoding, quoting, field count, duplicate or unsafe-name errors by
  CSV path and record line only, never record contents, credentials or decoder exception text.
  For multiline records use the record's starting physical line (header is line 1); do not
  include input bytes in diagnostics. File-access errors likewise expose only a safe category/path.

### Validation, enumeration and masking contract

- Validate the input directory, output directory/path and model threshold before creating
  outputs. Reject output equal to or beneath input, including paths equal/nested after resolving
  aliases or symlinks. An existing output must be a directory; a missing output directory is
  created only after configuration/map validation. Invalid/inaccessible directories fail safely.
- Model defaults match `mask`: model `None` (rules only), threshold `0.0`, revision `None`.
  Preserve mask's threshold semantics: when model-enabled it must be a number in `[0, 1]`
  (reject NaN/infinities); without a model it is ignored. Initial model failures are configuration
  failures, not one failure per selected document.
- Enumerate supported regular files exactly once, in filename order, non-recursively, using the
  loader registry's supported extensions. Ignore directories and unsupported files. Exclude the
  credential CSV by resolved path, including aliases; never copy or anonymise the map even when
  its `.csv` suffix is supported and it resides inside the input directory.
- Empty selection exits 0 without constructing/loading a model. For nonempty model-enabled runs,
  construct at most one `Anonymizer`, forwarding model, threshold and revision, and reuse its
  `mask` method. Otherwise call `piitier.mask`. Do not call `mask_file` for every item or repeatedly
  construct models. Preserve document-local numbering; no cross-document numbering/cache.
- For PDFs look up the exact input basename. A missing map entry means absent credential, not an
  explicit empty string. Empty mapped values are explicit empty credentials. Non-PDF files ignore
  map credentials and retain normal text-loader behavior; whole CSV documents are masked with no
  batch column-selection flags.
- Use `load_with_password` directly: the supplied/implicit-empty credential is tried first;
  only typed authentication failures may invoke PII-14-a's hidden terminal callback, for at most
  three entered attempts. Callback arguments are path, one-based entered-attempt number and
  whether the last failure was incorrect credentials. Strings are verbatim; `None` cancels.
- Prompt only when stdin and stderr are terminals, using `getpass` on stderr and refusing echoed
  fallback. Missing/wrong entries can be corrected interactively. Without a terminal, fail that
  file immediately. Do not persist entered answers, modify the map or reuse answers on other files.
  EOF cancels only the current file; subsequent files continue. Ctrl-C stops immediately.

### Output, failure and exit contract

- Write UTF-8 masked extracted text, never a PDF. Preserve text-input filenames; replace a PDF
  suffix with `.txt`. Masking occurs before opening an output. PDF page separators and text
  fidelity remain governed by PII-14-a and the renderer.
- Existing targets and collisions with earlier outputs fail the later item in filename order.
  Use exclusive creation only after successful loading and masking. Never overwrite an existing
  file, source or symlink target (including dangling destination symlinks). Do not truncate first
  and do not precreate empty success files.
- A write failure removes only the partial file created by that attempt, never a pre-existing
  target. Continue after per-file authentication, no-text, parser, inference and write failures.
  Count a file as masked only after a successful completed write; otherwise count it failed.
- Stdout stays empty. Normal completion prints the final stderr summary exactly
  `batch: N masked, M failed` followed by a newline, with actual integer counts, including
  `batch: 0 masked, 0 failed` for empty selection. Per-file stderr diagnostics are safe categories
  and paths, never credentials, map contents, document text, decoder/parser excerpts or tracebacks.
- Exit 0 when every selected file succeeds (including empty selection); exit 4 for any per-file
  failure; exit 2 for configuration/map validation or initial model failure; exit 130 for
  interruption. Ctrl-C preserves completed outputs and removes the active partial output created
  by that attempt, without processing later files. Do not swallow `KeyboardInterrupt` in the
  shared loader. EOF is not command interruption and contributes one failed current file.

## Acceptance criteria

Parameterise the listed boundaries within each stable UC; assert distinct outcomes separately.
Use synthetic documents and runtime-generated credentials, never committed password maps.

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-179 | operator | Read comma/semicolon maps, each with/without BOM, quoted punctuation/newlines, whitespace and empty passwords | Exact case-sensitive basename-to-string mapping; no data sniffing/stripping; header-only gives an empty map and blank records are skipped | unit |
| UC-180 | operator | Supply malformed header/encoding/quoting/field count, empty file, duplicate or unsafe filenames | Exit 2 before document processing/output creation; errors identify only map path and record line, never contents or decoder excerpts | unit |
| UC-181 | operator | Batch a mixed supported directory with a model, then rules-only | Exact UTF-8 masked outputs and names in filename order; one model construction for model run and none for rules-only; numbering resets per document; directories/unsupported files ignored | e2e |
| UC-182 | operator | Batch valid documents alongside missing/wrong credentials, corrupt PDFs and authenticated no-text PDFs | Failures remain individual; valid documents have exact masked outputs, failed documents have no outputs; stdout empty, accurate counts and exit 4 | e2e |
| UC-183 | terminal operator | Correct missing/wrong entries, cancel one prompt with EOF, exhaust three attempts or interrupt with Ctrl-C | Hidden correction succeeds without stored/reused answers; EOF/exhaustion fail only that file; Ctrl-C exits 130 immediately, preserves completed outputs and removes the active partial output | unit |
| UC-184 | operator | Place the map/aliases inside input and precreate destinations or colliding PDF/text output names | Map and its resolved aliases are excluded with no exported copy; existing files/symlink targets remain byte-for-byte unchanged; later collision fails without overwriting earlier output | e2e |
| UC-185 | operator | Exercise invalid directories/nested destinations/threshold/model, empty selection and mid-write/inference failures | Configuration/initial model failure exits 2 before file processing; empty selection exits 0 without model loading; write failure removes only its new partial file, subsequent files succeed and per-file failures yield exit 4 | unit |

## Non-functional

- No new password storage, tracing of input data or model-per-file overhead. Memory-only
  credentials and safe diagnostics apply equally to parser, inference and write exceptions.
- New `tests/test_passwords.py`, `tests/test_batch.py` and CLI tests are offline and run in the
  default suite, not behind network `integration` exclusions. UC ids occur in test names.
  Verify real output content and state transitions, not only mock calls/absence of exceptions.
- After approved dependency installation, run from the implementation repository root:

  ```bash
  uv run pytest -q tests/test_passwords.py tests/test_batch.py tests/test_cli.py
  uv run pytest -q -m 'not integration'
  ```

  Apply Python stack lint/type checks and update existing batch usage documentation.
- Required subprocess smoke beyond tests: create a unique temporary directory containing an
  input directory and sibling output directories. Generate an encrypted text PDF, an empty-user
  restricted text PDF, an encrypted image-only PDF and one plaintext file, using synthetic PII
  and runtime-generated credentials. Put a valid mapping CSV inside inputs.
  1. Run `mask --password-stdin` on the encrypted text PDF: correct input gives exact masked text
     and exit 0; incorrect input gives exit 2 and no output file.
  2. Run `mask-batch` noninteractively with the map and sibling output directory: assert three
     successful exact outputs, one no-text failure, exit 4, empty stdout, no exported mapping
     file and final stderr summary `batch: 3 masked, 1 failed`.
  3. Assert these results through subprocess calls, including source preservation and output
     names/content. Remove temporary smoke artifacts; never commit the generated map.
- The original draft was written without implementation or runtime verification. Supervised
  implementation was subsequently authorised by the human; PII-14-a remains the implementation
  prerequisite. Approval frontmatter remains human-controlled.

## Open questions

none
