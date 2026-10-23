"""Rules-based and custom NER model systems for piitier evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import piitier
from piitier.labels import Label
from piitier.spans import Span

if TYPE_CHECKING:
    pass

# NER-only types according to docs/TAXONOMY.md column Metoda
# (entities with method containing 'NER' without rule/wzorzec):
_RULES_UNMAPPED: frozenset[Label] = frozenset(
    {
        Label.OSOBA,
        Label.IMIE,
        Label.NAZWISKO,
        Label.DATA_URODZENIA,
        Label.WIEK,
        Label.PLEC,
        Label.ADRES,
        Label.MIEJSCOWOSC,
        Label.GEO,
        Label.KWOTA,
        Label.DOCHOD,
        Label.DANE_ZDROWOTNE,
        Label.ROZPOZNANIE,
        Label.LEK,
        Label.PLACOWKA,
        Label.LEKARZ,
    }
)


class RulesSystem:
    """Rule-based baseline system using deterministic piitier rules."""

    name: str = "rules"
    unmapped: frozenset[Label] = _RULES_UNMAPPED

    def __init__(self, **kwargs: object) -> None:
        pass

    def predict(self, text: str) -> list[Span]:
        """Detect PII spans using piitier rule detector."""
        return piitier.detect(text)


class NerSystem:
    """Custom trained NER model system."""

    name: str = "ner"
    unmapped: frozenset[Label] = frozenset()

    def __init__(
        self,
        checkpoint: str | Path,
        threshold: float = 0.0,
        device: str = "cpu",
        window: int = 512,
        stride: int = 256,
        **kwargs: object,
    ) -> None:
        from piitier.ner.inference import NerPredictor

        self._predictor = NerPredictor(
            checkpoint=checkpoint,
            threshold=threshold,
            device=device,
            window=window,
            stride=stride,
            **kwargs,
        )

    def predict(self, text: str) -> list[Span]:
        """Predict PII spans using NerPredictor."""
        return self._predictor.predict(text)
