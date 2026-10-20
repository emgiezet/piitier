"""piitier — Polish PII anonymiser for regulated sectors."""

from __future__ import annotations

from piitier import rules as _rules
from piitier.render import mask as _render_mask
from piitier.spans import Span

__version__ = "0.1.0"

__all__ = ["Span", "__version__", "detect", "mask"]


def detect(text: str) -> list[Span]:
    """Return every PII span detected in *text*, sorted by start offset.

    Args:
        text: Arbitrary Polish (or mixed) text to scan.

    Returns:
        Spans sorted by ``start``, non-overlapping within each detector's output.
    """
    return _rules.detect_all(text)


def mask(text: str) -> str:
    """Return *text* with every detected PII span replaced by its placeholder.

    Args:
        text: Arbitrary Polish (or mixed) text to anonymise.

    Returns:
        The anonymised string.  Characters outside detected spans are unchanged.
        Returns ``""`` for empty input.
    """
    return _render_mask(text, detect(text))
