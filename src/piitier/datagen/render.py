"""Document renderer for synthetic data generation (PII-2-a)."""

from __future__ import annotations

import random
from dataclasses import dataclass

from piitier.datagen import people
from piitier.datagen.template import Placeholder, Template, TemplateError, parse
from piitier.datagen.values import generate_value
from piitier.labels import Label
from piitier.spans import Span

# Person-group labels: OSOBA/IMIE/NAZWISKO/DATA_URODZENIA always use a PersonRecord;
# explicit PESEL#k also joins this group (anonymous PESEL keeps the old structured path).
_PERSON_LABELS: frozenset[Label] = frozenset(
    {Label.OSOBA, Label.IMIE, Label.NAZWISKO, Label.DATA_URODZENIA}
)
# Address-group labels: all three share one AddressRecord per entity.
_ADDRESS_LABELS: frozenset[Label] = frozenset({Label.ADRES, Label.KOD_POCZTOWY, Label.MIEJSCOWOSC})


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
        # PII-2-b person / address / contact labels
        Label.OSOBA,
        Label.IMIE,
        Label.NAZWISKO,
        Label.DATA_URODZENIA,
        Label.ADRES,
        Label.KOD_POCZTOWY,
        Label.MIEJSCOWOSC,
        Label.TELEFON,
        Label.EMAIL,
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

    # Cross-label explicit ID sets for grouped labels.
    # Anonymous allocations for person-group labels avoid ALL person-group explicit IDs
    # (including explicit PESEL) to prevent accidental PersonRecord sharing.
    all_person_explicit_ids: set[int] = set()
    for _lbl in (*_PERSON_LABELS, Label.PESEL):
        all_person_explicit_ids.update(explicit_ids.get(_lbl, set()))
    all_address_explicit_ids: set[int] = set()
    for _lbl in _ADDRESS_LABELS:
        all_address_explicit_ids.update(explicit_ids.get(_lbl, set()))

    # Next anonymous counter per label
    anon_counters: dict[Label, int] = {}

    def get_entity_id(label: Label, entity_str: str | None) -> str:
        if entity_str is not None:
            return entity_str
        # For grouped labels use the cross-label avoid set so that anonymous
        # entities never accidentally land on an explicit entity from a sibling label.
        if label in _PERSON_LABELS:
            avoid = all_person_explicit_ids
        elif label in _ADDRESS_LABELS:
            avoid = all_address_explicit_ids
        else:
            avoid = explicit_ids.get(label, set())
        if label not in anon_counters:
            anon_counters[label] = 1
            while anon_counters[label] in avoid:
                anon_counters[label] += 1
        else:
            anon_counters[label] += 1
            while anon_counters[label] in avoid:
                anon_counters[label] += 1
        eid = str(anon_counters[label])
        n_eid = int(eid)
        if label not in explicit_ids:
            explicit_ids[label] = set()
        explicit_ids[label].add(n_eid)
        # Keep cross-label avoid sets current for subsequent anonymous allocations.
        if label in _PERSON_LABELS:
            all_person_explicit_ids.add(n_eid)
        elif label in _ADDRESS_LABELS:
            all_address_explicit_ids.add(n_eid)
        return eid

    # Cache values by (label, entity_id)
    # Person/address record caches: keyed by entity_id string.
    person_records: dict[str, people.PersonRecord] = {}
    address_records: dict[str, people.AddressRecord] = {}
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
                # Explicit PESEL#k joins the person group; anonymous {{PESEL}} keeps
                # the old structured path so that UC-1/UC-2 determinism is preserved.
                is_person_linked = item.label in _PERSON_LABELS or (
                    item.label is Label.PESEL and item.entity is not None
                )
                if is_person_linked:
                    if eid not in person_records:
                        existing = frozenset(
                            f"{r.first_name} {r.last_name}" for r in person_records.values()
                        )
                        person_records[eid] = people.make_person(rng, existing)
                    value_cache[cache_key] = people.get_person_field(
                        item.label, person_records[eid]
                    )
                elif item.label in _ADDRESS_LABELS:
                    if eid not in address_records:
                        address_records[eid] = people.make_address(rng)
                    value_cache[cache_key] = people.get_address_field(
                        item.label, address_records[eid]
                    )
                else:
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
