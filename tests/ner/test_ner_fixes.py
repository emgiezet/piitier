from __future__ import annotations

from piitier.labels import Label
from piitier.ner.inference import merge_windows
from piitier.spans import Span


def test_uc70_merge_windows_touching_vs_overlapping() -> None:
    """UC-70 / Finding 7: touching same-label spans remain two spans, overlapping ones merge."""
    # Touching spans: end of first (5) == start of second (5)
    touching = [
        Span(0, 5, Label.OSOBA, "pred", 0.9, "valid"),
        Span(5, 10, Label.OSOBA, "pred", 0.9, "valid"),
    ]
    merged_touching = merge_windows(touching)
    assert len(merged_touching) == 2

    # Overlapping spans: end of first (6) > start of second (5)
    overlapping = [
        Span(0, 6, Label.OSOBA, "pred", 0.9, "valid"),
        Span(5, 10, Label.OSOBA, "pred", 0.9, "valid"),
    ]
    merged_overlapping = merge_windows(overlapping)
    assert len(merged_overlapping) == 1
    assert merged_overlapping[0].start == 0
    assert merged_overlapping[0].end == 10
    assert merged_overlapping[0].label is Label.OSOBA
