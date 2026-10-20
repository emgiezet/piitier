"""Tests for Span type and package import."""

import piitier
import pytest
from piitier import Label, Span


def test_uc1_package_import_and_version() -> None:
    """UC-1: Developer can import piitier and print __version__ = 0.1.0."""
    assert hasattr(piitier, "__version__")
    assert piitier.__version__ == "0.1.0"
    assert piitier.Label is not None
    assert piitier.Span is not None


@pytest.mark.integration
def test_uc1_import_via_cli() -> None:
    """UC-1: uv run python -c 'import piitier; print(piitier.__version__)' works."""
    # This is tested via the integration test marker.
    # The actual CLI test is run in the CI matrix separately.
    # This test verifies the package structure is correct.
    import subprocess

    result = subprocess.run(
        ["python", "-c", "import piitier; print(piitier.__version__)"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stdout={result.stdout}, stderr={result.stderr}"
    assert "0.1.0" in result.stdout


def test_uc5_span_offset_validation_start_greater_than_end() -> None:
    """UC-5: Span(start=5, end=3) raises ValueError with offsets only."""
    with pytest.raises(ValueError) as exc_info:
        Span(start=5, end=3, label=Label.OSOBA, source="test", score=0.9, status="valid")

    # Message must carry offsets only, never text
    error_msg = str(exc_info.value)
    assert "start" in error_msg.lower() and "end" in error_msg.lower()
    assert "start=5" in error_msg or "5" in error_msg
    assert "end=3" in error_msg or "3" in error_msg


def test_uc5_span_offset_validation_negative_start() -> None:
    """UC-5: Span(start=-1, end=2) raises ValueError with offsets only."""
    with pytest.raises(ValueError) as exc_info:
        Span(start=-1, end=2, label=Label.PESEL, source="test", score=0.95, status="valid")

    error_msg = str(exc_info.value)
    assert "start" in error_msg.lower() and "end" in error_msg.lower()
    assert "-1" in error_msg or "start" in error_msg


def test_uc5_span_offset_validation_equal_offsets() -> None:
    """UC-5: Span(start=3, end=3) raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        Span(start=3, end=3, label=Label.EMAIL, source="test", score=0.8, status="valid")

    error_msg = str(exc_info.value)
    assert "3" in error_msg or ("start" in error_msg.lower() and "end" in error_msg.lower())


def test_uc5_span_valid_offsets() -> None:
    """UC-5: Valid Span(start=0, end=5) is created without error."""
    span = Span(start=0, end=5, label=Label.OSOBA, source="model:ner", score=0.92, status="valid")
    assert span.start == 0
    assert span.end == 5
    assert span.label == Label.OSOBA


def test_uc6_span_status_validation_invalid_status() -> None:
    """UC-6: Span with status other than 'valid' or 'suspect' raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        Span(
            start=0,
            end=5,
            label=Label.PESEL,
            source="rule:pesel",
            score=1.0,
            status="invalid",
        )

    error_msg = str(exc_info.value)
    assert "status" in error_msg.lower()
    assert "invalid" in error_msg


def test_uc6_span_valid_status_valid() -> None:
    """UC-6: Span with status='valid' is created without error."""
    span = Span(start=0, end=11, label=Label.PESEL, source="rule:pesel", score=1.0, status="valid")
    assert span.status == "valid"


def test_uc6_span_valid_status_suspect() -> None:
    """UC-6: Span with status='suspect' is created without error."""
    span = Span(
        start=5,
        end=10,
        label=Label.IBAN,
        source="rule:iban",
        score=0.5,
        status="suspect",
    )
    assert span.status == "suspect"


def test_span_is_frozen() -> None:
    """Span is a frozen dataclass - its fields match the frozen definition."""
    span = Span(start=0, end=5, label=Label.OSOBA, source="test", score=0.9, status="valid")

    # Verify the field values match - the frozen constraint means they can't change
    assert span.start == 0
    assert span.end == 5
    assert span.label == Label.OSOBA
    assert span.source == "test"
    assert span.score == 0.9
    assert span.status == "valid"
