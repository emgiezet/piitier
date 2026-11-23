"""piitier — Polish PII anonymiser for regulated sectors."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

from piitier import rules as _rules
from piitier.coref import Coreferencer as _Coreferencer
from piitier.csvskip import filter_spans, parse_csv_field_ranges, plan_skips, sniff_delimiter
from piitier.fusion import fuse as _fuse
from piitier.render import mask as _render_mask
from piitier.spans import Span

__version__ = "0.1.1"

__all__ = ["Anonymizer", "Span", "__version__", "detect", "mask", "mask_csv"]


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


def mask_csv(
    text: str,
    skip_columns: list[str] | None = None,
    *,
    delimiter: str | None = None,
    detector: Callable[[str], list[Span]] | None = None,
    on_unknown_column: Callable[[str], None] | None = None,
) -> str:
    """Mask CSV text while leaving fully contained detections in selected cells untouched."""
    find = detector if detector is not None else detect
    if not skip_columns:
        return _render_mask(text, find(text))
    delim = delimiter if delimiter is not None else sniff_delimiter(text)
    if len(delim) != 1:
        raise ValueError("delimiter must be a 1-character string")
    plan = plan_skips(parse_csv_field_ranges(text, delim), skip_columns)
    if on_unknown_column is not None:
        for selector in plan.unknown_selectors:
            on_unknown_column(selector)
    return _render_mask(text, filter_spans(find(text), plan.protected_ranges))


class Anonymizer:
    """Rule + NER span fusion anonymiser.

    Loads a token-classification checkpoint once (in the constructor) and
    combines its predictions with deterministic rule detectors via
    :func:`piitier.fusion.fuse`.

    Parameters
    ----------
    model:
        Local checkpoint directory path **or** a Hugging Face Hub repo id of
        the form ``"owner/name"``.  Resolved via
        :func:`piitier.ner.hub.resolve_checkpoint`; a local directory always
        wins over an id with the same string value.  Mutually exclusive with
        *predictor*; providing both or neither raises ``ValueError`` **before**
        any heavy import (transformers / torch are never touched if the
        constructor raises).
    revision:
        Branch, tag, or commit hash passed to
        ``huggingface_hub.snapshot_download`` when *model* is a Hub repo id.
        Ignored for local paths.
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
        revision: str | None = None,
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
            # Resolve to a local directory (local path or Hub download).
            # resolve_checkpoint raises ValueError for missing/invalid models
            # so that torch/transformers are never imported on error (UC-110).
            assert model is not None  # guaranteed by the checks above
            from piitier.ner.hub import resolve_checkpoint

            model_path = resolve_checkpoint(model, revision)

            # Deferred heavy import: transformers and torch are loaded here.
            from piitier.ner import NerPredictor

            # Pass threshold=0.0 so NerPredictor returns all spans;
            # fusion applies the threshold inside fuse().
            self._predictor = NerPredictor(checkpoint=model_path, threshold=0.0, device=device)

        # One Coreferencer (one Morfeusz instance) per Anonymizer (PII-6-b).
        self._coref = _Coreferencer()

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

    def assign(self, text: str, spans: list[Span]) -> dict[tuple[int, int], int]:
        """Return the entity-index mapping for *spans* produced by coreference.

        Only numbered-label spans appear in the result.

        Args:
            text: The original input string (needed to read span tokens).
            spans: Non-overlapping spans (e.g. from :meth:`detect`).

        Returns:
            Mapping from ``(start, end)`` to entity index (1-based, per label).
        """
        return self._coref.assign(text, spans)

    def render(self, text: str, spans: list[Span]) -> str:
        """Return *text* with numbered placeholders, applying coreference numbering.

        Args:
            text: The original input string.
            spans: Non-overlapping spans (e.g. from :meth:`detect`).

        Returns:
            The anonymised string with numbered placeholders (``[OSOBA_1]`` etc.).
        """
        numbering = self._coref.assign(text, spans)
        return _render_mask(text, spans, numbering)

    def mask(self, text: str) -> str:
        """Return *text* with every fused PII span replaced by its placeholder.

        Numbered labels receive a coreference-assigned index suffix
        (``[OSOBA_1]``, ``[ADRES_2]``, …).

        Args:
            text: Input text to anonymise.

        Returns:
            The anonymised string.  Characters outside detected spans are
            unchanged.
        """
        spans = self.detect(text)
        numbering = self._coref.assign(text, spans)
        return _render_mask(text, spans, numbering)
