# piitier command-line reference

Every subcommand, option and exit code. The [README](../README.md) covers the common paths; this page is the contract.

## Subcommands and exit codes

```bash
piitier --version
piitier mask document.pdf                                        # rules only; .txt .md .csv .json .pdf (text layer)
piitier mask document.pdf -o out.txt --model <checkpoint-dir> --threshold 0.78
piitier mask document.pdf --model emgiezet/piitier --revision <sha> --threshold 0.78  # Hub repo id
piitier mask customers.csv --skip-columns "ID,2"                 # keep columns by header name or 1-based index
piitier mask customers.csv --skip-columns "ID" --delimiter ";"   # override delimiter auto-detection
piitier compare claims.csv --model <checkpoint-dir> --device cuda  # interactive TUI: pick columns, mask, export
piitier compare claims.csv --model emgiezet/piitier --revision <sha>  # Hub repo id form
piitier scan src/ docs/                                          # list checksum-valid identifiers, never their values
piitier scan src/ --write-allowlist .pii-allowlist               # write all fingerprints and exit 0
```

- `mask` writes the masked document. Exit 0 on success; exit 2 on a usage or input error (missing
  file, unsupported type, invalid threshold, model download failure); exit 3 when the input PDF has
  no text layer. Error messages name the path, never the document content.
- `compare` opens a side-by-side terminal view. For CSV it shows a table preview with per-column
  checkboxes (all masked by default), then lets you export next to the source without overwriting
  existing files. `--model` accepts a local directory or a Hugging Face Hub repo id; `--revision`
  pins a Hub branch, tag, or commit hash.
- `scan` prints `path:line:column: LABEL` for every checksum-valid identifier. Exit 0 when nothing
  outside the allowlist is found; exit 1 when unallowlisted identifiers are present; exit 2 on a
  missing path or missing allowlist file. `--write-allowlist <file>` writes fingerprints of all
  findings (merged with any existing allowlist) and exits 0 without printing findings. Run as a
  pre-commit hook to gate your own repository.

## JSON documents

`mask`, `mask-batch` and `compare` accept `.json` files (case-insensitive):

```bash
piitier mask record.json -o masked.json
piitier mask record.json -o masked.json --model <checkpoint-dir> --threshold 0.78
piitier compare record.json --model <checkpoint-dir>
```

Only **string values** are anonymised, including nested object/array values and a
top-level string. Detection sees decoded characters, so Unicode-escaped identifiers
are masked too. Keys, numbers, booleans and null remain unchanged: identifiers stored
as JSON numbers or object keys are **not anonymised**. Store sensitive identifiers in
string values when using this mode.

Replacements are applied to the original serialization, not to a re-encoded object.
Whitespace, CRLF, key order, duplicate keys, numeric spelling and escapes outside
replacements remain intact. Model-backed entity numbering is shared across values
within one document and resets for the next document. `compare` uses the existing
before/after panes and navigation; CSV-specific column selection/export is unchanged.

Input must be one valid UTF-8 JSON document; an optional leading UTF-8 BOM is retained.
Malformed JSON, invalid UTF-8 and non-JSON constants such as `NaN`/`Infinity` fail safely,
without echoing input. Single-file failures exit 2 before model loading or output
creation; batch failures affect only that file. JSONL, comments, field selectors and
machine-readable detection reports are not part of this input mode.

## Password-protected PDFs

`mask` accepts RC4, AES-128 and AES-256 PDFs with a user or owner password. Without a
credential it first tries the empty password, then offers up to three hidden attempts
when stdin and stderr are terminals:

```bash
piitier mask locked.pdf -o masked.txt
piitier mask locked.pdf --password-stdin -o masked.txt
```

`--password-stdin` reads one line, removing only its LF/CRLF terminator. A blank line is
an empty password; EOF is an input error. It never prompts. `--password VALUE` is also
available, but exposes the argument in process listings and shell history. The options
are mutually exclusive and PDF-only. No passwords or decrypted intermediate PDFs are
saved. Missing/wrong credentials exit 2 without creating or truncating the output;
authenticated PDFs without a text layer exit 3. EOF cancels entry; Ctrl-C exits 130.

Output is masked extracted text, not a redacted or encrypted PDF. Scanned PDFs still
require a text layer; this workflow does not perform OCR.

`compare locked.pdf --model <checkpoint-dir>` opens a masked password dialog before
loading the model or showing the existing comparison panes. Enter/Unlock submits the
exact value (including empty); Escape/Cancel exits 2. It requires terminal stdin and
stdout for credential entry, permits three attempts, and retains no password history.
If authentication is required without both terminals, `compare` exits 2 without
opening a dialog or loading the model.

## Directory batches

```bash
piitier mask-batch ./inputs -o ./masked --passwords ./inputs/passwords.csv
piitier mask-batch ./inputs -o ./masked --model <checkpoint-dir> --threshold 0.78
```

`--passwords` is optional. Its CSV must be UTF-8 (optional BOM) with exactly the header
`filename,password` or `filename;password`. Filenames are case-sensitive basenames,
not paths, and cannot repeat. Standard CSV quoting preserves punctuation, whitespace,
embedded newlines and empty passwords. Blank records are ignored; a header-only map
is valid. Invalid records fail before processing and report only the map path/line.
Treat the mapping as a secret file; never commit it.

Batch processes supported regular files once in filename order, without recursion.
The mapping file and its resolved aliases are excluded, even inside inputs.
Text and JSON filenames are retained; PDFs become `.txt`. Outputs must be outside the input
directory, and existing files/symlinks or earlier colliding outputs are never overwritten.
Each output is created only after extraction and masking succeed.

Model options match `mask`, including `--revision`; one model instance is reused while
numbering stays document-local. CSV inputs are masked as whole documents (no column
selection in batch). Missing/wrong passwords can be corrected through hidden terminal
entry; EOF fails only that file. Other per-file failures also allow later files to run.
Ctrl-C exits 130, preserves completed outputs and removes the active partial write.
Stdout remains empty. Stderr ends with `batch: N masked, M failed`; exit 0 means all
selected files succeeded (including empty selection), 4 means per-file failures, and 2
means invalid configuration or initial model failure.

