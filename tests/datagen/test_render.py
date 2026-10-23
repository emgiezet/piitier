"""Consolidated acceptance tests for PII-2-a — synthetic labelled document rendering.

Covers UC-1 through UC-8 per pre-implementation deduplication requirements.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import piitier
from piitier.labels import Label
from piitier.rules import iban as iban_rules
from piitier.rules import id_card as id_card_rules
from piitier.rules import nip as nip_rules
from piitier.rules import payment_card as payment_card_rules
from piitier.rules import pesel as pesel_rules
from piitier.rules import regon as regon_rules


def _render(text: str, seed: int, template_id: str = "t1", doc_type: str = "test"):
    from piitier.datagen import Template, render

    return render(Template(template_id=template_id, doc_type=doc_type, text=text), seed)


# ---------------------------------------------------------------------------
# UC-1 — basic PESEL render (consolidated)
# ---------------------------------------------------------------------------


def test_uc1_render_pesel_complete() -> None:
    """UC-1: verify text framing, PESEL span, metadata, and offset integrity."""
    doc = _render("Klient PESEL {{PESEL}}.", seed=7, template_id="policy-001", doc_type="policy")
    assert doc.text.startswith("Klient PESEL ")
    assert doc.text.endswith(".")
    assert doc.template_id == "policy-001"
    assert doc.doc_type == "policy"
    assert doc.seed == 7

    assert len(doc.spans) == 1
    span = doc.spans[0]
    assert span.label is Label.PESEL
    assert span.source == "synthetic"
    assert span.status == "valid"
    assert isinstance(span.entity, str)
    assert span.entity != ""
    assert span.text == doc.text[span.start : span.end]
    assert pesel_rules.is_valid(span.text)


# ---------------------------------------------------------------------------
# UC-2 — seed identity and seed difference (consolidated)
# ---------------------------------------------------------------------------


def test_uc2_seed_identity_and_difference() -> None:
    """UC-2: same seed gives identical text/spans; different seed gives different PESEL."""
    from piitier.datagen import Template, render

    t = Template(template_id="t2", doc_type="test", text="Klient PESEL {{PESEL}}.")
    doc7a = render(t, 7)
    doc7b = render(t, 7)
    doc8 = render(t, 8)

    assert doc7a.text == doc7b.text
    assert doc7a.spans == doc7b.spans

    val7 = doc7a.text[doc7a.spans[0].start : doc7a.spans[0].end]
    val8 = doc8.text[doc8.spans[0].start : doc8.spans[0].end]
    assert val7 != val8


# ---------------------------------------------------------------------------
# UC-3 — numbered-entity caching (consolidated)
# ---------------------------------------------------------------------------


def test_uc3_numbered_entity_caching() -> None:
    """UC-3: repeated #1 spans share identical text and entity='1'; #2 distinct."""
    doc = _render("{{IBAN#1}} oraz {{IBAN#1}}, inny {{IBAN#2}}", seed=42)
    assert len(doc.spans) == 3
    for span in doc.spans:
        assert doc.text[span.start : span.end] == span.text

    iban1 = [s for s in doc.spans if s.entity == "1"]
    iban2 = [s for s in doc.spans if s.entity == "2"]
    assert len(iban1) == 2
    assert len(iban2) == 1
    assert iban1[0].text == iban1[1].text
    assert iban1[0].text != iban2[0].text


# ---------------------------------------------------------------------------
# UC-4 — integration: all 6 labels detectable across 50 seeds (consolidated)
# ---------------------------------------------------------------------------

_UC4_TEMPLATE = (
    "PESEL {{PESEL}} NIP {{NIP}} REGON {{REGON}} "
    "IBAN {{IBAN}} Dowód {{NR_DOWODU}} Karta {{NR_KARTY}}"
)

_SIX_LABELS = frozenset(
    {Label.PESEL, Label.NIP, Label.REGON, Label.IBAN, Label.NR_DOWODU, Label.NR_KARTY}
)


@pytest.mark.integration
def test_uc4_all_seeds_detectability_and_validity() -> None:
    """UC-4: across 50 seeds, all 6 labels are rendered, detected, valid, and pass validators."""
    from piitier.datagen import Template, render

    validator = {
        Label.PESEL: lambda txt: pesel_rules.is_valid(pesel_rules._strip_separators(txt)),
        Label.NIP: lambda txt: nip_rules.is_valid(
            nip_rules._strip_separators(txt).upper().removeprefix("PL")
        ),
        Label.REGON: regon_rules.is_valid,
        Label.IBAN: iban_rules.is_valid,
        Label.NR_DOWODU: id_card_rules.is_valid,
        Label.NR_KARTY: payment_card_rules.is_valid,
    }
    t = Template(template_id="uc4", doc_type="test", text=_UC4_TEMPLATE)
    for seed in range(50):
        doc = render(t, seed)
        assert {s.label for s in doc.spans} == _SIX_LABELS

        detected_by_key = {(s.start, s.end, s.label): s for s in piitier.detect(doc.text)}
        for span in doc.spans:
            key = (span.start, span.end, span.label)
            assert key in detected_by_key
            assert detected_by_key[key].status == "valid"
            assert validator[span.label](span.text)


