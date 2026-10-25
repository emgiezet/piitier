"""Tests for NER inference module (UC-67..UC-71, UC-95..UC-97)."""

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


def test_uc95_spans_to_token_labels_leading_space_gets_b() -> None:
    """UC-95: token with leading whitespace that overlaps a span gets B-, not O.

    Reproduces the BPE-tokenizer bug where a token like ' FAB' at offset (926, 930)
    for a span starting at 927 was incorrectly labeled O because tok_start < span.start.
    """
    tag_names = bio_tag_names()
    tag_to_id = {n: i for i, n in enumerate(tag_names)}
    o_id = tag_to_id[BIO_O]
    b_adres = tag_to_id["B-ADRES"]
    i_adres = tag_to_id["I-ADRES"]

    # Fake text: "ULICA FABRYCZNA" where span covers "FABRYCZNA" starting at 6.
    # BPE tokenizer produces token ' FAB' with offset (5, 8) — includes the space at 5.
    text = "ULICA FABRYCZNA"
    span = Span(start=6, end=15, label=Label.ADRES, source="test", score=1.0, status="valid")
    offset_mapping: list[tuple[int, int]] = [
        (0, 0),  # [CLS] special
        (0, 5),  # 'ULICA'
        (5, 8),  # ' FAB'  ← leading-space token covering span start
        (8, 12),  # 'RYCZNA' (split for illustration)
        (12, 15),  # 'NA' (adjusted)
        (0, 0),  # [SEP] special
    ]
    # Correct the fake offsets so the spans actually tile the text:
    offset_mapping = [
        (0, 0),
        (0, 5),
        (5, 9),  # ' FAB' covers positions 5-8 inclusive (space + 'FAB')
        (9, 12),  # 'RYC'
        (12, 15),  # 'ZNA'
        (0, 0),
    ]
    labels = spans_to_token_labels([span], offset_mapping, text=text)

    assert labels[1] == o_id, "token before span → O"
    assert labels[2] == b_adres, "leading-space token overlapping span start → B-ADRES"
    assert labels[3] == i_adres, "next content token → I-ADRES"
    assert labels[4] == i_adres, "last content token → I-ADRES"
    assert labels[0] == o_id, "special token → O (not yet -100 at this stage)"
    assert labels[5] == o_id, "special token → O"


def test_uc96_spans_to_token_labels_whitespace_only_token_inside_span_is_ignore() -> None:
    """UC-96: a purely-whitespace token inside a span receives IGNORE (-100), not O or I-.

    This prevents the model from being taught O mid-entity, which would otherwise cause
    decode_spans to split "717 253,28" into two separate KWOTA spans.
    """
    tag_names = bio_tag_names()
    tag_to_id = {n: i for i, n in enumerate(tag_names)}
    o_id = tag_to_id[BIO_O]
    b_adres = tag_to_id["B-ADRES"]
    i_adres = tag_to_id["I-ADRES"]
    IGNORE = -100

    # "SOKOLA\tO8" — the tab between them is a separate whitespace-only token.
    text = "SOKOLA\tO8"
    span = Span(start=0, end=9, label=Label.ADRES, source="test", score=1.0, status="valid")
    offset_mapping: list[tuple[int, int]] = [
        (0, 0),  # [CLS]
        (0, 6),  # 'SOKOLA'
        (6, 7),  # '\t'   ← whitespace-only token strictly inside span
        (7, 9),  # 'O8'
        (0, 0),  # [SEP]
    ]
    labels = spans_to_token_labels([span], offset_mapping, text=text)

    assert labels[1] == b_adres, "'SOKOLA' → B-ADRES"
    assert labels[2] == IGNORE, "whitespace-only token inside span → IGNORE (-100)"
    assert labels[3] == i_adres, "'O8' → I-ADRES"

    # A whitespace-only token that is NOT inside any span must stay O.
    span_partial = Span(start=0, end=6, label=Label.ADRES, source="test", score=1.0, status="valid")
    labels_partial = spans_to_token_labels([span_partial], offset_mapping, text=text)
    assert labels_partial[2] == o_id, "whitespace-only token outside span → O"


