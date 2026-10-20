"""Deterministic rule-based PII detectors.

Provides a registry of ``find(text) -> list[Span]`` functions.
``detect_all`` runs every registered detector and returns the combined,
start-sorted span list.  Overlap resolution belongs to ``fusion.py``.

Adding a new detector: import its module here and append its ``find``
function to ``_DETECTORS``.
"""

from __future__ import annotations

from piitier.labels import Label
from piitier.rules import iban, pesel
from piitier.spans import Span

_DETECTORS = [pesel.find, iban.find]


def detect_all(text: str) -> list[Span]:
    """Run all registered detectors and return their spans sorted by start offset."""
    spans: list[Span] = []
    for detector in _DETECTORS:
        spans.extend(detector(text))
    spans.sort(key=lambda s: s.start)
    # UC-21: remove any PESEL span that falls entirely inside an IBAN span.
    # Applies equally to valid and suspect IBAN candidates; no general fusion needed.
    iban_spans = [s for s in spans if s.label is Label.IBAN]
    spans = [
        s
        for s in spans
        if not (
            s.label is Label.PESEL
            and any(ib.start <= s.start and s.end <= ib.end for ib in iban_spans)
        )
    ]
    return spans
