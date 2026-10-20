## PII-2-c + PII-2-e — Name inflection (Morfeusz 2) & LLM synthetic document generation (Bielik 11B)

**QA verdict: PASS** · **Both reviews: APPROVED (C source/test review zero findings; E security/source audit zero findings)** · UC coverage: 15/15 automated (UC-15–21, UC-30–37) · Tests: 377 → 463 (+86, 41.29s) · Skipped: 0

This PR is stacked onto `ai/pii-1g-2a-integration` (PR#2, open; base main). #2 targets main; this PR targets its head branch. Merge #2 first, then retarget this PR to main to preserve separately reviewed scope. No auto merge. Base: `9713e857ca4ab1568cc61cb8ce65108c218866e0`.

Written from [spec (PII-2-c)](https://github.com/emgiezet/piitier/blob/ai/pii-2ce-integration/specs/PII-2-c/spec.md) and [spec (PII-2-e)](https://github.com/emgiezet/piitier/blob/ai/pii-2ce-integration/specs/PII-2-e/spec.md). Component reports:
- PII-2-c: [QA Report](https://github.com/emgiezet/piitier/blob/ai/pii-2ce-integration/specs/PII-2-c/qa-report.md), [Verify Report](https://github.com/emgiezet/piitier/blob/ai/pii-2ce-integration/specs/PII-2-c/verify-report.md), [Scope Report](https://github.com/emgiezet/piitier/blob/ai/pii-2ce-integration/specs/PII-2-c/scope-report.md)
- PII-2-e: [QA Report](https://github.com/emgiezet/piitier/blob/ai/pii-2ce-integration/specs/PII-2-e/qa-report.md), [Verify Report](https://github.com/emgiezet/piitier/blob/ai/pii-2ce-integration/specs/PII-2-e/verify-report.md), [Scope Report](https://github.com/emgiezet/piitier/blob/ai/pii-2ce-integration/specs/PII-2-e/scope-report.md)

### What both specs add

1. **PII-2-c — Inflected names (Morfeusz 2):**
   - Support for `{{LABEL#k:case}}` for `OSOBA`, `IMIE`, and `NAZWISKO` with cases `nom`, `gen`, `dat`, `acc`, `inst`, `loc`, `voc`.
   - Grammatical inflection via `morfeusz2==1.99.15` agreeing with person sex; fallback to nominative with `inflection_fallbacks` tracking.
   - Case-aware caching, document counter, and manifest aggregation.

2. **PII-2-e — LLM synthetic document generation (Bielik 11B Instruct):**
   - Integration with LOCAL Ollama backend only for template authoring and paraphrasing (code injects synthetic values + labels; no remote backend support).
   - UC-37 verified with real Bielik model (`hf.co/SpeakLeash/Bielik-11B-v3.0-Instruct-GGUF:Q8_0`, digest `bc20c2f093b5aa89222064c5d588c61b5c12f0f7679f8bd2495d5bba4a64dc4c`, seed 42, temp 0.2, count 3 => accepted 1, duplicate 2; CLI build 10 / check 0).
   - Guardrails, SSRF/redirect defenses (local hosts/proxies disabled/redirect refused; policy CLI exit 2, unreachable 3), attempt counting, and JSON array manifest history.

### Verification results

- `uv run ruff format --check . && uv run ruff check .` — PASS (117 files)
- `uv run mypy src` — PASS (22 source files)
- `uv run pytest -q --basetemp /tmp/piitier-ce-verification-zjgrtrg_/pytest_release_final` — 463 passed, 41.29s, 0 skipped.
- **Installed Wheel Smoke Proof (2026-10-21):** Wheel `piitier-0.1.0-py3-none-any.whl` built and tested outside checkout using isolated Python 3.13 (`uv run --offline --isolated --no-project --python 3.13 --with <wheel> python -c ...`).
  - Real Morfeusz: 100 inflected documents / 2100 exact spans across all 7 cases; literals/CRLF/entity/seed/global RNG, CLI build/check 100, fallback aggregate 42 PASS.
  - Installed packaged prompt → real Bielik write-templates count 1 seed 42 temp 0.2 → accepted 1 rejected {}; model digest and prompt SHA verified; filename SHA12 matches content → CLI build 100 / check exit 0 → 100 JSONL records / 600 spans verifying all `text[start:end] == span['text']`; isolated import PASS.

### Usage Examples

Templates from local Bielik → synthetic dataset:
```bash
# Templates from local Bielik → synthetic dataset
uv run python -m piitier.datagen write-templates --doc-type zgloszenie_szkody --count 3 --seed 42 --temperature 0.2 --out templates-llm/
uv run python -m piitier.datagen build --templates templates-llm/ --n 100 --seed 42 --out dataset/
uv run python -m piitier.datagen check dataset/
```

Template placeholder example with case (`OSOBA#1:inst`):
`Osoba: {{OSOBA#1}}. Rozmowa z {{OSOBA#1:inst}}.`

### Scope, sizing and constraints

| Component | Added Lines | Files Touched | Modules Touched |
|---|---|---|---|
| PII-2-c | 621 | 8 | 3 |
| PII-2-e | 1811 | 12 | 2 |
| **Combined** | **2432** | **20** | **3** |

*Native scope vs immutable base (excluding specs and `uv.lock`, modules first 2 segments: `pyproject.toml`, `src/piitier`, `tests/datagen`). Hard ceiling 5000 not breached.*

*PII-2-e exact native files (12): `src/piitier/datagen/llm.py`, `src/piitier/datagen/__main__.py`, 8 prompt template files under `src/piitier/datagen/prompts/`, `tests/datagen/test_llm.py`, `tests/datagen/test_llm_ollama.py` (no original packaged templates or generators changed).*

Waived: over budget: 621 added lines > 560 (280 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)
Waived: over budget: 1811 added lines > 760 (380 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)
Waived: over budget: 2432 added lines > 800 (400 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)

Approval standing @local-user (2026-10-20), conditional on total added lines ≤ 5000, all UCs green, zero other unwaived findings. Both reviews APPROVED.

### Limitations and dependencies

- Training-data tooling for LLM data generation only; no model training or model weight publication in this repository.
- Morfeusz 2: BSD 2-Clause license ([Morfeusz License](https://morfeusz.sgjp.pl/doc/license/)).
