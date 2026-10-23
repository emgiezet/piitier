from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

if "eval.metrics" not in sys.modules:
    _metrics_path = Path(__file__).resolve().parent.parent / "eval" / "metrics.py"
    _spec_m = importlib.util.spec_from_file_location("eval.metrics", _metrics_path)
    if _spec_m is not None and _spec_m.loader is not None:
        _metrics_mod = importlib.util.module_from_spec(_spec_m)
        sys.modules["eval.metrics"] = _metrics_mod
        _spec_m.loader.exec_module(_metrics_mod)

from eval.metrics import entity_metrics
from piitier.ner.inference import NerPredictor
from piitier.spans import Span
from training.config import load_config
from training.train import read_jsonl


@dataclass(frozen=True)
class ThresholdResult:
    threshold: float
    recall: float
    precision: float
    target_met: bool


@dataclass(frozen=True)
class DocPrediction:
    gold: list[Span]
    pred: list[Span]


def calibrate_threshold(
    docs: list[dict[str, Any] | DocPrediction],
    target_recall: float = 0.98,
) -> ThresholdResult:
    """Calibrate detection threshold targeting recall >= target_recall.
    Candidates: 0.0 + sorted unique prediction scores (descending).
    For threshold t: predicted spans with score >= t; strict PRF via entity_metrics.
    Chooses the highest threshold with recall >= target_recall.
    If no threshold meets target, returns ThresholdResult(0.0, recall@0.0, precision@0.0, False).
    """
    scores = {0.0}
    for doc in docs:
        p_list = doc["pred"] if isinstance(doc, dict) else doc.pred
        for p in p_list:
            score = p.get("score", 1.0) if isinstance(p, dict) else getattr(p, "score", 1.0)
            if score is not None:
                scores.add(float(score))

    candidates = sorted(list(scores), reverse=True)

    results: list[ThresholdResult] = []
    for t in candidates:
        gold_all: list[Span] = []
        pred_all: list[Span] = []
        for doc in docs:
            g = doc["gold"] if isinstance(doc, dict) else doc.gold
            p_list = doc["pred"] if isinstance(doc, dict) else doc.pred

            gold_spans = [
                item
                if isinstance(item, Span)
                else Span(
                    start=item["start"],
                    end=item["end"],
                    label=item["label"],
                    source=item.get("source", "gold"),
                    score=item.get("score"),
                    status=item.get("status", "valid"),
                )
                for item in g
            ]
            pred_spans = []
            for item in p_list:
                span_obj = (
                    item
                    if isinstance(item, Span)
                    else Span(
                        start=item["start"],
                        end=item["end"],
                        label=item["label"],
                        source=item.get("source", "pred"),
                        score=item.get("score", 1.0),
                        status=item.get("status", "valid"),
                    )
                )
                score = span_obj.score if span_obj.score is not None else 1.0
                if score >= t:
                    pred_spans.append(span_obj)
            gold_all.extend(gold_spans)
            pred_all.extend(pred_spans)

        prf = entity_metrics(gold_all, pred_all, match="strict")
        target_met = prf.recall >= target_recall
        results.append(
            ThresholdResult(
                threshold=float(t),
                recall=float(prf.recall),
                precision=float(prf.precision),
                target_met=target_met,
            )
        )

    valid = [r for r in results if r.target_met]
    if valid:
        valid.sort(key=lambda r: r.threshold, reverse=True)
        return valid[0]
    else:
        zero_res = [r for r in results if abs(r.threshold - 0.0) < 1e-9]
        if zero_res:
            return ThresholdResult(
                threshold=0.0,
                recall=zero_res[0].recall,
                precision=zero_res[0].precision,
                target_met=False,
            )
        else:
            return ThresholdResult(0.0, 0.0, 0.0, False)


