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
Train-coverage guard: if every template of a doc type would be assigned to dev, all
                      templates of that type are forced to train instead.  The guard is
                      deterministic and independent of n/seed.  Forced types are recorded
                      in ``manifest.json`` under the key ``split_forced_train``.
IDs: ``doc_{i:07d}`` where i is the global document index [0, n).
Seeds: base_seed + i.
Traversal: round-robin over sorted(doc_types), then sorted(filenames) within each type
           — equal shares per type, stable across platforms.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import piitier
from piitier.datagen.augment import ALL_TRANSFORMS
from piitier.datagen.augment import augment as augment_doc
from piitier.datagen.hard_negatives import make_hard_negative_docs
from piitier.datagen.render import render
from piitier.datagen.template import Template

# The nine supported document types, sorted for deterministic traversal.
DOC_TYPES: frozenset[str] = frozenset(
    {
        "mail_klienta",
        "polisa",
        "skierowanie",
        "transkrypcja_infolinii",
        "umowa_kredytowa",
        "wypis_szpitalny",
        "wyciag",
        "raport_towarzystwa",
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
# Train-coverage guard
# ---------------------------------------------------------------------------


def _forced_train_types(type_templates: dict[str, list[Template]]) -> frozenset[str]:
    """Return the set of doc types where *every* template would be assigned to dev.

    For these types the caller must override the split to ``'train'`` so that every
    doc type is always represented in the training set.  Types with at least one
    train-assigned template are returned unchanged (empty intersection with result).
    """
    forced: set[str] = set()
    for doc_type, tmpls in type_templates.items():
        if all(_split_for(t.template_id) == "dev" for t in tmpls):
            forced.add(doc_type)
    return frozenset(forced)


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
# Augmentation helpers
# ---------------------------------------------------------------------------

# Per-transform inclusion probability when a document is selected for augmentation.
_TRANSFORM_PROBS: dict[str, float] = {
    "ocr_confusions": 0.5,
    "space_digit_groups": 0.5,
    "strip_diacritics": 0.5,
    "uppercase": 0.3,
}


def _select_transforms(rng: random.Random) -> frozenset[str]:
    """Return a random non-empty subset of augmentation transforms.

    Each transform in :data:`ALL_TRANSFORMS` is included independently with the
    probability given by :data:`_TRANSFORM_PROBS`.  If all draws miss the threshold
    (probability ≈ 0.5³ × 0.7 ≈ 0.09), a single transform is chosen uniformly at
    random to guarantee the returned set is non-empty.
    """
    selected: set[str] = {t for t in ALL_TRANSFORMS if rng.random() < _TRANSFORM_PROBS.get(t, 0.5)}
    if not selected:
        selected = {ALL_TRANSFORMS[rng.randrange(len(ALL_TRANSFORMS))]}
    return frozenset(selected)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build(
    templates_dir: Path,
    n: int,
    seed: int,
    out: Path,
    *,
    augment: bool = False,
    augment_fraction: float = 0.25,
    hard_negatives: int = 0,
) -> None:
    """Render *n* synthetic documents and write ``train.jsonl``, ``dev.jsonl``,
    and ``manifest.json`` into *out*.

    Parameters
    ----------
    templates_dir:
        Directory tree of ``.txt`` template files (``<dir>/<doc_type>/<id>.txt``).
    n:
        Total number of template documents to generate.
    seed:
        Base RNG seed.  Document *i* is rendered with seed ``seed + i``.
    out:
        Output directory.  Created if it does not exist; must be empty if it does,
        and must not resolve to a path containing a ``bench`` component.
        Raises :exc:`BuildError` before any writes if either guard is violated.
    augment:
        Whether to apply OCR and diacritic augmentation to a fraction of documents.
    augment_fraction:
        Fraction of documents to augment when *augment* is ``True``.  Each document
        is independently augmented with probability *augment_fraction* using a random
        non-empty subset of transforms (uppercase: P=0.3, others: P=0.5).
        Must satisfy ``0 < augment_fraction <= 1``.  Ignored when *augment* is False.
    hard_negatives:
        Number of hard negative documents to append.
    """
    _check_output_guard(out)
    if hard_negatives < 0:
        raise BuildError(f"hard_negatives must be >= 0, got {hard_negatives}")
    if n < 0:
        raise BuildError(f"n must be >= 0, got {n}")
    if augment and not (0 < augment_fraction <= 1):
        raise BuildError(f"augment_fraction must be in (0, 1], got {augment_fraction}")
    templates = collect_templates(templates_dir)
    if not templates:
        raise ValueError(f"No .txt templates found in {templates_dir}")

    train_lines: list[str] = []
    dev_lines: list[str] = []
    span_counts: dict[str, int] = {}
    split_counts: dict[str, int] = {"train": 0, "dev": 0}
    total_fallbacks: int = 0
    transform_doc_counts: dict[str, int] = {}
    augmented_doc_count: int = 0

    # Group templates by doc_type (collect_templates already sorts within each type).
    _type_templates: dict[str, list[Template]] = {}
    for t in templates:
        _type_templates.setdefault(t.doc_type, []).append(t)
    _types: list[str] = sorted(_type_templates)
    _type_counters: dict[str, int] = dict.fromkeys(_types, 0)
    _forced: frozenset[str] = _forced_train_types(_type_templates)

    # 1. Template documents
    for i in range(n):
        dt = _types[i % len(_types)]
        k = _type_counters[dt]
        _type_counters[dt] += 1
        tmpl = _type_templates[dt][k % len(_type_templates[dt])]
        doc_seed = seed + i
        doc_id = f"doc_{i:07d}"

        doc = render(tmpl, doc_seed)
        if augment:
            doc_rng = random.Random(doc_seed)
            if doc_rng.random() < augment_fraction:
                transforms = _select_transforms(doc_rng)
                doc = augment_doc(doc, doc_rng, transforms=transforms)
                augmented_doc_count += 1
                for transform_name in transforms:
                    transform_doc_counts[transform_name] = (
                        transform_doc_counts.get(transform_name, 0) + 1
                    )
        total_fallbacks += doc.inflection_fallbacks
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

        split = _split_for(tmpl.template_id) if tmpl.doc_type not in _forced else "train"
        if split == "dev":
            dev_lines.append(record)
            split_counts["dev"] += 1
        else:
            train_lines.append(record)
            split_counts["train"] += 1

        for s in doc.spans:
            lbl = s.label.name
            span_counts[lbl] = span_counts.get(lbl, 0) + 1

    # 2. Hard negative documents
    if hard_negatives > 0:
        hn_docs = make_hard_negative_docs(seed + n, hard_negatives)
        for j, doc in enumerate(hn_docs):
            doc_seed = doc.seed
            doc_id = doc.template_id  # hn_{j:07d}

            if augment:
                hn_rng = random.Random(doc_seed)
                if hn_rng.random() < augment_fraction:
                    transforms = _select_transforms(hn_rng)
                    doc = augment_doc(doc, hn_rng, transforms=transforms)
                    augmented_doc_count += 1
                    for transform_name in transforms:
                        transform_doc_counts[transform_name] = (
                            transform_doc_counts.get(transform_name, 0) + 1
                        )

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

            split = _split_for(doc_id)
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
        "split_forced_train": sorted(_forced),
        "version": piitier.__version__,
        "inflection_fallbacks": total_fallbacks,
        "augment": augment,
        "augment_fraction": augment_fraction if augment else None,
        "augmented_doc_count": augmented_doc_count,
        "transform_doc_counts": dict(sorted(transform_doc_counts.items())),
        "hard_negatives": hard_negatives,
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
