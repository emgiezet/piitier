"""Report writer module (eval/report.py) — PII-4-f."""

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
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    threshold_str = str(threshold) if threshold is not None else "brak — system bez progu"
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
    strict_micro = cast(EntityPRF, metrics.get("strict_micro", EntityPRF(0.0, 0.0, 0.0)))
    strict_by_label = cast(dict[Label, EntityPRF], metrics.get("strict_by_label", {}))
    partial_micro = cast(EntityPRF, metrics.get("partial_micro", EntityPRF(0.0, 0.0, 0.0)))
    partial_by_label = cast(dict[Label, EntityPRF], metrics.get("partial_by_label", {}))
    rwr = cast(float, metrics.get("risk_weighted_recall", 0.0))
    leak = cast(
        LeakRate,
        metrics.get("leak_rate", LeakRate(0, doc_count, 0, gold_count, [])),
    )
    fidelity_val = cast(int, metrics.get("fidelity", 0))
    numbering = cast(NumberingStats, metrics.get("numbering", NumberingStats(0, 0, 0, 0)))
    throughput = cast(ThroughputStats, metrics.get("throughput", ThroughputStats(0.0, 0.0)))

    leaked_ids_str = ", ".join(leak.leaked_doc_ids) if leak.leaked_doc_ids else "brak"
    split_str = f"{split} (final numbers)" if is_final else split

    lines = [
        f"# Raport: {system_name} na bench/{bench_version}/{split}",
        "",
        "## System",
        f"- Name: {system_name}",
        f"- Wersja: {system_version}",
        f"- Data: {date_str}",
        f"- Próg: {threshold_str}",
        "",
        "## Benchmark",
        f"- Wersja: {bench_version}",
        f"- Split: {split_str}",
        f"- Liczba dokumentów: {doc_count}",
        f"- Liczba spanów gold: {gold_count}",
        "",
        "## Sprzęt",
        f"- Platforma: {platform.platform()}",
        f"- Procesor: {platform.processor() or 'N/A'}",
        f"- GPU: {gpu_name}",
        f"- Peak RAM: {peak_ram} bytes",
        "",
        "## Encje (strict)",
        f"- Micro Precision: {strict_micro.precision:.4f}",
        f"- Micro Recall: {strict_micro.recall:.4f}",
        f"- Micro F1: {strict_micro.f1:.4f}",
        "",
        "| Etykieta | Precision | Recall | F1 |",
        "|---|---|---|---|",
    ]

    for lbl, prf in sorted(strict_by_label.items(), key=lambda x: x[0].name):
        lines.append(f"| {lbl.name} | {prf.precision:.4f} | {prf.recall:.4f} | {prf.f1:.4f} |")

    lines.extend(
        [
            "",
            "## Encje (partial)",
            f"- Micro Precision: {partial_micro.precision:.4f}",
            f"- Micro Recall: {partial_micro.recall:.4f}",
            f"- Micro F1: {partial_micro.f1:.4f}",
            "",
            "| Etykieta | Precision | Recall | F1 |",
            "|---|---|---|---|",
        ]
    )

    for lbl, prf in sorted(partial_by_label.items(), key=lambda x: x[0].name):
        lines.append(f"| {lbl.name} | {prf.precision:.4f} | {prf.recall:.4f} | {prf.f1:.4f} |")

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
                "## Porównywalna podtaksonomia (bardsai_v2)",
                f"- Etykiety: {label_names}",
                f"- Strict Micro Precision: {_comparable_strict.precision:.4f}",
                f"- Strict Micro Recall: {_comparable_strict.recall:.4f}",
                f"- Strict Micro F1: {_comparable_strict.f1:.4f}",
            ]
        )
        if _comparable_partial is not None:
            lines.extend(
                [
                    f"- Partial Micro Precision: {_comparable_partial.precision:.4f}",
                    f"- Partial Micro Recall: {_comparable_partial.recall:.4f}",
                    f"- Partial Micro F1: {_comparable_partial.f1:.4f}",
                ]
            )

    lines.extend(
        [
            "",
            "## Recall ważony ryzykiem",
            f"- Risk-weighted recall: {rwr:.4f}",
            "",
            "## Leak rate",
            f"- Docs leaked: {leak.docs_leaked} / {leak.docs_total}",
            f"- Values leaked: {leak.values_leaked} / {leak.values_total}",
            f"- Leaked doc IDs: {leaked_ids_str}",
            "",
            "## Wierność",
            f"- Changed chars outside spans: {fidelity_val}",
            "",
            "## Numeracja",
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
        lines.append("## Podział wg doc_type")
        lines.append("")
        for dt in sorted(_by_dt):
            dt_v = _by_dt[dt]
            sm = cast(EntityPRF, dt_v["strict_micro"])
            sbl = cast(dict[Label, EntityPRF], dt_v["strict_by_label"])
            lines.extend(
                [
                    f"### {dt}",
                    f"- Strict Micro Precision: {sm.precision:.4f}",
                    f"- Strict Micro Recall: {sm.recall:.4f}",
                    f"- Strict Micro F1: {sm.f1:.4f}",
                    "",
                    "| Etykieta | Precision | Recall | F1 |",
                    "|---|---|---|---|",
                ]
            )
            for lbl, prf in sorted(sbl.items(), key=lambda x: x[0].name):
                lines.append(
                    f"| {lbl.name} | {prf.precision:.4f} | {prf.recall:.4f} | {prf.f1:.4f} |"
                )
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
