"""CLI entry point: ``python -m piitier.datagen``.

Commands
--------
build --templates <dir> --n <N> --seed <S> --out <dir>
    Render N synthetic documents and write train.jsonl,
    dev.jsonl, manifest.json.

check <dir>
    Re-verify every span's offsets. Exit 0 if all correct;
    exit 1 naming first bad document id.

write-templates --doc-type <t> --count <N> --out <dir> ...
    Write synthetic templates using local Ollama model.

Exit codes
----------
0  success
1  check found a bad span
2  output directory is inside bench/ or already non-empty / URL error
3  Ollama unreachable
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from piitier.datagen.build import _PACKAGED_TEMPLATES_DIR, BuildError, build, check
from piitier.datagen.llm import OllamaUnreachableError, OllamaURLError, write_templates

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m piitier.datagen",
        description="Synthetic dataset builder for piitier.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- build ---------------------------------------------------------------
    build_p = sub.add_parser("build", help="Build JSONL dataset from templates.")
    build_p.add_argument(
        "--templates",
        type=Path,
        default=_PACKAGED_TEMPLATES_DIR,
        metavar="DIR",
        help="Template directory tree (default: packaged templates).",
    )
    build_p.add_argument("--n", type=int, required=True, metavar="N", help="Document count.")
    build_p.add_argument("--seed", type=int, required=True, metavar="S", help="Base RNG seed.")
    build_p.add_argument(
        "--out",
        type=Path,
        required=True,
        metavar="DIR",
        help="Output directory (must not exist or must be empty; must not be inside bench/).",
    )
    build_p.add_argument(
        "--augment",
        action="store_true",
        help="Apply OCR and diacritic augmentation to documents.",
    )
    build_p.add_argument(
        "--hard-negatives",
        type=int,
        default=0,
        metavar="N",
        help="Number of hard negative documents to add.",
    )

    # -- check ---------------------------------------------------------------
    check_p = sub.add_parser("check", help="Verify span offsets in a built dataset.")
    check_p.add_argument("data_dir", type=Path, metavar="DIR", help="Directory with JSONL files.")

    # -- write-templates -----------------------------------------------------
    wt_p = sub.add_parser(
        "write-templates", help="Write synthetic templates using local Ollama model."
    )
    wt_p.add_argument("--doc-type", required=True, help="Document type.")
    wt_p.add_argument("--count", type=int, required=True, help="Number of attempts/templates.")
    wt_p.add_argument("--out", type=Path, required=True, help="Output directory.")
    wt_p.add_argument(
        "--model", default="hf.co/SpeakLeash/Bielik-11B-v3.0-Instruct-GGUF:Q8_0", help="Model tag."
    )
    wt_p.add_argument("--ollama-url", default="http://127.0.0.1:11434", help="Ollama URL.")
    wt_p.add_argument("--seed", type=int, default=None, help="RNG seed.")
    wt_p.add_argument("--temperature", type=float, default=0.2, help="Temperature.")

    args = parser.parse_args()

    if args.command == "build":
        try:
            build(
                args.templates,
                args.n,
                args.seed,
                args.out,
                augment=args.augment,
                hard_negatives=args.hard_negatives,
            )
        except BuildError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(2)
    elif args.command == "check":
        code, msg = check(args.data_dir)
        if msg:
            print(msg, file=sys.stderr)
        sys.exit(code)

    elif args.command == "write-templates":
        try:
            write_templates(
                doc_type=args.doc_type,
                count=args.count,
                out=args.out,
                model=args.model,
                ollama_url=args.ollama_url,
                seed=args.seed,
                temperature=args.temperature,
            )
        except OllamaURLError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(2)
        except OllamaUnreachableError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(3)
        except (ValueError, FileExistsError, FileNotFoundError) as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(2)


if __name__ == "__main__":
    main()
