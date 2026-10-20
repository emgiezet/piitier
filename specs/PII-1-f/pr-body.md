## PII-1-f — `piitier mask <file>`: CLI for TXT, Markdown and CSV
**QA verdict: PASS** · UC coverage: 8/8 automated · Tests: 140 → 148 · Skipped: 0

🤖 Written by an agent from `specs/PII-1-f/spec.md`. Review the spec's `Out:` scope first —
that is where an unattended run is most likely to have overstepped.

### What the spec asked for

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-28 | developer | `piitier mask in.txt` | stdout is `piitier.mask(<file text>)` exactly; exit 0 | integration |
| UC-29 | developer | `piitier mask in.md` containing headings, a table and a code block | Markdown markup unchanged byte for byte; only the PESEL replaced; exit 0 | integration |
| UC-30 | developer | `piitier mask in.csv` with `;` delimiter, quoted fields and CRLF line endings | same row count, delimiter, quoting and CRLF; the PESEL cell becomes `[PESEL]`; exit 0 | integration |
| UC-33 | developer | `piitier mask in.txt -o out.txt` | `out.txt` holds the masked text; stdout empty; exit 0. With `-o in.txt`: exit 2, stderr `refusing to overwrite input: in.txt`, the input file unchanged *(added)* | integration |
| UC-34 | developer | `piitier mask in.docx`; `piitier mask missing.txt` | exit 2; stderr `unsupported file type: .docx` / `not found: missing.txt`; stdout empty *(added)* | integration |
| UC-35 | developer | `piitier mask` on a `.txt` holding `90051512340` followed by bytes `0x81 0x98` (invalid UTF-8, undefined in cp1250) | exit 2; stderr `cannot decode: <path>`; stdout empty; `90051512340` absent from stderr *(added)* | integration |
| UC-40 | developer | `piitier mask` on a cp1250-encoded `.csv` containing `Łódź;90051512340` | stdout is UTF-8 `Łódź;[PESEL]`; exit 0 *(added from prior art)* | integration |
| UC-41 | developer | `piitier mask` on a `.txt` with a NUL byte in its first 4096 bytes | exit 2; stderr `binary content: <path>`; stdout empty *(added from prior art)* | integration |

### How to verify
```bash
uv run pytest -q -m "not integration"              # 140 passing
uv run pytest -q                                    # 148 passing (integration tests included)
uv run ruff format --check . && uv run ruff check . # no lint issues
uv run mypy src                                     # no type issues
```

Smoke test scenario:
- `piitier mask test.txt` outputs masked PESEL to stdout
- `piitier mask test.md` preserves Markdown structure byte-for-byte
- `piitier mask test.csv` with CRLF and semicolon delimiter preserved
- `-o out.txt` writes to file; `-o test.txt` refuses with exit 2

### Review here first
- `src/piitier/cli.py` (39 lines): entry point for the `piitier mask <file>` command; encoding detection and loader dispatch
- `src/piitier/loaders.py` (68 lines): registry pattern for file type handlers; TXT/Markdown/CSV loaders share the text→mask→text pipeline
- `tests/test_cli.py`: 10 tests including 8 UC tests plus 2 fixtures; coverage of edge cases (missing files, unsupported types, encoding errors)

### Not covered
- Per-column CSV rules (deferred to PII-1-h)
- PDF support (deferred to PII-1-g)
- Directory/batch mode (out of scope)

