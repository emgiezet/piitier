"""Consolidated acceptance tests for PII-3-c — OCR/diacritic augmentation."""

from __future__ import annotations

import random

from piitier.datagen import Template, render
from piitier.datagen.augment import ALL_TRANSFORMS, augment
from piitier.datagen.render import Document, SyntheticSpan
from piitier.labels import Label


def assert_offsets(doc: Document) -> None:
    """Verify offsets: 0 <= start < end <= len(text), text[start:end] == span.text."""
    last_end = 0
    for span in doc.spans:
        assert 0 <= span.start < span.end <= len(doc.text)
        assert doc.text[span.start : span.end] == span.text
        assert span.start >= last_end
        last_end = span.end


# ---------------------------------------------------------------------------
# UC-54 — offset integrity across 100 rendered documents
# ---------------------------------------------------------------------------


def test_uc54_offset_integrity_100_docs() -> None:
    """UC-54: after each transform and all combined for 100 documents, offset integrity holds."""
    templates = [
        Template(
            "t1", "test", "Klient {{OSOBA#1}}, PESEL {{PESEL}}, IBAN {{IBAN}}, adres {{ADRES#1}}."
        ),
        Template(
            "t2",
            "test",
            "{{IMIE#1}} {{NAZWISKO#1}}, NIP {{NIP}}, REGON {{REGON}}, tel. {{TELEFON}}.",
        ),
        Template(
            "t3",
            "test",
            "Dowód {{NR_DOWODU}}, karta {{NR_KARTY}}, karta 2 {{NR_KARTY#2}}, mail {{EMAIL}}.",
        ),
    ]
    for i in range(100):
        tmpl = templates[i % len(templates)]
        doc = render(tmpl, seed=i)
        rng = random.Random(i + 1000)

        # Test individual transforms
        for transform in ALL_TRANSFORMS:
            aug = augment(doc, rng, transforms=frozenset({transform}))
            assert_offsets(aug)

        # Test all transforms combined
        aug_all = augment(doc, rng, transforms=None)
        assert_offsets(aug_all)


# ---------------------------------------------------------------------------
# UC-55 — strip_diacritics diacritic coverage and zero other changes
# ---------------------------------------------------------------------------


def test_uc55_strip_diacritics_alphabet_and_others() -> None:
    """UC-55: strip_diacritics replaces Polish diacritics, leaves others unchanged."""
    diac_text = (
        "ąęćłńóśźż ĄĘĆŁŃÓŚŹŻ abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789 !@#$%"
    )
    doc = Document(
        text=diac_text,
        template_id="test",
        doc_type="test",
        seed=0,
        spans=[
            SyntheticSpan(
                start=0,
                end=9,
                label=Label.OSOBA,
                source="synthetic",
                score=1.0,
                status="valid",
                text="ąęćłńóśźż",
            )
        ],
    )
    rng = random.Random(0)
    aug = augment(doc, rng, transforms=frozenset({"strip_diacritics"}))

    expected_text = (
        "aeclnoszz AECLNOSZZ abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789 !@#$%"
    )
    assert aug.text == expected_text
    assert_offsets(aug)


# ---------------------------------------------------------------------------
# UC-56 — ocr_confusions exclusivity (0<->O, 1<->l)
# ---------------------------------------------------------------------------


def test_uc56_ocr_confusions_exclusivity() -> None:
    """UC-56: ocr_confusions alters exclusively 0<->O and 1<->l and leaves other chars untouched."""
    base_text = "ABC 0123456789 OolL xyz XYZ !@#"
    doc = Document(
        text=base_text,
        template_id="test",
        doc_type="test",
        seed=0,
        spans=[
            SyntheticSpan(
                start=4,
                end=14,
                label=Label.PESEL,
                source="synthetic",
                score=1.0,
                status="valid",
                text="0123456789",
            )
        ],
    )
    rng = random.Random(42)
    aug = augment(doc, rng, transforms=frozenset({"ocr_confusions"}))
    assert_offsets(aug)

    # Check non-target characters are strictly identical
    for orig_c, aug_c in zip(base_text, aug.text):
        if orig_c not in {"0", "O", "1", "l"}:
            assert orig_c == aug_c


# ---------------------------------------------------------------------------
# UC-57 — space_digit_groups inside numeric spans only
# ---------------------------------------------------------------------------


def test_uc57_space_digit_groups_numeric_spans_only() -> None:
    """UC-57: digits split only inside numeric spans, text outside unchanged."""
    text = "PESEL 90051512345 and IBAN PL61109010140000071219812874 and text 123456."
    doc = Document(
        text=text,
        template_id="test",
        doc_type="test",
        seed=0,
        spans=[
            SyntheticSpan(
                start=6,
                end=17,
                label=Label.PESEL,
                source="synthetic",
                score=1.0,
                status="valid",
                text="90051512345",
            ),
            SyntheticSpan(
                start=27,
                end=53,
                label=Label.IBAN,
                source="synthetic",
                score=1.0,
                status="valid",
                text="PL61109010140000071219812874",
            ),
        ],
    )
    rng = random.Random(0)
    aug = augment(doc, rng, transforms=frozenset({"space_digit_groups"}))
    assert_offsets(aug)

    assert "900 515 123 45" in aug.text
    assert "and text 123456." in aug.text


# ---------------------------------------------------------------------------
# UC-58 — determinism and randomness
# ---------------------------------------------------------------------------


def test_uc58_determinism_and_stochasticity() -> None:
    """UC-58: same seed -> identical result; different seed -> different (stochastic)."""
    t = Template("t1", "test", f"PESEL {{PESEL}} and {'0O1l' * 8}")
    doc = render(t, seed=42)
    rng1 = random.Random(123)
    rng2 = random.Random(123)
    rng3 = random.Random(456)

    res1 = augment(doc, rng1, transforms=None)
    res2 = augment(doc, rng2, transforms=None)
    res3 = augment(doc, rng3, transforms=None)

    assert res1.text == res2.text
    assert res1.spans == res2.spans
    assert res1.text != res3.text


# ---------------------------------------------------------------------------
# UC-59 — empty transform set identity
# ---------------------------------------------------------------------------


def test_uc59_empty_transforms_identity() -> None:
    """UC-59: transforms=frozenset() returns a document identical to original."""
    doc = render(Template("t1", "test", "Klient {{OSOBA#1}}, PESEL {{PESEL}}."), seed=10)
    rng = random.Random(0)
    aug = augment(doc, rng, transforms=frozenset())

    assert aug.text == doc.text
    assert aug.template_id == doc.template_id
    assert aug.doc_type == doc.doc_type
    assert aug.seed == doc.seed
    assert aug.spans == doc.spans
    assert aug.inflection_fallbacks == doc.inflection_fallbacks
    assert_offsets(aug)
