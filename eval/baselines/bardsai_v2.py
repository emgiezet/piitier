"""Bardsai eu-pii-anonimization-multilang-v2 NER model baseline system.

Pinned revision: 5e61416e77675881185767fc0c67759d48b35592
Model type: modernbert, max_position_embeddings=8192.
Polish documents top out at ~1400 tokens so a single forward pass covers them.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from piitier.labels import Label
from piitier.spans import Span

if TYPE_CHECKING:
    from piitier.ner.inference import NerPredictor

# ---------------------------------------------------------------------------
# Revision pin and local-cache resolution
# ---------------------------------------------------------------------------

_REVISION: str = "5e61416e77675881185767fc0c67759d48b35592"
_MODEL_ID: str = "bardsai/eu-pii-anonimization-multilang-v2"
_LOCAL_SNAPSHOT: Path = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / "models--bardsai--eu-pii-anonimization-multilang-v2"
    / "snapshots"
    / _REVISION
)


def _checkpoint() -> str:
    """Return local snapshot path when cached, else fall back to HF model id.

    The local snapshot is guaranteed to match the pinned revision.  If it is
    absent the caller will attempt a network download; the revision is not
    passed here because ``NerPredictor`` does not expose that parameter — in
    that case pin it with ``huggingface-cli download bardsai/eu-pii-anonimization-multilang-v2
    --revision 5e61416e77675881185767fc0c67759d48b35592`` before evaluation.
    """
    if _LOCAL_SNAPSHOT.is_dir():
        return str(_LOCAL_SNAPSHOT)
    return _MODEL_ID


# ---------------------------------------------------------------------------
# Label mapping — every tag in the model's id2label is accounted for
# ---------------------------------------------------------------------------
# Tags NOT listed here are silently suppressed (mapped to "O") and their
# predictions count as false negatives in our taxonomy.  Unmapped bardsai
# classes:
#   AUTH_SECRET, BIOMETRIC_DATA, CONTACT_HANDLE, CRIMINAL_OFFENCE_DATA,
#   DEVICE_IDENTIFIER, ETHNIC_ORIGIN, IDENTIFYING_LINK, PERSON_ALIAS,
#   PERSON_ATTRIBUTE, PERSON_ROLE_OR_TITLE, POLITICAL_OPINION,
#   PROPER_NAME, RELIGION_OR_BELIEF, SEXUAL_ORIENTATION, TRADE_UNION_MEMBERSHIP
# ---------------------------------------------------------------------------

BARDSAI_LABEL_MAP: dict[str, Label] = {
    # Identification
    "PERSON_NAME": Label.OSOBA,
    "PERSON_IDENTIFIER": Label.PESEL,  # national person ID (PESEL in PL)
    "DATE_OF_BIRTH": Label.DATA_URODZENIA,
    # Finance
    "BANK_ACCOUNT_IDENTIFIER": Label.IBAN,
    "ACCOUNT_IDENTIFIER": Label.NR_RACHUNKU,  # generic account number
    "PAYMENT_CARD": Label.NR_KARTY,
    "PAYMENT_CARD_SECURITY": Label.CVV,
    "FINANCIAL_AMOUNT": Label.KWOTA,
    # Contact & location
    "PHONE_NUMBER": Label.TELEFON,
    "EMAIL_ADDRESS": Label.EMAIL,
    "IP_ADDRESS": Label.IP,
    "GEO_LOCATION": Label.GEO,
    "LOCATION": Label.MIEJSCOWOSC,
    "POSTAL_ADDRESS": Label.ADRES,
    # Documents
    "DOCUMENT_IDENTIFIER": Label.NR_DOWODU,  # identity document number
    "DOCUMENT_REFERENCE": Label.NR_DOKUMENTACJI,  # medical/case reference
    # Health
    "HEALTH_DATA": Label.DANE_ZDROWOTNE,
    # Vehicles
    "VEHICLE_IDENTIFIER": Label.VIN,
    # Organisations
    "ORGANIZATION_NAME": Label.PLACOWKA,
    "ORGANIZATION_IDENTIFIER": Label.NIP,  # NIP / REGON (primary PL org ID)
}

# Derived: labels from BARDSAI_LABEL_MAP values (mapped set)
_MAPPED_LABELS: frozenset[Label] = frozenset(BARDSAI_LABEL_MAP.values())


class BardsaiV2System:
    """Bardsai eu-pii-anonimization-multilang-v2 baseline.

    Uses sliding-window inference via ``NerPredictor``.  Window is set to 8 192
    tokens (the model's full context) so Polish documents (~1 400 tokens) are
    processed in a single forward pass without any tail truncation.
    """

    name: str = "bardsai-v2"

    def __init__(self, threshold: float = 0.0, device: str = "cpu", **kwargs: object) -> None:
        self.threshold = threshold
        self.device = device
        self._predictor: NerPredictor | None = None

    @property
    def unmapped(self) -> frozenset[Label]:
        """Labels in our taxonomy that bardsai does NOT predict."""
        return frozenset(Label) - _MAPPED_LABELS

    def _init_predictor(self) -> None:
        if self._predictor is not None:
            return

        from piitier.ner.inference import NerPredictor

        class _BardsaiPredictor(NerPredictor):
            """NerPredictor subclass that remaps bardsai BIO tags to our Label names."""

            def __init__(self, threshold: float, device: str) -> None:
                super().__init__(
                    checkpoint=_checkpoint(),
                    threshold=threshold,
                    device=device,
                    # 8 192 covers the whole model context; stride unused for short docs
                    window=8192,
                    stride=4096,
                )
                # Remap id2label in-place so decode_spans emits our Label names
                remapped: dict[int, str] = {}
                for k, tag in self.id2label.items():
                    if tag == "O":
                        remapped[k] = "O"
                    elif tag.startswith("B-"):
                        raw = tag.removeprefix("B-")
                        lbl = BARDSAI_LABEL_MAP.get(raw)
                        remapped[k] = f"B-{lbl.name}" if lbl else "O"
                    elif tag.startswith("I-"):
                        raw = tag.removeprefix("I-")
                        lbl = BARDSAI_LABEL_MAP.get(raw)
                        remapped[k] = f"I-{lbl.name}" if lbl else "O"
                    else:
                        remapped[k] = "O"
                self.id2label = remapped

            def predict(self, text: str) -> list[Span]:
                return [
                    Span(
                        start=s.start,
                        end=s.end,
                        label=s.label,
                        source="baseline:bardsai-v2",
                        score=s.score,
                        status=s.status,
                    )
                    for s in super().predict(text)
                ]

        self._predictor = _BardsaiPredictor(
            threshold=self.threshold,
            device=self.device,
        )

    def predict(self, text: str) -> list[Span]:
        """Predict PII spans using Bardsai v2 model."""
        if not text:
            return []
        self._init_predictor()
        assert self._predictor is not None
        return self._predictor.predict(text)
