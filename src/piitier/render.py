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

from piitier.spans import Span


def mask(text: str, spans: list[Span]) -> str:
    """Replace each span in *text* with its label's placeholder.

    Spans need not be pre-sorted; the function sorts them internally.
    Overlap resolution is not performed here — that belongs to ``fusion.py``.

    Args:
        text: The original input string (original-input offsets).
        spans: Zero or more non-overlapping spans.

    Returns:
        The text with each ``[span.start, span.end)`` range replaced by
        ``span.label.placeholder``.  Returns ``""`` for empty input.
    """
    result = text
    for span in sorted(spans, key=lambda s: s.start, reverse=True):
        result = result[: span.start] + span.label.placeholder + result[span.end :]
    return result
