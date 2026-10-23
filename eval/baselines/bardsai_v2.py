"""Bardsai v2 NER model baseline system."""

from __future__ import annotations

from typing import TYPE_CHECKING

from piitier.labels import Label
from piitier.spans import Span

if TYPE_CHECKING:
    from piitier.ner.inference import NerPredictor

BARDSAI_LABEL_MAP: dict[str, Label] = {
    "PERSON_NAME": Label.OSOBA,
    "DATE_OF_BIRTH": Label.DATA_URODZENIA,
    "BANK_ACCOUNT_IDENTIFIER": Label.IBAN,
    "PAYMENT_CARD": Label.NR_KARTY,
    "PAYMENT_CARD_SECURITY": Label.CVV,
    "PHONE_NUMBER": Label.TELEFON,
    "EMAIL_ADDRESS": Label.EMAIL,
    "IP_ADDRESS": Label.IP,
    "LOCATION": Label.MIEJSCOWOSC,
    "POSTAL_ADDRESS": Label.ADRES,
    "HEALTH_DATA": Label.DANE_ZDROWOTNE,
    "VEHICLE_IDENTIFIER": Label.VIN,
    "FINANCIAL_AMOUNT": Label.KWOTA,
    "ORGANIZATION_NAME": Label.PLACOWKA,
    "DOCUMENT_REFERENCE": Label.NR_DOKUMENTACJI,
}


class BardsaiV2System:
    """Bardsai v2 NER baseline system."""

    name: str = "bardsai-v2"

    def __init__(self, threshold: float = 0.0, device: str = "cpu", **kwargs: object) -> None:
        self.threshold = threshold
        self.device = device
        self._predictor: NerPredictor | None = None

    @property
    def unmapped(self) -> frozenset[Label]:
        return frozenset(lbl for lbl in Label if lbl not in BARDSAI_LABEL_MAP.values())

    def _init_predictor(self) -> None:
        if self._predictor is not None:
            return

        from piitier.ner.inference import NerPredictor

        class _BardsaiPredictor(NerPredictor):
            def __init__(self, checkpoint: str, threshold: float, device: str) -> None:
                super().__init__(checkpoint=checkpoint, threshold=threshold, device=device)
                remapped: dict[int, str] = {}
                for k, tag in self.id2label.items():
                    if tag == "O":
                        remapped[int(k)] = "O"
                    elif tag.startswith("B-"):
                        raw = tag.removeprefix("B-")
                        lbl = BARDSAI_LABEL_MAP.get(raw)
                        remapped[int(k)] = f"B-{lbl.name}" if lbl else "O"
                    elif tag.startswith("I-"):
                        raw = tag.removeprefix("I-")
                        lbl = BARDSAI_LABEL_MAP.get(raw)
                        remapped[int(k)] = f"I-{lbl.name}" if lbl else "O"
                    else:
                        remapped[int(k)] = "O"
                self.id2label = remapped

            def predict(self, text: str) -> list[Span]:
                spans: list[Span] = super().predict(text)
                return [
                    Span(
                        start=s.start,
                        end=s.end,
                        label=s.label,
                        source="baseline:bardsai-v2",
                        score=s.score,
                        status=s.status,
                    )
                    for s in spans
                ]

        self._predictor = _BardsaiPredictor(
            checkpoint="bardsai/eu-pii-anonimization-multilang-v2",
            threshold=self.threshold,
            device=self.device,
        )

    def predict(self, text: str) -> list[Span]:
        """Predict PII spans using Bardsai v2 model."""
        if not text:
            return []
        self._init_predictor()
        predictor = self._predictor
        assert predictor is not None
        return predictor.predict(text)
