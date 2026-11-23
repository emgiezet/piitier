---
ticket: PII-14-c
title: Secure credential entry before existing Textual comparison
status: approved
stacks: [python]
depends-on: PII-14-a
---

# PII-14-c — Secure credential entry before existing Textual comparison

## Problem

Operators cannot inspect password-protected PDFs in the existing comparison interface.
Credential cancellation must not expose document contents or trigger model downloads/loading.
The current comparison navigation and CSV selection/export remain required user workflows.

## Scope

In:
- A short-lived `PasswordPromptApp` in the existing Textual module, before comparison opens.
- Shared authenticated loading in `compare_file`, safe credential retries/cancellation and
  terminal gating, with model initialisation deferred until extraction succeeds.
- Offline Pilot coverage, existing comparison regressions and credential-entry usage docs.

Out:
- A new `tui` command, file picker, batch interface, second comparison viewer or password flags
  on `compare`; batch processing belongs to PII-14-b.
- New dependencies (including `pytest-asyncio`), OCR, PDF output, detector/model redesign,
  credential history/storage, CI, corpora/checkpoints, tracker changes or historical spec edits.

Change budget: 300 added lines, 4 files, 3 modules.

This is a review estimate, not a waiver of `.claude/sdlc.md` file/module limits. Permitted scope:
`src/piitier/tui.py`, `tests/test_tui.py`, `tests/test_loaders_pdf.py`, and existing `README.md`
comparison usage sections. Consume the approved slice a interface, without another retry helper
or loader registry. Existing CLI dispatch and arguments stay unchanged.

## Context

- Baseline: `release/0.1.0` at `69c9d1b946069ed19a5a31a4f49bd08f391fd6e0`, or a descendant
  retaining Textual comparison, model integration and CSV selection/export, plus implemented and
  verified [PII-14-a](../PII-14-a/spec.md). Implement only after human approval in an isolated
  branch/worktree, not the draft-authoring `feat/polisa-pdf-templates` checkout. There is no
  dependency on PII-14-b. Parent: [PII-14 decomposition](../PII-14/decomposition.md).
- `src/piitier/tui.py`: `compare_file`, `AnonymizationDiffApp`, `CsvSelectionScreen`, `build_diff`.
- `src/piitier/loaders.py`: PII-14-a's `load_with_password`, typed `ValueError` authentication
  errors and `PdfNoTextError`. `src/piitier/cli.py`: existing `compare` dispatch and argument API.
- Baseline `pyproject.toml`: `textual==8.2.8`, `pypdf==6.21.1`; slice a supplies pinned runtime
  cryptography support. No dependency additions are authorised here.
- `tests/test_tui.py`: `asyncio.run` around Textual `run_test` and Pilot; use the same pattern,
  without `pytest-asyncio`. `tests/test_loaders_pdf.py`: reuse synthetic text/image PDF builders.

### Credential entry and lifecycle contract

- `compare_file` uses the shared `load_with_password` before model initialisation and before
  constructing the comparison app. The helper first attempts the absent credential as empty,
  so unencrypted and empty-user readable restricted PDFs do not prompt.
- Only typed authentication errors invoke the callback. It receives path, one-based entered
  attempt number (1–3) and whether the last failure was incorrect credentials. Launch the
  short-lived `PasswordPromptApp` for that attempt, passing only filename and attempt/error
  state, never document contents. Do not give it the extracted document or comparison panes.
- Display a literal filename label (no interpretation as Rich/Textual markup), a visibly masked
  `Input`, an attempt/error status, and `Unlock`/`Cancel` buttons. Missing-credential and
  wrong-credential feedback is safe, revealing neither the attempted value nor document text.
- Enter or Unlock submits the exact input string, including leading/trailing whitespace and
  `""`. Escape or Cancel returns cancellation (`None`), not an empty credential. Clear the input
  after submission or cancellation and keep no history. The submitted value exists only for
  the current authentication attempt and is never written to disk or logs.
- The shared helper, not the UI, owns the limit of at most three entered attempts after the
  initial implicit-empty attempt. Wrong entry updates safe error/attempt state for the next
  prompt; after three failed entered attempts terminate without a fourth prompt. Do not retry
  parser, filesystem or no-text failures as credential failures.
