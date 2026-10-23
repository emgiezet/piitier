"""Tests for NER inference module (UC-67..UC-71)."""

from __future__ import annotations

import pytest

from piitier.labels import Label
from piitier.ner import (
    BIO_O,
    NerPredictor,
    bio_tag_names,
    decode_spans,
    merge_windows,
    spans_to_token_labels,
)
from piitier.spans import Span


def test_uc67_bio_tag_names() -> None:
    """UC-67: bio_tag_names() returns 79 names starting with 'O' and B-/I- for each Label."""
    names = bio_tag_names()
    expected_len = 1 + len(Label) * 2
    assert len(names) == expected_len
    assert names[0] == BIO_O

    idx = 1
    for lbl in Label:
        assert names[idx] == f"B-{lbl.name}"
        assert names[idx + 1] == f"I-{lbl.name}"
        idx += 2


def test_uc68_decode_spans() -> None:
    """UC-68: decode_spans decodes token probability distributions into Spans correctly."""
    text = "Jan Kowalski, PESEL 44051401359."
    tag_names = bio_tag_names()
    tag_to_id = {name: i for i, name in enumerate(tag_names)}
    id2label = {i: name for name, i in tag_to_id.items()}

    o_id = tag_to_id[BIO_O]
    b_osoba_id = tag_to_id["B-OSOBA"]
    i_osoba_id = tag_to_id["I-OSOBA"]
    b_pesel_id = tag_to_id["B-PESEL"]

    offset_mapping = [
        (0, 3),  # Jan (B-OSOBA)
        (4, 12),  # Kowalski (I-OSOBA)
        (12, 13),  # , (O)
        (14, 19),  # PESEL (O)
        (20, 31),  # 44051401359 (B-PESEL)
        (31, 32),  # . (O)
    ]

    probs = []
    for i, (start, end) in enumerate(offset_mapping):
        p = [0.0] * len(tag_names)
        if i == 0:
            p[b_osoba_id] = 0.95
        elif i == 1:
            p[i_osoba_id] = 0.90
        elif i == 4:
            p[b_pesel_id] = 0.99
        else:
            p[o_id] = 0.99
        probs.append(p)

    spans = decode_spans(text, offset_mapping, probs, id2label, threshold=0.0)
    assert len(spans) == 2

    assert spans[0].start == 0
    assert spans[0].end == 12
    assert spans[0].label == Label.OSOBA
    assert spans[0].source == "model:ner"
    assert spans[0].status == "valid"
    assert 0 < spans[0].score <= 1.0

    assert spans[1].start == 20
    assert spans[1].end == 31
    assert spans[1].label == Label.PESEL
    assert spans[1].source == "model:ner"
    assert spans[1].status == "valid"
    assert 0 < spans[1].score <= 1.0

    empty_probs = [
        [1.0 if idx == o_id else 0.0 for idx in range(len(tag_names))] for _ in offset_mapping
    ]
    empty_spans = decode_spans(text, offset_mapping, empty_probs, id2label, threshold=0.0)
    assert empty_spans == []


def test_uc69_threshold() -> None:
    """UC-69: threshold filters out spans below threshold and keeps spans at or above."""
    text = "Jan Kowalski"
    tag_names = bio_tag_names()
    tag_to_id = {name: i for i, name in enumerate(tag_names)}
    id2label = {i: name for name, i in tag_to_id.items()}
    o_id = tag_to_id[BIO_O]
    b_osoba_id = tag_to_id["B-OSOBA"]

    offset_mapping = [(0, 3)]

    # Below threshold (score 0.4 < threshold 0.6)
    p_low = [0.0] * len(tag_names)
    p_low[b_osoba_id] = 0.4
    p_low[o_id] = 0.1
    spans_high = decode_spans(text, offset_mapping, [p_low], id2label, threshold=0.6)
    assert spans_high == []

    # At boundary (score 0.5 == threshold 0.5)
    p_eq = [0.0] * len(tag_names)
    p_eq[b_osoba_id] = 0.5
    p_eq[o_id] = 0.1
    spans_equal = decode_spans(text, offset_mapping, [p_eq], id2label, threshold=0.5)
    assert len(spans_equal) == 1
    assert spans_equal[0].score == 0.5


def test_uc70_merge_windows() -> None:
    """UC-70: merge_windows merges overlapping same-label spans and resolves

    different-label overlaps by score.
    """
    span1 = Span(start=0, end=10, label=Label.OSOBA, source="model:ner", score=0.8, status="valid")
    span2 = Span(start=5, end=15, label=Label.OSOBA, source="model:ner", score=0.9, status="valid")
    merged = merge_windows([span1, span2])
    assert len(merged) == 1
    assert merged[0].start == 0
    assert merged[0].end == 15
    assert merged[0].label == Label.OSOBA
    assert merged[0].score == 0.9

    span_pesel = Span(
        start=10, end=21, label=Label.PESEL, source="model:ner", score=0.95, status="valid"
    )
    span_osoba2 = Span(
        start=8, end=15, label=Label.OSOBA, source="model:ner", score=0.70, status="valid"
    )
    resolved = merge_windows([span_pesel, span_osoba2])
    assert len(resolved) == 1
    assert resolved[0].label == Label.PESEL
    assert resolved[0].score == 0.95


@pytest.mark.integration
def test_uc71_predictor_integration() -> None:
    """UC-71: NerPredictor integration test with tiny random model."""
    predictor = NerPredictor(
        checkpoint="hf-internal-testing/tiny-random-BertForTokenClassification",
        threshold=0.0,
        device="cpu",
        window=512,
        stride=256,
    )
    text = "Jan Kowalski mieszka w Warszawie, PESEL 44051401359."
    spans = predictor.predict(text)
    bio_tag_names()
    for span in spans:
        assert 0 <= span.start < span.end <= len(text)
        assert isinstance(span.label, Label)
        assert span.source == "model:ner"
        assert span.status == "valid"
        assert 0.0 <= span.score <= 1.0

    if spans:
        offset_mapping = [(s.start, s.end) for s in spans]
        token_labels = spans_to_token_labels(spans, offset_mapping)
        assert len(token_labels) == len(offset_mapping)
