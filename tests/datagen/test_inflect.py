"""Acceptance tests for PII-2-c — inflect() function and case-aware render.

Covers UC-15 through UC-21 per specs/PII-2-c/spec.md.

Design notes
------------
- Imports of new modules (inflect, inflection_fallbacks on Document) happen
  inside test bodies so pytest collection succeeds before the modules exist;
  failures are execution-time RED, not collection errors.
- Morfeusz forms tested in UC-15/16 are from the parent's live probe:
    Kowalski gen m  → Kowalskiego (subst:sg:gen:m1)
    Kowalska gen f  → Kowalskiej  (subst:sg:gen:f)
    Anna     dat f  → Annie       (subst:sg:dat.loc:f — dot case component)
    Jan      inst m → Janem       (subst:sg:inst:m1)
- Unknown name "Xqzwy": generate() returns [('Xqzwy','Xqzwy','ign',[],[])];
  ign tag triggers fallback — verified by parent probe.
- people.make_person is monkeypatched to fix person identity for deterministic
  render assertions; patches are function-scoped (pytest default).
"""

from __future__ import annotations

from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from piitier.labels import Label

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _import_inflect():
    """Deferred import so collection succeeds before inflect.py is created."""
    from piitier.datagen.inflect import inflect

    return inflect


def _render(text: str, seed: int, template_id: str = "t1", doc_type: str = "test"):
    from piitier.datagen import Template, render

    return render(Template(template_id=template_id, doc_type=doc_type, text=text), seed)


def _make_person(sex: str = "M", first_name: str = "Jan", last_name: str = "Kowalski"):
    """Create a PersonRecord with fixed fields for deterministic inflection tests."""
    from piitier.datagen.people import PersonRecord

    return PersonRecord(
        sex=sex,
        first_name=first_name,
        last_name=last_name,
        birth_date=date(1980, 1, 1),
        pesel="80010112345",  # dummy; validators not invoked in inflection path
    )


# ---------------------------------------------------------------------------
# UC-15 — inflect surname genitive (Morfeusz real generation, sex agreement)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,case,sex,expected",
    [
        ("Kowalski", "gen", "m", "Kowalskiego"),
        ("Kowalska", "gen", "f", "Kowalskiej"),
    ],
)
def test_uc15_inflect_surname_gen(name: str, case: str, sex: str, expected: str) -> None:
    """UC-15: inflect(surname, case='gen', sex) returns the correct Morfeusz genitive form.

    Filtering must prefer sg+correct-gender forms; female indeclinable entries for
    'Kowalski' appear first in generate() output and must be skipped for sex='m'.
    """
    inflect = _import_inflect()
    assert inflect(name, case=case, sex=sex) == expected


# ---------------------------------------------------------------------------
# UC-16 — inflect first-name dat/inst (Morfeusz real generation)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,case,sex,expected",
    [
        ("Anna", "dat", "f", "Annie"),  # tag subst:sg:dat.loc:f — dot-separated case
        ("Jan", "inst", "m", "Janem"),  # tag subst:sg:inst:m1
    ],
)
def test_uc16_inflect_firstname_dat_inst(name: str, case: str, sex: str, expected: str) -> None:
    """UC-16: inflect(first_name, case, sex) returns the correct inflected form.

    Dot-separated case components (e.g. 'dat.loc') must be split on '.' and matched
    individually so that 'dat' finds 'dat.loc' entries.
    """
    inflect = _import_inflect()
    assert inflect(name, case=case, sex=sex) == expected


# ---------------------------------------------------------------------------
# UC-17 — render {{OSOBA#1:inst}} keeps entity="1"; second span "Janem Kowalskim"
# ---------------------------------------------------------------------------


def test_uc17_render_osoba_inst_second_span(monkeypatch) -> None:
    """UC-17: second span of {{OSOBA#1:inst}} is 'Janem Kowalskim'; both spans entity='1', OSOBA.

    OSOBA inflects first name and surname independently; results are joined with a space.
    """
    from piitier.datagen import people

    fixed = _make_person(sex="M", first_name="Jan", last_name="Kowalski")
    monkeypatch.setattr(people, "make_person", lambda rng, avoid=frozenset(): fixed)

    doc = _render("{{OSOBA#1}} rozmowa z {{OSOBA#1:inst}}", seed=42)

    assert len(doc.spans) == 2
    nom_span, inst_span = doc.spans

    # Both spans share entity "1" and label OSOBA
    assert nom_span.entity == "1"
    assert inst_span.entity == "1"
    assert nom_span.label is Label.OSOBA
    assert inst_span.label is Label.OSOBA

    # Nominative span: unchanged "Jan Kowalski"
    assert nom_span.text == "Jan Kowalski"
    assert doc.text[nom_span.start : nom_span.end] == "Jan Kowalski"

    # Instrumental span: first name and surname inflected independently
    assert inst_span.text == "Janem Kowalskim"
    assert doc.text[inst_span.start : inst_span.end] == "Janem Kowalskim"


