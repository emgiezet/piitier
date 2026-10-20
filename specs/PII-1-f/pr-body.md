## PII-1-f — `piitier mask <file>`: CLI for TXT, Markdown and CSV
**QA verdict: PASS** · UC coverage: 8/8 automated · Tests: 118 → 140 · Skipped: 0

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
uv run pytest -q -m "not integration"                # 138 passed, 2 deselected
uv run pytest -q                                    # 140 passed, zero skipped
uv run ruff format --check . && uv run ruff check . # no lint issues
uv run mypy src                                     # no type issues
```

Smoke test scenario:
- `piitier mask test.txt` outputs masked PESEL to stdout
- `piitier mask test.md` preserves Markdown structure byte-for-byte
- `piitier mask test.csv` with CRLF and semicolon delimiter preserved
- `-o out.txt` writes to file; `-o test.txt` refuses with exit 2

### Review here first
- `src/piitier/cli.py:43`: specific decode errors must precede the general ValueError handler.
- `src/piitier/loaders.py:16`: encoding fallback and byte-preserving text loading.
- `tests/test_cli.py:201`: exact stderr and privacy regression for undecodable input.

### Not covered
- Per-column CSV rules (out of scope)
- PDF support (deferred to PII-1-g)
- Directory/batch mode (out of scope)


### Conditional size approval

Waived: over budget: 610 added lines > 520 (260 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing) — Standing owner approval in `.claude/sdlc.md` permits added-line overruns up to 5000, conditional on QA/verification passing, all UCs covered and no other unwaived findings. All changed code/test paths are declared. — @local-user
