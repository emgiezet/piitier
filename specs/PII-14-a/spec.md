---
ticket: PII-14-a
title: Authenticated PDF extraction and single-file CLI credentials
status: draft
stacks: [python]
---

# PII-14-a — Authenticated PDF extraction and single-file CLI credentials

## Problem

Operators cannot anonymise password-protected PDFs even when they hold a valid credential.
Blanket encrypted-file rejection also excludes owner-restricted PDFs readable with an empty
user credential. Failures must not be mistaken for successfully anonymised empty documents.

## Scope

In:
- Optional credentials for PDF extraction, typed authentication failures and a shared callback
  retry helper for CLI, batch and Textual consumers.
- `piitier mask` credential arguments and secure terminal prompting, preserving existing APIs.
- Pinned runtime AES support, synthetic regression coverage and user-facing usage documentation.

Out:
- Directory processing and mapping CSV parsing (PII-14-b); Textual credential widgets (PII-14-c).
- OCR, PDF rewriting/redaction/encryption, metadata/annotation/form/attachment extraction.
- Detector/model algorithm changes, credential storage, changes to `load_text_file`, CI,
  corpora/checkpoints, frozen benchmarks, tracker issues or historical approved specifications.

Change budget: 400 added lines, 10 files, 3 modules.

This is a review estimate under `.claude/sdlc.md`, not a new waiver of file/module limits.
Permitted implementation scope: `src/piitier/loaders.py`, `src/piitier/cli.py`,
`tests/test_loaders_pdf.py`, `tests/test_loaders.py`, `tests/test_cli.py`,
`tests/datagen/test_templatize.py`, `pyproject.toml`, `uv.lock`, and existing `README.md` usage
sections. Other callsites below are inspection/regression anchors, not permission for unrelated
changes. Explicitly update both dependency files together; the lockfile is in scope.

## Context

- Baseline: `release/0.1.0` at `69c9d1b946069ed19a5a31a4f49bd08f391fd6e0`, or a descendant
  retaining Textual comparison, model integration and CSV selection/export. Implement only after
  human approval, in an isolated branch/worktree based on that baseline, not the draft-authoring
  `feat/polisa-pdf-templates` checkout. Parent: [PII-14 decomposition](../PII-14/decomposition.md).
- `src/piitier/loaders.py`: `load_pdf`, `PdfNoTextError`, `get_loader`, `_LOADERS`, `load_text_file`.
- Recheck callers in `src/piitier/cli.py` (`mask_file`, `main`), `src/piitier/tui.py`
  (`compare_file`), `src/piitier/datagen/templatize.py` (`templatize`),
  `tests/test_loaders.py` and `tests/test_loaders_pdf.py`.
- `tests/test_loaders_pdf.py`: reuse `_add_text_page`, `_add_image_only_page`, `_encrypted_pdf`;
  no additional PDF fixture library. `tests/datagen/test_templatize.py`: unreadable-donor contract.
- `pyproject.toml`, `uv.lock`: retain baseline `pypdf==6.21.1`; add `cryptography==50.0.2`
  as a pinned runtime dependency. Planning observed that AES fixture generation failed without
  cryptography; compatibility is unverified until real RC4/AES extraction tests pass.
- Historical `specs/PII-1-g/spec.md` UC-42: this draft supersedes blanket rejection of all
  encrypted PDFs and the exact `encrypted pdf: <path>` wording only. Preserve rejection before
  unauthenticated extraction, empty stdout, no PII disclosure and exit 2 when authentication
  cannot succeed. Record supersession here, never rewrite the approved historical spec.

### Extraction and registry contract

- Extend `load_pdf` with an optional credential. An explicitly supplied string is used verbatim,
  including `""`; absence means try `""` to support readable owner-restricted PDFs. Do not
  silently replace an explicitly wrong credential with the empty value.
- Authenticate before iterating or accessing pages. Accept both successful pypdf decrypt enum
  results (user and owner); `NOT_DECRYPTED` fails. Never decrypt to an intermediate disk file.
- Preserve extracted whitespace, page order and every blank-page separator: join all page text
  with `\n`, without stripping/filtering the result. Keep `PdfNoTextError` and
  `no text layer: <path>` when no page has non-whitespace text, including authenticated scans.
- Define distinct required-credential and incorrect-credential errors derived from `ValueError`.
  Failed absent/implicit-empty authentication is `password required: <path>`; failed explicit
  authentication, including explicit empty input, is `wrong password: <path>`.
- Keep `_LOADERS` and existing one-argument callers. `get_loader` gains an optional keyword
  credential; use `functools.partial` to bind it only for PDF and only when supplied. Its result
  remains a one-argument loader; unsupported types still return `None`. `load_text_file` is
  unchanged. Datagen's existing `(ValueError, PdfReadError)` unreadable rejection remains valid.
- Add `load_with_password` in `loaders.py`: try the supplied credential (implicit empty if absent)
  first. Only typed authentication failures may trigger an optional callback, with at most three
  entered attempts in addition to the initial attempt. No callback means immediate failure.
- Callback arguments are path, one-based entered-attempt number (1–3) and whether the last
  failure was an incorrect credential. Its returned string is attempted verbatim; `None` cancels
  without another extraction. Empty string is never cancellation. On cancellation/exhaustion,
  report a safe authentication failure. Non-authentication failures propagate without prompting.
  Do not catch `KeyboardInterrupt` inside this helper.

