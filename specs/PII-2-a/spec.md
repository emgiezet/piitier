---
ticket: PII-2-a
title: Render a labelled synthetic document from a placeholder template
status: approved
stacks: [python]
depends-on: [PII-1-a, PII-1-b, PII-1-c, PII-1-d, PII-1-e]
---

# PII-2-a — Render a labelled synthetic document from a placeholder template

## Problem

The author wants to generate NER training data with local models on their own GPU
[EVIDENCE: session reply]. Training data is only usable if every label's offsets are exact, and the
plan gets that by having code inject every value into a placeholder template, so the offsets are known
[EVIDENCE: docs/Plan MVP … medtech.md, section 3, "Generowanie syntetyczne" step 1]. Nothing can
turn a template into a labelled document yet.

## Scope

In:
- Template parser for `{{LABEL}}`, `{{LABEL#k}}` and `{{LABEL#k:case}}`. `LABEL` is a `Label` member
  name. `case` is parsed here but rejected until PII-2-c.
- `render(template: Template, seed: int) -> Document`. `Document` has `text`, `template_id`,
  `doc_type`, `seed`, and `spans: list[Span]` with `source="synthetic"`, `status="valid"`, plus an
  `entity` key per span (`"1"` for `#1`; a fresh id for each unnumbered placeholder).
- Value generators for `PESEL`, `NIP`, `REGON`, `IBAN`, `NR_DOWODU` and `NR_KARTY`. Each value is drawn
  at random and kept only if the PII-1 validator accepts it. The format variant is chosen at random from
  the variants the PII-1 detector accepts (spaced, dashed, `PL` prefix).
- The same `#k` within one document renders the same value.
- `TemplateError` for unknown labels, labels with no generator, and malformed placeholders. The message
  names `template_id` and the character offset, never document text.

Out:
- Person, address and contact generators (PII-2-b), inflection (PII-2-c), dataset files and CLI (PII-2-d),
  LLM templates (PII-2-e).
- Insurance, finance and medical ID generators, augmentation, hard negatives (PII-3).
- Any change to `src/piitier/rules/`, `Label`, `Span`, `detect()`, or `mask()`.
- Packaged template files. Tests build their templates inline.

Change budget: 350 added lines, 6 files, 2 modules

## Context

- `.claude/playbooks/synthetic-data.md`: steps 1, 3 and 7, and the offset-integrity test requirement.
- `src/piitier/labels.py` (`Label`), `src/piitier/spans.py` (`Span`), `src/piitier/rules/*.py`
  (validators) and `piitier.detect()`, from PII-1-a…e.
- New: `src/piitier/datagen/__init__.py`, `src/piitier/datagen/template.py`, `src/piitier/datagen/values.py`,
  `src/piitier/datagen/render.py`, `tests/datagen/__init__.py` (package marker — prevents namespace
  collision with the root-level `tests/test_render.py` under pytest's default import mode),
  `tests/datagen/test_template.py`, `tests/datagen/test_render.py`.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-1 | data author | `render` of `"Klient PESEL {{PESEL}}."` with seed 7 | `doc.text` starts `"Klient PESEL "` and ends `"."`; one span, `label=PESEL`; `doc.text[start:end]` passes the PESEL validator | unit |
| UC-2 | data author | `render` of the same template twice with seed 7, then once with seed 8 | seeds 7 and 7 give identical `Document`s; seed 8 gives a different PESEL | unit |
| UC-3 | data author | `render` of `"{{IBAN#1}} oraz {{IBAN#1}}, inny {{IBAN#2}}"` | the two `#1` spans have identical text and `entity="1"`; the `#2` value differs from it | unit |
| UC-4 | data author | `render`, over 50 seeds, of a template with one placeholder of each of the 6 labels (the REGON placeholder preceded by `REGON `, since PII-1-c detects bare 9-digit REGONs only after the keyword), then `piitier.detect(doc.text)` | for every rendered span, `detect` returns a span with the same offsets, the same label and `status="valid"`: the generators produce only formats the PII-1 detectors accept | integration |
| UC-5 | data author | `render` of `"{{FOO}}"` | `TemplateError` naming the template id and offset 0; no `Document` returned *(added)* | unit |
| UC-6 | data author | `render` of `"{{LEK}}"` (a `Label` with no generator yet) | `TemplateError` with `no generator for LEK` *(added)* | unit |
| UC-7 | data author | `render` of `"{{PESEL"`, `"{{PESEL#x}}"` and `"{{PESEL#1:gen}}"` | `TemplateError` each time: unclosed, bad entity id, case not supported yet *(added)* | unit |
| UC-8 | data author | hypothesis-generated templates mixing Polish literal text and the 6 placeholders | for every span, `doc.text[start:end]` is the injected value; the literal text between placeholders appears verbatim and in order; spans are sorted and non-overlapping | unit (property) |

## Non-functional

- Randomness comes only from `random.Random(seed)` (`.claude/rules/python.md`).
- No network access, no LLM.

## Open questions

none
