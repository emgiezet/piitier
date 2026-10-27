"""Command-line interface for piitier.

Entry points:

- ``piitier mask <path> [-o <out>] [--model <dir>] [--threshold T]``
  ``[--skip-columns COLS] [--delimiter CHAR]`` reads a .txt, .md, .csv or text-layer .pdf
  file and masks PII with ``piitier.mask()`` (rules only, default) or ``piitier.Anonymizer``
  (rules + NER when --model is given). Selected CSV columns remain unmasked.
  Exit 0 on success, 2 on usage/input error, 3 on a PDF with no text layer.
- ``piitier compare <path> --model <dir> [--threshold T] [--device cpu|cuda]`` opens
  a local two-pane TUI to inspect replacements without printing the document.
- ``piitier scan [--allowlist F] [--write-allowlist F] <path>...`` reports checksum-valid
  identifiers as ``path:line:column: LABEL`` (never the value). Exit 0 when nothing outside the
  allowlist is found, 1 when something is, 2 on a missing path or allowlist.
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path

import piitier
from piitier.csvskip import parse_csv_field_ranges, sniff_delimiter
from piitier.loaders import PdfNoTextError, get_loader
from piitier.scan import Finding, read_allowlist, scan_file


def mask_file(
    input_path: Path,
    output_path: Path | None,
    model: Path | None = None,
    threshold: float = 0.0,
    skip_columns: list[str] | None = None,
    delimiter: str | None = None,
) -> int:
    """Mask PII in a file and write output.

    Args:
        input_path: Path to the input file.
        output_path: Path to the output file (None = stdout).
        model: Optional path to a local NER checkpoint directory.
        threshold: Minimum NER score; ignored when model is None.
        skip_columns: CSV header names or 1-based indices to leave unmasked.
        delimiter: Optional single-character CSV delimiter.

    Returns:
        Exit code: 0 on success, 2 on error.
    """
    # 1. Validate model path (must be an existing directory) BEFORE reading
    #    the input so that nothing is ever written to -o on error (UC-109).
    if model is not None and not model.is_dir():
        print(f"model not found: {model}", file=sys.stderr)
        return 2
    # `not (0 <= t <= 1)` is also True for NaN, which fails every comparison.
    if model is not None and not (0.0 <= threshold <= 1.0):
        print(f"invalid threshold: {threshold} (expected a number in [0, 1])", file=sys.stderr)
        return 2
    if input_path.suffix.lower() != ".csv":
        if skip_columns:
            print(f"--skip-columns is only supported for .csv files: {input_path}", file=sys.stderr)
            return 2
        if delimiter is not None:
            print(f"--delimiter is only supported for .csv files: {input_path}", file=sys.stderr)
            return 2
    if delimiter is not None and not skip_columns:
        print("cannot use --delimiter without --skip-columns", file=sys.stderr)
        return 2
    if delimiter is not None and len(delimiter) != 1:
        print(f"invalid delimiter: {delimiter!r} (must be exactly 1 character)", file=sys.stderr)
        return 2

    # 2. Refuse to overwrite input with output — check early, before model
    #    load, so a bad --model never writes partial output (NIT finding 8).
    if output_path is not None and output_path.resolve() == input_path.resolve():
        print(f"refusing to overwrite input: {output_path}", file=sys.stderr)
        return 2

    # 3. Check input file exists and is a supported type.
    if not input_path.is_file():
        print(f"not found: {input_path}", file=sys.stderr)
        return 2

    loader = get_loader(input_path)
    if loader is None:
        print(f"unsupported file type: {input_path.suffix}", file=sys.stderr)
        return 2

    # 4. Load the file text.
    try:
        text = loader(input_path)
    except FileNotFoundError:
        print(f"not found: {input_path}", file=sys.stderr)
        return 2
    except UnicodeDecodeError as e:
        print(e.reason, file=sys.stderr)
        return 2
    except PdfNoTextError as e:
        print(str(e), file=sys.stderr)
        return 3
    except ValueError as e:
        # Binary file, encrypted PDF, or other file-related error
        print(str(e), file=sys.stderr)
        return 2

    if skip_columns and any("," in item for item in skip_columns):
        rows = parse_csv_field_ranges(text, delimiter or sniff_delimiter(text)).rows
        headers = {cell.value.strip().casefold() for cell in rows[0]} if rows else set()
        skip_columns = [
            token.strip()
            for item in skip_columns
            for token in ([item] if item.casefold() in headers else item.split(","))
            if token.strip()
        ]

    # 5. Mask the content.
    def warn_unknown(col: str) -> None:
        print(f"warning: unknown column: {col}", file=sys.stderr)

    if model is not None:
        # Catch model construction and inference errors without a traceback.
        try:
            anonymizer = piitier.Anonymizer(model=model, threshold=threshold)
            if skip_columns:
                masked_text = piitier.mask_csv(
                    text,
                    skip_columns=skip_columns,
                    delimiter=delimiter,
                    detector=anonymizer.detect,
                    on_unknown_column=warn_unknown,
                )
            else:
                masked_text = anonymizer.mask(text)
        except (OSError, ValueError, ImportError):
            print(f"model error: {model}", file=sys.stderr)
            return 2
    elif skip_columns:
        masked_text = piitier.mask_csv(
            text,
            skip_columns=skip_columns,
            delimiter=delimiter,
            detector=piitier.detect,
            on_unknown_column=warn_unknown,
        )
    else:
        masked_text = piitier.mask(text)

    # 6. Write output.
    if output_path is None:
        sys.stdout.write(masked_text)
    else:
        output_path.write_text(masked_text, encoding="utf-8")

    return 0


def scan_files(paths: list[Path], allowlist: Path | None, write_allowlist: Path | None) -> int:
    """Scan *paths* for checksum-valid identifiers; see the module docstring for exit codes."""
    allowed: frozenset[str] = frozenset()
    if allowlist is not None:
        if not allowlist.is_file():
            print(f"allowlist not found: {allowlist}", file=sys.stderr)
            return 2
        allowed = read_allowlist(allowlist)

    findings: list[Finding] = []
    for path in paths:
        if not path.is_file():
            print(f"not found: {path}", file=sys.stderr)
            return 2
        found = scan_file(path)
        if found is not None:
            findings.extend(found)

    if write_allowlist is not None:
        fingerprints = sorted({f.fingerprint for f in findings} | allowed)
        header = '# sha256("<LABEL>:<value>") of synthetic identifiers allowed in this repo.\n'
        write_allowlist.write_text(header + "".join(fp + "\n" for fp in fingerprints), "utf-8")
        return 0

    unexpected = [f for f in findings if f.fingerprint not in allowed]
    for f in unexpected:
        print(f"{f.path}:{f.line}:{f.column}: {f.label.name}")
    if unexpected:
        print(
            f"{len(unexpected)} checksum-valid identifier(s) not in the allowlist. If they are "
            "synthetic, add them with --write-allowlist; real data must not be committed.",
            file=sys.stderr,
        )
        return 1
    return 0


def main() -> int:
    """Main entry point for the piitier CLI."""
    parser = ArgumentParser(
        prog="piitier",
        description="Polish PII anonymiser",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # mask subcommand
    mask_parser = subparsers.add_parser(
        "mask",
        help="Mask PII in a file",
    )
    mask_parser.add_argument(
        "input",
        type=Path,
        help="Input file path (.txt, .md, .csv, .pdf)",
    )
    mask_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        dest="output",
        default=None,
        help="Output file path (default: stdout)",
    )
    mask_parser.add_argument(
        "--model",
        type=Path,
        dest="model",
        default=None,
        help="Path to a local NER checkpoint directory (enables rule+NER fusion)",
    )
    mask_parser.add_argument(
        "--threshold",
        type=float,
        dest="threshold",
        default=0.0,
        help="Minimum NER span score to keep (default: 0.0); ignored without --model",
    )
    mask_parser.add_argument(
        "--skip-columns",
        action="append",
        default=None,
        metavar="COLS",
        help="Comma-separated column names or 1-based indices to leave unmasked (CSV only)",
    )
    mask_parser.add_argument(
        "--delimiter",
        type=str,
        default=None,
        metavar="CHAR",
        help="CSV field delimiter override, e.g. ';' or ',' (CSV only; default: auto-detected)",
    )

    compare_parser = subparsers.add_parser(
        "compare",
        help="Inspect original and anonymized text side by side in a terminal",
    )
    compare_parser.add_argument("input", type=Path, help="Input file (.txt, .md, .csv, .pdf)")
    compare_parser.add_argument("--model", type=Path, required=True, help="Local NER checkpoint")
    compare_parser.add_argument("--threshold", type=float, default=0.0, help="Minimum NER score")
    compare_parser.add_argument("--device", default="cpu", help="Torch device (cpu or cuda)")

    scan_parser = subparsers.add_parser(
        "scan",
        help="Report checksum-valid identifiers by position (never by value)",
    )
    scan_parser.add_argument("paths", type=Path, nargs="+", help="Files to scan")
    scan_parser.add_argument(
        "--allowlist",
        type=Path,
        default=None,
        help="File of allowed fingerprints (sha256 of '<LABEL>:<value>'), one per line",
    )
    scan_parser.add_argument(
        "--write-allowlist",
        type=Path,
        dest="write_allowlist",
        default=None,
        help="Write the fingerprints of every finding (plus --allowlist entries) and exit 0",
    )

    args = parser.parse_args()

    if args.command == "mask":
        skip_columns = (
            [item.strip() for item in args.skip_columns if item.strip()]
            if args.skip_columns is not None
            else None
        )
        delimiter = "\t" if args.delimiter == "\\t" else args.delimiter
        return mask_file(
            args.input, args.output, args.model, args.threshold, skip_columns, delimiter
        )
    if args.command == "scan":
        return scan_files(args.paths, args.allowlist, args.write_allowlist)
    if args.command == "compare":
        from piitier.tui import compare_file

        return compare_file(args.input, args.model, args.threshold, args.device)

    return 1


if __name__ == "__main__":
    sys.exit(main())
