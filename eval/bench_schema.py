"""Bench schema v2 validator (eval/bench_schema.py) — PII-11.

CLI: ``python -m eval.bench_schema <file> ...``

Validates v2 bench JSONL files and prints errors as::

    line <N>: <rule>: <description>

Line numbers are 1-based JSONL positions.  No file-supplied value (label text,
annotator id, twin id, doc_type value, etc.) appears in any error message.

Exit codes
----------
0 — all records valid
1 — one or more validation errors
2 — file not found, not a file, malformed JSON, non-object line, or no args
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# eval.metrics lives in the same package; when run as
# ``python -m eval.bench_schema`` the repo root is in sys.path.
# Tests pre-populate sys.modules["eval.metrics"] via importlib.util.
from eval.metrics import DIRECT_IDENTIFIERS
from piitier.labels import Label

_VALID_LABEL_NAMES: frozenset[str] = frozenset(lbl.name for lbl in Label)

# Mix rule: no single doc_type may represent more than this share.
_MIX_LIMIT = 0.30

_REQUIRED_RECORD_KEYS = (
    "id",
    "doc_type",
    "text",
    "spans",
    "annotations",
    "adjudicated_by",
    "twin_of",
    "notes",
)
_REQUIRED_SPAN_KEYS = ("start", "end", "label", "text")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _has_direct_id(spans: list[dict[str, Any]]) -> bool:
    """Return True if any span label is in DIRECT_IDENTIFIERS."""
    for span in spans:
        name = span.get("label")
        if not isinstance(name, str):
            continue
        try:
            lbl = Label[name]
        except KeyError:
            continue
        if lbl in DIRECT_IDENTIFIERS:
            return True
    return False


def _validate_spans(
    lineno: int,
    text: str,
    spans_raw: object,
    context: str,
) -> list[str]:
    """Validate span dicts in *spans_raw*; return error strings (no file values)."""
    errors: list[str] = []
    if not isinstance(spans_raw, list):
        errors.append(f"line {lineno}: schema: {context} must be a list")
        return errors
    for i, span in enumerate(spans_raw):
        if not isinstance(span, dict):
            errors.append(f"line {lineno}: schema: {context}[{i}] must be an object")
            continue
        for key in _REQUIRED_SPAN_KEYS:
            if key not in span:
                errors.append(
                    f"line {lineno}: schema: missing required key {key!r} in {context}[{i}]"
                )

        start = span.get("start")
        end = span.get("end")
        label = span.get("label")
        span_text = span.get("text")

        # --- offset rule ---
        if isinstance(start, int) and isinstance(end, int):
            n = len(text)
            if not (0 <= start < end <= n):
                errors.append(
                    f"line {lineno}: offset: [{start},{end}) out of bounds"
                    f" (len={n}) in {context}[{i}]"
                )
            elif isinstance(span_text, str) and text[start:end] != span_text:
                errors.append(
                    f"line {lineno}: offset: [{start},{end}) does not match"
                    f" 'text' field in {context}[{i}]"
                )
        elif start is not None or end is not None:
            errors.append(f"line {lineno}: offset: non-integer start/end in {context}[{i}]")

        # --- label rule (no echo of value) ---
        if isinstance(label, str):
            if label not in _VALID_LABEL_NAMES:
                errors.append(f"line {lineno}: label: unknown label in {context}[{i}]")
        elif label is not None:
            errors.append(f"line {lineno}: label: non-string label in {context}[{i}]")

    return errors


def _find_overlaps(
    lineno: int,
    spans: list[dict[str, Any]],
    context: str,
) -> list[str]:
    """Return errors for any pair of spans that share at least one character."""
    errors: list[str] = []
    valid: list[tuple[int, dict[str, Any]]] = [
        (i, s)
        for i, s in enumerate(spans)
        if isinstance(s.get("start"), int) and isinstance(s.get("end"), int)
    ]
    for a_idx, (i, si) in enumerate(valid):
        for j, sj in [v for v in valid[a_idx + 1 :]]:
            if max(si["start"], sj["start"]) < min(si["end"], sj["end"]):
                errors.append(f"line {lineno}: overlap: {context}[{i}] and {context}[{j}] overlap")
    return errors


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate(
    records: list[dict[str, Any]],
    linenums: list[int] | None = None,
) -> list[str]:
    """Validate a list of v2 records.

    *linenums* maps each record to its 1-based line number in the source file.
    When omitted, line numbers are assigned 1, 2, 3, ...

    Returns a (possibly empty) list of error strings.  An empty list means the
    file is valid.  No file-supplied value appears in any error string.
    """
    if linenums is None:
        linenums = list(range(1, len(records) + 1))

    errors: list[str] = []

    # --- empty file ---
    if not records:
        errors.append("schema: empty file")
        return errors

    # --- build id registry (for twin lookup and duplicate detection) ---
    id_to_lineno: dict[str, int] = {}
    id_to_doc_type: dict[str, str] = {}
    id_to_gold: dict[str, list[dict[str, Any]]] = {}

    for rec, ln in zip(records, linenums):
        if not isinstance(rec, dict):
            continue
        doc_id = rec.get("id")
        if not isinstance(doc_id, str) or not doc_id:
            continue
        if doc_id in id_to_lineno:
            errors.append(f"line {ln}: schema: duplicate id (first at line {id_to_lineno[doc_id]})")
        else:
            id_to_lineno[doc_id] = ln
            dt = rec.get("doc_type")
            id_to_doc_type[doc_id] = dt if isinstance(dt, str) else ""
            raw_gold = rec.get("spans")
            id_to_gold[doc_id] = (
                [s for s in raw_gold if isinstance(s, dict)] if isinstance(raw_gold, list) else []
            )

    all_ids = set(id_to_lineno.keys())

    # --- mix rule (no minimum-record threshold) ---
    total = len(records)
    counts: Counter[str] = Counter()
    for rec in records:
        if isinstance(rec, dict):
            dt = rec.get("doc_type")
            if isinstance(dt, str):
                counts[dt] += 1
    for _dt, count in counts.items():
        share = count / total
        if share > _MIX_LIMIT:
            errors.append(f"mix: {count}/{total} = {share:.1%} (limit {_MIX_LIMIT:.0%})")

    # --- per-record rules ---
    for rec, ln in zip(records, linenums):
        if not isinstance(rec, dict):
            errors.append(f"line {ln}: schema: record must be an object")
            continue

        # required top-level keys
        for key in _REQUIRED_RECORD_KEYS:
            if key not in rec:
                errors.append(f"line {ln}: schema: missing required key {key!r}")

        text = rec.get("text")
        if not isinstance(text, str):
            text = ""

        # gold spans
        gold_raw = rec.get("spans")
        gold_spans: list[dict[str, Any]] = []
        if isinstance(gold_raw, list):
            gold_spans = [s for s in gold_raw if isinstance(s, dict)]
            errors.extend(_validate_spans(ln, text, gold_raw, "spans"))
            errors.extend(_find_overlaps(ln, gold_spans, "spans"))
        elif gold_raw is not None:
            errors.append(f"line {ln}: schema: 'spans' must be a list")

        # annotations
        anns_raw = rec.get("annotations")
        annotations: list[dict[str, Any]] = []
        if isinstance(anns_raw, list):
            for j, ann in enumerate(anns_raw):
                if not isinstance(ann, dict):
                    errors.append(f"line {ln}: schema: annotations[{j}] must be an object")
                    continue
                annotations.append(ann)
                ann_spans_raw = ann.get("spans", [])
                errors.extend(_validate_spans(ln, text, ann_spans_raw, f"annotations[{j}].spans"))
                if isinstance(ann_spans_raw, list):
                    valid_ann = [s for s in ann_spans_raw if isinstance(s, dict)]
                    errors.extend(_find_overlaps(ln, valid_ann, f"annotations[{j}].spans"))
        elif anns_raw is not None:
            errors.append(f"line {ln}: schema: 'annotations' must be a list")

        # annotators rule: ≥ 2
        if len(annotations) < 2:
            errors.append(f"line {ln}: annotators: {len(annotations)} < 2")

        # adjudication rule
        adj = rec.get("adjudicated_by")
        if not (isinstance(adj, str) and adj.strip()):
            errors.append(f"line {ln}: adjudication: missing or empty")

        # twin_of reference must exist when set
        twin_of = rec.get("twin_of")
        if twin_of is not None:
            if not isinstance(twin_of, str):
                errors.append(f"line {ln}: twin_of: non-string value")
            elif twin_of not in all_ids:
                errors.append(f"line {ln}: twin_of: target not found in file")

        # twin rule: every record with a DIRECT_IDENTIFIER span needs a valid twin
        if _has_direct_id(gold_spans):
            if twin_of is None:
                errors.append(f"line {ln}: twin: missing twin_of for record with direct identifier")
            elif isinstance(twin_of, str) and twin_of in all_ids:
                my_dt = rec.get("doc_type", "")
                twin_dt = id_to_doc_type.get(twin_of, "")
                if my_dt != twin_dt:
                    errors.append(f"line {ln}: twin: doc_type mismatch")
                twin_gold = id_to_gold.get(twin_of, [])
                if _has_direct_id(twin_gold):
                    errors.append(f"line {ln}: twin: twin contains direct identifier")

    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: python -m eval.bench_schema <file>...", file=sys.stderr)
        return 2

    all_errors: list[str] = []
    for path_str in args:
        path = Path(path_str)
        if not path.exists():
            print(f"error: not found: {path_str}", file=sys.stderr)
            return 2
        if not path.is_file():
            print(f"error: not a file: {path_str}", file=sys.stderr)
            return 2

        records: list[dict[str, Any]] = []
        linenums: list[int] = []
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
                            f"error: malformed JSON at line {lineno}: {path_str}",
                            file=sys.stderr,
                        )
                        return 2
                    if not isinstance(obj, dict):
                        print(
                            f"error: non-object at line {lineno}: {path_str}",
                            file=sys.stderr,
                        )
                        return 2
                    records.append(obj)
                    linenums.append(lineno)
        except OSError as exc:
            print(f"error: {path_str}: {exc.strerror}", file=sys.stderr)
            return 2

        all_errors.extend(validate(records, linenums))

    for err in all_errors:
        print(err)

    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())
