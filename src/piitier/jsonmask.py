"""Mask decoded JSON string values through spans in the original serialization."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import replace

from piitier.fusion import fuse
from piitier.render import mask as render_mask
from piitier.spans import Span

_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')
_KEY_END = re.compile(r"[ \t\r\n]*:")


def _reject_constant(value: str) -> None:
    raise ValueError("invalid JSON")


def validate_json(text: str) -> None:
    """Validate one JSON document without echoing parser input or converting numbers."""
    try:
        json.loads(
            text.removeprefix("\ufeff"),
            parse_int=lambda value: None,
            parse_float=lambda value: None,
            parse_constant=_reject_constant,
        )
    except (ValueError, RecursionError):
        raise ValueError("invalid JSON") from None


def _source_boundaries(token: str, start: int) -> list[int]:
    """Map decoded character boundaries to source offsets, including surrogate pairs."""
    index = 1  # opening quote
    boundaries = [start + index]
    while index < len(token) - 1:
        width = 1
        if token[index] == "\\":
            width = 2
            if token[index + 1] == "u":
                width = 6
                if (
                    0xD800 <= int(token[index + 2 : index + 6], 16) <= 0xDBFF
                    and token[index + 6 : index + 8] == "\\u"
                    and 0xDC00 <= int(token[index + 8 : index + 12], 16) <= 0xDFFF
                ):
                    width = 12
        index += width
        boundaries.append(start + index)
    return boundaries


def detect_json(
    text: str,
    *,
    detector: Callable[[str], list[Span]],
    numbering_fn: Callable[[str, list[Span]], dict[tuple[int, int], int]] | None = None,
) -> tuple[list[Span], dict[tuple[int, int], int] | None]:
    """Detect each value independently and assign numbering across decoded document values.

    Returned spans and numbering keys index the original serialized JSON. Keys and
    non-string values never reach the detector. Existing rendering and comparison
    can therefore replace these spans without reserializing the document.
    """
    validate_json(text)
    source_spans: list[Span] = []
    decoded_spans: list[Span] = []
    values: list[str] = []
    offset = 0
    for match in _STRING.finditer(text):
        if _KEY_END.match(text, match.end()):
            continue
        token = match.group()
        value = json.loads(token)
        # Rules-only detection can overlap; the renderer requires disjoint ranges.
        spans = fuse(detector(value), []) if value else []
        if spans:
            boundaries = _source_boundaries(token, match.start())
            for span in spans:
                source_spans.append(
                    replace(span, start=boundaries[span.start], end=boundaries[span.end])
                )
                if numbering_fn is not None:
                    decoded_spans.append(
                        replace(span, start=offset + span.start, end=offset + span.end)
                    )
        if numbering_fn is not None:
            values.append(value)
            offset += len(value) + 1  # newline between values for document-level numbering

    if numbering_fn is None:
        return source_spans, None
    numbering = numbering_fn("\n".join(values), decoded_spans)
    source_numbering = {
        (source.start, source.end): numbering[(decoded.start, decoded.end)]
        for source, decoded in zip(source_spans, decoded_spans, strict=True)
        if (decoded.start, decoded.end) in numbering
    }
    return source_spans, source_numbering


def mask_json(
    text: str,
    *,
    detector: Callable[[str], list[Span]],
    numbering_fn: Callable[[str, list[Span]], dict[tuple[int, int], int]] | None = None,
) -> str:
    """Replace only detected value content, preserving every other source character."""
    spans, numbering = detect_json(text, detector=detector, numbering_fn=numbering_fn)
    return render_mask(text, spans, numbering)
