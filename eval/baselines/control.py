"""Control baselines: none (zero spans) and mask-all (every non-whitespace run).

These are sanity-check control systems used to bound metric ranges and verify
that the evaluation pipeline distinguishes systems.  Neither imports torch or
transformers.
"""

from __future__ import annotations

import re

from piitier.labels import Label
from piitier.spans import Span


class NoneSystem:
    """Control baseline that predicts no spans (lower-bound on precision/recall)."""

    name: str = "none"
    unmapped: frozenset[Label] = frozenset()

    def __init__(self, **kwargs: object) -> None:
        pass

    def predict(self, text: str) -> list[Span]:
        """Return empty span list — nothing is detected."""
        return []


class MaskAllSystem:
    """Control baseline that emits one OSOBA span per maximal non-whitespace run.

    This is an upper-bound sanity system: it masks everything, so value leak
    rate should be 0 and precision very low.  Source is ``baseline:mask-all``.
    """

    name: str = "mask-all"
    unmapped: frozenset[Label] = frozenset()

    def __init__(self, **kwargs: object) -> None:
        pass

    def predict(self, text: str) -> list[Span]:
        """Return one OSOBA span for every maximal non-whitespace run in text."""
        return [
            Span(
                start=m.start(),
                end=m.end(),
                label=Label.OSOBA,
                source="baseline:mask-all",
                score=1.0,
                status="valid",
            )
            for m in re.finditer(r"\S+", text)
        ]
