"""Report writer module (eval/report.py) — PII-4-f, PII-9."""

from __future__ import annotations

import platform
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from eval.metrics import EntityPRF, LeakRate, NumberingStats, ThroughputStats
from piitier.labels import Label

if TYPE_CHECKING:
    from eval.run import BenchResult
else:
    BenchResult = object


# ---------------------------------------------------------------------------
# Formatting helpers — "undefined" is decided from TP/FP/FN counts
# ---------------------------------------------------------------------------


def _fmt_p(prf: EntityPRF) -> str:
    """Format precision; 'undefined (0/0)' when TP+FP = 0."""
    if (prf.tp + prf.fp) == 0:
        return "undefined (0/0)"
    return f"{prf.precision:.4f}"


def _fmt_r(prf: EntityPRF) -> str:
    """Format recall; 'undefined (0/0)' when TP+FN = 0."""
    if (prf.tp + prf.fn) == 0:
        return "undefined (0/0)"
    return f"{prf.recall:.4f}"


def _fmt_f1(prf: EntityPRF) -> str:
    """Format F1; 'undefined (0/0)' when 2*TP+FP+FN = 0."""
    if (2 * prf.tp + prf.fp + prf.fn) == 0:
        return "undefined (0/0)"
    return f"{prf.f1:.4f}"


def _fmt_rwr(rwr: float, *, undefined: bool) -> str:
    """Format risk-weighted recall; 'undefined (0/0)' when gold weight = 0."""
    if undefined:
        return "undefined (0/0)"
    return f"{rwr:.4f}"


def _fmt_doc_leak(leak: LeakRate) -> str:
    """Format docs-leaked fraction; undefined when no docs with direct ID."""
    if leak.docs_with_direct_id == 0:
        return "undefined (0/0)"
    return f"{leak.docs_leaked}/{leak.docs_with_direct_id}"


def _fmt_val_leak(leak: LeakRate) -> str:
    """Format values-leaked fraction; undefined when no gold values."""
    if leak.values_total == 0:
        return "undefined (0/0)"
    return f"{leak.values_leaked}/{leak.values_total}"


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------


