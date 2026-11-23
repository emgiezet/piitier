---
ticket: PII-14
title: Password-protected PDF extraction, directory batches and comparison credentials
status: draft
stacks: [python]
---

# PII-14 — Password-protected PDFs

## Problem

Encrypted PDFs cannot currently enter the anonymisation workflow, even when the operator knows
the password. Operators also lack directory processing with per-file credentials. The existing
Textual comparison interface must remain the interactive inspection surface.

## Baseline and approval gate

- Specification baseline: `release/0.1.0` at `69c9d1b946069ed19a5a31a4f49bd08f391fd6e0`.
  It includes Textual comparison, model integration and CSV selection/export.
- Drafts are authored without switching the checkout: `feat/polisa-pdf-templates` at
  `3fd9d10bed78edd9b56d090945735b95aac38a41`. That checkout is not the implementation base.
- Known local branches, remote-tracking refs, tags and stash were checked. Specifications run
  through PII-13 / UC-162, but implementation-time checking also found existing test identifiers
  through UC-172. Per the collision contingency, this feature uses UC-173–UC-189; the initial
  draft range UC-163–UC-179 is superseded. Existing historical acceptance identifiers are unchanged.
- The original draft-writing delivery created only this decomposition and three specifications,
  without application changes or dependency installation. The human subsequently authorised
  supervised implementation in conversation; that does not authorise tracker mutation,
  release publication or merging.
- Only a human may set `status: approved`. Frontmatter remains draft; no unattended queue
  approval is implied by the supervised implementation.
- Later implementation must use an isolated branch/worktree from this release baseline or a
  descendant retaining its features. If the release advances, re-read the relevant descendant.
  If comparison features disappear, do not substitute CLI prompting for the Textual requirement.
  Preserve unexpected user changes.

## Slices and dependency order

| Slice | Deliverable | Depends on | Acceptance ids | Status |
|---|---|---|---|---|
| [PII-14-a](../PII-14-a/spec.md) | Authenticated PDF loading and single-file CLI credentials | release baseline | UC-173–UC-178 | draft |
| [PII-14-b](../PII-14-b/spec.md) | Strict filename/password CSV and `mask-batch` | PII-14-a | UC-179–UC-185 | draft |
| [PII-14-c](../PII-14-c/spec.md) | Credential entry before existing Textual comparison | PII-14-a | UC-186–UC-189 | draft |

Implement and verify a first. Slices b and c are independent after a: b owns batch execution
and mapping; c owns the comparison credential app. Both consume a's shared loader callback.
Neither may introduce a second retry policy, loader registry, or comparison viewer.

| Slice | Estimated added lines | Estimated files | Module budget |
|---|---:|---:|---:|
| a | 400 | 10 | 3 |
| b | 400 | 8 | 3 |
| c | 300 | 4 | 3 |

These are review estimates, not new waivers. Apply `.claude/sdlc.md` scope accounting and its
existing three-module budget; no exception to file/module limits is granted. Slice a explicitly
permits both `pyproject.toml` and `uv.lock`. Exceeding scope requires the normal human review or
re-decomposition, not a silently widened allowance.

## Shared contracts

- `src/piitier/loaders.py` owns authenticated extraction and `load_with_password`: one initial
  supplied/empty attempt, then at most three callback-entered attempts only on typed
  authentication failures. A callback gets path, one-based attempt number and whether the last
  failure was an incorrect credential; a string is verbatim, `None` cancels. No callback fails
  immediately; `KeyboardInterrupt` propagates to the command boundary.
- Missing and incorrect credentials are distinct `ValueError` subclasses with safe messages
  `password required: <path>` and `wrong password: <path>`. Existing datagen unreadable-donor
  handling remains compatible. No credential, document text or parser excerpt enters diagnostics.
- Passwords are never persisted or decrypted to disk. Empty strings are credentials, not
  cancellation. CLI/batch prompting requires terminal stdin and stderr and refuses echoed
  fallback; Textual prompting requires terminal stdin and stdout.
- Outputs are extracted masked text, not redacted/encrypted PDFs. Text fidelity, page order,
  blank-page separators, no-text errors and document-local numbering remain intact. OCR is
  unchanged. Batch is nonrecursive and uses exact case-sensitive basenames, not path precedence.
- UC-42's unauthenticated-extraction protection and exit 2 remain required. PII-14-a supersedes
  only its blanket encrypted-file rejection and obsolete exact diagnostic; do not rewrite the
  approved PII-1-g specification.

## Verification and handoff

The original specification-only delivery checked draft frontmatter, baseline, dependency order
and requirements, especially hidden entry, empty credentials, metadata-file exclusion,
non-destructive writes and cancellation. Runtime checks below belong to the subsequent
human-authorised implementation, not to the initial draft delivery.

After human approval and dependency installation, run the commands and smoke scenarios in each
slice. Shared full offline regression, from the implementation repository root:

```bash
uv run pytest -q -m 'not integration'
```

Apply the Python stack's lint/type checks too. New CLI and Pilot tests are offline default-suite
tests, not network integration exclusions. Reuse synthetic PDF/PII builders and runtime-generated
credentials; never commit real secrets or password maps. Assert exact contents and state
transitions, not only mocked calls or absence of exceptions. Each UC must appear in a test name.

The end-to-end batch smoke belongs to b; the real-terminal comparison smoke belongs to c. A
missing-model error after decryption alone is not sufficient proof of the comparison interface.
All implementation behavior and acceptance requirements live in these repository artifacts;
no session-local plan is required for implementation.

## Open questions

none