def write_threshold(
    config_path: Path,
    result: ThresholdResult,
    target_recall: float = 0.98,
    doc_count: int = 0,
) -> None:
    """Updates `threshold` in config YAML and updates/creates MODEL_CARD.md in output_dir."""
    config_text = config_path.read_text(encoding="utf-8")
    data = yaml.safe_load(config_text) or {}
    data["threshold"] = result.threshold
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    output_dir = Path(data.get("output_dir", "training/out"))
    output_dir.mkdir(parents=True, exist_ok=True)
    model_card_path = output_dir / "MODEL_CARD.md"

    section = (
        f"\n## Kalibracja progu\n\n"
        f"- **Próg (Threshold):** {result.threshold}\n"
        f"- **Recall:** {result.recall:.4f}\n"
        f"- **Precision:** {result.precision:.4f}\n"
        f"- **Target Recall:** {target_recall}\n"
        f"- **Target Met:** {result.target_met}\n"
        f"- **Liczba dokumentów:** {doc_count}\n"
    )

    if model_card_path.exists():
        content = model_card_path.read_text(encoding="utf-8")
        if "## Kalibracja progu" in content:
            parts = content.split("## Kalibracja progu")
            base = parts[0].rstrip()
            rest = parts[1]
            next_sections = rest.split("\n## ")
            remainder = "\n## ".join(next_sections[1:]) if len(next_sections) > 1 else ""
            new_content = (
                base + "\n\n" + section.strip() + ("\n\n## " + remainder if remainder else "\n")
            )
        else:
            new_content = content.rstrip() + "\n\n" + section.strip() + "\n"
    else:
        new_content = f"# Model Card\n\n{section.strip()}\n"

    model_card_path.write_text(new_content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print(
            "Usage: python -m training.calibrate <config.yaml> [predictions.jsonl]", file=sys.stderr
        )
        return 2

    config_path = Path(argv[0])
    try:
        config = load_config(config_path)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return 1

    predictions_path = Path(argv[1]) if len(argv) > 1 else config.output_dir / "predictions.jsonl"

    if predictions_path.exists() and len(argv) > 1:
        raw_docs = read_jsonl(predictions_path)
        docs = []
        for r in raw_docs:
            gold = [
                Span(
                    s["start"],
                    s["end"],
                    s["label"],
                    s.get("source", "gold"),
                    s.get("score"),
                    s.get("status", "valid"),
                )
                for s in r.get("gold", [])
            ]
            pred = [
                Span(
                    p["start"],
                    p["end"],
                    p["label"],
                    p.get("source", "pred"),
                    p.get("score", 1.0),
                    p.get("status", "valid"),
                )
                for p in r.get("pred", [])
            ]
            docs.append(DocPrediction(gold=gold, pred=pred))
    else:
        eval_records = read_jsonl(config.eval_file)

        checkpoint = config.base_checkpoint
        if config.output_dir.exists():
            checkpoints = list(config.output_dir.glob("checkpoint-*"))
            if checkpoints:
                checkpoints.sort(key=lambda p: int(p.name.split("-")[-1]))
                checkpoint = checkpoints[-1]
            elif (config.output_dir / "config.json").exists():
                checkpoint = config.output_dir

        predictor = NerPredictor(checkpoint=checkpoint, threshold=0.0)

        docs = []
        predictions_output = []
        for r in eval_records:
            gold_spans = [
                Span(
                    s["start"],
                    s["end"],
                    s["label"],
                    s.get("source", "gold"),
                    s.get("score"),
                    s.get("status", "valid"),
                )
                for s in r.get("spans", r.get("gold", []))
            ]
            pred_spans = predictor.predict(r["text"])
            docs.append(DocPrediction(gold=gold_spans, pred=pred_spans))

            predictions_output.append(
                {
                    "id": r.get("id"),
                    "text": r["text"],
                    "gold": [
                        {"start": s.start, "end": s.end, "label": s.label} for s in gold_spans
                    ],
                    "pred": [
                        {"start": s.start, "end": s.end, "label": s.label, "score": s.score}
                        for s in pred_spans
                    ],
                }
            )

        config.output_dir.mkdir(parents=True, exist_ok=True)
        predictions_path.write_text(
            "\n".join(json.dumps(d, ensure_ascii=False) for d in predictions_output) + "\n",
            encoding="utf-8",
        )

    result = calibrate_threshold(docs, target_recall=0.98)
    write_threshold(config_path, result, target_recall=0.98, doc_count=len(docs))

    print(
        "Calibration completed: threshold="
        f"{result.threshold}, recall={result.recall:.4f}, "
        f"precision={result.precision:.4f}, target_met={result.target_met}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
