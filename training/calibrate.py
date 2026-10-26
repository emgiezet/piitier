from __future__ import annotations

import importlib.util
import math
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml

if "eval.metrics" not in sys.modules:
    _metrics_path = Path(__file__).resolve().parent.parent / "eval" / "metrics.py"
    _spec_m = importlib.util.spec_from_file_location("eval.metrics", _metrics_path)
    if _spec_m is not None and _spec_m.loader is not None:
        _metrics_mod = importlib.util.module_from_spec(_spec_m)
        sys.modules["eval.metrics"] = _metrics_mod
        _spec_m.loader.exec_module(_metrics_mod)

from eval.metrics import (
    GROUP_WEIGHTS,
    _entity_counts,
    corpus_entity_metrics,
    group_for_label,
)
from piitier.labels import Label
from piitier.ner.inference import NerPredictor
from piitier.spans import Span
from training.config import load_config
from training.train import read_jsonl

_MatchMode = Literal["strict", "partial"]


def to_label(val: str | Label) -> Label:
    if isinstance(val, Label):
        return val
    try:
        return Label[val]
    except KeyError:
        for member in Label:
            if member.value == val or member.name == val:
                return member
        raise KeyError(f"Unknown label: {val}")


@dataclass(frozen=True)
class GroupRecall:
    """Per-risk-group recall with span count."""

    group: str
    recall: float
    span_count: int


@dataclass(frozen=True)
class ThresholdResult:
    threshold: float
    recall: float
    precision: float
    target_met: bool
    reason: str | None = None  # None = success; "unsupported"; "target_not_met"
    gold_span_count: int = 0
    doc_count: int = 0
    group_recalls: tuple[GroupRecall, ...] = field(default_factory=tuple)
    wilson_lower: float = 0.0
    wilson_upper: float = 0.0


@dataclass(frozen=True)
class DocPrediction:
    gold: list[Span]
    pred: list[Span]


