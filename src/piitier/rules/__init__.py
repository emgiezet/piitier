"""Deterministic rule-based PII detectors.

Provides a registry of ``find(text) -> list[Span]`` functions.
``detect_all`` runs every registered detector and returns the combined,
start-sorted span list.  ``detect_all`` applies a narrow filter: any non-IBAN
span wholly contained within an IBAN span (valid or suspect) is suppressed
(UC-21 / integration fix).  This covers PESEL, REGON, NIP, and any future
detector whose tokens can appear inside an IBAN body.  Disjoint spans and
spans that are themselves IBAN are left untouched.
Full overlap resolution between non-contained spans belongs to ``fusion.py``.

Adding a new detector: import its module here and append its ``find``
function to ``_DETECTORS``.
"""

from __future__ import annotations

from piitier.labels import Label
from piitier.rules import iban, id_card, nip, payment_card, pesel, regon
from piitier.spans import Span

_DETECTORS = [pesel.find, nip.find, regon.find, iban.find, id_card.find, payment_card.find]


def detect_all(text: str) -> list[Span]:
    """Run all registered detectors and return their spans sorted by start offset."""
    spans: list[Span] = []
    for detector in _DETECTORS:
        spans.extend(detector(text))
    spans.sort(key=lambda s: s.start)
    # UC-21 / integration: remove any non-IBAN span that falls entirely inside
    # an IBAN span (valid or suspect).  Covers PESEL, REGON, NIP, and future
    # detectors whose tokens can overlap with IBAN digit bodies.
    # Disjoint spans and outer IBAN spans themselves are preserved unchanged.
    iban_spans = [s for s in spans if s.label is Label.IBAN]
    spans = [
        s
        for s in spans
        if not (
            s.label is not Label.IBAN
            and any(ib.start <= s.start and s.end <= ib.end for ib in iban_spans)
        )
    ]
    return spans
