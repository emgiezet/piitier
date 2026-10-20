# QA Report — PII-1-f

## Verdict: PASS

Every UC has a passing test carrying its id. All tests pass. Zero findings.

## UC Coverage Map

| UC | actor | use case | automated test | status |
|----|-------|----------|---|---|
| UC-28 | developer | `piitier mask in.txt` → stdout | `test_uc28_mask_txt_stdout` | ✓ |
| UC-29 | developer | `piitier mask in.md` preserves Markdown | `test_uc29_mask_md_preserves_structure` | ✓ |
| UC-30 | developer | `piitier mask in.csv` with CRLF, semicolon | `test_uc30_mask_csv_preserves_format` | ✓ |
| UC-33 | developer | `-o out.txt` writes to file; refuses `-o in.txt` | `test_uc33_mask_with_output_file`, `test_uc33_refuse_overwrite_input` | ✓ |
| UC-34 | developer | unsupported `.docx`; missing file | `test_uc34_unsupported_file_type`, `test_uc34_missing_file` | ✓ |
| UC-35 | developer | invalid UTF-8/cp1250; stderr no PESEL | `test_uc35_invalid_utf8_undefined_cp1250` | ✓ |
| UC-40 | developer | cp1250-encoded `.csv` → UTF-8 | `test_uc40_mask_cp1250_csv` | ✓ |
| UC-41 | developer | NUL byte in first 4096 bytes | `test_uc41_binary_file_with_nul_byte` | ✓ |

All UCs present: 8/8 automated. All passing.

## Suite output

**Unit & Integration Tests:**
```
140 passed in 1.40s
```

- `tests/test_cli.py`: 10 tests for PII-1-f CLI functionality (8 UC tests + 2 fixtures)
- `tests/test_loaders.py`: 13 tests for file loading and encoding detection (7 UC-adjacent + 6 registry)
- Existing tests for API, rules, render, spans, labels: 117 tests (unchanged, passing)
- Skipped: 0
- Integration: 2 (UC-40 marked as integration due to detector model load)

**Verification run evidence:**

Smoke tests confirmed:
- UC-28: `piitier mask test.txt` outputs masked PESEL to stdout, exit 0 ✓
- UC-29: Markdown structure byte-for-byte preserved, only PESEL replaced ✓
- UC-30: CSV CRLF and semicolon delimiter preserved ✓
- UC-33: `-o out.txt` writes to file, no stdout ✓
- UC-33: `-o test.txt` refuses, exit 2, stderr "refusing to overwrite input: test.txt" ✓
- UC-34: `.docx` file exists, stderr "unsupported file type: .docx", exit 2 ✓
- UC-34: `missing.txt` not found, stderr "not found: missing.txt", exit 2 ✓
- UC-35: Invalid bytes `0x81 0x98` → exit 2, stderr message contains path, no PESEL leaked ✓
- UC-40: cp1250-encoded file read; output UTF-8 "Łódź;[PESEL]" ✓
- UC-41: NUL byte in first 4096 → exit 2, stderr "binary content: <path>" ✓

## Findings

None. Implementation matches spec exactly.

## Not verified

- Per-column CSV rules (deferred to PII-1-h as per spec scope)
- PDF support (deferred to PII-1-g as per spec scope)
- Directory/batch mode (out of scope)
- `--mode pseudonymize` (out of scope)
- JSON span output (out of scope)
- PyPI, Docker, gateway packaging (out of scope)
