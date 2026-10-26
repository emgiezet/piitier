"""Inter-annotator agreement metrics (eval/agreement.py) — PII-11.

CLI: ``python -m eval.agreement <file>``

Computes span F1 (strict and partial, overall and per label) and Cohen's kappa
over per-character labels (``O`` = outside all spans) for the **first two
annotators** in each record of a v2 bench JSONL file.  Metrics are
micro-aggregated (pooled) across all records.

Output
------
One ``key: value`` line per metric, 4 decimal places, sorted alphabetically.
Per-label keys are emitted only for labels that are valid ``piitier.labels.Label``
member names; any unknown label causes an immediate exit 2.
No file-supplied value appears in the output.

Exit codes
----------
0 — kappa ≥ 0.7
1 — kappa < 0.7 (message on stderr)
2 — any input error (missing file, malformed JSON, unknown label, no characters)
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from piitier.labels import Label

_VALID_LABEL_NAMES: frozenset[str] = frozenset(lbl.name for lbl in Label)
_KAPPA_THRESHOLD = 0.7
_OUTSIDE = "O"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _char_labels(text: str, spans: list[dict[str, Any]]) -> list[str]:
    """Return per-character label list.

    Positions not covered by any span get ``'O'``.  When spans overlap,
    the span that comes *last* in ``(start, end, label)`` sorted order wins.
    The sort makes the result deterministic regardless of the input order.
    """
    labels = [_OUTSIDE] * len(text)
    for span in sorted(
        spans, key=lambda s: (s.get("start", 0), s.get("end", 0), s.get("label", ""))
    ):
        s: int = span.get("start", 0)
        e: int = span.get("end", 0)
        lbl: str = span.get("label", _OUTSIDE)
        for i in range(s, e):
            if 0 <= i < len(labels):
                labels[i] = lbl
    return labels


def _spans_match(a: dict[str, Any], b: dict[str, Any], mode: str) -> bool:
    """Return True when span *a* and span *b* match under *mode*."""
    if a.get("label") != b.get("label"):
        return False
    as_: int = int(a.get("start", 0))
    ae: int = int(a.get("end", 0))
    bs: int = int(b.get("start", 0))
    be: int = int(b.get("end", 0))
    if mode == "strict":
        return as_ == bs and ae == be
    # partial: same label + any character-level overlap
    return bool(max(as_, bs) < min(ae, be))


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
    prec: float = tp / (tp + fp) if tp + fp > 0 else 0.0
    rec: float = tp / (tp + fn) if tp + fn > 0 else 0.0
    f1: float = 2.0 * prec * rec / (prec + rec) if prec + rec > 0.0 else 0.0
    return prec, rec, f1


def _validate_labels(records: list[dict[str, Any]]) -> list[str]:
    """Check all annotation span labels; return errors (no file values echoed)."""
    errors: list[str] = []
    for lineno, rec in enumerate(records, start=1):
        if not isinstance(rec, dict):
            continue
        anns = rec.get("annotations", [])
        if not isinstance(anns, list):
            continue
        for j, ann in enumerate(anns):
            if not isinstance(ann, dict):
                continue
            spans = ann.get("spans", [])
            if not isinstance(spans, list):
                continue
            for k, span in enumerate(spans):
                if not isinstance(span, dict):
                    continue
                label = span.get("label")
                if isinstance(label, str):
                    if label not in _VALID_LABEL_NAMES:
                        errors.append(
                            f"line {lineno}: label: unknown label in annotations[{j}].spans[{k}]"
                        )
                elif label is not None:
                    errors.append(
                        f"line {lineno}: label: non-string label in annotations[{j}].spans[{k}]"
                    )
    return errors


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_agreement(records: list[dict[str, Any]]) -> dict[str, float]:
    """Return a metric-name → value dict from a list of v2 records.

    Only the first two annotators per record are used.  Records with fewer
    than two annotators are skipped and counted in the ``skipped_records`` key.

    All label names in the output (``strict_<LABEL>``, ``partial_<LABEL>``)
    are valid ``piitier.labels.Label`` member names.  Callers should validate
    labels before calling this function (see ``_validate_labels``).

    Special keys (not printed directly):
    - ``_char_total``: total character positions compared (used to detect
      empty input — the caller should exit 2 when this is 0).
    """
    # Global span counts (micro-aggregated)
    tp_s: int = 0
    fp_s: int = 0
    fn_s: int = 0
    tp_p: int = 0
    fp_p: int = 0
    fn_p: int = 0

    # Per-label span counts
    lbl_tp_s: dict[str, int] = defaultdict(int)
    lbl_fp_s: dict[str, int] = defaultdict(int)
    lbl_fn_s: dict[str, int] = defaultdict(int)
    lbl_tp_p: dict[str, int] = defaultdict(int)
    lbl_fp_p: dict[str, int] = defaultdict(int)
    lbl_fn_p: dict[str, int] = defaultdict(int)

    # Character-level kappa accumulators
    char_agree: int = 0
    char_total: int = 0
    cnt_a: dict[str, int] = defaultdict(int)
    cnt_b: dict[str, int] = defaultdict(int)

    skipped: int = 0

    for rec in records:
        if not isinstance(rec, dict):
            skipped += 1
            continue
        anns = rec.get("annotations", [])
        if not isinstance(anns, list) or len(anns) < 2:
            skipped += 1
            continue
        ann0 = anns[0]
        ann1 = anns[1]
        if not isinstance(ann0, dict) or not isinstance(ann1, dict):
            skipped += 1
            continue
        spans_a: list[dict[str, Any]] = [s for s in ann0.get("spans", []) if isinstance(s, dict)]
        spans_b: list[dict[str, Any]] = [s for s in ann1.get("spans", []) if isinstance(s, dict)]
        raw_text = rec.get("text")
        text: str = raw_text if isinstance(raw_text, str) else ""

        # Global span F1
        tp_, fp_, fn_ = _entity_counts(spans_a, spans_b, "strict")
        tp_s += tp_
        fp_s += fp_
        fn_s += fn_
        tp_, fp_, fn_ = _entity_counts(spans_a, spans_b, "partial")
        tp_p += tp_
        fp_p += fp_
        fn_p += fn_

        # Per-label span F1 (only valid label names)
        all_lbls: set[str] = set()
        for s in spans_a + spans_b:
            lbl_val = s.get("label")
            if isinstance(lbl_val, str) and lbl_val in _VALID_LABEL_NAMES:
                all_lbls.add(lbl_val)

        for lbl in all_lbls:
            ga = [s for s in spans_a if s.get("label") == lbl]
            gb = [s for s in spans_b if s.get("label") == lbl]
            tps, fps, fns = _entity_counts(ga, gb, "strict")
            lbl_tp_s[lbl] += tps
            lbl_fp_s[lbl] += fps
            lbl_fn_s[lbl] += fns
            tpp, fpp, fnp = _entity_counts(ga, gb, "partial")
            lbl_tp_p[lbl] += tpp
            lbl_fp_p[lbl] += fpp
            lbl_fn_p[lbl] += fnp

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
    all_seen: set[str] = set(lbl_tp_s) | set(lbl_fp_s) | set(lbl_fn_s)
    per_strict: dict[str, float] = {}
    per_partial: dict[str, float] = {}
    for lbl in all_seen:
        _, _, f1v = _f1(lbl_tp_s[lbl], lbl_fp_s[lbl], lbl_fn_s[lbl])
        per_strict[lbl] = f1v
        _, _, f1v = _f1(lbl_tp_p[lbl], lbl_fp_p[lbl], lbl_fn_p[lbl])
        per_partial[lbl] = f1v

    # Cohen's kappa (character-level multi-class, pooled over all records)
    if char_total == 0:
        kappa = 0.0
    else:
        p_o: float = char_agree / char_total
        all_classes: set[str] = set(cnt_a) | set(cnt_b)
        p_e: float = sum(
            (cnt_a.get(cl, 0) / char_total) * (cnt_b.get(cl, 0) / char_total) for cl in all_classes
        )
        # When p_e ≥ 1−ε, both annotators assigned every character the same
        # single class and agree perfectly → kappa = 1.0.
        if p_e >= 1.0 - 1e-12:
            kappa = 1.0
        else:
            kappa = (p_o - p_e) / (1.0 - p_e)

    result: dict[str, float] = {
        "kappa": kappa,
        "partial_overall": f1_partial,
        "strict_overall": f1_strict,
        "_char_total": float(char_total),
        "_skipped": float(skipped),
    }
    for lbl, f1v in per_strict.items():
        result[f"strict_{lbl}"] = f1v
    for lbl, f1v in per_partial.items():
        result[f"partial_{lbl}"] = f1v

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: python -m eval.agreement <file>", file=sys.stderr)
        return 2

    path = Path(args[0])
    if not path.exists():
        print(f"error: not found: {args[0]}", file=sys.stderr)
        return 2
    if not path.is_file():
        print(f"error: not a file: {args[0]}", file=sys.stderr)
        return 2

    records: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    print(
                        f"error: malformed JSON at line {lineno}: {args[0]}",
                        file=sys.stderr,
                    )
                    return 2
                if not isinstance(obj, dict):
                    print(
                        f"error: non-object at line {lineno}: {args[0]}",
                        file=sys.stderr,
                    )
                    return 2
                records.append(obj)
    except OSError as exc:
        print(f"error: {args[0]}: {exc.strerror}", file=sys.stderr)
        return 2

    # Validate all labels before computing metrics
    label_errors = _validate_labels(records)
    if label_errors:
        for err in label_errors:
            print(err, file=sys.stderr)
        return 2

    metrics = compute_agreement(records)

    char_total = int(metrics.pop("_char_total", 0.0))
    skipped = int(metrics.pop("_skipped", 0.0))

    if char_total == 0:
        print(
            "error: no characters to compare (empty file, all records skipped, or all texts empty)",
            file=sys.stderr,
        )
        return 2

    for key in sorted(metrics):
        print(f"{key}: {metrics[key]:.4f}")
    if skipped:
        print(f"skipped_records: {skipped}")

    kappa: float = metrics.get("kappa", 0.0)
    if kappa < _KAPPA_THRESHOLD:
        print(
            f"kappa {kappa:.4f} < threshold {_KAPPA_THRESHOLD:.4f}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
