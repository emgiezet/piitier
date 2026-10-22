"""Dataset builder for synthetic PII training data (PII-2-d).

Public API
----------
collect_templates(templates_dir)  — sorted list of Template objects
build(templates_dir, n, seed, out) — write train.jsonl / dev.jsonl / manifest.json;
                                     raises BuildError for bench/ or non-empty output
check(data_dir)                   — verify span offsets; returns (exit_code, error_msg)
BuildError                        — raised by build() for guarded write conditions

The CLI (``python -m piitier.datagen build|check``) is in ``__main__.py``.

Split rule: sha256(template_id, encoding='utf-8') % 10 == 0  →  dev,  else  train.
IDs: ``doc_{i:07d}`` where i is the global document index [0, n).
Seeds: base_seed + i.
Traversal: sorted(doc_types) then sorted(filenames) — stable across platforms.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import piitier
from piitier.datagen.render import render
from piitier.datagen.template import Template

# The eight supported document types, sorted for deterministic traversal.
DOC_TYPES: frozenset[str] = frozenset(
    {
        "mail_klienta",
        "polisa",
        "skierowanie",
        "transkrypcja_infolinii",
        "umowa_kredytowa",
        "wypis_szpitalny",
        "wyciag",
        "zgloszenie_szkody",
    }
)

# Default templates bundled with the package.
_PACKAGED_TEMPLATES_DIR: Path = Path(__file__).parent / "templates"


# ---------------------------------------------------------------------------
# Output guard
# ---------------------------------------------------------------------------


class BuildError(Exception):
    """Raised by :func:`build` when the output path must not be written.

    Conditions:
    - The resolved output path contains a ``bench`` path component (exact name
      match, case-sensitive, regardless of cwd).  Symlinks are followed via
      ``Path.resolve()`` before the check.
    - The output directory already exists and is non-empty.
    """


def _check_output_guard(out: Path) -> None:
    """Raise :exc:`BuildError` if *out* must not be written.

    Checks are done on the **resolved** path (symlinks followed) so a symlink
    alias pointing into ``bench/`` is also rejected.
    """
    out_resolved = out.resolve()
    if "bench" in out_resolved.parts:
        raise BuildError("refusing to write into bench/")
    if out.exists() and any(out.iterdir()):
        raise BuildError(f"output directory not empty: {out}")


# ---------------------------------------------------------------------------
# Split rule
# ---------------------------------------------------------------------------


def _split_for(template_id: str) -> str:
    """Return ``'dev'`` when sha256(template_id) % 10 == 0, else ``'train'``.

    Uses sha256 — *not* Python's built-in ``hash()`` — so results are stable
    across interpreter versions and invocations.
    """
    digest = int(hashlib.sha256(template_id.encode()).hexdigest(), 16)
    return "dev" if digest % 10 == 0 else "train"


# ---------------------------------------------------------------------------
# Template collection
# ---------------------------------------------------------------------------


def collect_templates(templates_dir: Path) -> list[Template]:
    """Return all ``.txt`` templates found under *templates_dir*, sorted deterministically.

    Sort order: ``doc_type`` (ASCII-ascending) then ``template_id`` (ASCII-ascending).
    Only directories whose name is a member of :data:`DOC_TYPES` are visited.
    """
    result: list[Template] = []
    for doc_type in sorted(DOC_TYPES):
        type_dir = templates_dir / doc_type
        if not type_dir.is_dir():
            continue
        for path in sorted(type_dir.glob("*.txt")):
            text = path.read_bytes().decode("utf-8")
            result.append(
                Template(
                    template_id=path.stem,
                    doc_type=doc_type,
                    text=text,
                )
            )
    return result


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build(templates_dir: Path, n: int, seed: int, out: Path) -> None:
    """Render *n* synthetic documents and write ``train.jsonl``, ``dev.jsonl``,
    and ``manifest.json`` into *out*.

    Parameters
    ----------
    templates_dir:
        Directory tree of ``.txt`` template files (``<dir>/<doc_type>/<id>.txt``).
    n:
        Total number of documents to generate.
    seed:
        Base RNG seed.  Document *i* is rendered with seed ``seed + i``.
    out:
        Output directory.  Created if it does not exist; must be empty if it does,
        and must not resolve to a path containing a ``bench`` component.
        Raises :exc:`BuildError` before any writes if either guard is violated.
    """
    _check_output_guard(out)
    templates = collect_templates(templates_dir)
    if not templates:
        raise ValueError(f"No .txt templates found in {templates_dir}")

    train_lines: list[str] = []
    dev_lines: list[str] = []
    span_counts: dict[str, int] = {}
    split_counts: dict[str, int] = {"train": 0, "dev": 0}

    for i in range(n):
        tmpl = templates[i % len(templates)]
        doc_seed = seed + i
        doc_id = f"doc_{i:07d}"

        doc = render(tmpl, doc_seed)

        spans_data = [
            {
                "start": s.start,
                "end": s.end,
                "label": s.label.name,
                "entity": s.entity,
                "text": s.text,
            }
            for s in doc.spans
        ]

        record = json.dumps(
            {
                "id": doc_id,
                "doc_type": doc.doc_type,
                "template_id": doc.template_id,
                "seed": doc_seed,
                "text": doc.text,
                "spans": spans_data,
            },
            ensure_ascii=False,
        )

        split = _split_for(tmpl.template_id)
        if split == "dev":
            dev_lines.append(record)
            split_counts["dev"] += 1
        else:
            train_lines.append(record)
            split_counts["train"] += 1

        for s in doc.spans:
            lbl = s.label.name
            span_counts[lbl] = span_counts.get(lbl, 0) + 1

    # Template counts per doc_type (sorted for deterministic manifest JSON)
    template_counts: dict[str, int] = {}
    for t in templates:
        template_counts[t.doc_type] = template_counts.get(t.doc_type, 0) + 1

    out.mkdir(parents=True, exist_ok=True)

    (out / "train.jsonl").write_text(
        "".join(line + "\n" for line in train_lines),
        encoding="utf-8",
    )
    (out / "dev.jsonl").write_text(
        "".join(line + "\n" for line in dev_lines),
        encoding="utf-8",
    )

    manifest: dict[str, object] = {
        "n": n,
        "seed": seed,
        "template_counts": dict(sorted(template_counts.items())),
        "span_counts": dict(sorted(span_counts.items())),
        "split_counts": split_counts,
        "version": piitier.__version__,
        "inflection_fallbacks": 0,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------


def check(data_dir: Path) -> tuple[int, str]:
    """Verify span offsets in ``train.jsonl`` and ``dev.jsonl`` under *data_dir*.

    Returns
    -------
    (0, "")
        All spans are correct and both split files exist.
    (1, error_msg)
        *error_msg* is the ``id`` of the first bad document, or a
        ``<location>`` string when the id is unavailable.  Document text is
        **never** included in the error string (privacy/security).

    Rejects
    -------
    - Missing or unreadable split files (``OSError``).
    - Files that are not valid UTF-8 (``UnicodeDecodeError``).
    - Records that are not JSON objects (dicts).
    - ``text`` field absent or not a ``str``.
    - ``spans`` field absent or not a ``list``.
    - Span items that are not dicts.
    - ``start`` / ``end`` that are not plain ``int`` (booleans rejected; in
      Python ``bool`` is a subclass of ``int`` but is not a valid index type
      for this format).
    - Bounds violation: ``not (0 <= start < end <= len(text))``.
    - Slice mismatch: ``text[start:end] != span["text"]``.
    """
    for filename in ("train.jsonl", "dev.jsonl"):
        path = data_dir / filename
        if not path.exists():
            return 1, f"<missing file: {filename}>"

        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            return 1, f"<unreadable file: {filename}: {exc.strerror}>"
        except UnicodeError:
            # Invalid byte sequence — report filename only, no raw bytes.
            return 1, f"<encoding error in {filename}>"

        for lineno, raw in enumerate(content.splitlines(), 1):
            if not raw.strip():
                continue

            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                # Report position only — never leak file content.
                return 1, f"<malformed JSON at {filename}:{lineno}>"

            if not isinstance(record, dict):
                return 1, f"<invalid record shape at {filename}:{lineno}>"

            loc = f"<line {filename}:{lineno}>"
            doc_id: str = str(record.get("id", loc))

            text = record.get("text")
            if not isinstance(text, str):
                return 1, doc_id

            spans_raw = record.get("spans")
            if not isinstance(spans_raw, list):
                return 1, doc_id

            for span in spans_raw:
                if not isinstance(span, dict):
                    return 1, doc_id

                start = span.get("start")
                end = span.get("end")
                expected = span.get("text", "")

                # bool is a subclass of int in Python; reject it explicitly.
                if not isinstance(start, int) or isinstance(start, bool):
                    return 1, doc_id
                if not isinstance(end, int) or isinstance(end, bool):
                    return 1, doc_id
                if not (0 <= start < end <= len(text)):
                    return 1, doc_id
                if text[start:end] != expected:
                    return 1, doc_id

    return 0, ""
