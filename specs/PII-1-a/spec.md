---
ticket: PII-1-a
title: Project skeleton, entity taxonomy, and the Label/Span core types
status: approved
stacks: [python]
---

# PII-1-a — Project skeleton, entity taxonomy, and the Label/Span core types

## Problem

The author has written a one-off anonymisation script five times, once per data source, because
nothing reusable exists [EVIDENCE: session reply, specs/briefs/polish-pii-anonymizer.md]. Every later
slice needs one installable package, one list of entity types, and one span shape. Without them,
each detector would invent its own labels and offsets, which is how the five scripts happened.

## Scope

In:
- An installable uv project for package `piitier`, version `0.1.0`, Python ≥ 3.12, licence Apache-2.0.
- `docs/TAXONOMY.md`: the single list of entity types and placeholders.
- A `Label` enum mirroring the taxonomy exactly, and a validated `Span` type.
- Dev tooling pinned to exact versions: pytest, hypothesis, ruff, mypy. The `integration`
  pytest marker is registered.

Out:
- Any detector or validator. Those are PII-1-b (PESEL), PII-1-c (NIP/REGON), PII-1-d (IBAN) and
  PII-1-e (ID card, payment card).
- `piitier.mask()` / `piitier.detect()` and the renderer, which are PII-1-b.
- The CLI and file loaders, which are PII-1-f.
- Unicode normalisation, NER, fusion, coreference/numbering, and the risk-weight column in the
  taxonomy (that last one is a later evaluation ticket).
- Art. 9/10 "other" categories and quasi-identifiers as labels. They appear in the taxonomy doc
  under a `Roadmap` heading and get no enum member.
- CI configuration, pre-commit, publishing to PyPI or the Hugging Face Hub.

Change budget: 610 added lines, 10 files, 7 modules

## Context

- `docs/Plan MVP polskiego modelu do anonimizacji danych wrażliwych dla fintech, insurtech i medtech.md`:
  section 4 "Proponowana taksonomia MVP" is the source of the 39 types, their 6 groups, their
  placeholders, and their methods. Section 9, week 1, records the Apache 2.0 decision.
- `.claude/rules/python.md`: `src/` layout, `Span` in `src/piitier/spans.py`, labels in
  `src/piitier/labels.py`, exact pins, test layout.
- `.claude/playbooks/taxonomy-change.md`: the enum/taxonomy sync test this slice introduces.
- New: `pyproject.toml`, `uv.lock`, `src/piitier/__init__.py`, `src/piitier/py.typed`,
  `src/piitier/spans.py`, `src/piitier/labels.py`, `docs/TAXONOMY.md`, `tests/test_labels.py`,
  `tests/test_spans.py`.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-1 | developer | `uv sync`, then `uv run python -c "import piitier; print(piitier.__version__)"` | prints `0.1.0`; exit 0 | integration |
| UC-2 | maintainer | runs the test suite with `docs/TAXONOMY.md` and `Label` in agreement | the sync test passes; the set of placeholders parsed from the taxonomy table equals the set of `Label` placeholders, 39 entries | unit |
| UC-3 | maintainer | adds a row to the `docs/TAXONOMY.md` table without adding a `Label` member (simulated with a fixture copy of the file) | the sync test fails, and its message names the missing placeholder | unit |
| UC-4 | developer | reads `Label.<member>.placeholder` for every member | equals the taxonomy column verbatim, diacritics included (`Label.MIEJSCOWOSC.placeholder == "[MIEJSCOWOŚĆ]"`); numbered types (`OSOBA`, `IMIE`, `NAZWISKO`, `ADRES`, `LEKARZ`) have `numbered is True` and placeholder `[OSOBA_n]` style; all others `numbered is False` | unit |
| UC-5 | developer | constructs `Span(start=5, end=3, …)`, `Span(start=-1, end=2, …)`, `Span(start=3, end=3, …)` | each raises `ValueError`; the message carries offsets only, never text *(added)* | unit |
| UC-6 | developer | constructs `Span` with `status` other than `"valid"` or `"suspect"` | raises `ValueError` *(added)* | unit |

## Non-functional

- `Span` is a frozen dataclass with fields `start: int`, `end: int`, `label: Label`,
  `source: str`, `score: float`, `status: str`. `[start, end)` is half-open in original-input offsets.
- `uv run mypy src` passes with no ignores.

## Open questions

none
