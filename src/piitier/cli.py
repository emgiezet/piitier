"""Command-line interface for piitier mask <file>.

Entry point: piitier mask <path> [-o <out>]

Behavior:
- Reads a .txt, .md, or .csv file
- Masks PII using piitier.mask()
- Writes masked content to stdout (default) or file (-o <out>)
- Exit 0 on success, 2 on usage/input error
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path

import piitier
from piitier.loaders import get_loader


def mask_file(input_path: Path, output_path: Path | None) -> int:
    """Mask PII in a file and write output.

    Args:
        input_path: Path to the input file.
        output_path: Path to the output file (None = stdout).

    Returns:
        Exit code: 0 on success, 2 on error.
    """
    # Check if input file exists
    if not input_path.is_file():
        print(f"not found: {input_path}", file=sys.stderr)
        return 2

    # Check if file type is supported
    loader = get_loader(input_path)
    if loader is None:
        print(f"unsupported file type: {input_path.suffix}", file=sys.stderr)
        return 2

    # Load the file
    try:
        text = loader(input_path)
    except FileNotFoundError:
        print(f"not found: {input_path}", file=sys.stderr)
        return 2
    except ValueError as e:
        # Binary file or other file-related error
        print(str(e), file=sys.stderr)
        return 2
    except UnicodeDecodeError as e:
        # Decoding failed (both UTF-8 and cp1250)
        # Extract the error message from the exception
        print(e.reason, file=sys.stderr)
        return 2

    # Mask the content
    masked_text = piitier.mask(text)

    # Write output
    if output_path is None:
        # Write to stdout
        sys.stdout.write(masked_text)
    else:
        # Check if trying to overwrite input file
        if output_path.resolve() == input_path.resolve():
            print(f"refusing to overwrite input: {output_path}", file=sys.stderr)
            return 2

        # Write to file
        output_path.write_text(masked_text, encoding="utf-8")

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
        help="Input file path (.txt, .md, .csv)",
    )
    mask_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        dest="output",
        default=None,
        help="Output file path (default: stdout)",
    )

    args = parser.parse_args()

    if args.command == "mask":
        return mask_file(args.input, args.output)

    return 1


if __name__ == "__main__":
    sys.exit(main())
