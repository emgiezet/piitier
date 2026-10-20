"""Acceptance tests for PII-2-b — person, address and contact generators.

Covers UC-9 through UC-14.  All tests exercise the real render() public API or
the production people.py functions (make_person / PersonRecord) that render.py
itself calls — no test-only production API.

Test command:
    pytest tests/datagen/test_people.py -v
Integration subset (exercises piitier.detect):
    pytest tests/datagen/test_people.py -v -m integration
"""

from __future__ import annotations

import random
import re

import pytest

from piitier.datagen import Template, render
from piitier.labels import Label
from piitier.rules import pesel as pesel_rules

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render(text: str, seed: int, template_id: str = "t1", doc_type: str = "test"):
    return render(Template(template_id=template_id, doc_type=doc_type, text=text), seed)


def _spans_by_label(doc) -> dict:
    result: dict = {}
    for s in doc.spans:
        result.setdefault(s.label, []).append(s)
    return result


# ---------------------------------------------------------------------------
# UC-9 — PESEL encodes birth date and sex parity; consistent with DATA_URODZENIA
# ---------------------------------------------------------------------------


def test_uc9_pesel_date_matches_data_urodzenia() -> None:
    """UC-9: across 200 seeds, PESEL date digits decode to the rendered DATA_URODZENIA."""
    template = "{{OSOBA#1}}, PESEL {{PESEL#1}}, ur. {{DATA_URODZENIA#1}}"
    for seed in range(200):
        doc = _render(template, seed)
        sbl = _spans_by_label(doc)

        assert Label.PESEL in sbl, f"seed={seed}: no PESEL span"
        assert Label.DATA_URODZENIA in sbl, f"seed={seed}: no DATA_URODZENIA span"

        pesel_text = sbl[Label.PESEL][0].text
        dob_text = sbl[Label.DATA_URODZENIA][0].text

        digits = pesel_rules._strip_separators(pesel_text)
        assert len(digits) == 11, f"seed={seed}: stripped PESEL length {len(digits)} != 11"
        assert pesel_rules.is_valid(digits), f"seed={seed}: PESEL {digits!r} fails validation"

        decoded = pesel_rules._decode_birth_date(digits)
        assert decoded is not None, f"seed={seed}: cannot decode birth date from {digits!r}"
        year, month, day = decoded
        expected_dob = f"{day:02d}.{month:02d}.{year}"
        assert dob_text == expected_dob, (
            f"seed={seed}: PESEL encodes {expected_dob!r} but DATA_URODZENIA rendered {dob_text!r}"
        )


def test_uc9_sex_digit_matches_personrecord_sex() -> None:
    """UC-9: PersonRecord.sex matches PESEL digit-9 parity; both M and F appear across 200 seeds.

    Calls make_person (the same production function used by render) directly so that
    PersonRecord.sex can be compared to the derived sex-digit parity.  No test-only
    production API is introduced.
    """
    from piitier.datagen.people import make_person

    seen_sexes: set[str] = set()
    for seed in range(200):
        rng = random.Random(seed)
        record = make_person(rng)

        digits = pesel_rules._strip_separators(record.pesel)
        assert len(digits) == 11, f"seed={seed}: bad PESEL length from PersonRecord"
        sex_digit = int(digits[9])

        if record.sex == "F":
            assert sex_digit % 2 == 0, (
                f"seed={seed}: record.sex='F' but sex_digit={sex_digit} (odd)"
            )
        else:
            assert sex_digit % 2 == 1, (
                f"seed={seed}: record.sex='M' but sex_digit={sex_digit} (even)"
            )

        seen_sexes.add(record.sex)

    assert "M" in seen_sexes and "F" in seen_sexes, (
        f"Only one sex generated across 200 seeds: {seen_sexes}"
    )


# ---------------------------------------------------------------------------
# UC-10 — OSOBA = IMIE + " " + NAZWISKO (independent of placeholder order)
# ---------------------------------------------------------------------------


def test_uc10_osoba_equals_imie_space_nazwisko() -> None:
    """UC-10: OSOBA#1 == IMIE#1 + ' ' + NAZWISKO#1 (IMIE before OSOBA in template)."""
    doc = _render("{{IMIE#1}} {{NAZWISKO#1}} / {{OSOBA#1}}", seed=0)
    sbl = _spans_by_label(doc)

    imie = sbl[Label.IMIE][0].text
    nazwisko = sbl[Label.NAZWISKO][0].text
    osoba = sbl[Label.OSOBA][0].text

    assert osoba == f"{imie} {nazwisko}", (
        f"OSOBA {osoba!r} != IMIE {imie!r} + ' ' + NAZWISKO {nazwisko!r}"
    )