# ---------------------------------------------------------------------------
# UC-18 — {{NAZWISKO#1:xyz}} raises TemplateError naming the unknown case
# ---------------------------------------------------------------------------


def test_uc18_invalid_case_error_names_the_case() -> None:
    """UC-18: {{NAZWISKO#1:xyz}} raises TemplateError whose message contains 'xyz'.

    The case token 'xyz' is not in _VALID_CASES; parse() must include it in the
    error message so the author can identify the typo.
    """
    from piitier.datagen import TemplateError

    with pytest.raises(TemplateError) as exc_info:
        _render("{{NAZWISKO#1:xyz}}", seed=0, template_id="uc18-tmpl")

    assert "xyz" in str(exc_info.value)


def test_uc18_invalid_case_error_carries_template_id() -> None:
    """UC-18: TemplateError message also carries template_id (safe-error contract preserved)."""
    from piitier.datagen import TemplateError

    with pytest.raises(TemplateError) as exc_info:
        _render("{{IMIE#1:xyz}}", seed=0, template_id="uc18-tid")

    assert "uc18-tid" in str(exc_info.value)


# ---------------------------------------------------------------------------
# UC-19 — case not allowed for non-inflectable labels (PESEL, ADRES)
# ---------------------------------------------------------------------------


def test_uc19_case_not_allowed_for_pesel() -> None:
    """UC-19: {{PESEL#1:gen}} raises TemplateError (case not allowed for PESEL)."""
    from piitier.datagen import TemplateError

    with pytest.raises(TemplateError):
        _render("{{PESEL#1:gen}}", seed=0)


def test_uc19_case_not_allowed_for_adres() -> None:
    """UC-19: {{ADRES#1:loc}} raises TemplateError (case not allowed for ADRES)."""
    from piitier.datagen import TemplateError

    with pytest.raises(TemplateError):
        _render("{{ADRES#1:loc}}", seed=0)


def test_uc19_rejection_originates_in_parse() -> None:
    """UC-19: parse() rejects label+case after label resolution, not at render time.

    The parent contract requires this so that PII-2-e completion validation
    (which calls parse() directly) also rejects {{PESEL#1:gen}} / {{ADRES#1:loc}}.
    reason must not be 'Unknown label' — that string is reserved for PII-2-e mapping.
    """
    from piitier.datagen.template import Template, TemplateError, parse

    for tmpl_text in ("{{PESEL#1:gen}}", "{{ADRES#1:loc}}"):
        tmpl = Template(template_id="uc19", doc_type="test", text=tmpl_text)
        with pytest.raises(TemplateError) as exc_info:
            parse(tmpl)
        assert exc_info.value.reason != "Unknown label", (
            f"reason for {tmpl_text!r} must differ from 'Unknown label'"
        )


# ---------------------------------------------------------------------------
# UC-20 — fallback for ign-tagged name: span text unchanged; counter incremented
# ---------------------------------------------------------------------------


def test_uc20_inflect_xqzwy_returns_input() -> None:
    """UC-20: inflect('Xqzwy', 'gen', 'm') returns 'Xqzwy' (fallback)."""
    inflect = _import_inflect()
    assert inflect("Xqzwy", case="gen", sex="m") == "Xqzwy"


def test_multi_word_name_inflection() -> None:
    """Multi-word name 'Anna Maria' in genitive yields 'Anny Marii'."""
    inflect = _import_inflect()
    assert inflect("Anna Maria", case="gen", sex="f") == "Anny Marii"


def test_uc20_render_fallback_span_and_counter(monkeypatch) -> None:
    """UC-20: unknown surname in :gen → span.text='Xqzwy'; doc.inflection_fallbacks == 1."""
    from piitier.datagen import people

    fixed = _make_person(sex="M", first_name="Jan", last_name="Xqzwy")
    monkeypatch.setattr(people, "make_person", lambda rng, avoid=frozenset(): fixed)

    doc = _render("{{NAZWISKO#1:gen}}", seed=0)

    assert len(doc.spans) == 1
    span = doc.spans[0]
    assert span.text == "Xqzwy"
    assert doc.text[span.start : span.end] == "Xqzwy"
    assert doc.inflection_fallbacks == 1


