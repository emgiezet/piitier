"""Span type for PII detection results."""

from dataclasses import dataclass

from piitier.labels import Label


@dataclass(frozen=True)
class Span:
    """
    A detected PII span with [start, end) half-open offsets into the original input.

    Attributes:
        start: Inclusive start offset (must be >= 0).
        end: Exclusive end offset (must be > start).
        label: PII entity label.
        source: Where the detection came from (e.g., "rule:pesel", "model:ner").
        score: Confidence score [0, 1].
        status: "valid" (passed checksum) or "suspect" (failed checksum, borderline).
    """

    start: int
    end: int
    label: Label
    source: str
    score: float
    status: str

    def __post_init__(self) -> None:
        """Validate span offsets and status."""
        if self.start < 0 or self.end <= self.start:
            raise ValueError(f"Invalid span offsets: start={self.start}, end={self.end}")
        if self.status not in ("valid", "suspect"):
            raise ValueError(f"Invalid status: {self.status}")