def test_uc10_osoba_consistency_when_osoba_first() -> None:
    """UC-10: OSOBA formed correctly even when OSOBA appears before IMIE/NAZWISKO."""
    for seed in range(10):
        doc = _render("{{OSOBA#1}} = {{IMIE#1}} {{NAZWISKO#1}}", seed)
        sbl = _spans_by_label(doc)
        imie = sbl[Label.IMIE][0].text
        nazwisko = sbl[Label.NAZWISKO][0].text
        osoba = sbl[Label.OSOBA][0].text
        assert osoba == f"{imie} {nazwisko}", f"seed={seed}: OSOBA mismatch"


def test_uc10_entity_scope_two_people() -> None:
    """UC-10: OSOBA#1/#2 each match their own IMIE/NAZWISKO pair."""
    doc = _render(
        "{{IMIE#1}} {{NAZWISKO#1}} ({{OSOBA#1}}) i {{IMIE#2}} {{NAZWISKO#2}} ({{OSOBA#2}})",
        seed=5,
    )
    sbl = _spans_by_label(doc)

    osoba_by = {s.entity: s.text for s in sbl[Label.OSOBA]}
    imie_by = {s.entity: s.text for s in sbl[Label.IMIE]}
    nazwisko_by = {s.entity: s.text for s in sbl[Label.NAZWISKO]}

    for eid in ("1", "2"):
        assert osoba_by[eid] == f"{imie_by[eid]} {nazwisko_by[eid]}", (
            f"entity #{eid}: OSOBA mismatch"
        )


# ---------------------------------------------------------------------------
# UC-11 — shared address record; postcode format; ADRES contains house number
# ---------------------------------------------------------------------------

_POSTCODE_RE = re.compile(r"^\d{2}-\d{3}$")
_DIGIT_RE = re.compile(r"\d")


def test_uc11_address_fields_and_format() -> None:
    """UC-11: three address spans; valid postcode; house-number digit; postcode+town in ADRES."""
    doc = _render("{{ADRES#1}}, {{KOD_POCZTOWY#1}} {{MIEJSCOWOSC#1}}", seed=0)
    sbl = _spans_by_label(doc)

    for lbl in (Label.ADRES, Label.KOD_POCZTOWY, Label.MIEJSCOWOSC):
        assert lbl in sbl, f"Missing {lbl.name} span"
        assert sbl[lbl][0].entity == "1", f"{lbl.name} entity should be '1'"

    postcode = sbl[Label.KOD_POCZTOWY][0].text
    adres = sbl[Label.ADRES][0].text
    miejscowosc = sbl[Label.MIEJSCOWOSC][0].text

    assert _POSTCODE_RE.match(postcode), (
        f"KOD_POCZTOWY {postcode!r} does not match \\d{{2}}-\\d{{3}}"
    )
    assert _DIGIT_RE.search(adres), f"ADRES {adres!r} contains no digit (house number missing)"
    assert len(miejscowosc) > 0, "MIEJSCOWOSC is empty"
    # ADRES is composed from one AddressRecord — postcode and town must appear in it
    assert postcode in adres, f"KOD_POCZTOWY {postcode!r} not found in ADRES {adres!r}"
    assert miejscowosc in adres, f"MIEJSCOWOSC {miejscowosc!r} not found in ADRES {adres!r}"


def test_uc11_address_record_shared_across_labels() -> None:
    """UC-11: ADRES, KOD_POCZTOWY, MIEJSCOWOSC with same entity come from one AddressRecord.

    Verifies cache coherence (each label rendered twice gives same value) and that
    ADRES is composed from the shared record — postcode and town are substrings.
    """
    template = (
        "{{ADRES#1}} | {{KOD_POCZTOWY#1}} | {{MIEJSCOWOSC#1}} | {{ADRES#1}} | {{KOD_POCZTOWY#1}}"
    )
    doc = _render(template, seed=0)
    sbl = _spans_by_label(doc)

    adres_spans = sbl[Label.ADRES]
    kp_spans = sbl[Label.KOD_POCZTOWY]
    msc_text = sbl[Label.MIEJSCOWOSC][0].text

    assert len(adres_spans) == 2, f"Expected 2 ADRES spans, got {len(adres_spans)}"
    assert len(kp_spans) == 2, f"Expected 2 KOD_POCZTOWY spans, got {len(kp_spans)}"

    assert adres_spans[0].text == adres_spans[1].text, (
        "ADRES#1 differs between occurrences — not from shared record"
    )
    assert kp_spans[0].text == kp_spans[1].text, (
        "KOD_POCZTOWY#1 differs between occurrences — not from shared record"
    )
    # ADRES must be composed from the same record — postcode and town are substrings
    adres_text = adres_spans[0].text
    assert kp_spans[0].text in adres_text, (
        f"KOD_POCZTOWY {kp_spans[0].text!r} not in ADRES {adres_text!r}"
    )
    assert msc_text in adres_text, f"MIEJSCOWOSC {msc_text!r} not in ADRES {adres_text!r}"