def wilson_interval(tp: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score confidence interval for recall (tp successes out of n total).

    Returns (lower, upper) both clamped to [0, 1].
    Returns (0.0, 1.0) when n == 0 (maximum uncertainty).
    """
    if n == 0:
        return (0.0, 1.0)
    p = tp / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))
    return (max(0.0, center - margin), min(1.0, center + margin))


def _as_match_mode(s: str) -> _MatchMode:
    """Convert a validated string to the Literal match mode type."""
    if s == "partial":
        return "partial"
    return "strict"


def _compute_group_recalls(
    gold_docs: list[list[Span]],
    pred_docs: list[list[Span]],
    match: _MatchMode,
) -> tuple[GroupRecall, ...]:
    """Compute per-risk-group recall over the corpus at a fixed threshold."""
    group_tp: dict[str, int] = {g: 0 for g in GROUP_WEIGHTS}
    group_fn: dict[str, int] = {g: 0 for g in GROUP_WEIGHTS}

    for gold_doc, pred_doc in zip(gold_docs, pred_docs):
        for group in GROUP_WEIGHTS:
            g = [s for s in gold_doc if group_for_label(s.label) == group]
            p = [s for s in pred_doc if group_for_label(s.label) == group]
            if not g and not p:
                continue
            tp, _fp, fn = _entity_counts(g, p, match)
            group_tp[group] += tp
            group_fn[group] += fn

    results: list[GroupRecall] = []
    for group in GROUP_WEIGHTS:
        tp = group_tp[group]
        fn = group_fn[group]
        span_count = tp + fn
        recall = tp / span_count if span_count > 0 else 0.0
        results.append(GroupRecall(group=group, recall=recall, span_count=span_count))
    return tuple(results)


def _make_result(
    threshold: float,
    prf: Any,
    pred_docs: list[list[Span]],
    gold_docs: list[list[Span]],
    total_gold: int,
    doc_count: int,
    match: _MatchMode,
    target_recall: float,
) -> ThresholdResult:
    """Compute Wilson interval and group recalls for one candidate threshold."""
    target_met = prf.recall >= target_recall
    tp = round(prf.recall * total_gold)
    w_lower, w_upper = wilson_interval(tp, total_gold)
    gr = _compute_group_recalls(gold_docs, pred_docs, match)
    return ThresholdResult(
        threshold=float(threshold),
        recall=float(prf.recall),
        precision=float(prf.precision),
        target_met=target_met,
        reason=None if target_met else "target_not_met",
        gold_span_count=total_gold,
        doc_count=doc_count,
        group_recalls=gr,
        wilson_lower=w_lower,
        wilson_upper=w_upper,
    )


def calibrate_threshold(
    docs: list[dict[str, Any] | DocPrediction],
    target_recall: float = 0.98,
    match: _MatchMode = "strict",
    min_support: int = 0,
) -> ThresholdResult:
    """Calibrate detection threshold targeting recall >= target_recall.

    Candidates: 0.0 + sorted unique prediction scores (descending).
    For threshold t: predicted spans with score >= t; PRF via corpus_entity_metrics.
    Matching is per-document (a prediction from doc B cannot match gold from doc A).
    Returns the highest threshold with recall >= target_recall (early exit on first hit).
    Wilson interval and group recalls are computed only for the returned result.

    Args:
        min_support: minimum number of gold spans required; 0 = no minimum.
            When total gold spans < min_support, returns reason="unsupported".
        match: "strict" (exact [start,end)) or "partial" (any overlap, same label).

    Returns:
        ThresholdResult with reason=None on success, or reason in
        {"unsupported", "target_not_met"} on failure.  Config is only written
        by the caller when reason is None.
    """
    doc_count = len(docs)

    # Collect all prediction scores as threshold candidates.
    # score=None is coerced to 1.0 at application time, so include 1.0 as a candidate.
    scores: set[float] = {0.0}
    for doc in docs:
        p_list = doc["pred"] if isinstance(doc, dict) else doc.pred
        for p in p_list:
            score = p.get("score", 1.0) if isinstance(p, dict) else getattr(p, "score", 1.0)
            scores.add(float(score) if score is not None else 1.0)

    # Build per-doc gold span lists and scored pred lists (done once, not per threshold)
    gold_docs: list[list[Span]] = []
    raw_preds: list[list[tuple[Span, float]]] = []
    for doc in docs:
        g = doc["gold"] if isinstance(doc, dict) else doc.gold
        p_list = doc["pred"] if isinstance(doc, dict) else doc.pred

        gold_spans = [
            Span(
                start=item.start if isinstance(item, Span) else item["start"],
                end=item.end if isinstance(item, Span) else item["end"],
                label=to_label(item.label if isinstance(item, Span) else item["label"]),
                source=item.source if isinstance(item, Span) else item.get("source", "gold"),
                score=item.score if isinstance(item, Span) else item.get("score"),
                status=item.status if isinstance(item, Span) else item.get("status", "valid"),
            )
            for item in g
        ]
        scored_preds: list[tuple[Span, float]] = []
        for item in p_list:
            span_obj = Span(
                start=item.start if isinstance(item, Span) else item["start"],
                end=item.end if isinstance(item, Span) else item["end"],
                label=to_label(item.label if isinstance(item, Span) else item["label"]),
                source=item.source if isinstance(item, Span) else item.get("source", "pred"),
                score=item.score if isinstance(item, Span) else item.get("score", 1.0),
                status=item.status if isinstance(item, Span) else item.get("status", "valid"),
            )
            item_score = float(span_obj.score) if span_obj.score is not None else 1.0
            scored_preds.append((span_obj, item_score))
        gold_docs.append(gold_spans)
        raw_preds.append(scored_preds)

    # Count total gold spans for support check
    total_gold = sum(len(gold) for gold in gold_docs)

    # Unsupported: not enough gold spans
    if min_support > 0 and total_gold < min_support:
        pred_docs_at_0 = [[sp for sp, _sc in doc_preds] for doc_preds in raw_preds]
        prf = corpus_entity_metrics(gold_docs, pred_docs_at_0, match=match)
        result = _make_result(
            0.0, prf, pred_docs_at_0, gold_docs, total_gold, doc_count, match, target_recall
        )
        return ThresholdResult(
            threshold=result.threshold,
            recall=result.recall,
            precision=result.precision,
            target_met=False,
            reason="unsupported",
            gold_span_count=total_gold,
            doc_count=doc_count,
            group_recalls=result.group_recalls,
            wilson_lower=result.wilson_lower,
            wilson_upper=result.wilson_upper,
        )

    # Iterate candidates from highest to lowest; break at the first hit (= highest valid threshold).
    # Group recalls and Wilson are computed only for the returned result.
    candidates = sorted(list(scores), reverse=True)
    fallback_prf: Any = None
    fallback_pred_docs: list[list[Span]] = []

    for t in candidates:
        pred_docs = [[sp for sp, sc in doc_preds if sc >= t] for doc_preds in raw_preds]
        prf = corpus_entity_metrics(gold_docs, pred_docs, match=match)

        if abs(t) < 1e-9:
            # Save 0.0 stats for fallback if no threshold meets the target
            fallback_prf = prf
            fallback_pred_docs = pred_docs

        if prf.recall >= target_recall:
            # First (= highest) threshold that meets the target — return immediately
            return _make_result(
                t, prf, pred_docs, gold_docs, total_gold, doc_count, match, target_recall
            )

    # No threshold met target — report recall at 0.0
    if fallback_prf is not None:
        result = _make_result(
            0.0,
            fallback_prf,
            fallback_pred_docs,
            gold_docs,
            total_gold,
            doc_count,
            match,
            target_recall,
        )
        return ThresholdResult(
            threshold=0.0,
            recall=result.recall,
            precision=result.precision,
            target_met=False,
            reason="target_not_met",
            gold_span_count=total_gold,
            doc_count=doc_count,
            group_recalls=result.group_recalls,
            wilson_lower=result.wilson_lower,
            wilson_upper=result.wilson_upper,
        )

    # Absolute fallback: empty docs
    return ThresholdResult(0.0, 0.0, 0.0, False, "target_not_met", total_gold, doc_count)


# ---------------------------------------------------------------------------
# MODEL_CARD writing
# ---------------------------------------------------------------------------


def _get_output_dir(config_path: Path) -> Path:
    """Resolve output_dir from config YAML relative to the config file's directory."""
    out_val = (yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}).get(
        "output_dir", "training/out"
    )
    output_dir = Path(str(out_val))
    if not output_dir.is_absolute():
        output_dir = (config_path.parent / output_dir).resolve()
    return output_dir