### Single-file CLI contract

- Add mutually exclusive `--password VALUE` and `--password-stdin` to `mask`. Help for
  `--password` warns that arguments may appear in process listings and shell history.
- Preserve `mask_file`'s existing positional argument meanings, model/threshold/revision,
  CSV column selection/delimiter, source-overwrite protection and successful output behavior.
  Reject explicit password options on non-PDF inputs before reading stdin; invalid combinations
  and unsupported input remain input errors, without echoing a supplied credential.
- Stdin mode reads one line, removes exactly a terminating LF and its immediately preceding CR,
  and preserves all other whitespace. Without LF, preserve the entire line, including a bare CR.
  Immediate EOF is an input error; a blank line supplies `""`. Never prompt after stdin mode,
  even if authentication fails or terminal descriptors are present.
- Otherwise hidden prompting is allowed only when both stdin and stderr are terminals. Use
  `getpass` with prompts on stderr, via a callback reusable by batch. Refuse its echoed-input
  fallback before any secret can be displayed. A supplied wrong `--password` may be corrected
  interactively under the same rules; no terminal means immediate authentication failure.
- EOF cancels the current file. Ctrl-C interrupts the command, including stdin/hidden entry,
  and exits 130. Success exits 0; input/authentication/read/filesystem failures exit 2; no text
  layer exits 3. Expected PDF/parser and filesystem failures have safe messages, no traceback.
- Do not create or truncate the destination until extraction and masking both succeed.
  Authentication failure leaves an absent destination absent and an existing destination
  unchanged; stdout contains neither extracted PII nor a misleading successful empty result.
- Exceptions, help/argument errors, prompts, logs and parser diagnostics must not reveal
  credentials, extracted text or parser excerpts/input bytes. Error categories and paths are
  sufficient; do not forward unsafe parser exception text.

## Acceptance criteria

Each row is a stable behavioral family; parameterise its listed boundaries and assert each
outcome separately. Credentials are runtime-generated and document contents synthetic.

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-173 | library caller | Extract with user or owner credentials, parameterised over RC4, AES-128 and AES-256 | Exact expected page text, leading/trailing whitespace and blank-page separators; both successful credential kinds unlock extraction | unit |
| UC-174 | library caller | Load missing/wrong/explicit-empty credentials, empty-user restricted PDFs and authenticated image-only PDFs | Typed safe authentication failures precede page extraction; implicit empty opens readable restricted PDF without callback; authenticated scan raises the existing no-text error | unit |
| UC-175 | CLI operator | Mask via explicit or stdin credential; repeat with missing/wrong credentials and absent/existing destinations | Success emits exact masked text and exit 0; failure exits 2 with empty stdout, absent/unchanged destination and no credential/PII/parser disclosure | e2e |
| UC-176 | terminal operator | Exercise hidden wrong-then-correct entry, EOF, three wrong entries, Ctrl-C and echoed fallback | Correction succeeds; EOF cancels with exit 2; exactly three entered failures terminate with exit 2; Ctrl-C exits 130; fallback is refused without echo; non-authentication errors never retry | unit |
| UC-177 | CLI operator | Supply conflicting flags, non-PDF flags, stdin EOF, blank input and whitespace-bearing credentials | Invalid flags/EOF exit 2 without credential disclosure or non-PDF stdin reads; LF/CRLF removal only, bare CR/other whitespace and explicit empty survive exactly; stdin mode never prompts | e2e |
| UC-178 | existing caller | Run plaintext/PDF/datagen and CLI model/CSV paths using existing APIs | Plaintext encodings/line endings, PDF fidelity, no-text behavior, datagen unreadable counts, UC-42 protection/exit 2 and exact model/CSV masked outputs remain intact | unit |

## Non-functional

- Keep credentials in memory only, with no persistence/history. All fixtures and diagnostic
  assertions use synthetic PII and runtime-generated credentials, never committed real secrets.
- Authentication must complete before masking/model work or output mutation. Failure safety is
  observable state, not merely a check that a mock was called.
- Reuse current test conventions. UC identifiers appear in test names. New CLI/authentication
  tests are offline default-suite tests, not excluded with the network `integration` marker.
  Remove obsolete exact-wording-only assertions while retaining behavioral protection coverage.
- After approved dependency installation, run from the implementation repository root:

  ```bash
  uv run pytest -q tests/test_loaders_pdf.py tests/test_loaders.py tests/test_cli.py tests/datagen/test_templatize.py
  uv run pytest -q -m 'not integration'
  ```

  Also apply the Python rules' lint/type checks. Import inspection alone cannot establish
  encryption compatibility: generate and decrypt all three algorithm families.
- Smoke beyond tests: in a unique temporary directory generate an encrypted text PDF and
  credentials at runtime. Through subprocesses run `mask --password-stdin` with correct and
  incorrect input. Assert exact masked text/exit 0 on success, exit 2 and no output file on
  failure. Leave source and existing destinations unchanged on failed authentication. Remove
  temporary artifacts; update existing usage documentation, not historical approved specs.
- The original draft was written without implementation or runtime verification. Supervised
  implementation was subsequently authorised by the human; approval frontmatter remains
  human-controlled, and no unattended queue approval is implied.

## Open questions

none
