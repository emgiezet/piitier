"""Behaviour tests for Template, Placeholder and parse() from piitier.datagen.template.

Parser public contract only; render behaviour (UC-1–4, UC-6 no-generator error,
UC-7 case-rejection at render time) is tested in tests/datagen/test_render.py.

Acceptance criteria addressed:
  UC-5  — unknown label → TemplateError naming template_id + offset; no doc text / payload.
  UC-7  — malformed syntax → TemplateError with same safe-error contract.
  UC-6  — parse of {{LEK}} succeeds (no-generator error is render's job).

Safe-error contract (all TemplateErrors): message carries template_id and character offset
only; raw template.text and unknown-placeholder payload must never appear in the message.

Unicode: Placeholder.offset is a codepoint index, not a UTF-8 byte offset.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from piitier.labels import Label

# ---------------------------------------------------------------------------
# Runtime import helper — keeps collection green before module is written.
# Missing module causes a genuine ModuleNotFoundError at test-execution (RED).
# ---------------------------------------------------------------------------


def _import() -> tuple:
    from piitier.datagen.template import Placeholder, Template, TemplateError, parse

    return Template, TemplateError, Placeholder, parse


# ---------------------------------------------------------------------------
# parse — literal-only templates
# ---------------------------------------------------------------------------


def test_parse_empty_text_returns_empty_list() -> None:
    """parse on an empty template text returns []."""
    Template, _, _, parse = _import()
    assert parse(Template(template_id="t", doc_type="email", text="")) == []


def test_parse_literal_only_returns_single_string() -> None:
    """Template with no placeholders gives a single-element list holding the full text."""
    Template, _, _, parse = _import()
    assert parse(Template(template_id="t", doc_type="email", text="hello world")) == ["hello world"]


def test_parse_polish_diacritics_in_literal_preserved_verbatim() -> None:
    """Polish diacritics in a literal-only template are returned character-for-character."""
    Template, _, _, parse = _import()
    text = "Żółw biegł łąką."
    assert parse(Template(template_id="t", doc_type="email", text=text)) == [text]


# ---------------------------------------------------------------------------
# parse — three legal placeholder forms
# ---------------------------------------------------------------------------


def test_parse_plain_label_form() -> None:
    """{{PESEL}} → [Placeholder(label=PESEL, entity=None, case=None, offset=0)]."""
    Template, _, Placeholder, parse = _import()
    result = parse(Template(template_id="t", doc_type="email", text="{{PESEL}}"))
    assert len(result) == 1
    p = result[0]
    assert isinstance(p, Placeholder)
    assert p.label is Label.PESEL
    assert p.entity is None
    assert p.case is None
    assert p.offset == 0


def test_parse_entity_numbered_form() -> None:
    """{{PESEL#2}} → Placeholder with entity='2' and case=None."""
    Template, _, Placeholder, parse = _import()
    result = parse(Template(template_id="t", doc_type="email", text="{{PESEL#2}}"))
    assert len(result) == 1
    p = result[0]
    assert isinstance(p, Placeholder)
    assert p.entity == "2"
    assert p.case is None


def test_parse_entity_and_case_form() -> None:
    """{{PESEL#1:nom}} → Placeholder with entity='1' and case='nom'."""
    Template, _, Placeholder, parse = _import()
    result = parse(Template(template_id="t", doc_type="email", text="{{PESEL#1:nom}}"))
    assert len(result) == 1
    p = result[0]
    assert isinstance(p, Placeholder)
    assert p.entity == "1"
    assert p.case == "nom"


# ---------------------------------------------------------------------------
# parse — all seven grammatical case tags accepted (render rejects until PII-2-c)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_tag", ["nom", "gen", "dat", "acc", "inst", "loc", "voc"])
def test_parse_all_legal_case_tags_accepted(case_tag: str) -> None:
    """Each of the seven grammatical case tags is valid syntax; parse must not raise.

    UC-7 'case not supported yet' is a render-time rejection, not a parse error.
    """
    Template, _, Placeholder, parse = _import()
    text = "{{" + f"PESEL#1:{case_tag}" + "}}"
    result = parse(Template(template_id="t", doc_type="email", text=text))
    assert len(result) == 1
    p = result[0]
    assert isinstance(p, Placeholder)
    assert p.case == case_tag


# ---------------------------------------------------------------------------
# parse — literal + placeholder mixing; all literal segments preserved
# ---------------------------------------------------------------------------


def test_parse_prefix_literal_preserved() -> None:
    """Literal text before a placeholder is the first string element."""
    Template, _, Placeholder, parse = _import()
    result = parse(Template(template_id="t", doc_type="email", text="Klient {{PESEL}}"))
    assert isinstance(result[0], str) and result[0] == "Klient "
    assert isinstance(result[1], Placeholder)


def test_parse_suffix_literal_preserved() -> None:
    """Literal text after a placeholder is the last string element."""
    Template, _, Placeholder, parse = _import()
    result = parse(Template(template_id="t", doc_type="email", text="{{PESEL}}."))
    assert isinstance(result[0], Placeholder)
    assert result[1] == "."


def test_parse_multiple_placeholders_all_literals_in_order() -> None:
    """All literal segments between and around placeholders appear verbatim and in order."""
    Template, _, Placeholder, parse = _import()
    result = parse(Template(template_id="t", doc_type="email", text="A {{PESEL}} B {{NIP}} C"))
    strings = [e for e in result if isinstance(e, str)]
    placeholders = [e for e in result if isinstance(e, Placeholder)]
    assert strings == ["A ", " B ", " C"]
    assert [p.label for p in placeholders] == [Label.PESEL, Label.NIP]


# ---------------------------------------------------------------------------
# Offset accuracy — codepoint index, not UTF-8 byte offset
# ---------------------------------------------------------------------------


def test_parse_offset_equals_char_index_of_opening_brace() -> None:
    """Placeholder.offset is the 0-based character index of '{{' in the template text."""
    Template, _, Placeholder, parse = _import()
    prefix = "abc"  # 3 characters
    result = parse(Template(template_id="t", doc_type="email", text=f"{prefix}{{{{PESEL}}}}"))
    p = next(e for e in result if isinstance(e, Placeholder))
    assert p.offset == len(prefix)  # 3


def test_unicode_offset_is_codepoint_index_not_utf8_byte_offset() -> None:
    """ "Żółw " is 5 codepoints but 8 UTF-8 bytes; offset must be 5, not 8."""
    Template, _, Placeholder, parse = _import()
    prefix = "Żółw "
    assert len(prefix) == 5, "precondition: 5 Unicode codepoints"
    result = parse(Template(template_id="t", doc_type="email", text=f"{prefix}{{{{PESEL}}}}"))
    p = next(e for e in result if isinstance(e, Placeholder))
    assert p.offset == 5


# ---------------------------------------------------------------------------
# UC-5 — unknown label: TemplateError with safe-error contract
#
# Each parametrised row is a distinct input; all assertions run together:
#   • raises TemplateError
#   • message contains template_id
#   • message contains expected offset
#   • message does not contain the raw template.text
#   • message does not contain any strings in extra_absent
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,tid,offset_str,extra_absent",
    [
        # unknown label at position 0 — id, offset, and no raw text
        ("{{ZQXFOO}}", "uc5-safe-id", "0", []),
        # unknown label at non-zero position — offset 7 ("Klient " is 7 chars)
        ("Klient {{ZQXFOO}}", "uc5-pos-id", "7", []),
        # unknown label payload must not leak — neither with nor without braces
        ("{{ZQXUNKNOWNLABEL}}", "uc5-payload-id", "0", ["ZQXUNKNOWNLABEL"]),
    ],
)
def test_uc5_unknown_label_error_contract(
    text: str, tid: str, offset_str: str, extra_absent: list[str]
) -> None:
    """UC-5: unknown label raises TemplateError; message names template_id + offset only."""
    Template, TemplateError, _, parse = _import()
    with pytest.raises(TemplateError) as exc_info:
        parse(Template(template_id=tid, doc_type="email", text=text))
    msg = str(exc_info.value)
    assert tid in msg
    assert offset_str in msg
    assert text not in msg  # raw template.text must never appear
    for s in extra_absent:
        assert s not in msg


# ---------------------------------------------------------------------------
# UC-7 — malformed syntax: TemplateError with safe-error contract
#
# Each row is a distinct malformed input; same assertions as UC-5.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,tid,offset_str",
    [
        # unclosed placeholder
        ("{{PESEL", "uc7-tmpl", "0"),
        # bad entity id — non-digit letter
        ("{{PESEL#x}}", "uc7-bad-entity", "0"),
        # bad entity id — mixed alphanumeric
        ("{{PESEL#1a}}", "uc7-tmpl", "0"),
        # bad entity id — empty after #
        ("{{PESEL#}}", "uc7-tmpl", "0"),
        # empty label name
        ("{{}}", "uc7-tmpl", "0"),
        # unknown case tag (only nom/gen/dat/acc/inst/loc/voc are valid)
        ("{{PESEL#1:english}}", "uc7-tmpl", "0"),
        # case tag present but no entity #k ({{LABEL:case}} is not a valid form)
        ("{{PESEL:nom}}", "uc7-tmpl", "0"),
        # bad entity id mid-template — offset reflects '{{' position (9 chars of prefix)
        ("Umowa nr {{PESEL#badid}} z dnia", "uc7-long", "9"),
    ],
)
def test_uc7_malformed_syntax_raises_template_error(text: str, tid: str, offset_str: str) -> None:
    """UC-7: malformed placeholder raises TemplateError; message names template_id + offset only."""
    Template, TemplateError, _, parse = _import()
    with pytest.raises(TemplateError) as exc_info:
        parse(Template(template_id=tid, doc_type="email", text=text))
    msg = str(exc_info.value)
    assert tid in msg
    assert offset_str in msg
    assert text not in msg  # raw template.text must never appear


