"""Inter-annotator agreement metrics (eval/agreement.py) — PII-11.

CLI: ``python -m eval.agreement <file>``

Computes span F1 (strict and partial, overall and per label) and Cohen's kappa
over per-character labels (``O`` = outside all spans) for the **first two
annotators** in each record of a v2 bench JSONL file.

Output
------
One ``key: value`` line per metric, 4 decimal places, sorted alphabetically.
No document text or PII values appear in the output.

Exit codes
----------
0 — kappa ≥ 0.7
1 — kappa < 0.7 (message with value and threshold printed to stderr)
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

_KAPPA_THRESHOLD = 0.7
_OUTSIDE = "O"


def _char_labels(text: str, spans: list[dict[str, Any]]) -> list[str]:
    """Return per-character label list; positions outside spans get ``'O'``."""
    labels = [_OUTSIDE] * len(text)
    for span in spans:
        s = span.get("start", 0)
        e = span.get("end", 0)
        lbl = span.get("label", _OUTSIDE)
        for i in range(s, e):
            if 0 <= i < len(labels):
                labels[i] = lbl
    return labels


def _spans_match(a: dict[str, Any], b: dict[str, Any], mode: str) -> bool:
    """Return True when span *a* and span *b* match under *mode*."""
    if a.get("label") != b.get("label"):
        return False
    as_, ae = a.get("start", 0), a.get("end", 0)
    bs, be = b.get("start", 0), b.get("end", 0)
    if mode == "strict":
        return as_ == bs and ae == be
    # partial: same label + any character-level overlap
    return max(as_, bs) < min(ae, be)


def _entity_counts(
    gold: list[dict[str, Any]],
    pred: list[dict[str, Any]],
    mode: str,
) -> tuple[int, int, int]:
    """Return (TP, FP, FN); each span matched at most once."""
    pred_matched = [False] * len(pred)
    tp = 0
    for g in gold:
        for j, p in enumerate(pred):
            if not pred_matched[j] and _spans_match(g, p, mode):
                tp += 1
                pred_matched[j] = True
                break
    fp = sum(1 for m in pred_matched if not m)
    fn = len(gold) - tp
    return tp, fp, fn


def _f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    prec = tp / (tp + fp) if tp + fp > 0 else 0.0
    rec = tp / (tp + fn) if tp + fn > 0 else 0.0
    f1 = 2.0 * prec * rec / (prec + rec) if prec + rec > 0 else 0.0
    return prec, rec, f1


def compute_agreement(records: list[dict[str, Any]]) -> dict[str, float]:
    """Return a metric-name → value dict from a list of v2 records.

    Only the first two annotators per record are used.  Records with fewer
    than two annotators are skipped.
    """
    # Global span counts (micro-aggregated)
    tp_s = fp_s = fn_s = 0
    tp_p = fp_p = fn_p = 0

    # Per-label span counts
    lbl_tp_s: dict[str, int] = defaultdict(int)
    lbl_fp_s: dict[str, int] = defaultdict(int)
    lbl_fn_s: dict[str, int] = defaultdict(int)
    lbl_tp_p: dict[str, int] = defaultdict(int)
    lbl_fp_p: dict[str, int] = defaultdict(int)
    lbl_fn_p: dict[str, int] = defaultdict(int)

    # Character-level kappa accumulators
    char_agree = 0
    char_total = 0
    cnt_a: dict[str, int] = defaultdict(int)
    cnt_b: dict[str, int] = defaultdict(int)

    for rec in records:
        anns = rec.get("annotations", [])
        if len(anns) < 2:
            continue
        spans_a: list[dict[str, Any]] = anns[0].get("spans", [])
        spans_b: list[dict[str, Any]] = anns[1].get("spans", [])
        text: str = rec.get("text", "")

        # Global span F1
        a, b, c = _entity_counts(spans_a, spans_b, "strict")
        tp_s += a
        fp_s += b
        fn_s += c
        a, b, c = _entity_counts(spans_a, spans_b, "partial")
        tp_p += a
        fp_p += b
        fn_p += c

        # Per-label span F1
        all_lbls = {s.get("label") for s in spans_a + spans_b} - {None}
        for lbl in all_lbls:
            ga = [s for s in spans_a if s.get("label") == lbl]
            gb = [s for s in spans_b if s.get("label") == lbl]
            t, f, n = _entity_counts(ga, gb, "strict")
            lbl_tp_s[lbl] += t
            lbl_fp_s[lbl] += f
            lbl_fn_s[lbl] += n
            t, f, n = _entity_counts(ga, gb, "partial")
            lbl_tp_p[lbl] += t
            lbl_fp_p[lbl] += f
            lbl_fn_p[lbl] += n

        # Character-level kappa
        la = _char_labels(text, spans_a)
        lb = _char_labels(text, spans_b)
        for ca, cb in zip(la, lb):
            char_total += 1
            if ca == cb:
                char_agree += 1
            cnt_a[ca] += 1
            cnt_b[cb] += 1

    # Overall F1
    _, _, f1_strict = _f1(tp_s, fp_s, fn_s)
    _, _, f1_partial = _f1(tp_p, fp_p, fn_p)

    # Per-label F1
    all_seen = set(lbl_tp_s) | set(lbl_fp_s) | set(lbl_fn_s)
    per_strict: dict[str, float] = {}
    per_partial: dict[str, float] = {}
    for lbl in all_seen:
        _, _, f = _f1(lbl_tp_s[lbl], lbl_fp_s[lbl], lbl_fn_s[lbl])
        per_strict[lbl] = f
        _, _, f = _f1(lbl_tp_p[lbl], lbl_fp_p[lbl], lbl_fn_p[lbl])
        per_partial[lbl] = f

    # Cohen's kappa (character-level multi-class)
    if char_total == 0:
        kappa = 0.0
    else:
        p_o = char_agree / char_total
        all_classes = set(cnt_a) | set(cnt_b)
        p_e = sum(
            (cnt_a.get(cl, 0) / char_total) * (cnt_b.get(cl, 0) / char_total) for cl in all_classes
        )
        denom = 1.0 - p_e
        kappa = (p_o - p_e) / denom if denom > 1e-12 else 0.0

    result: dict[str, float] = {
        "kappa": kappa,
        "partial_overall": f1_partial,
        "strict_overall": f1_strict,
    }
    for lbl, f in per_strict.items():
        result[f"strict_{lbl}"] = f
    for lbl, f in per_partial.items():
        result[f"partial_{lbl}"] = f

    return result


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: python -m eval.agreement <file>", file=sys.stderr)
        return 1

    path = Path(args[0])
    if not path.exists():
        print(f"error: file not found: {args[0]}", file=sys.stderr)
        return 1

    with path.open(encoding="utf-8") as fh:
        records = [json.loads(line) for line in fh if line.strip()]

    metrics = compute_agreement(records)

    for key in sorted(metrics):
        print(f"{key}: {metrics[key]:.4f}")

    kappa = metrics.get("kappa", 0.0)
    if kappa < _KAPPA_THRESHOLD:
        print(
            f"kappa {kappa:.4f} < threshold {_KAPPA_THRESHOLD:.4f}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