- Prompt only when stdin and stdout are terminals. If either is nonterminal and authentication
  is required, return a safe authentication error without launching a headless interactive app.
  Do not substitute CLI `getpass` prompting for this Textual workflow.
- Cancellation or authentication exhaustion exits 2. Ctrl-C exits 130, including while the
  prompt/comparison app runs; explicitly handle interruption rather than default quit-success.
  Other input/authentication/read failures exit 2 safely with no traceback or parser excerpts;
  retain existing no-text exit 3 and successful comparison exit 0.
- Model initialisation, including model download/loading, occurs only after successful
  extraction. Cancellation, authentication failure or required-auth nonterminal invocation must
  not construct a model, create outputs or expose document content in diagnostics/panes.
- Correct authentication leads into the existing `AnonymizationDiffApp`, with its current
  before/after panes, detected-span highlighting, numbering and navigation. Do not replace it
  with another viewer. Preserve the existing CSV selection and exclusive export workflow.

## Acceptance criteria

Each stable UC has parameterised boundaries with separate observable assertions. All documents
and PII are synthetic; credentials are generated at runtime, never committed with a password map.

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-186 | terminal operator | Enter a valid credential via Enter or Unlock on an encrypted PDF | Filename is literal, input visibly masked, submitted value exact and field cleared; existing comparison panes show the expected original and exactly masked content after successful extraction | e2e |
| UC-187 | terminal operator | Submit wrong-then-correct, three wrong entries, whitespace-bearing input and empty input; separately cancel with Escape/Cancel | Safe attempt/error feedback permits correction; three failures exit 2 without fourth prompt; whitespace/empty strings are submitted credentials, cancellation returns no credential; fields clear and no history persists | unit |
| UC-188 | operator | Cancel authentication, invoke with nonterminal stdin/stdout or interrupt with Ctrl-C | Cancellation/nonterminal auth failure exits 2 without content disclosure, output creation or model initialisation/download; no headless prompt app; Ctrl-C exits 130; no raw parser diagnostics or credentials | e2e |
| UC-189 | comparison user | Navigate findings after unlocking; exercise existing CSV selection and export | Current highlighting, wraparound/scroll navigation and document-local numbering remain intact; selected CSV columns and exact exported content/encoding remain correct and source/existing targets are not overwritten | e2e |

## Non-functional

- Secrets stay in memory only. Neither temporary app state/history nor diagnostics may retain
  passwords or document text. Literal filename rendering must not execute markup.
- Use current `asyncio.run`/Pilot tests in the offline default suite, not network `integration`
  exclusions. UC ids appear in test names. Assert rendered masking, exact pane/export contents
  and state transitions, not merely widget existence, forwarded calls or no exception.
- Include unencrypted and empty-user restricted PDFs as no-prompt regression boundaries;
  authenticated image-only PDFs retain the no-text failure before model initialisation.
- After approved dependency installation, run from the implementation repository root:

  ```bash
  uv run pytest -q tests/test_tui.py tests/test_loaders_pdf.py
  uv run pytest -q -m 'not integration'
  ```

  Apply Python stack lint/type checks and update existing comparison usage documentation.
- Required real-terminal smoke beyond tests: generate a synthetic encrypted text PDF and
  runtime credential in a unique temporary directory. Discover an available local checkpoint;
  do not assume a particular training output directory exists. Launch the actual `compare`
  command with it. Verify visibly masked entry, wrong-then-correct flow, actual before/after
  comparison panes with expected masked text, navigation and Ctrl-C exit 130. In a separate
  invocation Escape must exit before model loading. Observe the actual terminal surface.
- If no local checkpoint is available, exercise a throwaway smoke harness using real
  `piitier.detect`, renderer and Textual app through a test-only model seam, and explicitly report
  model integration as unverified. Do not add a production fallback. A missing-model error after
  decryption alone is not sufficient TUI proof. Remove temporary smoke scaffolds and fixtures.
- The original draft was written without implementation or runtime verification. Supervised
  implementation was subsequently authorised by the human; approval frontmatter remains
  human-controlled, and no unattended queue approval is implied.

## Open questions

none
