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
) -> Path:
    """Generate Markdown evaluation report with required sections in mandatory order."""
    path.parent.mkdir(parents=True, exist_ok=True)

    threshold_str = str(threshold) if threshold is not None else "brak — system bez progu"
    date_str = datetime.now().isoformat()
    doc_count = len(result.doc_ids)
    gold_count = len(result.gold_spans)

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

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