def _success_section(result: ThresholdResult, target_recall: float, match_mode: str) -> str:
    """Build the full ## Kalibracja progu section text for a successful calibration."""
    today = date.today().isoformat()
    lines: list[str] = [
        "## Kalibracja progu\n",
        f"\n- **Data kalibracji:** {today}",
        f"\n- **Próg (Threshold):** {result.threshold}",
        f"\n- **Recall:** {result.recall:.4f}",
        f"\n- **Precision:** {result.precision:.4f}",
        f"\n- **Target Recall:** {target_recall}",
        f"\n- **Match Mode:** {match_mode}",
        f"\n- **Liczba spanów gold:** {result.gold_span_count}",
        f"\n- **Liczba dokumentów:** {result.doc_count}",
        (
            f"\n- **Przedział ufności Wilsona 95%:** "
            f"[{result.wilson_lower:.4f}, {result.wilson_upper:.4f}]"
        ),
    ]
    if result.group_recalls:
        lines.append("\n\n### Recall per grupa ryzyka\n")
        for gr in result.group_recalls:
            if gr.span_count > 0:
                lines.append(f"\n- **{gr.group}:** recall={gr.recall:.4f}, spans={gr.span_count}")
    return "".join(lines) + "\n"


def _failure_subsection(result: ThresholdResult, match_mode: str) -> str:
    """Build a ### Nieudana próba subsection for a failed calibration."""
    today = date.today().isoformat()
    reason = result.reason or "unknown"
    lines: list[str] = [
        f"\n### Nieudana próba kalibracji ({today})\n",
        f"\n- **Próg:** nie zapisano ({reason})",
        f"\n- **Recall:** {result.recall:.4f}",
        f"\n- **Match Mode:** {match_mode}",
        f"\n- **Liczba spanów gold:** {result.gold_span_count}",
        f"\n- **Liczba dokumentów:** {result.doc_count}",
        (
            f"\n- **Przedział ufności Wilsona 95%:** "
            f"[{result.wilson_lower:.4f}, {result.wilson_upper:.4f}]"
        ),
    ]
    if result.group_recalls:
        for gr in result.group_recalls:
            if gr.span_count > 0:
                lines.append(f"\n- **{gr.group}:** recall={gr.recall:.4f}, spans={gr.span_count}")
    return "".join(lines) + "\n"


