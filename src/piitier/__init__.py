"""piitier — Polish PII anonymiser for regulated sectors."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Protocol, runtime_checkable

from piitier import rules as _rules
from piitier.fusion import fuse as _fuse
from piitier.render import mask as _render_mask
from piitier.spans import Span

__version__ = "0.1.0"

__all__ = ["Anonymizer", "Span", "__version__", "detect", "mask"]


@runtime_checkable
class _PredictorProtocol(Protocol):
    """Minimal duck-type contract for a NER predictor."""

    def predict(self, text: str) -> list[Span]:
        """Return predicted spans for *text*."""
        ...


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


class Anonymizer:
    """Rule + NER span fusion anonymiser.

    Loads a token-classification checkpoint once (in the constructor) and
    combines its predictions with deterministic rule detectors via
    :func:`piitier.fusion.fuse`.

    Parameters
    ----------
    model:
        Path to a local HuggingFace checkpoint directory.  Mutually exclusive
        with *predictor*; providing both or neither raises ``ValueError``
        **before** any heavy import (transformers / torch are never touched if
        the constructor raises).
    predictor:
        An object satisfying the ``predict(text: str) -> list[Span]`` protocol.
        Use this in tests or when you already hold a loaded predictor.
        Mutually exclusive with *model*.
    threshold:
        Minimum inclusive score for NER spans in ``[0, 1]``.  Spans with
        ``score < threshold`` are dropped during fusion.  Rule spans are never
        filtered.  Raises ``ValueError`` for NaN or values outside ``[0, 1]``.
    device:
        Torch device string (``"cpu"``, ``"cuda"``, …).  Ignored when
        *predictor* is given.
    """

    def __init__(
        self,
        model: str | Path | None = None,
        *,
        predictor: _PredictorProtocol | None = None,
        threshold: float = 0.0,
        device: str = "cpu",
    ) -> None:
        # ------------------------------------------------------------------ #
        # All validation before any heavy import (UC-110).                    #
        # ------------------------------------------------------------------ #
        if model is not None and predictor is not None:
            raise ValueError("Provide exactly one of 'model' or 'predictor', not both.")
        if model is None and predictor is None:
            raise ValueError("Provide exactly one of 'model' (checkpoint path) or 'predictor'.")

        # Validate threshold before touching the filesystem or loading weights.
        if math.isnan(threshold) or not (0.0 <= threshold <= 1.0):
            raise ValueError(f"threshold must be a finite value in [0, 1]; got {threshold!r}")

        self.threshold: float = threshold

        if predictor is not None:
            self._predictor: _PredictorProtocol = predictor
        else:
            # Check model path before importing heavy deps so that a missing
            # checkpoint raises ValueError rather than triggering an HF Hub
            # lookup (finding 5 / UC-110).
            assert model is not None  # guaranteed by the checks above
            model_path = Path(model)
            if not model_path.exists():
                raise ValueError(f"model checkpoint not found: {model_path}")

            # Deferred heavy import: transformers and torch are loaded here.
            from piitier.ner import NerPredictor

            # Pass threshold=0.0 so NerPredictor returns all spans;
            # fusion applies the threshold inside fuse().
            self._predictor = NerPredictor(checkpoint=model, threshold=0.0, device=device)

    def detect(self, text: str) -> list[Span]:
        """Return fused PII spans for *text* (rules + NER).

        Args:
            text: Input text to scan.

        Returns:
            Non-overlapping list of :class:`~piitier.spans.Span` objects
            sorted by ``start``.
        """
        rule_spans = _rules.detect_all(text)
        ner_spans: list[Span] = self._predictor.predict(text)
        return _fuse(rule_spans, ner_spans, threshold=self.threshold)

    def mask(self, text: str) -> str:
        """Return *text* with every fused PII span replaced by its placeholder.

        Args:
            text: Input text to anonymise.

        Returns:
            The anonymised string.  Characters outside detected spans are
            unchanged.
        """
        return _render_mask(text, self.detect(text))