def test_format_diversity_observed() -> None:
    """Verify that multiple format variants are generated across seeds."""
    from piitier.datagen import Template, render

    t = Template(template_id="div", doc_type="test", text="{{PESEL}} {{IBAN}}")
    pesel_forms = set()
    iban_forms = set()
    for seed in range(50):
        doc = render(t, seed)
        for s in doc.spans:
            if s.label is Label.PESEL:
                pesel_forms.add(s.text)
            elif s.label is Label.IBAN:
                iban_forms.add(s.text)
    assert len(pesel_forms) > 1
    assert len(iban_forms) > 1


# ---------------------------------------------------------------------------
# UC-5, UC-6, UC-7 — errors (consolidated)
# ---------------------------------------------------------------------------


def test_uc5_unknown_label_error() -> None:
    """UC-5: {{FOO}} raises TemplateError naming template_id and offset, without leaking text."""
    from piitier.datagen import TemplateError

    with pytest.raises(TemplateError) as exc_info:
        _render("before {{FOO}} after", seed=0, template_id="safe-id")
    msg = str(exc_info.value)
    assert "safe-id" in msg
    assert "before" not in msg
    assert "after" not in msg


def test_uc6_no_generator_error() -> None:
    """UC-6: {{WIEK}} raises TemplateError mentioning WIEK."""
    from piitier.datagen import TemplateError

    with pytest.raises(TemplateError, match="WIEK"):
        _render("{{WIEK}}", seed=0)


def test_uc7_malformed_errors() -> None:
    """UC-7: unclosed placeholder, bad entity ID, and case raise TemplateError."""
    from piitier.datagen import TemplateError

    with pytest.raises(TemplateError, match="bad-tmpl"):
        _render("{{PESEL", seed=0, template_id="bad-tmpl")
    with pytest.raises(TemplateError):
        _render("{{PESEL#x}}", seed=0)
    with pytest.raises(TemplateError):
        _render("{{PESEL#1:gen}}", seed=0)


# ---------------------------------------------------------------------------
# UC-8 — hypothesis property test (consolidated)
# ---------------------------------------------------------------------------

_SAFE_ALPHA = "abcdefghijklmnoprstuwzAąęóśźżćńł "

_SUPPORTED_PLACEHOLDERS = [
    "{{PESEL}}",
    "{{NIP}}",
    "{{IBAN}}",
    "{{NR_DOWODU}}",
    "{{NR_KARTY}}",
    "{{REGON}}",
]


@st.composite
def _render_fixture(draw):
    from piitier.datagen import Template, render

    prefix = draw(st.text(alphabet=_SAFE_ALPHA, min_size=1, max_size=12))
    suffix = draw(st.text(alphabet=_SAFE_ALPHA, min_size=1, max_size=12))
    sep = draw(st.text(alphabet=_SAFE_ALPHA, min_size=1, max_size=6))
    chosen = draw(st.lists(st.sampled_from(_SUPPORTED_PLACEHOLDERS), min_size=0, max_size=4))
    template_text = prefix + sep.join(chosen) + suffix
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    return (
        render(Template(template_id="uc8-prop", doc_type="test", text=template_text), seed),
        prefix,
        suffix,
    )


@given(fixture=_render_fixture())
@settings(max_examples=60)
def test_uc8_properties_consolidated(fixture) -> None:
    """UC-8: offset integrity, sorted non-overlapping spans, metadata, and literal preservation."""
    doc, prefix, suffix = fixture
    assert doc.text.startswith(prefix)
    assert doc.text.endswith(suffix)

    starts = [s.start for s in doc.spans]
    assert starts == sorted(starts)

    for i in range(len(doc.spans) - 1):
        assert doc.spans[i].end <= doc.spans[i + 1].start

    for span in doc.spans:
        assert span.source == "synthetic"
        assert span.status == "valid"
        assert span.text == doc.text[span.start : span.end]


# ---------------------------------------------------------------------------
# Entity caching & scoping
# ---------------------------------------------------------------------------


def test_entity_caching_and_scoping() -> None:
    """Anonymous vs explicit IDs, mutual distinctness, and label-scoped caching."""
    # Anonymous non-collision & distinctness
    doc1 = _render("{{IBAN#3}} x {{IBAN}} y {{IBAN}}", seed=0)
    anon_spans = [s for s in doc1.spans if s.entity != "3"]
    assert len(anon_spans) == 2
    assert anon_spans[0].entity != anon_spans[1].entity
    assert all(s.entity != "3" for s in anon_spans)

    # Label-scoped caching (IBAN#1 vs NR_KARTY#1)
    doc2 = _render("{{IBAN#1}} {{IBAN#1}} {{NR_KARTY#1}} {{NR_KARTY#1}}", seed=42)
    iban_spans = [s for s in doc2.spans if s.label is Label.IBAN]
    card_spans = [s for s in doc2.spans if s.label is Label.NR_KARTY]
    assert iban_spans[0].text == iban_spans[1].text
    assert card_spans[0].text == card_spans[1].text
    assert iban_rules.is_valid(iban_spans[0].text)
    assert payment_card_rules.is_valid(card_spans[0].text)
