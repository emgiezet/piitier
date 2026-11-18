"""Placeholder renderer.

``mask(text, spans)`` rebuilds the input string, replacing each detected span
with its label's placeholder.  Replacements are applied right-to-left so that
lower offsets remain correct after each substitution (CLAUDE.md invariant 4).

Fidelity guarantee
------------------
Every character at a position that is *not* inside any span is byte-identical
in the returned string.  The property test in ``tests/test_render.py`` pins
this at zero changed characters outside spans.
"""

from __future__ import annotations

from collections.abc import Mapping
from itertools import pairwise

from piitier.fusion import fuse
from piitier.spans import Span


def _resolve_placeholder(label_placeholder: str, index: int) -> str:
    """Replace the ``_n`` suffix in *label_placeholder* with *index*."""
    return label_placeholder.replace("_n", f"_{index}")


def mask(
    text: str,
    spans: list[Span],
    numbering: Mapping[tuple[int, int], int] | None = None,
) -> str:
    """Replace each span in *text* with its label's placeholder.

    Spans need not be pre-sorted or disjoint. Overlapping inputs are resolved
    by ``fusion.fuse`` using its existing precedence and coverage rules.

    Args:
        text: The original input string (original-input offsets).
        spans: Zero or more spans in original-input offsets.
        numbering: Optional mapping from ``(start, end)`` to entity index.
            When provided and a span's label is numbered, the ``_n`` suffix in
            the placeholder is replaced with the assigned index.
            Spans absent from *numbering* fall back to the template placeholder.
            After overlap resolution, each fragment uses its own exact range
            key; an original span's index is not inherited by new fragments.

    Returns:
        The text with each ``[span.start, span.end)`` range replaced by the
        resolved placeholder.  Returns ``""`` for empty input.
    """
    ordered = sorted(spans, key=lambda span: span.start)
    if any(left.end > right.start for left, right in pairwise(ordered)):
        ordered = fuse(ordered, [])
    result = text
    for span in reversed(ordered):
        if numbering is not None and span.label.numbered:
            idx = numbering.get((span.start, span.end))
            ph = (
                _resolve_placeholder(span.label.placeholder, idx)
                if idx is not None
                else span.label.placeholder
            )
        else:
            ph = span.label.placeholder
        result = result[: span.start] + ph + result[span.end :]
    return result