def test_uc11_address_shared_across_seeds() -> None:
    """UC-11: postcode format, house-number, and record-composition hold across 200 seeds."""
    for seed in range(200):
        doc = _render("{{KOD_POCZTOWY#1}} {{MIEJSCOWOSC#1}}, {{ADRES#1}}", seed)
        sbl = _spans_by_label(doc)
        kp_text = sbl[Label.KOD_POCZTOWY][0].text
        adres_text = sbl[Label.ADRES][0].text
        assert _POSTCODE_RE.match(kp_text), f"seed={seed}: bad postcode {kp_text!r}"
        assert _DIGIT_RE.search(adres_text), f"seed={seed}: no house number in ADRES {adres_text!r}"
        assert kp_text in adres_text, (
            f"seed={seed}: KOD_POCZTOWY {kp_text!r} not in ADRES {adres_text!r}"
        )


# ---------------------------------------------------------------------------
# UC-12 — TELEFON format; detect never reports PESEL or NIP inside it
# ---------------------------------------------------------------------------

_PHONE_INTL_RE = re.compile(r"^\+48 \d{3} \d{3} \d{3}$")
_PHONE_SPACED_RE = re.compile(r"^\d{3} \d{3} \d{3}$")
_PHONE_COMPACT_RE = re.compile(r"^\d{9}$")


@pytest.mark.integration
def test_uc12_telefon_accepted_shapes_and_no_false_detect() -> None:
    """UC-12: phone matches accepted shape; piitier.detect finds no PESEL or NIP inside it."""
    import piitier

    for seed in range(200):
        doc = _render("tel. {{TELEFON}}", seed)
        assert len(doc.spans) == 1, f"seed={seed}: expected 1 span, got {len(doc.spans)}"
        phone_text = doc.spans[0].text

        assert (
            _PHONE_INTL_RE.match(phone_text)
            or _PHONE_SPACED_RE.match(phone_text)
            or _PHONE_COMPACT_RE.match(phone_text)
        ), f"seed={seed}: {phone_text!r} matches no accepted phone shape"

        detected = piitier.detect(doc.text)
        for span in detected:
            assert span.label not in (Label.PESEL, Label.NIP), (
                f"seed={seed}: detect found {span.label.name} in "
                f"phone document {doc.text!r} (phone={phone_text!r})"
            )


# ---------------------------------------------------------------------------
# UC-13 — EMAIL syntax: one @, dot in domain, no whitespace
# ---------------------------------------------------------------------------


def test_uc13_email_syntax() -> None:
    """UC-13: EMAIL has exactly one '@', a dot in the domain part, and no whitespace."""
    for seed in range(20):
        doc = _render("{{EMAIL}}", seed)
        assert len(doc.spans) == 1, f"seed={seed}: expected 1 EMAIL span"
        email_text = doc.spans[0].text

        assert email_text.count("@") == 1, (
            f"seed={seed}: {email_text!r} has {email_text.count('@')} '@' characters"
        )
        local, domain = email_text.split("@", 1)
        assert len(local) > 0, f"seed={seed}: empty local part in {email_text!r}"
        assert "." in domain, f"seed={seed}: domain {domain!r} has no '.'"
        assert " " not in email_text, f"seed={seed}: whitespace in {email_text!r}"
        assert len(domain) > 2, f"seed={seed}: domain {domain!r} too short"


# ---------------------------------------------------------------------------
# UC-14 — two explicit people are always distinct across 200 seeds
# ---------------------------------------------------------------------------


def test_uc14_two_explicit_people_distinct() -> None:
    """UC-14: OSOBA#1 and OSOBA#2 never share the same full name across 200 seeds."""
    for seed in range(200):
        doc = _render("{{OSOBA#1}} i {{OSOBA#2}}", seed)
        sbl = _spans_by_label(doc)
        osoba_spans = sbl.get(Label.OSOBA, [])
        assert len(osoba_spans) == 2, f"seed={seed}: expected 2 OSOBA spans, got {len(osoba_spans)}"

        name_by_entity = {s.entity: s.text for s in osoba_spans}
        assert "1" in name_by_entity and "2" in name_by_entity, (
            f"seed={seed}: missing entity in OSOBA spans: {name_by_entity}"
        )
        assert name_by_entity["1"] != name_by_entity["2"], (
            f"seed={seed}: OSOBA#1 and OSOBA#2 both rendered {name_by_entity['1']!r}"
        )


# ---------------------------------------------------------------------------
# Cross-label identity — anonymous must not accidentally reuse explicit entity
# ---------------------------------------------------------------------------


