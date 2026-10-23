"""Benchmark runner module (eval/run.py) — PII-4-f."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import piitier
import piitier.render
from eval.baselines import System, get_system
from eval.metrics import (
    NumberingStats,
    entity_metrics,
    entity_metrics_by_label,
    fidelity,
    leak_rate,
    numbering_consistency,
    peak_ram_bytes,
    risk_weighted_recall,
    throughput_stats,
)
from piitier.labels import Label
from piitier.spans import Span


@dataclass(frozen=True)
class BenchDoc:
    id: str
    doc_type: str
    text: str
    gold: list[Span]


@dataclass(frozen=True)
class BenchResult:
    gold_spans: list[Span]
    pred_spans: list[Span]
    gold_spans_per_doc: list[list[Span]]
    pred_spans_per_doc: list[list[Span]]
    originals: list[str]
    rendered: list[str]
    doc_ids: list[str]
    latencies: list[float]
    threshold: float | None


def read_bench(bench_dir: Path) -> list[BenchDoc]:
    """Read all *.jsonl files in bench_dir and validate offsets and labels."""
    docs: list[BenchDoc] = []
    if not bench_dir.exists():
        raise FileNotFoundError(f"Bench directory not found: {bench_dir}")

    for jsonl_path in sorted(bench_dir.glob("*.jsonl")):
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                doc_id = record["id"]
                doc_type = record["doc_type"]
                text = record["text"]
                spans_data = record["spans"]

                gold_spans: list[Span] = []
                for s_data in spans_data:
                    start = s_data["start"]
                    end = s_data["end"]
                    label_name = s_data["label"]
                    span_text = s_data["text"]

                    if label_name not in Label.__members__:
                        raise ValueError(f"Document {doc_id}: unknown label {label_name!r}")
                    label = Label[label_name]

                    if start < 0 or end > len(text) or start >= end:
                        raise ValueError(
                            f"Document {doc_id}: invalid span offsets "
                            f"[{start}, {end}) for text of len {len(text)}"
                        )

                    actual_substring = text[start:end]
                    if actual_substring != span_text:
                        raise ValueError(
                            f"Document {doc_id}: span text mismatch at [{start}, {end}): "
                            f"expected {span_text!r}, got {actual_substring!r}"
                        )

                    gold_spans.append(
                        Span(
                            start=start,
                            end=end,
                            label=label,
                            source="gold",
                            score=1.0,
                            status="valid",
                        )
                    )
                docs.append(BenchDoc(id=doc_id, doc_type=doc_type, text=text, gold=gold_spans))
    return docs


def run_benchmark(
    system: System,
    docs: list[BenchDoc],
    *,
    threshold: float | None = None,
) -> BenchResult:
    """Run benchmark evaluation across documents."""
    gold_spans_flat: list[Span] = []
    pred_spans_flat: list[Span] = []
    gold_spans_per_doc: list[list[Span]] = []
    pred_spans_per_doc: list[list[Span]] = []
    originals: list[str] = []
    rendered: list[str] = []
    doc_ids: list[str] = []
    latencies: list[float] = []

    for doc in docs:
        doc_ids.append(doc.id)
        originals.append(doc.text)
        gold_spans_per_doc.append(doc.gold)
        gold_spans_flat.extend(doc.gold)

        t0 = time.perf_counter()
        pred = system.predict(doc.text)
        t1 = time.perf_counter()
        latencies.append(t1 - t0)

        pred_spans_per_doc.append(pred)
        pred_spans_flat.extend(pred)

        rend = piitier.render.mask(doc.text, pred)
        rendered.append(rend)

    return BenchResult(
        gold_spans=gold_spans_flat,
        pred_spans=pred_spans_flat,
        gold_spans_per_doc=gold_spans_per_doc,
        pred_spans_per_doc=pred_spans_per_doc,
        originals=originals,
        rendered=rendered,
        doc_ids=doc_ids,
        latencies=latencies,
        threshold=threshold,
    )


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point for benchmark runner."""
    parser = argparse.ArgumentParser(description="Run PII benchmark evaluation.")
    parser.add_argument("--system", required=True, help="System name to evaluate")
    parser.add_argument("--bench", default="v1", help="Benchmark version")
    parser.add_argument("--split", default="dev", choices=["dev", "test"], help="Dataset split")
    parser.add_argument("--checkpoint", help="Model checkpoint path (required for ner system)")
    parser.add_argument("--threshold", type=float, help="Detection threshold")
    parser.add_argument("--out-dir", default="eval/reports", help="Output directory for reports")

    args = parser.parse_args(argv)

    if args.split == "test":
        print("WARNING: Running on test split (final numbers).")

    bench_dir = Path("bench") / args.bench / args.split
    if not bench_dir.exists():
        print(f"Error: bench directory {bench_dir} does not exist.", file=sys.stderr)
        return 1

    if args.system == "ner" and not args.checkpoint:
        print("Error: --checkpoint required for system 'ner'.", file=sys.stderr)
        return 1

    try:
        docs = read_bench(bench_dir)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error reading benchmark: {e}", file=sys.stderr)
        return 1

    system_kwargs = {}
    if args.checkpoint:
        system_kwargs["checkpoint"] = args.checkpoint
    if args.threshold is not None:
        system_kwargs["threshold"] = args.threshold

    try:
        system = get_system(args.system, **system_kwargs)
    except Exception as e:
        print(f"Error initializing system {args.system}: {e}", file=sys.stderr)
        return 1

    result = run_benchmark(system, docs, threshold=args.threshold)

    # Compute metrics
    strict_micro = entity_metrics(result.gold_spans, result.pred_spans, match="strict")
    strict_by_label = entity_metrics_by_label(result.gold_spans, result.pred_spans, match="strict")
    partial_micro = entity_metrics(result.gold_spans, result.pred_spans, match="partial")
    partial_by_label = entity_metrics_by_label(
        result.gold_spans, result.pred_spans, match="partial"
    )
    rwr = risk_weighted_recall(result.gold_spans, result.pred_spans)
    leak = leak_rate(result.originals, result.gold_spans_per_doc, result.rendered, result.doc_ids)

    total_fidelity = sum(
        fidelity(orig, rend, spans)
        for orig, rend, spans in zip(result.originals, result.rendered, result.gold_spans_per_doc)
    )

    numbered_labels = {lbl for lbl in Label if lbl.numbered}
    total_numbering = NumberingStats(0, 0, 0, 0)
    for orig, rend, spans, pred_spans in zip(
        result.originals, result.rendered, result.gold_spans_per_doc, result.pred_spans_per_doc
    ):
        ns = numbering_consistency(
            rend, spans, numbered_labels, original=orig, masked_spans=pred_spans
        )
        total_numbering = NumberingStats(
            same_entity_consistent=(
                total_numbering.same_entity_consistent + ns.same_entity_consistent
            ),
            same_entity_total=total_numbering.same_entity_total + ns.same_entity_total,
            different_entity_distinct=(
                total_numbering.different_entity_distinct + ns.different_entity_distinct
            ),
            different_entity_total=(
                total_numbering.different_entity_total + ns.different_entity_total
            ),
        )

    throughput = throughput_stats(result.latencies)
    peak_ram = peak_ram_bytes()

    metrics = {
        "strict_micro": strict_micro,
        "strict_by_label": strict_by_label,
        "partial_micro": partial_micro,
        "partial_by_label": partial_by_label,
        "risk_weighted_recall": rwr,
        "leak_rate": leak,
        "fidelity": total_fidelity,
        "numbering": total_numbering,
        "throughput": throughput,
        "peak_ram": peak_ram,
    }

    date_prefix = datetime.now().strftime("%Y-%m-%d")
    report_filename = f"{date_prefix}-{args.system}-bench{args.bench}-{args.split}.md"
    report_path = Path(args.out_dir) / report_filename

    system_version = getattr(system, "version", getattr(piitier, "__version__", "0.1.0"))

    from eval.report import write_report

    write_report(
        report_path,
        system_name=args.system,
        system_version=str(system_version),
        bench_version=args.bench,
        split=args.split,
        threshold=args.threshold,
        result=result,
        metrics=metrics,
        is_final=(args.split == "test"),
    )

    print(f"Report written to {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
