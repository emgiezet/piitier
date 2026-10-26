"""Command-line interface for piitier mask <file>.

Entry point: piitier mask <path> [-o <out>] [--model <dir>] [--threshold T]

- Reads a .txt, .md, .csv, or text-layer .pdf file
- Masks PII using piitier.mask() (rules only, default) or
  piitier.Anonymizer (rules + NER when --model is given)
- Writes masked content to stdout (default) or file (-o <out>)
- Exit 0 on success, 2 on usage/input error, 3 on PDF with no text layer
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path

import piitier
from piitier.loaders import PdfNoTextError, get_loader


def mask_file(
    input_path: Path,
    output_path: Path | None,
    model: Path | None = None,
    threshold: float = 0.0,
) -> int:
    """Mask PII in a file and write output.

    Args:
        input_path: Path to the input file.
        output_path: Path to the output file (None = stdout).
        model: Optional path to a local NER checkpoint directory.
        threshold: Minimum NER score; ignored when model is None.

    Returns:
        Exit code: 0 on success, 2 on error.
    """
    # 1. Validate model path (must be an existing directory) BEFORE reading
    #    the input so that nothing is ever written to -o on error (UC-109).
    if model is not None and not model.is_dir():
        print(f"model not found: {model}", file=sys.stderr)
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

    # 5. Mask the content.
    if model is not None:
        # Catch construction and inference errors (empty dir, bad checkpoint,
        # NaN/out-of-range threshold, missing torch/transformers) so that the
        # CLI always exits cleanly without a traceback (finding 3 & 4).
        try:
            anonymizer = piitier.Anonymizer(model=model, threshold=threshold)
            masked_text = anonymizer.mask(text)
        except (OSError, ValueError, ImportError):
            print(f"model error: {model}", file=sys.stderr)
            return 2
    else:
        masked_text = piitier.mask(text)

    # 6. Write output.
    if output_path is None:
        sys.stdout.write(masked_text)
    else:
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

    args = parser.parse_args()

    if args.command == "mask":
        return mask_file(args.input, args.output, args.model, args.threshold)

    return 1


if __name__ == "__main__":
    sys.exit(main())
