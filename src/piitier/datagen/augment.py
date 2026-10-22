"""OCR/diacritic augmentation with exact offset recomputation (PII-3-c)."""

from __future__ import annotations

import random
import re

from piitier.datagen.render import Document, SyntheticSpan
from piitier.labels import Label

ALL_TRANSFORMS: tuple[str, ...] = (
    "ocr_confusions",
    "space_digit_groups",
    "strip_diacritics",
    "uppercase",
)

_DIACRITICS_MAP = str.maketrans(
    {
        "ą": "a",
        "Ą": "A",
        "ć": "c",
        "Ć": "C",
        "ę": "e",
        "Ę": "E",
        "ł": "l",
        "Ł": "L",
        "ń": "n",
        "Ń": "N",
        "ó": "o",
        "Ó": "O",
        "ś": "s",
        "Ś": "S",
        "ź": "z",
        "Ź": "Z",
        "ż": "z",
        "Ż": "Z",
    }
)

_NUMERIC_LABELS: frozenset[Label] = frozenset(
    {
        Label.PESEL,
        Label.NIP,
        Label.REGON,
        Label.IBAN,
        Label.NR_DOWODU,
        Label.NR_KARTY,
        Label.TELEFON,
        Label.NPWZ,
    }
)


def _apply_ocr_confusions(
    text: str, spans: list[SyntheticSpan], rng: random.Random
) -> tuple[str, list[SyntheticSpan]]:
    chars = []
    for c in text:
        if c in "0O1l":
            if rng.random() < 0.3:
                if c == "0":
                    chars.append("O")
                elif c == "O":
                    chars.append("0")
                elif c == "1":
                    chars.append("l")
                elif c == "l":
                    chars.append("1")
            else:
                chars.append(c)
        else:
            chars.append(c)
    new_text = "".join(chars)
    new_spans = [
        SyntheticSpan(
            start=s.start,
            end=s.end,
            label=s.label,
            source=s.source,
            score=s.score,
            status=s.status,
            entity=s.entity,
            text=new_text[s.start : s.end],
        )
        for s in spans
    ]
    return new_text, new_spans


def _space_digits(s: str) -> str:
    def repl(m: re.Match[str]) -> str:
        digits = m.group(0)
        groups = [digits[i : i + 3] for i in range(0, len(digits), 3)]
        return " ".join(groups)

    return re.sub(r"\d+", repl, s)


def _apply_space_digit_groups(
    text: str, spans: list[SyntheticSpan]
) -> tuple[str, list[SyntheticSpan]]:
    new_parts = []
    new_spans = []
    current_offset = 0
    last_end = 0

    for span in spans:
        gap = text[last_end : span.start]
        new_parts.append(gap)
        current_offset += len(gap)

        new_start = current_offset
        orig_span_text = text[span.start : span.end]

        if span.label in _NUMERIC_LABELS:
            new_span_text = _space_digits(orig_span_text)
        else:
            new_span_text = orig_span_text

        new_parts.append(new_span_text)
        current_offset += len(new_span_text)
        new_end = current_offset

        new_spans.append(
            SyntheticSpan(
                start=new_start,
                end=new_end,
                label=span.label,
                source=span.source,
                score=span.score,
                status=span.status,
                entity=span.entity,
                text=new_span_text,
            )
        )
        last_end = span.end

    tail = text[last_end:]
    new_parts.append(tail)
    new_text = "".join(new_parts)
    return new_text, new_spans


def _apply_strip_diacritics(
    text: str, spans: list[SyntheticSpan]
) -> tuple[str, list[SyntheticSpan]]:
    new_text = text.translate(_DIACRITICS_MAP)
    new_spans = [
        SyntheticSpan(
            start=s.start,
            end=s.end,
            label=s.label,
            source=s.source,
            score=s.score,
            status=s.status,
            entity=s.entity,
            text=new_text[s.start : s.end],
        )
        for s in spans
    ]
    return new_text, new_spans


def _apply_uppercase(text: str, spans: list[SyntheticSpan]) -> tuple[str, list[SyntheticSpan]]:
    # Precondition: str.upper() preserves string length (1:1 mapping in Python unicode).
    new_text = text.upper()
    assert len(new_text) == len(text)
    new_spans = [
        SyntheticSpan(
            start=s.start,
            end=s.end,
            label=s.label,
            source=s.source,
            score=s.score,
            status=s.status,
            entity=s.entity,
            text=new_text[s.start : s.end],
        )
        for s in spans
    ]
    return new_text, new_spans


def augment(
    doc: Document,
    rng: random.Random,
    transforms: frozenset[str] | None = None,
) -> Document:
    """Augment a document with OCR confusions, digit spacing, stripping, uppercase."""
    valid_transforms = set(ALL_TRANSFORMS)
    if transforms is None:
        active = list(ALL_TRANSFORMS)
    else:
        unknown = transforms - valid_transforms
        if unknown:
            raise ValueError(f"Unknown transform(s): {sorted(unknown)}")
        active = [t for t in ALL_TRANSFORMS if t in transforms]

    text = doc.text
    spans = sorted(doc.spans, key=lambda s: s.start)

    for t in active:
        if t == "ocr_confusions":
            text, spans = _apply_ocr_confusions(text, spans, rng)
        elif t == "space_digit_groups":
            text, spans = _apply_space_digit_groups(text, spans)
        elif t == "strip_diacritics":
            text, spans = _apply_strip_diacritics(text, spans)
        elif t == "uppercase":
            text, spans = _apply_uppercase(text, spans)

    return Document(
        text=text,
        template_id=doc.template_id,
        doc_type=doc.doc_type,
        seed=doc.seed,
        spans=spans,
        inflection_fallbacks=doc.inflection_fallbacks,
    )