def test_uc20_no_fallback_for_known_name_nom(monkeypatch) -> None:
    """No fallback counted when nom requested for a known name."""
    from piitier.datagen import people

    fixed = _make_person(sex="M", first_name="Jan", last_name="Kowalski")
    monkeypatch.setattr(people, "make_person", lambda rng, avoid=frozenset(): fixed)

    doc = _render("{{OSOBA#1:nom}}", seed=0)
    assert doc.inflection_fallbacks == 0


def test_uc20_multiple_component_fallbacks_sum(monkeypatch) -> None:
    """Each unknown component increments inflection_fallbacks by 1; two separate label keys → 2."""
    from piitier.datagen import people

    # Both first_name and last_name are unknown to Morfeusz
    fixed = _make_person(sex="M", first_name="Xqzwy", last_name="Xqzwy")
    monkeypatch.setattr(people, "make_person", lambda rng, avoid=frozenset(): fixed)

    # IMIE#1:gen and NAZWISKO#1:gen have different cache keys (label differs) → 2 fallbacks
    doc = _render("{{IMIE#1:gen}} {{NAZWISKO#1:gen}}", seed=0)
    assert doc.inflection_fallbacks == 2


def test_repeated_slot_fallback_accumulates_per_occurrence(monkeypatch) -> None:
    """Repeated NAZWISKO#1:gen with unknown surname counts 2 fallbacks."""
    from piitier.datagen import people

    fixed = _make_person(sex="M", first_name="Jan", last_name="Xqzwy")
    monkeypatch.setattr(people, "make_person", lambda rng, avoid=frozenset(): fixed)

    doc = _render("{{NAZWISKO#1:gen}} and {{NAZWISKO#1:gen}}", seed=0)
    assert doc.inflection_fallbacks == 2


# ---------------------------------------------------------------------------
# UC-21 — offset property test rerun with case-suffixed name placeholders (+ CRLF)
# ---------------------------------------------------------------------------

_SAFE_LITERAL = "abcdefAąęóśźżćńł "

# Valid case-annotated and plain name placeholders; entity IDs are fixed single digits
_CASE_PLACEHOLDERS = [
    "{{OSOBA#1:gen}}",
    "{{OSOBA#1:dat}}",
    "{{OSOBA#1:acc}}",
    "{{OSOBA#1:inst}}",
    "{{OSOBA#1:loc}}",
    "{{OSOBA#1:voc}}",
    "{{OSOBA#1}}",  # plain nominative — no case suffix
    "{{IMIE#2:gen}}",
    "{{IMIE#2:dat}}",
    "{{IMIE#2}}",
    "{{NAZWISKO#3:gen}}",
    "{{NAZWISKO#3:inst}}",
    "{{NAZWISKO#3}}",
]

# Include \r\n to verify 2-char CRLF line endings are counted as 2 code-points
_SEPARATORS = [" ", ", ", "\n", "\r\n"]


@st.composite
def _uc21_fixture(draw):
    from piitier.datagen import Template, render

    prefix = draw(st.text(alphabet=_SAFE_LITERAL, min_size=1, max_size=8))
    suffix = draw(st.text(alphabet=_SAFE_LITERAL, min_size=1, max_size=8))
    sep = draw(st.sampled_from(_SEPARATORS))
    chosen = draw(st.lists(st.sampled_from(_CASE_PLACEHOLDERS), min_size=1, max_size=4))
    template_text = prefix + sep.join(chosen) + suffix
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    return render(Template(template_id="uc21-prop", doc_type="test", text=template_text), seed)


@given(doc=_uc21_fixture())
@settings(max_examples=50)
def test_uc21_offset_integrity_with_case_suffixes(doc) -> None:
    """UC-21: doc.text[start:end] == span.text for every span, even case-inflected names.

    This is the PII-2-a offset property (UC-8) rerun with case-suffixed name placeholders.
    CRLF separators confirm 2-char line endings are counted as 2 code-points.
    """
    for span in doc.spans:
        assert doc.text[span.start : span.end] == span.text, (
            f"Offset mismatch: label={span.label.name} entity={span.entity!r} "
            f"span.text={span.text!r} "
            f"text[{span.start}:{span.end}]={doc.text[span.start : span.end]!r}"
        )


# ---------------------------------------------------------------------------
# Additional: Document.inflection_fallbacks default = 0 (old constructors unchanged)
# ---------------------------------------------------------------------------


