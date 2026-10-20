"""Span type representing a single detected PII entity in original-input offsets.

The half-open interval ``[start, end)`` indexes characters of the original input
string before any normalisation.  Immutable: construct a new ``Span`` to represent
a change.
"""

from __future__ import annotations

from dataclasses import dataclass

from piitier.labels import Label

_VALID_STATUSES: frozenset[str] = frozenset({"valid", "suspect"})


@dataclass(frozen=True)
class Span:
    """A detected PII span in original-input character offsets.

    Fields
    ------
    start:
        Inclusive start offset (≥ 0).
    end:
        Exclusive end offset (> start).
    label:
        PII entity type.
    source:
        Origin of the detection, e.g. ``"rule:pesel"`` or ``"model:ner"``.
        Never contains document text.
    score:
        Confidence in [0, 1] (1.0 = certain for rule-based detectors).
    status:
        ``"valid"`` — passed checksum / pattern validation;
        ``"suspect"`` — structurally plausible but failed checksum (still masked).
    """

    start: int
    end: int
    label: Label
    source: str
    score: float
    status: str

    def __post_init__(self) -> None:
        """Validate offsets and status; raise ``ValueError`` on violation."""
        if self.start < 0 or self.end <= self.start:
            raise ValueError(
                f"span offsets must satisfy 0 <= start < end; "
                f"got start={self.start}, end={self.end}"
            )
        if self.status not in _VALID_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(_VALID_STATUSES)!r}; got {self.status!r}"
            )