def test_uc97_decode_spans_leading_space_stripped_and_orphan_i_as_b() -> None:
    """UC-97: decode_spans strips leading whitespace from B- offsets and treats orphan I- as B-.

    Round-trip: text[span.start:span.end] == gold entity text for a hand-built fixture
    that simulates what the model predicts when trained on the buggy labels (B- on the
    second token with no leading space) and the corrected labels (B- on the first token
    with leading space).
    """
    text = "Email: JANINA75@EXAMPLE.NET koniec"
    # gold: "JANINA75@EXAMPLE.NET" at [7, 27)
    gold_entity = "JANINA75@EXAMPLE.NET"
    assert text[7:27] == gold_entity

    tag_names = bio_tag_names()
    tag_to_id = {n: i for i, n in enumerate(tag_names)}
    id2label = {i: n for i, n in enumerate(tag_names)}
    b_email = tag_to_id["B-EMAIL"]
    i_email = tag_to_id["I-EMAIL"]
    o_id = tag_to_id[BIO_O]

    def _make_probs(tag_id: int) -> list[float]:
        p = [0.0] * len(tag_names)
        p[tag_id] = 0.99
        return p

    # Scenario A: model correctly predicts B- on the leading-space token ' JAN' at (6, 10).
    # After the fix the span start should be stripped to 7 (past the space).
    offset_mapping_a: list[tuple[int, int]] = [
        (0, 6),  # 'Email:'
        (6, 10),  # ' JAN'  ← leading space, B-EMAIL predicted
        (10, 12),  # 'IN'
        (12, 14),  # 'A7'
        (14, 15),  # '5'
        (15, 16),  # '@'
        (16, 23),  # 'EXAMPLE'
        (23, 24),  # '.'
        (24, 27),  # 'NET'
        (27, 28),  # ' '
        (28, 34),  # 'koniec'
    ]
    probs_a = (
        [_make_probs(o_id)]  # 'Email:'
        + [_make_probs(b_email)]  # ' JAN' → B-EMAIL
        + [_make_probs(i_email)] * 7  # 'IN'..'NET' → I-EMAIL
        + [_make_probs(o_id)]  # ' '
        + [_make_probs(o_id)]  # 'koniec'
    )
    spans_a = decode_spans(text, offset_mapping_a, probs_a, id2label, threshold=0.0)
    assert len(spans_a) == 1, f"expected 1 span, got {spans_a}"
    assert text[spans_a[0].start : spans_a[0].end] == gold_entity, (
        f"span text {text[spans_a[0].start : spans_a[0].end]!r} != {gold_entity!r}"
    )

    # Scenario B: model (trained on buggy labels) predicts O for ' JAN' then I- for 'IN'.
    # The orphan I- should be treated as a new B-, recovering a near-correct span.
    probs_b = (
        [_make_probs(o_id)]  # 'Email:'
        + [_make_probs(o_id)]  # ' JAN' → O  (buggy model behaviour)
        + [_make_probs(i_email)]  # 'IN'   → orphan I-EMAIL, treated as B-
        + [_make_probs(i_email)] * 6  # remaining → I-EMAIL
        + [_make_probs(o_id)]  # ' '
        + [_make_probs(o_id)]  # 'koniec'
    )
    spans_b = decode_spans(text, offset_mapping_a, probs_b, id2label, threshold=0.0)
    assert len(spans_b) == 1, f"expected 1 span, got {spans_b}"
    # Span starts at 'IN' (10), missing 'JAN' — partial match, but not empty.
    assert spans_b[0].start == 10
    assert text[spans_b[0].start : spans_b[0].end] == "INA75@EXAMPLE.NET"


