"""Tests for the Span dataclass (UC-5, UC-6)."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from piitier.labels import Label
from piitier.spans import Span

# A valid label for constructing Spans in tests.
_LABEL = Label.PESEL


def _make_span(
    start: int = 0,
    end: int = 5,
    label: Label = _LABEL,
    source: str = "rule:pesel",
    score: float = 1.0,
    status: str = "valid",
) -> Span:
    """Build a Span with sensible defaults for test brevity."""
    return Span(start=start, end=end, label=label, source=source, score=score, status=status)


# ---------------------------------------------------------------------------
# Happy-path / smoke
# ---------------------------------------------------------------------------


def test_span_happy_path_valid_status() -> None:
    """Span with start<end, non-negative offsets, valid status constructs without error."""
    span = _make_span(start=0, end=11, status="valid")
    assert span.start == 0
    assert span.end == 11
    assert span.label is _LABEL
    assert span.status == "valid"


def test_span_happy_path_suspect_status() -> None:
    """status='suspect' is also accepted."""
    span = _make_span(start=2, end=13, status="suspect")
    assert span.status == "suspect"


# ---------------------------------------------------------------------------
# UC-5 — offset validation (start, end)
# ---------------------------------------------------------------------------


def test_uc5_start_greater_than_end_raises() -> None:
    """UC-5: Span(start=5, end=3, …) raises ValueError."""
    with pytest.raises(ValueError):
        _make_span(start=5, end=3)


def test_uc5_negative_start_raises() -> None:
    """UC-5: Span(start=-1, end=2, …) raises ValueError."""
    with pytest.raises(ValueError):
        _make_span(start=-1, end=2)


def test_uc5_equal_offsets_raises() -> None:
    """UC-5: Span(start=3, end=3, …) raises ValueError (empty span not allowed)."""
    with pytest.raises(ValueError):
        _make_span(start=3, end=3)


def test_uc5_error_message_contains_offsets() -> None:
    """UC-5: ValueError message carries the start and end values."""
    with pytest.raises(ValueError, match=r"start") as exc_info:
        _make_span(start=5, end=3)
    msg = str(exc_info.value)
    assert "5" in msg
    assert "3" in msg


def test_UC_5_error_message_offsets_only_never_text() -> None:
    """UC-5 (added): ValueError message carries offsets only, never field text.

    Spec requirement: "the message carries offsets only, never text".
    Verifies that other field values (source, status, score, label name) do NOT
    appear in the offset-error message — only start/end integer values are present.
    """
    sentinel = "SENTINEL_PII_TEXT_XYZZY_42"
    with pytest.raises(ValueError) as exc_info:
        Span(
            start=5,
            end=3,
            label=_LABEL,
            source=sentinel,
            score=0.99,
            status="valid",
        )
    msg = str(exc_info.value)
    # Must contain the offset values
    assert "5" in msg
    assert "3" in msg
    # Must NOT contain any other field value — no text leaks into the error
    assert sentinel not in msg, f"source field value leaked into ValueError message: {msg!r}"
    assert "0.99" not in msg, f"score field value leaked into ValueError message: {msg!r}"
    assert "PESEL" not in msg, f"label name leaked into ValueError message: {msg!r}"


def test_uc5_negative_end_raises() -> None:
    """Negative end also violates start < end constraint."""
    with pytest.raises(ValueError):
        _make_span(start=0, end=-1)


# ---------------------------------------------------------------------------
# UC-6 — status validation
# ---------------------------------------------------------------------------


def test_uc6_invalid_status_uppercase_raises() -> None:
    """UC-6: status other than 'valid' or 'suspect' raises ValueError."""
    with pytest.raises(ValueError):
        _make_span(status="VALID")


def test_uc6_empty_status_raises() -> None:
    """UC-6: empty string status raises ValueError."""
    with pytest.raises(ValueError):
        _make_span(status="")


def test_uc6_unknown_status_raises() -> None:
    """UC-6: arbitrary string status raises ValueError."""
    with pytest.raises(ValueError):
        _make_span(status="uncertain")


# ---------------------------------------------------------------------------
# Density — branch coverage for both valid statuses accepted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["valid", "suspect"])
def test_span_both_valid_statuses_accepted(status: str) -> None:
    """Both 'valid' and 'suspect' are accepted without error."""
    span = _make_span(status=status)
    assert span.status == status


# ---------------------------------------------------------------------------
# Property-based — any (start, end) where start >= end or start < 0 must raise
# ---------------------------------------------------------------------------


@given(
    start=st.integers(min_value=0, max_value=100),
    end=st.integers(min_value=0, max_value=100),
)
def test_span_invalid_offsets_always_raise(start: int, end: int) -> None:
    """For any start >= end, ValueError is raised; for start < end it must not."""
    if start >= end:
        with pytest.raises(ValueError):
            _make_span(start=start, end=end)
    else:
        span = _make_span(start=start, end=end)
        assert span.start == start
        assert span.end == end


@given(start=st.integers(max_value=-1), end=st.integers(min_value=0))
def test_span_negative_start_always_raises(start: int, end: int) -> None:
    """Any negative start raises ValueError regardless of end."""
    with pytest.raises(ValueError):
        _make_span(start=start, end=end)


# ---------------------------------------------------------------------------
# Span field storage and label coverage
# ---------------------------------------------------------------------------


def test_span_all_labels_constructible() -> None:
    """Every Label member can be used to construct a valid Span."""
    for lbl in Label:
        span = Span(start=0, end=1, label=lbl, source="test", score=0.9, status="valid")
        assert span.label is lbl


def test_span_score_stored() -> None:
    """score field is stored verbatim."""
    span = _make_span(score=0.75)
    assert span.score == pytest.approx(0.75)


def test_span_source_stored() -> None:
    """source field is stored verbatim."""
    span = _make_span(source="model:ner")
    assert span.source == "model:ner"


# ---------------------------------------------------------------------------
# Equality and hashing (frozen dataclass)
# ---------------------------------------------------------------------------


def test_span_equality() -> None:
    """Two Spans with identical fields compare equal."""
    a = _make_span(start=0, end=5)
    b = _make_span(start=0, end=5)
    assert a == b


def test_span_inequality_different_start() -> None:
    """Spans differing in start are not equal."""
    a = _make_span(start=0, end=5)
    b = _make_span(start=1, end=5)
    assert a != b


def test_span_hashable() -> None:
    """Frozen dataclass must be hashable (can be stored in a set)."""
    s1 = _make_span(start=0, end=5)
    s2 = _make_span(start=1, end=6)
    assert len({s1, s2}) == 2