def _write_model_card(
    config_path: Path,
    result: ThresholdResult,
    target_recall: float,
    match_mode: str,
) -> None:
    """Write (or update) the '## Kalibracja progu' section in MODEL_CARD.md.

    On success (reason is None): overwrites the section with the new threshold and date.
    On failure: keeps the existing section intact (preserving the last successful threshold)
    and appends a failure sub-section.  Never shows a numeric threshold on failure.
    """
    output_dir = _get_output_dir(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_card_path = output_dir / "MODEL_CARD.md"

    if result.reason is None:
        # SUCCESS: overwrite the section with new data
        section = _success_section(result, target_recall, match_mode)
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
    else:
        # FAILURE: preserve the existing ## Kalibracja progu section; append failure subsection.
        # If no section exists yet, create a minimal one that only shows the failure.
        failure = _failure_subsection(result, match_mode)
        if model_card_path.exists():
            content = model_card_path.read_text(encoding="utf-8")
            if "## Kalibracja progu" in content:
                # Insert failure sub-section before the next top-level ## heading
                parts = content.split("## Kalibracja progu")
                base = parts[0]
                rest = parts[1]
                next_sections = rest.split("\n## ")
                section_body = next_sections[0].rstrip()
                remainder = "\n## ".join(next_sections[1:]) if len(next_sections) > 1 else ""
                new_content = (
                    base
                    + "## Kalibracja progu"
                    + section_body
                    + "\n\n"
                    + failure.strip()
                    + ("\n\n## " + remainder if remainder else "\n")
                )
            else:
                # No success section yet: create failure-only section
                new_content = (
                    content.rstrip() + "\n\n## Kalibracja progu\n\n" + failure.strip() + "\n"
                )
        else:
            new_content = f"# Model Card\n\n## Kalibracja progu\n\n{failure.strip()}\n"
        model_card_path.write_text(new_content, encoding="utf-8")


def write_threshold(
    config_path: Path,
    result: ThresholdResult,
    target_recall: float = 0.98,
    doc_count: int = 0,
    match_mode: str = "strict",
) -> None:
    """Write threshold to config YAML (only when result.reason is None) and update MODEL_CARD.md.

    The MODEL_CARD section is always written.  The config threshold is written
    only on success (reason is None), leaving the config byte-identical on failure.
    """
    # Merge doc_count: prefer result.doc_count; fall back to the parameter for backward compat.
    if result.doc_count == 0 and doc_count > 0:
        result = ThresholdResult(
            threshold=result.threshold,
            recall=result.recall,
            precision=result.precision,
            target_met=result.target_met,
            reason=result.reason,
            gold_span_count=result.gold_span_count,
            doc_count=doc_count,
            group_recalls=result.group_recalls,
            wilson_lower=result.wilson_lower,
            wilson_upper=result.wilson_upper,
        )

    # Write config threshold only on success
    if result.reason is None:
        config_text = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(config_text) or {}
        data["threshold"] = result.threshold
        config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    _write_model_card(config_path, result, target_recall=target_recall, match_mode=match_mode)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print(
            "Usage: python -m training.calibrate <config.yaml>",
            file=sys.stderr,
        )
        return 2

    config_path = Path(argv[0])
    try:
        config = load_config(config_path)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return 1

    # UC-141: calibration_file must be present in config
    if config.calibration_file is None:
        print(
            "calibration_file is not set in config; cannot calibrate. "
            "Set the 'calibration_file' key in the config YAML.",
            file=sys.stderr,
        )
        return 2

    # Always run the predictor on calibration_file (UC-145: eval_file is never read here)
    cal_records = read_jsonl(config.calibration_file)

    checkpoint = config.base_checkpoint
    if config.output_dir.exists():
        checkpoints = list(config.output_dir.glob("checkpoint-*"))
        if checkpoints:
            checkpoints.sort(key=lambda p: int(p.name.split("-")[-1]))
            checkpoint = checkpoints[-1]
        elif (config.output_dir / "config.json").exists():
            checkpoint = config.output_dir

    predictor = NerPredictor(checkpoint=checkpoint, threshold=0.0)

    docs: list[DocPrediction] = []
    for r in cal_records:
        gold_spans = [
            Span(
                s["start"],
                s["end"],
                to_label(s["label"]),
                s.get("source", "gold"),
                s.get("score"),
                s.get("status", "valid"),
            )
            for s in r.get("spans", r.get("gold", []))
        ]
        pred_spans = predictor.predict(r["text"])
        docs.append(DocPrediction(gold=gold_spans, pred=pred_spans))

    result = calibrate_threshold(
        docs,
        target_recall=config.calibration_target_recall,
        match=_as_match_mode(config.calibration_match),
        min_support=config.calibration_min_support,
    )

    write_threshold(
        config_path,
        result,
        target_recall=config.calibration_target_recall,
        match_mode=config.calibration_match,
    )

    if result.reason is None:
        print(
            f"Calibration completed: threshold={result.threshold}, "
            f"recall={result.recall:.4f}, precision={result.precision:.4f}, "
            f"gold_spans={result.gold_span_count}, docs={result.doc_count}, "
            f"wilson=[{result.wilson_lower:.4f}, {result.wilson_upper:.4f}]"
        )
        return 0
    else:
        print(
            f"Calibration failed: reason={result.reason}, "
            f"recall={result.recall:.4f}, gold_spans={result.gold_span_count}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
