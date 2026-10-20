---
ticket: PII-2-e
title: python -m piitier.datagen write-templates — local Bielik writes placeholder templates
status: approved
stacks: [python]
depends-on: [PII-2-d]
---

# PII-2-e — `python -m piitier.datagen write-templates`: local Bielik writes placeholder templates

## Problem

The author wants local models on their own GPU to produce the training data [EVIDENCE: session reply].
Hand-written templates (PII-2-d) do not scale to thousands of varied documents. The plan has a local
Bielik write document text with placeholders in place of PII, and never lets it write values or labels
[EVIDENCE: docs/Plan MVP … medtech.md, section 3, step 2; CLAUDE.md invariant 5]. Bielik 11B v3 Q8_0 is
installed in Ollama, next to an RTX 3090 Ti with 24 GB [EVIDENCE: ollama list, nvidia-smi].

## Scope

In:
- `python -m piitier.datagen write-templates --doc-type <t> --count <N> --out <dir>
  [--model <tag>] [--ollama-url <url>] [--seed <S>] [--temperature <x>]`.
  The default model is `hf.co/SpeakLeash/Bielik-11B-v3.0-Instruct-GGUF:Q8_0`, and the default URL is
  `http://127.0.0.1:11434`.
- Calls Ollama's `/api/generate` with stdlib `urllib` (no new dependency), `stream: false`, and the seed
  and temperature passed through.
- The prompt is in Polish, one per doc type, stored in `src/piitier/datagen/prompts/<doc_type>.txt`. It
  lists only the labels that currently have generators, the placeholder syntax, and one packaged
  template as an example.
- Every completion goes through checks in this order, and the first failure rejects it:
  1. It parses as a template (PII-2-a parser), or the reason is `parse_error`.
  2. Every label has a generator, or the reason is `unknown_label`.
  3. It has at least 3 placeholders, or the reason is `too_few_placeholders`.
  4. With placeholders removed, `piitier.detect()` finds nothing and there is no run of 7 or more
     digits (single spaces or dashes between digits count as part of the run, so `501 234 567` is a run
     of 9), or the reason is `leaked_value`. Amounts such as `250 000 zł` (6 digits) pass.
  5. Its sha256 is not already in `--out`, or the reason is `duplicate`.
- An accepted completion is written to `<out>/<doc_type>/<template_id>.txt`, where `template_id` is
  `<doc_type>-<sha256[:12]>`. Rejected completions are never written.
- `<out>/manifest.json` is appended with the model tag, the model digest from `/api/tags`, the prompt
  sha256, temperature, seed, and counts accepted and rejected by reason.
- Only loopback URLs are allowed (`127.0.0.1`, `::1`, `localhost`); any other host exits 2 before a
  request is sent. Ollama unreachable: exit 3.

Out:
- Starting, configuring, rebinding or inspecting the Ollama server, including any check of which
  interface it listens on. The author trusts the local Ollama, which holds local models only
  [EVIDENCE: session reply]. The CLI only refuses to *send* to a non-loopback URL (UC-34).
- Letting the LLM produce values, labels or offsets. Using the LLM to verify or score documents.
- Non-Bielik generators. `--model` accepts any tag, but licence checks for publication are PII-3.
- Fine-tuning any model, the production run, the HF dataset card.
- Any change to `build`, `render` or the generators.

Change budget: 380 added lines, 7 files, 3 modules

## Context

- `src/piitier/datagen/template.py` (parser), `values.py` (generator registry) and `__main__.py`
  (subcommands), from PII-2-a and PII-2-d. The packaged templates from PII-2-d serve as prompt examples.
- Prior art for loopback-only Ollama: `trasti/complaint-classifier/scripts/scan_pii.py`
  `private_ollama_listener` (lines 38–43). Its server-bind check is deliberately **not** carried over (see Out).
  Read it for behaviour. Do not copy code from that repository.
- New: `src/piitier/datagen/llm.py`, `src/piitier/datagen/prompts/*.txt` (8 files),
  `tests/datagen/test_llm.py`, `tests/datagen/test_llm_ollama.py` (`@pytest.mark.integration`).
- Unit tests run against a local `http.server` fake on `127.0.0.1` that returns canned completions, so
  the real HTTP path is exercised without a model.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-30 | data author | `write-templates --count 1` against the fake server returning a valid 4-placeholder `zgloszenie_szkody` template | exit 0; one file in `<out>/zgloszenie_szkody/`; manifest `accepted=1` | integration |
| UC-31 | data author | the fake returns text with `PESEL 90051512340` where a placeholder belongs | not written; manifest `rejected.leaked_value=1` | integration |
| UC-32 | data author | the fake returns `{{FOO}}`, and separately a template with 2 placeholders | not written; `rejected.unknown_label=1`, `rejected.too_few_placeholders=1` | integration |
| UC-33 | data author | the fake returns the same valid template twice with `--count 2` | one file written; `rejected.duplicate=1` | integration |
| UC-34 | data author | `--ollama-url http://192.168.1.5:11434` | exit 2; stderr `refusing non-loopback ollama url`; the fake server received no request *(added)* | integration |
| UC-35 | data author | `--ollama-url http://127.0.0.1:<closed port>` | exit 3; stderr `ollama not reachable at <url>` *(added)* | integration |
| UC-36 | data author | read `manifest.json` after UC-30 | holds model tag, model digest, prompt sha256, temperature and seed exactly as sent | integration |
| UC-37 | data author | real Ollama with Bielik 11B Q8_0: `write-templates --doc-type zgloszenie_szkody --count 3`, then `build --templates <out> --n 10` | at least 1 accepted template; `build` and `check` exit 0 | integration (marked, needs GPU) |

## Open questions

none
