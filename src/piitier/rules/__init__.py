"""Deterministic rule-based PII detectors.

Provides a registry of ``find(text) -> list[Span]`` functions.
``detect_all`` runs every registered detector and returns the combined,
start-sorted span list.  Overlap resolution belongs to ``fusion.py``.

Adding a new detector: import its module here and append its ``find``
function to ``_DETECTORS``.
"""

from __future__ import annotations

from piitier.rules import nip, pesel
from piitier.spans import Span

_DETECTORS = [pesel.find, nip.find]


def detect_all(text: str) -> list[Span]:
    """Run all registered detectors and return their spans sorted by start offset."""
    spans: list[Span] = []
    for detector in _DETECTORS:
        spans.extend(detector(text))
    spans.sort(key=lambda s: s.start)
    return spans