def test_document_inflection_fallbacks_default_zero() -> None:
    """Document.inflection_fallbacks == 0 when no inflection is requested."""
    doc = _render("{{PESEL}}", seed=0)
    assert doc.inflection_fallbacks == 0


# ---------------------------------------------------------------------------
# Additional: parse() accepts inflectable labels paired with valid case (happy path)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label_name", ["OSOBA", "IMIE", "NAZWISKO"])
@pytest.mark.parametrize("case_tag", ["nom", "gen", "dat", "acc", "inst", "loc", "voc"])
def test_parse_inflectable_label_with_case_succeeds(label_name: str, case_tag: str) -> None:
    """parse() returns a Placeholder for inflectable label + any valid case (no error)."""
    from piitier.datagen.template import Placeholder, Template, parse

    tmpl = Template(
        template_id="t",
        doc_type="test",
        text="{{" + f"{label_name}#1:{case_tag}" + "}}",
    )
    result = parse(tmpl)
    assert len(result) == 1
    p = result[0]
    assert isinstance(p, Placeholder)
    assert p.case == case_tag


# ---------------------------------------------------------------------------
# Additional: entity ID consistent across mixed cases and reverse case order
# ---------------------------------------------------------------------------


def test_entity_consistent_mixed_cases(monkeypatch) -> None:
    """Same entity ID on all spans when one person appears in gen/dat/nom cases."""
    from piitier.datagen import people

    fixed = _make_person(sex="F", first_name="Anna", last_name="Kowalska")
    monkeypatch.setattr(people, "make_person", lambda rng, avoid=frozenset(): fixed)

    doc = _render("{{OSOBA#1:gen}} i {{OSOBA#1:dat}} i {{OSOBA#1}}", seed=0)
    assert len(doc.spans) == 3
    for span in doc.spans:
        assert span.entity == "1"
        assert span.label is Label.OSOBA
        assert doc.text[span.start : span.end] == span.text


def test_entity_consistent_reverse_case_order(monkeypatch) -> None:
    """Reverse order (gen first, nom second) yields consistent entity ID and correct offsets."""
    from piitier.datagen import people

    fixed = _make_person(sex="M", first_name="Jan", last_name="Kowalski")
    monkeypatch.setattr(people, "make_person", lambda rng, avoid=frozenset(): fixed)

    # gen appears BEFORE nom — opposite of the typical pattern
    doc = _render("rozmowa z {{OSOBA#1:gen}}, czyli {{OSOBA#1}}", seed=0)
    assert len(doc.spans) == 2
    gen_span, nom_span = doc.spans

    assert gen_span.entity == "1"
    assert nom_span.entity == "1"
    assert gen_span.label is Label.OSOBA
    assert nom_span.label is Label.OSOBA

    # Offset integrity
    assert doc.text[gen_span.start : gen_span.end] == gen_span.text
    assert doc.text[nom_span.start : nom_span.end] == nom_span.text

    # Nominative is "Jan Kowalski" (known, unchanged)
    assert nom_span.text == "Jan Kowalski"
    # Genitive form differs from nominative for a known name
    assert gen_span.text != "Jan Kowalski"


# ---------------------------------------------------------------------------
# Additional: TemplateError.reason == 'Unknown label' preserved (PII-2-e contract)
# ---------------------------------------------------------------------------


def test_unknown_label_reason_field_stable() -> None:
    """TemplateError.reason is exactly 'Unknown label' for unknown labels (PII-2-e mapping)."""
    from piitier.datagen.template import Template, TemplateError, parse

    # Unknown label fires before any label-case check; reason must remain unchanged
    tmpl = Template(template_id="e-compat", doc_type="test", text="{{XYZZY#1:gen}}")
    with pytest.raises(TemplateError) as exc_info:
        parse(tmpl)
    assert exc_info.value.reason == "Unknown label"


# ---------------------------------------------------------------------------
# Additional: nominative render byte-identical to pre-PII-2-c
# ---------------------------------------------------------------------------


def test_nominative_render_byte_identical(monkeypatch) -> None:
    """Plain {{OSOBA#1}} renders as 'Jan Kowalski' — unchanged from pre-PII-2-c."""
    from piitier.datagen import people

    fixed = _make_person(sex="M", first_name="Jan", last_name="Kowalski")
    monkeypatch.setattr(people, "make_person", lambda rng, avoid=frozenset(): fixed)

    doc = _render("{{OSOBA#1}}", seed=0)
    assert len(doc.spans) == 1
    assert doc.spans[0].text == "Jan Kowalski"
    assert doc.text == "Jan Kowalski"
    assert doc.inflection_fallbacks == 0