def write_report(
    path: Path,
    *,
    system_name: str,
    system_version: str,
    bench_version: str,
    split: str,
    threshold: float | None,
    result: BenchResult,
    metrics: dict[str, object],
    is_final: bool = False,
    comparable_labels: frozenset[Label] | None = None,
    by_doc_type: dict[str, dict[str, object]] | None = None,
    git_commit: str = "unknown",
    bench_sha256: dict[str, str] | None = None,
) -> Path:
    """Generate Markdown evaluation report with required sections in mandatory order.

    Args:
        path: Destination ``.md`` file (parent dirs are created automatically).
        system_name: Short system identifier (e.g. ``"bardsai-v2"``).
        system_version: Version string for the system.
        bench_version: Benchmark version tag (e.g. ``"v1"``).
        split: Dataset split name (``"dev"``, ``"test"``, or JSONL stem).
        threshold: Detection threshold or ``None`` if the system has none.
        result: ``BenchResult`` from ``run_benchmark``.
        metrics: Metrics dict as built by ``main()`` in ``eval.run``.
        is_final: When ``True`` the split label is annotated as final.
        comparable_labels: Optional subset of labels for the comparable-subset block.
        by_doc_type: Optional per-doc_type metric dicts from ``_by_doc_type_metrics``.
        git_commit: Git commit SHA (40 hex chars) or ``"unknown"``.
        bench_sha256: Mapping of bench filename → SHA-256 hex digest.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    threshold_str = str(threshold) if threshold is not None else "none — threshold-free system"
    date_str = datetime.now().isoformat()
    doc_count = len(result.doc_ids)
    gold_count = sum(len(g) for g in result.gold_spans_per_doc)

    gpu_name = "CPU"
    try:
        import torch

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
    except ImportError:
        pass

    peak_ram = cast(int, metrics.get("peak_ram", 0))
    _default_prf = EntityPRF(0.0, 0.0, 0.0, 0, 0, 0)
    strict_micro = cast(EntityPRF, metrics.get("strict_micro", _default_prf))
    strict_by_label = cast(dict[Label, EntityPRF], metrics.get("strict_by_label", {}))
    partial_micro = cast(EntityPRF, metrics.get("partial_micro", _default_prf))
    partial_by_label = cast(dict[Label, EntityPRF], metrics.get("partial_by_label", {}))
    rwr = cast(float, metrics.get("risk_weighted_recall", 0.0))
    # Decide undefined from gold_count: consistent with other count-based decisions
    rwr_undefined = gold_count == 0
    leak = cast(
        LeakRate,
        metrics.get("leak_rate", LeakRate(0, doc_count, 0, gold_count, [], 0)),
    )
    fidelity_val = cast(int, metrics.get("fidelity", 0))
    numbering = cast(NumberingStats, metrics.get("numbering", NumberingStats(0, 0, 0, 0)))
    throughput = cast(ThroughputStats, metrics.get("throughput", ThroughputStats(0.0, 0.0)))

    leaked_ids_str = ", ".join(leak.leaked_doc_ids) if leak.leaked_doc_ids else "none"
    split_str = f"{split} (final numbers)" if is_final else split

    sha256_lines: list[str] = []
    if bench_sha256:
        for fname, digest in sorted(bench_sha256.items()):
            sha256_lines.append(f"  - {fname}: {digest}")

    lines = [
        f"# Report: {system_name} on bench/{bench_version}/{split}",
        "",
        "## System",
        f"- Name: {system_name}",
        f"- Version: {system_version}",
        f"- Date: {date_str}",
        f"- Threshold: {threshold_str}",
        "",
        "## Metadata",
        f"- Commit: {git_commit}",
        f"- Documents: {doc_count}",
        f"- Split: {split_str}",
        f"- Threshold: {threshold_str}",
    ]

    if sha256_lines:
        lines.append("- SHA-256 bench:")
        lines.extend(sha256_lines)
    else:
        lines.append("- SHA-256 bench: (no bench file or synthetic data)")

    lines.extend(
        [
            "",
            "## Benchmark",
            f"- Version: {bench_version}",
            f"- Split: {split_str}",
            f"- Number of documents: {doc_count}",
            f"- Number of gold spans: {gold_count}",
            "",
            "## Hardware",
            f"- Platform: {platform.platform()}",
            f"- CPU: {platform.processor() or 'N/A'}",
            f"- GPU: {gpu_name}",
            f"- Peak RAM: {peak_ram} bytes",
            "",
            "## Entities (strict)",
            f"- Micro Precision: {_fmt_p(strict_micro)}"
            f" (TP={strict_micro.tp}, FP={strict_micro.fp}, FN={strict_micro.fn})",
            f"- Micro Recall: {_fmt_r(strict_micro)}",
            f"- Micro F1: {_fmt_f1(strict_micro)}",
            "",
            "| Label | Precision | Recall | F1 | TP | FP | FN |",
            "|---|---|---|---|---|---|---|",
        ]
    )

    for lbl, prf in sorted(strict_by_label.items(), key=lambda x: x[0].name):
        lines.append(
            f"| {lbl.name} | {_fmt_p(prf)} | {_fmt_r(prf)}"
            f" | {_fmt_f1(prf)} | {prf.tp} | {prf.fp} | {prf.fn} |"
        )

    lines.extend(
        [
            "",
            "## Entities (partial)",
            f"- Micro Precision: {_fmt_p(partial_micro)}"
            f" (TP={partial_micro.tp}, FP={partial_micro.fp}, FN={partial_micro.fn})",
            f"- Micro Recall: {_fmt_r(partial_micro)}",
            f"- Micro F1: {_fmt_f1(partial_micro)}",
            "",
            "| Label | Precision | Recall | F1 | TP | FP | FN |",
            "|---|---|---|---|---|---|---|",
        ]
    )

    for lbl, prf in sorted(partial_by_label.items(), key=lambda x: x[0].name):
        lines.append(
            f"| {lbl.name} | {_fmt_p(prf)} | {_fmt_r(prf)}"
            f" | {_fmt_f1(prf)} | {prf.tp} | {prf.fp} | {prf.fn} |"
        )

    # ------------------------------------------------------------------
    # Comparable subset block
    # ------------------------------------------------------------------
    _comparable_labels = comparable_labels or cast(
        frozenset[Label] | None, metrics.get("comparable_labels")
    )
    _comparable_strict = cast(EntityPRF | None, metrics.get("comparable_strict_micro"))
    _comparable_partial = cast(EntityPRF | None, metrics.get("comparable_partial_micro"))

    if _comparable_labels and _comparable_strict is not None:
        label_names = ", ".join(sorted(lbl.name for lbl in _comparable_labels))
        lines.extend(
            [
                "",
                "## Comparable subtaxonomy (bardsai_v2)",
                f"- Labels: {label_names}",
                f"- Strict Micro Precision: {_fmt_p(_comparable_strict)}"
                f" (TP={_comparable_strict.tp}, FP={_comparable_strict.fp},"
                f" FN={_comparable_strict.fn})",
                f"- Strict Micro Recall: {_fmt_r(_comparable_strict)}",
                f"- Strict Micro F1: {_fmt_f1(_comparable_strict)}",
            ]
        )
        if _comparable_partial is not None:
            lines.extend(
                [
                    f"- Partial Micro Precision: {_fmt_p(_comparable_partial)}"
                    f" (TP={_comparable_partial.tp}, FP={_comparable_partial.fp},"
                    f" FN={_comparable_partial.fn})",
                    f"- Partial Micro Recall: {_fmt_r(_comparable_partial)}",
                    f"- Partial Micro F1: {_fmt_f1(_comparable_partial)}",
                ]
            )

    lines.extend(
        [
            "",
            "## Risk-weighted recall",
            f"- Risk-weighted recall: {_fmt_rwr(rwr, undefined=rwr_undefined)}",
            "",
            "## Leak rate",
            f"- Docs leaked: {_fmt_doc_leak(leak)}"
            f" (docs_with_direct_id={leak.docs_with_direct_id},"
            f" docs_total={leak.docs_total})",
            f"- Values leaked: {_fmt_val_leak(leak)}",
            f"- Leaked doc IDs: {leaked_ids_str}",
            "",
            "## Fidelity",
            f"- Changed chars outside spans: {fidelity_val}",
            "",
            "## Numbering",
            f"- Same entity consistent: {numbering.same_entity_consistent} "
            f"/ {numbering.same_entity_total}",
            f"- Different entity distinct: "
            f"{numbering.different_entity_distinct} "
            f"/ {numbering.different_entity_total}",
            "",
            "## Throughput",
            f"- Throughput: {throughput.docs_per_second:.2f} docs/s",
            f"- P95 latency: {throughput.p95_latency_seconds:.4f} s",
            "",
        ]
    )

    # ------------------------------------------------------------------
    # Per-doc_type breakdown
    # ------------------------------------------------------------------
    _by_dt = by_doc_type or cast(dict[str, dict[str, object]] | None, metrics.get("by_doc_type"))

    if _by_dt:
        lines.append("## Breakdown by doc_type")
        lines.append("")
        for dt in sorted(_by_dt):
            dt_v = _by_dt[dt]
            sm = cast(EntityPRF, dt_v["strict_micro"])
            sbl = cast(dict[Label, EntityPRF], dt_v["strict_by_label"])
            lines.extend(
                [
                    f"### {dt}",
                    f"- Strict Micro Precision: {_fmt_p(sm)} (TP={sm.tp}, FP={sm.fp}, FN={sm.fn})",
                    f"- Strict Micro Recall: {_fmt_r(sm)}",
                    f"- Strict Micro F1: {_fmt_f1(sm)}",
                    "",
                    "| Label | Precision | Recall | F1 | TP | FP | FN |",
                    "|---|---|---|---|---|---|---|",
                ]
            )
            for lbl, prf in sorted(sbl.items(), key=lambda x: x[0].name):
                lines.append(
                    f"| {lbl.name} | {_fmt_p(prf)} | {_fmt_r(prf)}"
                    f" | {_fmt_f1(prf)} | {prf.tp} | {prf.fp} | {prf.fn} |"
                )
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
