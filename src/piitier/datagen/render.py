"""Document renderer for synthetic data generation (PII-2-a)."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

from piitier.datagen import people
from piitier.datagen.inflect import _inflect
from piitier.datagen.template import (
    _INFLECTABLE_LABELS,
    Placeholder,
    Template,
    TemplateError,
    parse,
)
from piitier.datagen.values import generate_dochod, generate_kwota, generate_value
from piitier.labels import Label
from piitier.spans import Span

# Labels whose span may absorb an adjacent template-literal currency token.
_CURRENCY_LABELS: frozenset[Label] = frozenset({Label.KWOTA, Label.DOCHOD})
# Matches optional whitespace + a currency token at start of a string.
_CURRENCY_FOLLOW_RE: re.Pattern[str] = re.compile(r"^[ \t]*(?:złotych|zł|PLN|EUR|euro|€)(?!\w)")


# Person-group labels: OSOBA/IMIE/NAZWISKO/DATA_URODZENIA always use a PersonRecord;
# explicit PESEL#k also joins this group (anonymous PESEL keeps the old structured path).
_PERSON_LABELS: frozenset[Label] = frozenset(
    {Label.OSOBA, Label.IMIE, Label.NAZWISKO, Label.DATA_URODZENIA}
)
# Address-group labels: all three share one AddressRecord per entity.
_ADDRESS_LABELS: frozenset[Label] = frozenset({Label.ADRES, Label.KOD_POCZTOWY, Label.MIEJSCOWOSC})
# Doctor-group labels: LEKARZ uses person record + prefix.
_DOCTOR_LABELS: frozenset[Label] = frozenset({Label.LEKARZ})


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
    inflection_fallbacks: int = 0


def render(template: Template, seed: int) -> Document:
    """Render a labelled synthetic document from a placeholder template."""
    rng = random.Random(seed)
    parsed = parse(template)

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
        # PII-3-a finance / insurance labels
        Label.NR_UMOWY,
        Label.KWOTA,
        Label.DOCHOD,
        Label.NR_POLISY,
        Label.NR_SZKODY,
        Label.NR_REJESTRACYJNY,
        Label.VIN,
        Label.NR_KW,
        # PII-3-b medical labels
        Label.ICD10,
        Label.LEK,
        Label.ROZPOZNANIE,
        Label.PLACOWKA,
        Label.LEKARZ,
        Label.NPWZ,
        Label.DANE_ZDROWOTNE,
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
    all_doctor_explicit_ids: set[int] = set()
    for _lbl in _DOCTOR_LABELS:
        all_doctor_explicit_ids.update(explicit_ids.get(_lbl, set()))

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
        elif label in _DOCTOR_LABELS:
            avoid = all_doctor_explicit_ids
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
        elif label in _DOCTOR_LABELS:
            all_doctor_explicit_ids.add(n_eid)
        return eid

    # Cache values by (label, entity_id, case).
    # The case component prevents a nominative cache entry from poisoning a
    # genitive lookup or vice versa (PII-2-c cache-poisoning invariant).
    # Person/address record caches: keyed by entity_id string (case-independent).
    person_records: dict[str, people.PersonRecord] = {}
    address_records: dict[str, people.AddressRecord] = {}
    doctor_records: dict[str, tuple[people.PersonRecord, str]] = {}
    value_cache: dict[tuple[Label, str, str | None, bool], tuple[str, int]] = {}

    # Second pass: build text and spans
    rendered_parts: list[str] = []
    spans: list[SyntheticSpan] = []
    current_offset = 0
    fallbacks: int = 0  # per-document inflection fallback counter

    for _i, item in enumerate(parsed):
        if isinstance(item, str):
            rendered_parts.append(item)
            current_offset += len(item)
        elif isinstance(item, Placeholder):
            eid = get_entity_id(item.label, item.entity)
            # KWOTA/DOCHOD: peek at the next parsed element to determine whether a
            # currency token follows in the template. This prevents embedded-currency
            # values from being generated when the template already supplies one.
            if item.label in _CURRENCY_LABELS:
                _nxt = parsed[_i + 1] if _i + 1 < len(parsed) else None
                _curr_follows: bool = bool(
                    isinstance(_nxt, str) and _CURRENCY_FOLLOW_RE.match(_nxt)
                )
            else:
                _curr_follows = False
            cache_key = (item.label, eid, item.case, _curr_follows)
            if cache_key not in value_cache:
                # Explicit PESEL#k joins the person group; anonymous {{PESEL}} keeps
                # the old structured path so that UC-1/UC-2 determinism is preserved.
                is_person_linked = item.label in _PERSON_LABELS or (
                    item.label is Label.PESEL and item.entity is not None
                )
                is_doctor_linked = item.label in _DOCTOR_LABELS
                occ_fb = 0
                if is_person_linked:
                    if eid not in person_records:
                        existing = frozenset(
                            f"{r.first_name} {r.last_name}" for r in person_records.values()
                        )
                        person_records[eid] = people.make_person(rng, existing)

                    if item.case is not None and item.label in _INFLECTABLE_LABELS:
                        rec = person_records[eid]
                        sex = rec.sex.lower()
                        if item.label is Label.OSOBA:
                            fn_form, fn_fb = _inflect(rec.first_name, item.case, sex)
                            ln_form, ln_fb = _inflect(rec.last_name, item.case, sex)
                            occ_fb = int(fn_fb) + int(ln_fb)
                            val = f"{fn_form} {ln_form}"
                        elif item.label is Label.IMIE:
                            fn_form, fn_fb = _inflect(rec.first_name, item.case, sex)
                            occ_fb = int(fn_fb)
                            val = fn_form
                        else:  # NAZWISKO
                            ln_form, ln_fb = _inflect(rec.last_name, item.case, sex)
                            occ_fb = int(ln_fb)
                            val = ln_form
                    else:
                        val = people.get_person_field(item.label, person_records[eid])

                    value_cache[cache_key] = (val, occ_fb)
                elif is_doctor_linked:
                    if eid not in doctor_records:
                        existing = frozenset(
                            [f"{r.first_name} {r.last_name}" for r in person_records.values()]
                            + [f"{r.first_name} {r.last_name}" for r, _ in doctor_records.values()]
                        )
                        rec = people.make_person(rng, existing)
                        prefix = rng.choice(["dr", "lek. med."])
                        doctor_records[eid] = (rec, prefix)

                    rec, prefix = doctor_records[eid]
                    sex = rec.sex.lower()
                    if item.case is not None and item.label in _INFLECTABLE_LABELS:
                        fn_form, fn_fb = _inflect(rec.first_name, item.case, sex)
                        ln_form, ln_fb = _inflect(rec.last_name, item.case, sex)
                        occ_fb = int(fn_fb) + int(ln_fb)
                        val = f"{prefix} {fn_form} {ln_form}"
                    else:
                        val = f"{prefix} {rec.first_name} {rec.last_name}"

                    value_cache[cache_key] = (val, occ_fb)
                elif item.label in _ADDRESS_LABELS:
                    if eid not in address_records:
                        address_records[eid] = people.make_address(rng)
                    val = people.get_address_field(item.label, address_records[eid])
                    value_cache[cache_key] = (val, 0)
                else:
                    if item.label is Label.KWOTA:
                        val = generate_kwota(rng, currency_follows=_curr_follows)
                    elif item.label is Label.DOCHOD:
                        val = generate_dochod(rng, currency_follows=_curr_follows)
                    else:
                        val = generate_value(item.label, rng)
                    value_cache[cache_key] = (val, 0)
            val, occ_fb = value_cache[cache_key]
            fallbacks += occ_fb

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

    # Extend KWOTA/DOCHOD spans over an adjacent template-literal currency token.
    # The generator was told not to embed currency when the template has one, so
    # the span must absorb the currency text to keep doc.text[s.start:s.end]==s.text.
    extended_spans: list[SyntheticSpan] = []
    for _span in spans:
        if _span.label in _CURRENCY_LABELS:
            _m = _CURRENCY_FOLLOW_RE.match(text[_span.end :])
            if _m:
                _new_end = _span.end + len(_m.group(0))
                _span = SyntheticSpan(
                    start=_span.start,
                    end=_new_end,
                    label=_span.label,
                    source=_span.source,
                    score=_span.score,
                    status=_span.status,
                    entity=_span.entity,
                    text=text[_span.start : _new_end],
                )
        extended_spans.append(_span)

    return Document(
        text=text,
        template_id=template.template_id,
        doc_type=template.doc_type,
        seed=seed,
        spans=extended_spans,
        inflection_fallbacks=fallbacks,
    )
