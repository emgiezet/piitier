"""piitier — Polish PII anonymiser for regulated sectors."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from piitier import rules as _rules
from piitier.fusion import fuse as _fuse
from piitier.render import mask as _render_mask
from piitier.spans import Span

__version__ = "0.1.0"

__all__ = ["Anonymizer", "Span", "__version__", "detect", "mask"]


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
        An object with a ``predict(text: str) -> list[Span]`` method.  Use
        this in tests or when you already hold a loaded :class:`NerPredictor`.
        Mutually exclusive with *model*.
    threshold:
        Minimum inclusive score for NER spans.  Spans with ``score < threshold``
        are dropped during fusion.  Rule spans are never filtered.
    device:
        Torch device string (``"cpu"``, ``"cuda"``, …).  Ignored when
        *predictor* is given.
    """

    def __init__(
        self,
        model: str | Path | None = None,
        *,
        predictor: Any = None,
        threshold: float = 0.0,
        device: str = "cpu",
    ) -> None:
        # Validate BEFORE any heavy import so that ValueError is raised without
        # pulling in transformers or torch (UC-110).
        if model is not None and predictor is not None:
            raise ValueError("Provide exactly one of 'model' or 'predictor', not both.")
        if model is None and predictor is None:
            raise ValueError("Provide exactly one of 'model' (checkpoint path) or 'predictor'.")

        self.threshold: float = threshold

        if predictor is not None:
            self._predictor: Any = predictor
        else:
            # Deferred heavy import: transformers and torch are loaded here.
            from piitier.ner import NerPredictor

            # Pass threshold=0.0 so that NerPredictor returns all spans;
            # fusion applies the threshold in fuse().
            assert model is not None  # guaranteed by the ValueError checks above
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
