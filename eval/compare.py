"""Compare two eval JSON reports and flag recall regressions.

Usage::

    uv run python -m eval.compare BASE.json NEW.json [--threshold 0.02]

Exits 1 when any label in the comparable subset loses more than *threshold*
recall (strict) relative to the base report.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers (pure, no I/O — easy to unit-test)
# ---------------------------------------------------------------------------


def _prf_entry(by_label: dict[str, object], label: str) -> tuple[float, float, float]:
    """Return (precision, recall, f1) for *label* from a strict_by_label dict.

    Missing labels are treated as (0, 0, 0) — they had no gold or pred spans.
    """
    raw = by_label.get(label, None)
    if not isinstance(raw, dict):
        return 0.0, 0.0, 0.0
    return float(raw.get("p", 0.0)), float(raw.get("r", 0.0)), float(raw.get("f1", 0.0))


def _micro_entry(report: dict[str, object], key: str) -> tuple[float, float, float]:
    """Extract micro (p, r, f1) from a nested dict under *key* in *report*."""
    m = report.get(key)
    if not isinstance(m, dict):
        return 0.0, 0.0, 0.0
    return float(m.get("p", 0.0)), float(m.get("r", 0.0)), float(m.get("f1", 0.0))


# ---------------------------------------------------------------------------
# Core comparison logic
# ---------------------------------------------------------------------------


def compare_reports(
    base: dict[str, object],
    new: dict[str, object],
    threshold: float = 0.02,
) -> tuple[str, bool]:
    """Compare two deserialized JSON reports.

    Returns:
        (markdown_output, regression_detected)

    A *regression* is defined as any label in the comparable subset losing more
    than *threshold* recall (strict) relative to the base report.
    """
    comparable_raw = base.get("comparable_labels", [])
    comparable_set: frozenset[str] = (
        frozenset(comparable_raw) if isinstance(comparable_raw, list) else frozenset()
    )

    base_by_label = base.get("strict_by_label", {})
    new_by_label = new.get("strict_by_label", {})
    base_by_label = base_by_label if isinstance(base_by_label, dict) else {}
    new_by_label = new_by_label if isinstance(new_by_label, dict) else {}
    all_labels = sorted(set(base_by_label) | set(new_by_label))

    lines: list[str] = []

    # ----------------------------------------------------------------
    # Header: comparable-subset micro summary
    # ----------------------------------------------------------------
    lines.append("## Comparable-Subset Micro (strict)")
    lines.append("")
    lines.append("| | Base P | Base R | Base F1 | New P | New R | New F1 |")
    lines.append("|---|---|---|---|---|---|---|")

    bp, br, bf = _micro_entry(base, "comparable_strict_micro")
    np_, nr, nf = _micro_entry(new, "comparable_strict_micro")
    lines.append(f"| strict | {bp:.4f} | {br:.4f} | {bf:.4f} | {np_:.4f} | {nr:.4f} | {nf:.4f} |")

    bpp, brp, bfp = _micro_entry(base, "comparable_partial_micro")
    npp, nrp, nfp = _micro_entry(new, "comparable_partial_micro")
    lines.append(
        f"| partial | {bpp:.4f} | {brp:.4f} | {bfp:.4f} | {npp:.4f} | {nrp:.4f} | {nfp:.4f} |"
    )

    # ----------------------------------------------------------------
    # Per-label table
    # ----------------------------------------------------------------
    lines.extend(
        [
            "",
            "## Per-Label Comparison (strict)",
            "",
            "| Label | Base P | New P | ΔP | Base R | New R | ΔR | "
            "Base F1 | New F1 | ΔF1 | Status |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
    )

    regression = False
    regressions: list[str] = []

    for label in all_labels:
        bp_l, br_l, bf_l = _prf_entry(base_by_label, label)
        np_l, nr_l, nf_l = _prf_entry(new_by_label, label)

        dp = np_l - bp_l
        dr = nr_l - br_l
        df1 = nf_l - bf_l

        in_comparable = label in comparable_set

        if in_comparable and dr < -threshold:
            regression = True
            regressions.append(label)
            status = "REGRESSION"
        elif in_comparable:
            status = "ok"
        else:
            status = ""

        lines.append(
            f"| {label} | {bp_l:.4f} | {np_l:.4f} | {dp:+.4f} | "
            f"{br_l:.4f} | {nr_l:.4f} | {dr:+.4f} | "
            f"{bf_l:.4f} | {nf_l:.4f} | {df1:+.4f} | {status} |"
        )

    # ----------------------------------------------------------------
    # Per-doc_type table
    # ----------------------------------------------------------------
    base_by_dt = base.get("by_doc_type", {})
    new_by_dt = new.get("by_doc_type", {})
    base_by_dt = base_by_dt if isinstance(base_by_dt, dict) else {}
    new_by_dt = new_by_dt if isinstance(new_by_dt, dict) else {}
    all_dt = sorted(set(base_by_dt) | set(new_by_dt))

    if all_dt:
        lines.extend(
            [
                "",
                "## Per-Doc-Type Comparison (strict micro)",
                "",
                "| Doc Type | Base P | New P | ΔP | Base R | New R | ΔR | Base F1 | New F1 | ΔF1 |",
                "|---|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for dt in all_dt:
            base_dt = base_by_dt.get(dt, {})
            new_dt = new_by_dt.get(dt, {})
            base_dt = base_dt if isinstance(base_dt, dict) else {}
            new_dt = new_dt if isinstance(new_dt, dict) else {}

            def _sm(d: dict[str, object]) -> tuple[float, float, float]:
                sm = d.get("strict_micro", {})
                sm = sm if isinstance(sm, dict) else {}
                return float(sm.get("p", 0.0)), float(sm.get("r", 0.0)), float(sm.get("f1", 0.0))

            bm = _sm(base_dt)
            nm = _sm(new_dt)
            dp = nm[0] - bm[0]
            dr = nm[1] - bm[1]
            df1 = nm[2] - bm[2]
            lines.append(
                f"| {dt} | {bm[0]:.4f} | {nm[0]:.4f} | {dp:+.4f} | "
                f"{bm[1]:.4f} | {nm[1]:.4f} | {dr:+.4f} | "
                f"{bm[2]:.4f} | {nm[2]:.4f} | {df1:+.4f} |"
            )

    # ----------------------------------------------------------------
    # Leak rate comparison
    # ----------------------------------------------------------------
    base_lr = base.get("leak_rate")
    new_lr = new.get("leak_rate")
    if isinstance(base_lr, dict) or isinstance(new_lr, dict):
        base_lr = base_lr if isinstance(base_lr, dict) else {}
        new_lr = new_lr if isinstance(new_lr, dict) else {}
        lines.extend(
            [
                "",
                "## Leak Rate",
                "",
                "| | Docs Leaked | Values Leaked |",
                "|---|---|---|",
                (
                    f"| Base | {base_lr.get('docs_leaked', 0)}/{base_lr.get('docs_total', 0)} | "
                    f"{base_lr.get('values_leaked', 0)}/{base_lr.get('values_total', 0)} |"
                ),
                (
                    f"| New  | {new_lr.get('docs_leaked', 0)}/{new_lr.get('docs_total', 0)} | "
                    f"{new_lr.get('values_leaked', 0)}/{new_lr.get('values_total', 0)} |"
                ),
            ]
        )

    # ----------------------------------------------------------------
    # Verdict
    # ----------------------------------------------------------------
    lines.append("")
    if regression:
        reg_str = ", ".join(regressions)
        lines.append(
            f"REGRESSION DETECTED — labels with >{threshold:.2f} recall drop "
            f"in comparable subset: {reg_str}"
        )
    else:
        lines.append(
            f"No recall regression detected in comparable subset (threshold {threshold:.2f})."
        )

    return "\n".join(lines), regression


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Main entry point: compare two JSON eval reports."""
    parser = argparse.ArgumentParser(
        description="Compare two eval JSON reports and flag recall regressions."
    )
    parser.add_argument("base", help="Path to base-model JSON report")
    parser.add_argument("new", help="Path to new (fine-tuned) JSON report")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.02,
        help="Recall regression threshold (default: 0.02)",
    )
    args = parser.parse_args(argv)

    base_path = Path(args.base)
    new_path = Path(args.new)

    for p in (base_path, new_path):
        if not p.exists():
            print(f"Error: {p} not found.", file=sys.stderr)
            return 1

    with open(base_path, "r", encoding="utf-8") as f:
        base: dict[str, object] = json.load(f)
    with open(new_path, "r", encoding="utf-8") as f:
        new: dict[str, object] = json.load(f)

    table, regression = compare_reports(base, new, threshold=args.threshold)
    print(table)

    return 1 if regression else 0


if __name__ == "__main__":
    sys.exit(main())