def test_anonymous_person_avoids_explicit_pesel_entity() -> None:
    """Anonymous OSOBA must not share person_records with explicit PESEL#1's entity."""
    doc = _render("{{PESEL#1}} {{OSOBA}}", seed=0)
    sbl = _spans_by_label(doc)

    pesel_spans = sbl.get(Label.PESEL, [])
    osoba_spans = sbl.get(Label.OSOBA, [])
    assert len(pesel_spans) == 1 and len(osoba_spans) == 1

    assert osoba_spans[0].entity != "1", (
        "Anonymous OSOBA received entity '1', colliding with explicit PESEL#1"
    )


def test_anonymous_address_avoids_explicit_adres_entity() -> None:
    """Anonymous KOD_POCZTOWY must not share address_records with explicit ADRES#1 entity."""
    doc = _render("{{ADRES#1}}, {{KOD_POCZTOWY}}", seed=0)
    sbl = _spans_by_label(doc)

    adres_spans = sbl.get(Label.ADRES, [])
    postcode_spans = sbl.get(Label.KOD_POCZTOWY, [])
    assert len(adres_spans) == 1 and len(postcode_spans) == 1

    assert postcode_spans[0].entity != "1", (
        "Anonymous KOD_POCZTOWY received entity '1', colliding with explicit ADRES#1"
    )


# ---------------------------------------------------------------------------
# Regression: make_person raises on collision exhaustion (mock third-party names)
# ---------------------------------------------------------------------------


def test_make_person_raises_on_collision_exhaustion() -> None:
    """make_person raises RuntimeError when all 30 Faker name attempts collide.

    Faker's name providers (third-party randomness) are mocked to always return
    the same full name, causing every attempt to hit avoid_full_names.
    """
    from unittest.mock import MagicMock, patch

    from piitier.datagen.people import make_person

    fixed_first, fixed_last = "Janina", "Kowalska"
    avoid = frozenset({f"{fixed_first} {fixed_last}"})

    with patch("piitier.datagen.people.Faker") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        # All four name providers return the same name regardless of sex
        mock_instance.first_name_male.return_value = fixed_first
        mock_instance.first_name_female.return_value = fixed_first
        mock_instance.last_name_male.return_value = fixed_last
        mock_instance.last_name_female.return_value = fixed_last

        with pytest.raises(RuntimeError, match="could not generate"):
            make_person(random.Random(0), avoid_full_names=avoid)


# ---------------------------------------------------------------------------
# Regression: people/address/contact generators must not leak global RNG state
# ---------------------------------------------------------------------------


def test_no_global_rng_state_leak_from_people_generators() -> None:
    """Rendering people/address/contact documents must not contaminate global RNG state.

    Protocol:
    1. Capture Python's global random state before any render.
    2. Render a structured-only template (PESEL + NIP) at seed 7 → doc_before.
    3. Render several mixed documents at other seeds, exercising make_person,
       make_address, generate_email, and generate_telefon code paths, including
       multi-entity and cross-label templates.
    4. Render the same structured template at seed 7 again → doc_after.
    5. Assert doc_before == doc_after: no cross-document state contamination.
    6. Assert Python global random.getstate() is unchanged: generators must not
       call module-level random functions or use Faker.seed().
    """
    import random as _global_random

    t_structured = Template(
        template_id="reg-s7", doc_type="test", text="PESEL {{PESEL}} NIP {{NIP}}"
    )

    # Step 1: snapshot global random state
    state_before = _global_random.getstate()

    # Step 2: structured-only render at seed 7
    doc_before = render(t_structured, 7)

    # Step 3: exercise all new code paths at other seeds
    for seed in range(5, 15):
        _render("{{OSOBA#1}} {{IMIE#1}} {{NAZWISKO#1}} {{DATA_URODZENIA#1}} {{PESEL#1}}", seed)
        _render("{{ADRES#1}}, {{KOD_POCZTOWY#1}} {{MIEJSCOWOSC#1}}", seed)
        _render("tel. {{TELEFON}} mail {{EMAIL}}", seed)
        _render("{{OSOBA#1}} i {{OSOBA#2}}", seed)

    # Step 4: structured-only render at seed 7 again
    doc_after = render(t_structured, 7)

    # Step 5: Documents must be identical
    assert doc_before.text == doc_after.text, (
        "Structured-only document text differs after running people/address generators: "
        "cross-document RNG state contamination detected"
    )
    assert doc_before.spans == doc_after.spans, (
        "Structured-only document spans differ after running people/address generators"
    )

    # Step 6: Python global random state must be pristine
    state_after = _global_random.getstate()
    assert state_before == state_after, (
        "Python global random.getstate() changed after people/address/contact renders: "
        "generators must use only per-document Random instances, not module-level random"
    )
