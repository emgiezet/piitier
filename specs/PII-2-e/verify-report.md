PASS

## Verification Report: PII-2-e (`write-templates`)

- **Date**: 2026-10-21
- **Observed Commands & Counts**:
  - `uv run pytest -q -m "not integration"`: **389 passed**, 30 deselected (18.13s) — including all 3 UC-31 parameterized cases (8-digit run, PESEL `90051512340`, and 6-digit ID card `ABA300000` exercising `piitier.detect`).
  - `uv run pytest -q tests/datagen/test_llm_ollama.py`: 1 passed (16.68s) against local Ollama with `hf.co/SpeakLeash/Bielik-11B-v3.0-Instruct-GGUF:Q8_0` (digest `bc20c2f093b5aa89222064c5d588c61b5c12f0f7679f8bd2495d5bba4a64dc4c`, prompt hash `272ca1c5d31b10ffc049f0c6ba545ca282ee470c90db32f2d968f0fabaec7c24`), yielding `accepted=1`, `rejected.duplicate=2`, followed by successful dataset build (`n=10`) and offset verification (`check` exit 0).
  - Final Combined Test Suite (`uv run pytest -q`): **463 passed** (0 skips, baseline 377 => +86).
  - Native E: 1811 added lines / 12 files / 2 modules. Combined metrics: 2432 / 20 / 3.
  - Static Analysis: Ruff checks all repository code (117 files PASS); mypy checks `src` (22 src PASS).
- **Security & Robustness Summary**:
  - Whitelisted `doc_type` against 8 packaged prompt names; absolute paths and `../` traversal rejected before I/O or network.
  - Strict loopback host allowlist restricted exactly to `localhost`, `127.0.0.1`, `::1` (`[::1]` is IPv6 URL literal syntax, not a fourth host).
  - Zero-proxy opener (`ProxyHandler({})` and redirect refusal) ignoring proxy environment variables.
  - Strict model identifier string checks and nonempty string digest validation.
  - Manifest persistence as a JSON array with strict JSON parsing and blank/whitespace rejection preserving original bytes.
  - Support for all 15 supported labels (including person and address groups via `_SUPPORTED_LABELS`).
  - Safe failure on non-string API responses.