def test_uc99_decode_spans_internal_whitespace_does_not_split_entity() -> None:
    """UC-99: decode_spans skips whitespace-only tokens so "717 253,28" stays one KWOTA span.

    Reproduces the pii-5-v2 regression where the model predicted O for the space token
    inside "717 253,28" (trained on IGNORE labels), which flushed the entity mid-span.
    """
    # text: "Kwota: 717 253,28 PLN"  — KWOTA spans "717 253,28" at [7, 17)
    text = "Kwota: 717 253,28 PLN"
    gold_entity = "717 253,28"
    assert text[7:17] == gold_entity

    tag_names = bio_tag_names()
    tag_to_id = {n: i for i, n in enumerate(tag_names)}
    id2label = {i: n for i, n in enumerate(tag_names)}
    b_kwota = tag_to_id["B-KWOTA"]
    i_kwota = tag_to_id["I-KWOTA"]
    o_id = tag_to_id[BIO_O]

    def _p(tag_id: int) -> list[float]:
        p = [0.0] * len(tag_names)
        p[tag_id] = 0.99
        return p

    # Fake BPE offsets for "Kwota: 717 253,28 PLN":
    # The tokenizer emits a standalone space token between '717' and '253'.
    offset_mapping: list[tuple[int, int]] = [
        (0, 7),  # 'Kwota: '   — O
        (7, 10),  # '717'       — B-KWOTA
        (10, 11),  # ' '         — whitespace-only: model predicts O (IGNORE in training)
        (11, 14),  # '253'       — I-KWOTA
        (14, 15),  # ','         — I-KWOTA
        (15, 17),  # '28'        — I-KWOTA
        (17, 21),  # ' PLN'      — O
    ]
    # Model trained on IGNORE for the space; predicts O for it (untrained logit wins).
    probs = [
        _p(o_id),  # 'Kwota: '
        _p(b_kwota),  # '717'
        _p(o_id),  # ' ' — O predicted (but should not flush)
        _p(i_kwota),  # '253'
        _p(i_kwota),  # ','
        _p(i_kwota),  # '28'
        _p(o_id),  # ' PLN'
    ]
    spans = decode_spans(text, offset_mapping, probs, id2label, threshold=0.0)
    assert len(spans) == 1, f"expected 1 span for '717 253,28', got {spans}"
    assert text[spans[0].start : spans[0].end] == gold_entity, (
        f"span text {text[spans[0].start : spans[0].end]!r} != {gold_entity!r}"
    )
    assert spans[0].label == Label.KWOTA


def test_uc100_decode_spans_o_content_token_between_entities_keeps_two_spans() -> None:
    """UC-100: an O-predicted *content* token between two entities produces two spans.

    Ensures that skipping whitespace-only tokens does not accidentally merge entities
    that are genuinely separated by a non-whitespace O token.
    """
    text = "PESEL: 44051401359, NIP: 526-10-81-912"
    tag_names = bio_tag_names()
    tag_to_id = {n: i for i, n in enumerate(tag_names)}
    id2label = {i: n for i, n in enumerate(tag_names)}
    b_pesel = tag_to_id["B-PESEL"]
    b_nip = tag_to_id["B-NIP"]
    o_id = tag_to_id[BIO_O]

    def _p(tag_id: int) -> list[float]:
        p = [0.0] * len(tag_names)
        p[tag_id] = 0.99
        return p

    # "," is a content token predicted O → must split the two entities.
    offset_mapping: list[tuple[int, int]] = [
        (0, 7),  # 'PESEL: '
        (7, 18),  # '44051401359'  — B-PESEL
        (18, 20),  # ', '           — content O (comma+space), acts as separator
        (20, 24),  # 'NIP:'         — O
        (24, 38),  # ' 526-10-81-912' — B-NIP (leading space stripped)
    ]
    probs = [
        _p(o_id),  # 'PESEL: '
        _p(b_pesel),  # '44051401359'
        _p(o_id),  # ', '   ← content O: should flush PESEL
        _p(o_id),  # 'NIP:'
        _p(b_nip),  # ' 526-10-81-912'
    ]
    spans = decode_spans(text, offset_mapping, probs, id2label, threshold=0.0)
    assert len(spans) == 2, f"expected 2 spans, got {spans}"
    pesel_span = next(s for s in spans if s.label == Label.PESEL)
    nip_span = next(s for s in spans if s.label == Label.NIP)
    assert text[pesel_span.start : pesel_span.end] == "44051401359"
    # Leading space stripped from NIP span start.
    assert text[nip_span.start : nip_span.end] == "526-10-81-912"
