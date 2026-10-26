"""Compare two eval JSON reports and flag recall regressions.

Usage::

    uv run python -m eval.compare BASE.json NEW.json [--threshold 0.02]

Exits 1 when any label in the comparable subset loses more than *threshold*
recall (strict) relative to the base report.

PII-9 note: P/R/F1 values in the JSON may be ``null`` (undefined) when the
denominator is zero.  Helpers return ``None`` for null values.  A regression
check is *skipped* (not flagged) when either side has undefined recall.
"""

from __future__ import annotations

import argparse
import json
import sys

# ---------------------------------------------------------------------------
# Helpers (pure, no I/O — easy to unit-test)
# ---------------------------------------------------------------------------


def _nullable_float(v: object) -> float | None:
    """Return a float or None; pass through None (JSON null)."""
    if v is None:
        return None
    return float(v)


def _fmt_val(v: float | None) -> str:
    """Format a metric value; None → 'undefined'."""
    if v is None:
        return "undefined"
    return f"{v:.4f}"


def _fmt_delta(a: float | None, b: float | None) -> str:
    """Format a metric delta; N/A when either side is undefined."""
    if a is None or b is None:
        return "N/A"
    return f"{b - a:+.4f}"


def _prf_entry(
    by_label: dict[str, object], label: str
) -> tuple[float | None, float | None, float | None]:
    """Return (precision, recall, f1) for *label* from a strict_by_label dict.

    A label *absent* from the report is treated as (0.0, 0.0, 0.0) — the system
    produced no output for it.  A label *present* with a null value is treated as
    ``None`` (undefined denominator — regression check is skipped for that label).
    """
    raw = by_label.get(label)
    if raw is None or not isinstance(raw, dict):
        # Label absent entirely → treat as zero output (old behaviour, enables regression detection)
        return 0.0, 0.0, 0.0
    return (
        _nullable_float(raw.get("p")),
        _nullable_float(raw.get("r")),
        _nullable_float(raw.get("f1")),
    )


def _micro_entry(
    report: dict[str, object], key: str
) -> tuple[float | None, float | None, float | None]:
    """Extract micro (p, r, f1) from a nested dict under *key* in *report*."""
    m = report.get(key)
    if not isinstance(m, dict):
        return None, None, None
    return (
        _nullable_float(m.get("p")),
        _nullable_float(m.get("r")),
        _nullable_float(m.get("f1")),
    )


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
    than *threshold* recall (strict) relative to the base report.  When either
    side has undefined (null) recall, the label is reported as SKIP and does
    not count as a regression.
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
    lines.append(
        f"| strict | {_fmt_val(bp)} | {_fmt_val(br)} | {_fmt_val(bf)}"
        f" | {_fmt_val(np_)} | {_fmt_val(nr)} | {_fmt_val(nf)} |"
    )

    bpp, brp, bfp = _micro_entry(base, "comparable_partial_micro")
    npp, nrp, nfp = _micro_entry(new, "comparable_partial_micro")
    lines.append(
        f"| partial | {_fmt_val(bpp)} | {_fmt_val(brp)} | {_fmt_val(bfp)}"
        f" | {_fmt_val(npp)} | {_fmt_val(nrp)} | {_fmt_val(nfp)} |"
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

        in_comparable = label in comparable_set

        if in_comparable:
            if br_l is None or nr_l is None:
                status = "SKIP (undefined)"
            elif nr_l - br_l < -threshold:
                regression = True
                regressions.append(label)
                status = "REGRESSION"
            else:
                status = "ok"
        else:
            status = ""

        lines.append(
            f"| {label} | {_fmt_val(bp_l)} | {_fmt_val(np_l)} | {_fmt_delta(bp_l, np_l)}"
            f" | {_fmt_val(br_l)} | {_fmt_val(nr_l)} | {_fmt_delta(br_l, nr_l)}"
            f" | {_fmt_val(bf_l)} | {_fmt_val(nf_l)} | {_fmt_delta(bf_l, nf_l)}"
            f" | {status} |"
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

            def _sm(d: dict[str, object]) -> tuple[float | None, float | None, float | None]:
                sm = d.get("strict_micro", {})
                sm = sm if isinstance(sm, dict) else {}
                return (
                    _nullable_float(sm.get("p")),
                    _nullable_float(sm.get("r")),
                    _nullable_float(sm.get("f1")),
                )

            bm = _sm(base_dt)
            nm = _sm(new_dt)
            lines.append(
                f"| {dt} | {_fmt_val(bm[0])} | {_fmt_val(nm[0])} | {_fmt_delta(bm[0], nm[0])}"
                f" | {_fmt_val(bm[1])} | {_fmt_val(nm[1])} | {_fmt_delta(bm[1], nm[1])}"
                f" | {_fmt_val(bm[2])} | {_fmt_val(nm[2])} | {_fmt_delta(bm[2], nm[2])} |"
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
    parser = argparse.ArgumentParser(description="Compare two eval JSON reports.")
    parser.add_argument("base", help="Base JSON report path")
    parser.add_argument("new", help="New JSON report path")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.02,
        help="Recall drop threshold for regression (default: 0.02)",
    )
    args = parser.parse_args(argv)

    with open(args.base, "r", encoding="utf-8") as f:
        base_data: dict[str, object] = json.load(f)
    with open(args.new, "r", encoding="utf-8") as f:
        new_data: dict[str, object] = json.load(f)

    output, regression = compare_reports(base_data, new_data, threshold=args.threshold)
    print(output)
    return 1 if regression else 0


if __name__ == "__main__":
    sys.exit(main())