# ---------------------------------------------------------------------------
# UC-6 (parse side) — LEK is a known Label; parse does not reject it
# ---------------------------------------------------------------------------


def test_uc6_lek_parse_succeeds_and_label_stored() -> None:
    """UC-6 (parse side): {{LEK}} is a known Label; parse returns a Placeholder.

    The 'no generator' TemplateError is raised by render, not parse.
    """
    Template, _, Placeholder, parse = _import()
    result = parse(Template(template_id="t", doc_type="discharge", text="{{LEK}}"))
    assert len(result) == 1
    p = result[0]
    assert isinstance(p, Placeholder)
    assert p.label is Label.LEK
    assert p.entity is None
    assert p.case is None


# ---------------------------------------------------------------------------
# Property — placeholder offsets are consistent with '{{' positions in text
# ---------------------------------------------------------------------------

_GENERATOR_LABEL_NAMES: list[str] = [
    "PESEL",
    "NIP",
    "REGON",
    "IBAN",
    "NR_DOWODU",
    "NR_KARTY",
]

# Literal parts contain no braces so they cannot accidentally form a placeholder.
_st_literal = st.text(
    alphabet=st.characters(blacklist_characters="{}", min_codepoint=32),
    min_size=0,
    max_size=20,
)
_st_placeholder_token = st.sampled_from([f"{{{{{lbl}}}}}" for lbl in _GENERATOR_LABEL_NAMES])
_st_part = st.one_of(_st_literal, _st_placeholder_token)


@given(parts=st.lists(_st_part, min_size=1, max_size=8))
@settings(max_examples=200)
def test_property_placeholder_offsets_point_to_opening_braces(parts: list[str]) -> None:
    """For any generated template, text[p.offset : p.offset+2] == '{{' for every Placeholder."""
    Template, _, Placeholder, parse = _import()
    text = "".join(parts)
    result = parse(Template(template_id="prop-test", doc_type="email", text=text))
    for element in result:
        if isinstance(element, Placeholder):
            assert text[element.offset : element.offset + 2] == "{{"
