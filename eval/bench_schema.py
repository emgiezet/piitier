"""Bench schema v2 validator (eval/bench_schema.py) — PII-11.

CLI: ``python -m eval.bench_schema <file> ...``

Validates v2 bench JSONL files and prints errors as::

    <id>: <rule>: <detail>

No document text appears in any error message.

Exit codes
----------
0 — all records valid
1 — one or more validation errors
2 — file not found or no arguments given
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# eval.metrics lives in the same package; when run as
# ``python -m eval.bench_schema`` the repo root is in sys.path.
# Tests load eval.metrics via importlib.util first so that
# sys.modules["eval.metrics"] is populated before this module is executed.
from eval.metrics import DIRECT_IDENTIFIERS
from piitier.labels import Label

_VALID_LABEL_NAMES: frozenset[str] = frozenset(lbl.name for lbl in Label)

# Mix rule: no single doc_type may exceed this share of all records.
_MIX_LIMIT = 0.30

# The mix rule is only enforced when the file has enough records for the
# 30 % threshold to be meaningful.  A twin pair (2 records of the same
# doc_type) represents 50 % of a 4-record file, which would spuriously trip
# the rule.  The minimum is ceil(2 / 0.30) = 7: at 7+ records two same-type
# entries are at most 28.6 %, which is ≤ 30 %.
_MIX_MIN_RECORDS = 7


def _has_direct_id(spans: list[dict[str, Any]]) -> bool:
    """Return True if any span label belongs to DIRECT_IDENTIFIERS."""
    for span in spans:
        name = span.get("label", "")
        try:
            lbl = Label[name]
        except KeyError:
            continue
        if lbl in DIRECT_IDENTIFIERS:
            return True
    return False


def _validate_spans(
    doc_id: str,
    text: str,
    spans: list[dict[str, Any]],
    context: str,
) -> list[str]:
    """Validate span dicts; return error strings (no document text)."""
    errors: list[str] = []
    for i, span in enumerate(spans):
        start = span.get("start")
        end = span.get("end")
        label = span.get("label", "")

        # --- offset rule ---
        if not (isinstance(start, int) and isinstance(end, int)):
            errors.append(f"{doc_id}: offset: non-integer offsets in {context}[{i}]")
            continue
        n = len(text)
        if not (0 <= start < end <= n):
            errors.append(
                f"{doc_id}: offset: [{start},{end}) out of bounds (text len={n}) in {context}[{i}]"
            )
        elif "text" in span and text[start:end] != span["text"]:
            errors.append(
                f"{doc_id}: offset: [{start},{end}) does not match 'text' field in {context}[{i}]"
            )

        # --- label rule ---
        if label not in _VALID_LABEL_NAMES:
            errors.append(f"{doc_id}: label: unknown {label!r} in {context}[{i}]")

    return errors


def validate(records: list[dict[str, Any]]) -> list[str]:
    """Validate a list of v2 records.

    Returns a (possibly empty) list of error strings.  An empty list means
    the file is valid.  No document text appears in any error string.
    """
    errors: list[str] = []

    all_ids: set[str] = {r.get("id", "") for r in records}
    id_to_doc_type: dict[str, str] = {r.get("id", ""): r.get("doc_type", "") for r in records}
    id_to_gold: dict[str, list[dict[str, Any]]] = {
        r.get("id", ""): r.get("spans", []) for r in records
    }

    total = len(records)

    # --- mix rule (applied only for files large enough to be meaningful) ---
    if total >= _MIX_MIN_RECORDS:
        counts: Counter[str] = Counter(r.get("doc_type", "") for r in records)
        for dt, count in counts.items():
            share = count / total
            if share > _MIX_LIMIT:
                errors.append(
                    f"mix: doc_type {dt!r} is {count}/{total} = {share:.1%}"
                    f" (limit {_MIX_LIMIT:.0%})"
                )

    for rec in records:
        doc_id = rec.get("id", "<missing>")
        text = rec.get("text", "")

        # --- validate gold spans ---
        gold_spans: list[dict[str, Any]] = rec.get("spans", [])
        errors.extend(_validate_spans(doc_id, text, gold_spans, "spans"))

        # --- validate annotation spans ---
        annotations: list[dict[str, Any]] = rec.get("annotations", [])
        for ann in annotations:
            annotator = ann.get("annotator", "?")
            errors.extend(
                _validate_spans(doc_id, text, ann.get("spans", []), f"annotations[{annotator}]")
            )

        # --- annotators rule: at least 2 ---
        if len(annotations) < 2:
            errors.append(f"{doc_id}: annotators: {len(annotations)} < 2")

        # --- adjudication rule ---
        if not str(rec.get("adjudicated_by", "")).strip():
            errors.append(f"{doc_id}: adjudication: missing or empty")

        # --- twin_of reference must exist ---
        twin_of = rec.get("twin_of")
        if twin_of is not None and twin_of not in all_ids:
            errors.append(f"{doc_id}: twin_of: {twin_of!r} not found in file")

        # --- twin rule: records with DIRECT_IDENTIFIER spans need a valid twin ---
        if _has_direct_id(gold_spans):
            if twin_of is None:
                errors.append(f"{doc_id}: twin: missing twin_of for record with direct identifier")
            elif twin_of in all_ids:
                my_dt = rec.get("doc_type", "")
                twin_dt = id_to_doc_type.get(twin_of, "")
                if twin_dt != my_dt:
                    errors.append(
                        f"{doc_id}: twin: doc_type mismatch ({my_dt!r} vs twin {twin_dt!r})"
                    )
                twin_gold = id_to_gold.get(twin_of, [])
                if _has_direct_id(twin_gold):
                    errors.append(f"{doc_id}: twin: twin {twin_of!r} contains direct identifier")

    return errors


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
            print(f"error: file not found: {path_str}", file=sys.stderr)
            return 2

        with path.open(encoding="utf-8") as fh:
            records = [json.loads(line) for line in fh if line.strip()]

        all_errors.extend(validate(records))

    for err in all_errors:
        print(err)

    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())
