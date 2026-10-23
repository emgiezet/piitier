"""NER inference module."""

from __future__ import annotations

from piitier.ner.inference import (
    BIO_O,
    NerPredictor,
    bio_tag_names,
    decode_spans,
    merge_windows,
    spans_to_token_labels,
)

__all__ = [
    "BIO_O",
    "NerPredictor",
    "bio_tag_names",
    "decode_spans",
    "merge_windows",
    "spans_to_token_labels",
]
