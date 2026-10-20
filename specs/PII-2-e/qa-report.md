# QA Report: PII-2-e (`write-templates`)

## Verdict
**PASS**

## Use Case (UC) × Test Coverage Matrix

| id | actor | action | expected observable result | test function | verdict |
|----|-------|--------|----------------------------|---------------|---------|
| UC-30 | data author | `write-templates --count 1` against fake server returning valid 4-placeholder `zgloszenie_szkody` template | exit 0; one file in `<out>/zgloszenie_szkody/`; manifest `accepted=1` | `test_uc30_valid_template_accepted_and_written` | PASS |
| UC-31 | data author | fake returns text with 8-digit run, leaked PESEL value `90051512340`, or ID card `ABA300000` exercising `piitier.detect` | not written across all 3 parameterized leak cases; manifest `rejected.leaked_value=1` | `test_uc31_leaked_value_rejected` (parameterized over 3 cases) | PASS |
| UC-32 | data author | fake returns `{{FOO}}`, and separately a template with 2 placeholders | not written; `rejected.unknown_label=1`, `rejected.too_few_placeholders=1` | `test_uc32_unknown_label_and_too_few_placeholders` | PASS |
| UC-33 | data author | fake returns same valid template twice with `--count 2` | one file written; `rejected.duplicate=1` | `test_uc33_duplicate_rejected` | PASS |
| UC-34 | data author | `--ollama-url http://192.168.1.5:11434` | exit 2; stderr `refusing non-loopback ollama url`; fake server received no request | `test_uc34_nonloopback_url_raises_before_any_request`, `test_uc34_cli_exits_2_for_nonloopback_url` | PASS |
| UC-35 | data author | `--ollama-url http://127.0.0.1:<closed port>` | exit 3; stderr `ollama not reachable at <url>` | `test_uc35_unreachable_ollama_raises`, `test_uc35_cli_exits_3_when_ollama_unreachable` | PASS |
| UC-36 | data author | read `manifest.json` after UC-30 | holds model tag, model digest, prompt sha256, temperature and seed exactly as sent | `test_uc36_manifest_contains_exact_fields` | PASS |
| UC-37 | data author | real Ollama with Bielik 11B Q8_0: `write-templates --doc-type zgloszenie_szkody --count 3`, then `build --templates <out> --n 10` | at least 1 accepted template (manifest checked `accepted >= 1`); `build` and `check` exit 0 | `test_uc37_real_ollama_cli_workflow` | PASS |

## Observed Verification Results
- Non-integration test selection (`uv run pytest -q -m "not integration"`): **389 passed**, 30 deselected (18.13s).
- Real UC-37 GPU integration test (`uv run pytest -q tests/datagen/test_llm_ollama.py`) against local Ollama with Bielik 11B Q8_0 (`count=3`, `seed=42`, `temperature=0.2`) produced `accepted=1`, `rejected.duplicate=2`, followed by successful dataset build (`n=10`) and offset verification (`check` exit 0).
- Final combined test suite (`uv run pytest -q`): **463 passed** (0 skips, baseline 377 => +86). Native E: 1811 added lines / 12 files / 2 modules. Combined metrics: 2432 / 20 / 3.
- Static analysis (Ruff across 117 files, mypy on 22 src) passes cleanly.
