"""Document renderer for synthetic data generation (PII-2-a)."""

from __future__ import annotations

import random
from dataclasses import dataclass

from piitier.datagen.template import Placeholder, Template, TemplateError, parse
from piitier.datagen.values import generate_value
from piitier.labels import Label
from piitier.spans import Span


@dataclass(frozen=True)
class SyntheticSpan(Span):
    """Synthetic span extending canonical Span with entity and text metadata."""

    entity: str | None = None
    text: str = ""


@dataclass(frozen=True)
class Document:
    """Rendered synthetic document with text, metadata, and labeled spans."""

    text: str
    template_id: str
    doc_type: str
    seed: int
    spans: list[SyntheticSpan]


def render(template: Template, seed: int) -> Document:
    """Render a labelled synthetic document from a placeholder template."""
    rng = random.Random(seed)
    parsed = parse(template)

    # Reject case syntax until PII-2-c
    for item in parsed:
        if isinstance(item, Placeholder) and item.case is not None:
            raise TemplateError(
                template.template_id,
                item.offset,
                f"Case specifier {item.case!r} not supported yet",
            )

    # Check for labels with no generator (e.g. LEK)
    supported_labels = {
        Label.PESEL,
        Label.NIP,
        Label.REGON,
        Label.IBAN,
        Label.NR_DOWODU,
        Label.NR_KARTY,
    }
    for item in parsed:
        if isinstance(item, Placeholder) and item.label not in supported_labels:
            raise TemplateError(
                template.template_id,
                item.offset,
                f"no generator for {item.label.name}",
            )

    # Entity allocation & caching per label
    # First pass: collect explicit entity IDs per label and reserve them
    explicit_ids: dict[Label, set[int]] = {}
    for item in parsed:
        if isinstance(item, Placeholder) and item.entity is not None:
            lbl = item.label
            if lbl not in explicit_ids:
                explicit_ids[lbl] = set()
            explicit_ids[lbl].add(int(item.entity))

    # Next anonymous counter per label
    anon_counters: dict[Label, int] = {}

    def get_entity_id(label: Label, entity_str: str | None) -> str:
        if entity_str is not None:
            return entity_str
        if label not in anon_counters:
            anon_counters[label] = 1
            # avoid colliding with any explicit ID
            while anon_counters[label] in explicit_ids.get(label, set()):
                anon_counters[label] += 1
        else:
            anon_counters[label] += 1
            while anon_counters[label] in explicit_ids.get(label, set()):
                anon_counters[label] += 1
        eid = str(anon_counters[label])
        if label not in explicit_ids:
            explicit_ids[label] = set()
        explicit_ids[label].add(int(eid))
        return eid

    # Cache values by (label, entity_id)
    value_cache: dict[tuple[Label, str], str] = {}

    # Second pass: build text and spans
    rendered_parts: list[str] = []
    spans: list[SyntheticSpan] = []
    current_offset = 0

    for item in parsed:
        if isinstance(item, str):
            rendered_parts.append(item)
            current_offset += len(item)
        elif isinstance(item, Placeholder):
            eid = get_entity_id(item.label, item.entity)
            cache_key = (item.label, eid)
            if cache_key not in value_cache:
                value_cache[cache_key] = generate_value(item.label, rng)
            val = value_cache[cache_key]

            start = current_offset
            end = start + len(val)
            rendered_parts.append(val)
            current_offset = end

            spans.append(
                SyntheticSpan(
                    start=start,
                    end=end,
                    label=item.label,
                    source="synthetic",
                    score=1.0,
                    status="valid",
                    entity=eid,
                    text=val,
                )
            )

    text = "".join(rendered_parts)
    return Document(
        text=text,
        template_id=template.template_id,
        doc_type=template.doc_type,
        seed=seed,
        spans=spans,
    )
