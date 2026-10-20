"""CLI entry point: ``python -m piitier.datagen``.

Commands
--------
build --templates <dir> --n <N> --seed <S> --out <dir>
    Render N synthetic documents and write train.jsonl, dev.jsonl, manifest.json.

check <dir>
    Re-verify every span's offsets.  Exit 0 if all correct; exit 1 naming the
    first bad document id (no document text in output).

Exit codes
----------
0  success
1  check found a bad span
2  output directory is inside bench/ or already non-empty
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from piitier.datagen.build import _PACKAGED_TEMPLATES_DIR, BuildError, build, check

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

    # -- check ---------------------------------------------------------------
    check_p = sub.add_parser("check", help="Verify span offsets in a built dataset.")
    check_p.add_argument("data_dir", type=Path, metavar="DIR", help="Directory with JSONL files.")

    args = parser.parse_args()

    if args.command == "build":
        try:
            build(args.templates, args.n, args.seed, args.out)
        except BuildError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(2)

    elif args.command == "check":
        code, msg = check(args.data_dir)
        if msg:
            print(msg, file=sys.stderr)
        sys.exit(code)


if __name__ == "__main__":
    main()
