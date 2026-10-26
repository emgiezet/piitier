"""Benchmark runner module (eval/run.py) — PII-4-f."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import cast

import piitier
import piitier.render
from eval.baselines import System, get_system
from eval.metrics import (
    EntityPRF,
    NumberingStats,
    corpus_entity_metrics,
    corpus_entity_metrics_by_label,
    corpus_risk_weighted_recall,
    fidelity,
    leak_rate,
    numbering_consistency,
    peak_ram_bytes,
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
    gold_spans_per_doc: list[list[Span]]
    pred_spans_per_doc: list[list[Span]]
    originals: list[str]
    rendered: list[str]
    doc_ids: list[str]
    latencies: list[float]
    threshold: float | None
    doc_types: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Document readers
# ---------------------------------------------------------------------------


def _parse_spans(text: str, spans_data: list[dict[str, object]], doc_id: str) -> list[Span]:
    """Parse span dicts into Span objects, validating offsets and labels."""
    gold_spans: list[Span] = []
    for s_data in spans_data:
        start = int(cast(int, s_data["start"]))
        end = int(cast(int, s_data["end"]))
        label_name = str(s_data["label"])
        span_text = str(s_data["text"])

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
    return gold_spans


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
                record: dict[str, object] = json.loads(line)
                doc_id = str(record["id"])
                doc_type = str(record["doc_type"])
                text = str(record["text"])
                spans_raw = cast(list[dict[str, object]], record["spans"])
                gold_spans = _parse_spans(text, spans_raw, doc_id)
                docs.append(BenchDoc(id=doc_id, doc_type=doc_type, text=text, gold=gold_spans))
    return docs


def read_docs(path: Path, limit: int | None = None) -> list[BenchDoc]:
    """Read a synthetic JSONL file (datagen build format) into BenchDoc objects.

    Records must have:
        id, doc_type, text, spans:[{start, end, label, entity, text}]
    Extra fields (template_id, seed) are ignored.

    Args:
        path: Path to the ``.jsonl`` file.
        limit: If given, return only the first *limit* documents (deterministic).
    """
    if not path.exists():
        raise FileNotFoundError(f"Docs file not found: {path}")

    docs: list[BenchDoc] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if limit is not None and len(docs) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            record: dict[str, object] = json.loads(line)
            doc_id = str(record["id"])
            doc_type = str(record["doc_type"])
            text = str(record["text"])
            spans_raw = cast(list[dict[str, object]], record["spans"])
            gold_spans = _parse_spans(text, spans_raw, doc_id)
            docs.append(BenchDoc(id=doc_id, doc_type=doc_type, text=text, gold=gold_spans))
    return docs


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------


def run_benchmark(
    system: System,
    docs: list[BenchDoc],
    *,
    threshold: float | None = None,
) -> BenchResult:
    """Run benchmark evaluation across documents."""
    gold_spans_per_doc: list[list[Span]] = []
    pred_spans_per_doc: list[list[Span]] = []
    originals: list[str] = []
    rendered: list[str] = []
    doc_ids: list[str] = []
    doc_types: list[str] = []
    latencies: list[float] = []

    for doc in docs:
        doc_ids.append(doc.id)
        doc_types.append(doc.doc_type)
        originals.append(doc.text)
        gold_spans_per_doc.append(doc.gold)

        t0 = time.perf_counter()
        pred = system.predict(doc.text)
        t1 = time.perf_counter()
        latencies.append(t1 - t0)

        pred_spans_per_doc.append(pred)

        rend = piitier.render.mask(doc.text, pred)
        rendered.append(rend)

    return BenchResult(
        gold_spans_per_doc=gold_spans_per_doc,
        pred_spans_per_doc=pred_spans_per_doc,
        originals=originals,
        rendered=rendered,
        doc_ids=doc_ids,
        latencies=latencies,
        threshold=threshold,
        doc_types=doc_types,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _prf_dict(prf: EntityPRF) -> dict[str, object]:
    """Serialize an EntityPRF to JSON-safe dict.

    P/R/F1 are ``null`` in JSON when the denominator is zero (undefined);
    tp, fp, fn are always integers.
    """
    return {
        "p": prf.precision if (prf.tp + prf.fp) > 0 else None,
        "r": prf.recall if (prf.tp + prf.fn) > 0 else None,
        "f1": prf.f1 if (2 * prf.tp + prf.fp + prf.fn) > 0 else None,
        "tp": prf.tp,
        "fp": prf.fp,
        "fn": prf.fn,
    }


def _by_doc_type_metrics(
    result: BenchResult,
) -> dict[str, dict[str, object]]:
    """Compute corpus_entity_metrics per doc_type (strict and partial).

    Matching is per-document within each doc_type group.
    """
    dt_gold: dict[str, list[list[Span]]] = {}
    dt_pred: dict[str, list[list[Span]]] = {}
    for dt, g_spans, p_spans in zip(
        result.doc_types, result.gold_spans_per_doc, result.pred_spans_per_doc
    ):
        dt_gold.setdefault(dt, []).append(g_spans)
        dt_pred.setdefault(dt, []).append(p_spans)

    out: dict[str, dict[str, object]] = {}
    for dt in sorted(dt_gold):
        g_docs = dt_gold[dt]
        p_docs = dt_pred.get(dt, [[] for _ in g_docs])
        out[dt] = {
            "strict_micro": corpus_entity_metrics(g_docs, p_docs, match="strict"),
            "strict_by_label": corpus_entity_metrics_by_label(g_docs, p_docs, match="strict"),
            "partial_micro": corpus_entity_metrics(g_docs, p_docs, match="partial"),
            "partial_by_label": corpus_entity_metrics_by_label(g_docs, p_docs, match="partial"),
        }
    return out


def _get_git_commit() -> str:
    """Return 40-char HEAD SHA or 'unknown' if git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
            if len(commit) == 40 and all(c in "0123456789abcdef" for c in commit):
                return commit
    except Exception:
        pass
    return "unknown"


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point for benchmark runner."""
    parser = argparse.ArgumentParser(description="Run PII benchmark evaluation.")
    parser.add_argument("--system", required=True, help="System name to evaluate")
    parser.add_argument("--bench", default="v1", help="Benchmark version")
    parser.add_argument("--split", default="dev", choices=["dev", "test"], help="Dataset split")
    parser.add_argument(
        "--docs",
        help=(
            "Path to a synthetic JSONL file (datagen format); "
            "alternative to --bench/--split for loading."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N documents (deterministic; applies to --docs).",
    )
    parser.add_argument("--checkpoint", help="Model checkpoint path (required for ner system)")
    parser.add_argument("--threshold", type=float, help="Detection threshold")
    parser.add_argument(
        "--device",
        default="cpu",
        help="Compute device: 'cpu' or 'cuda:0' (default: cpu)",
    )
    parser.add_argument(
        "--label-subset",
        choices=["bardsai_v2"],
        default=None,
        help=(
            "Restrict metrics to the comparable-subset labels of the named baseline. "
            "Use 'bardsai_v2' to compare a fine-tuned model against the bardsai_v2 baseline."
        ),
    )
    parser.add_argument("--out-dir", default="eval/reports", help="Output directory for reports")

    args = parser.parse_args(argv)

    # ------------------------------------------------------------------
    # Document loading
    # ------------------------------------------------------------------
    use_docs = args.docs is not None

    if use_docs:
        docs_path = Path(args.docs)
        try:
            docs = read_docs(docs_path, limit=args.limit)
        except (FileNotFoundError, ValueError) as e:
            print(f"Error reading docs: {e}", file=sys.stderr)
            return 1
        stem = f"{docs_path.parent.name}-{docs_path.stem}"
        bench_label = docs_path.parent.name
        split_label = docs_path.stem
    else:
        if args.split == "test":
            print("WARNING: Running on test split (final numbers).")
        bench_dir = Path("bench") / args.bench / args.split
        if not bench_dir.exists():
            print(f"Error: bench directory {bench_dir} does not exist.", file=sys.stderr)
            return 1
        try:
            docs = read_bench(bench_dir)
        except (FileNotFoundError, ValueError) as e:
            print(f"Error reading benchmark: {e}", file=sys.stderr)
            return 1
        stem = f"bench{args.bench}-{args.split}"
        bench_label = args.bench
        split_label = args.split

    # ------------------------------------------------------------------
    # Provenance: git commit and bench file SHA-256
    # ------------------------------------------------------------------
    git_commit = _get_git_commit()
    bench_sha256: dict[str, str] = {}
    if use_docs:
        bench_sha256[docs_path.name] = _sha256_file(docs_path)
    else:
        for _bpath in sorted(bench_dir.glob("*.jsonl")):
            bench_sha256[_bpath.name] = _sha256_file(_bpath)

    if not docs:
        print("Error: no documents found.", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # System initialisation
    # ------------------------------------------------------------------
    if args.system == "ner" and not args.checkpoint:
        print("Error: --checkpoint required for system 'ner'.", file=sys.stderr)
        return 1

    system_kwargs: dict[str, object] = {"device": args.device}
    if args.checkpoint:
        system_kwargs["checkpoint"] = args.checkpoint
    if args.threshold is not None:
        system_kwargs["threshold"] = args.threshold

    try:
        system = get_system(args.system, **system_kwargs)
    except Exception as e:
        print(f"Error initializing system {args.system}: {e}", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------
    result = run_benchmark(system, docs, threshold=args.threshold)

    # ------------------------------------------------------------------
    # Metrics — full taxonomy
    # ------------------------------------------------------------------
    strict_micro = corpus_entity_metrics(
        result.gold_spans_per_doc, result.pred_spans_per_doc, match="strict"
    )
    strict_by_label = corpus_entity_metrics_by_label(
        result.gold_spans_per_doc, result.pred_spans_per_doc, match="strict"
    )
    partial_micro = corpus_entity_metrics(
        result.gold_spans_per_doc, result.pred_spans_per_doc, match="partial"
    )
    partial_by_label = corpus_entity_metrics_by_label(
        result.gold_spans_per_doc, result.pred_spans_per_doc, match="partial"
    )
    rwr = corpus_risk_weighted_recall(result.gold_spans_per_doc, result.pred_spans_per_doc)
    # rwr_undefined: true when total gold weight is zero (no gold spans in corpus)
    rwr_undefined = sum(len(g) for g in result.gold_spans_per_doc) == 0
    leak = leak_rate(result.originals, result.gold_spans_per_doc, result.rendered, result.doc_ids)

    total_fidelity = sum(
        fidelity(orig, rend, spans)
        for orig, rend, spans in zip(result.originals, result.rendered, result.pred_spans_per_doc)
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

    # ------------------------------------------------------------------
    # Metrics — comparable subset
    # ------------------------------------------------------------------
    comparable_labels: frozenset[Label] | None = None

    if args.system == "bardsai-v2" or args.label_subset == "bardsai_v2":
        from eval.baselines.bardsai_v2 import BARDSAI_LABEL_MAP

        comparable_labels = frozenset(BARDSAI_LABEL_MAP.values())
    elif args.label_subset is None and hasattr(system, "unmapped") and system.unmapped:
        comparable_labels = frozenset(Label) - system.unmapped

    comparable_strict_micro: EntityPRF | None = None
    comparable_partial_micro: EntityPRF | None = None
    if comparable_labels:
        cg_docs = [
            [s for s in g if s.label in comparable_labels] for g in result.gold_spans_per_doc
        ]
        cp_docs = [
            [s for s in p if s.label in comparable_labels] for p in result.pred_spans_per_doc
        ]
        comparable_strict_micro = corpus_entity_metrics(cg_docs, cp_docs, match="strict")
        comparable_partial_micro = corpus_entity_metrics(cg_docs, cp_docs, match="partial")

    # ------------------------------------------------------------------
    # Metrics — per-doc_type
    # ------------------------------------------------------------------
    by_doc_type = _by_doc_type_metrics(result)

    # ------------------------------------------------------------------
    # Write markdown report
    # ------------------------------------------------------------------
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    report_filename = f"{date_prefix}-{args.system}-{stem}.md"
    report_path = Path(args.out_dir) / report_filename

    system_version = getattr(system, "version", getattr(piitier, "__version__", "0.1.0"))

    from eval.report import write_report

    metrics: dict[str, object] = {
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
        "comparable_strict_micro": comparable_strict_micro,
        "comparable_partial_micro": comparable_partial_micro,
        "comparable_labels": comparable_labels,
        "by_doc_type": by_doc_type,
    }

    write_report(
        report_path,
        system_name=args.system,
        system_version=str(system_version),
        bench_version=bench_label,
        split=split_label,
        threshold=args.threshold,
        result=result,
        metrics=metrics,
        is_final=(not use_docs and args.split == "test"),
        comparable_labels=comparable_labels,
        by_doc_type=by_doc_type,
        git_commit=git_commit,
        bench_sha256=bench_sha256,
    )

    # ------------------------------------------------------------------
    # Write JSON sidecar
    # ------------------------------------------------------------------
    json_path = report_path.with_suffix(".json")

    def _dt_v(v: dict[str, object]) -> dict[str, object]:
        """Serialize a per-doc_type metrics dict to JSON-safe form."""
        sm = cast(EntityPRF, v["strict_micro"])
        pm = cast(EntityPRF, v["partial_micro"])
        sbl = cast(dict[Label, EntityPRF], v["strict_by_label"])
        pbl = cast(dict[Label, EntityPRF], v["partial_by_label"])
        return {
            "strict_micro": _prf_dict(sm),
            "strict_by_label": {lbl.name: _prf_dict(prf) for lbl, prf in sbl.items()},
            "partial_micro": _prf_dict(pm),
            "partial_by_label": {lbl.name: _prf_dict(prf) for lbl, prf in pbl.items()},
        }

    report_json: dict[str, object] = {
        "system": args.system,
        "system_version": str(system_version),
        "git_commit": git_commit,
        "bench_sha256": bench_sha256,
        "bench": bench_label,
        "split": split_label,
        "source": args.docs if use_docs else f"bench/{args.bench}/{args.split}",
        "date": datetime.now().isoformat(),
        "threshold": args.threshold,
        "device": args.device,
        "docs": len(docs),
        "gold_spans": sum(len(g) for g in result.gold_spans_per_doc),
        "strict_micro": _prf_dict(strict_micro),
        "strict_by_label": {lbl.name: _prf_dict(prf) for lbl, prf in strict_by_label.items()},
        "partial_micro": _prf_dict(partial_micro),
        "partial_by_label": {lbl.name: _prf_dict(prf) for lbl, prf in partial_by_label.items()},
        "comparable_strict_micro": (
            _prf_dict(comparable_strict_micro) if comparable_strict_micro else None
        ),
        "comparable_partial_micro": (
            _prf_dict(comparable_partial_micro) if comparable_partial_micro else None
        ),
        "comparable_labels": (
            sorted(lbl.name for lbl in comparable_labels) if comparable_labels else []
        ),
        "by_doc_type": {dt: _dt_v(v) for dt, v in by_doc_type.items()},
        "risk_weighted_recall": None if rwr_undefined else rwr,
        "leak_rate": {
            "docs_leaked": leak.docs_leaked,
            "docs_total": leak.docs_total,
            "docs_with_direct_id": leak.docs_with_direct_id,
            "values_leaked": leak.values_leaked,
            "values_total": leak.values_total,
            "leaked_doc_ids": leak.leaked_doc_ids,
            "doc_leak_rate": (
                leak.docs_leaked / leak.docs_with_direct_id
                if leak.docs_with_direct_id > 0
                else None
            ),
            "value_leak_rate": (
                leak.values_leaked / leak.values_total if leak.values_total > 0 else None
            ),
        },
        "fidelity": total_fidelity,
        "throughput": {
            "docs_per_second": throughput.docs_per_second,
            "p95_latency_seconds": throughput.p95_latency_seconds,
        },
        "peak_ram_bytes": peak_ram,
    }

    json_path.write_text(json.dumps(report_json, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Report written to {report_path}")
    print(f"JSON written to  {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
