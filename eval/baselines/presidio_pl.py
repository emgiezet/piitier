"""Presidio analyzer baseline system configured for Polish PII detection without spaCy."""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING

from piitier.labels import Label
from piitier.spans import Span

if TYPE_CHECKING:
    from presidio_analyzer import AnalyzerEngine

PRESIDIO_LABEL_MAP: dict[str, Label] = {
    "EMAIL_ADDRESS": Label.EMAIL,
    "PHONE_NUMBER": Label.TELEFON,
    "IBAN_CODE": Label.IBAN,
    "CREDIT_CARD": Label.NR_KARTY,
    "IP_ADDRESS": Label.IP,
    "PERSON": Label.OSOBA,
    "LOCATION": Label.MIEJSCOWOSC,
    "DATE_TIME": Label.DATA_URODZENIA,
    "PL_PESEL": Label.PESEL,
    "PL_NIP": Label.NIP,
    "PL_REGON": Label.REGON,
}


class PresidioSystem:
    """Presidio analyzer baseline system (regex/non-NLP only)."""

    name: str = "presidio"

    def __init__(self, **kwargs: object) -> None:
        if importlib.util.find_spec("presidio_analyzer") is None:
            raise ImportError(
                "presidio-analyzer is required for PresidioSystem. Run `uv sync` to install."
            )
        self._analyzer: AnalyzerEngine | None = None

    @property
    def unmapped(self) -> frozenset[Label]:
        return frozenset(lbl for lbl in Label if lbl not in PRESIDIO_LABEL_MAP.values())

    def _init_analyzer(self) -> None:
        if self._analyzer is not None:
            return

        from presidio_analyzer import (
            AnalyzerEngine,
            Pattern,
            PatternRecognizer,
            RecognizerRegistry,
        )
        from presidio_analyzer.nlp_engine import NoOpNlpEngine
        from presidio_analyzer.predefined_recognizers import (
            CreditCardRecognizer,
            EmailRecognizer,
            IbanRecognizer,
            IpRecognizer,
            PhoneRecognizer,
        )

        # Re-use regexes from piitier.rules (sources: piitier.rules.pesel, nip, regon)
        from piitier.rules.nip import _NIP_KEYWORD_RE, _NIP_RE
        from piitier.rules.pesel import _PESEL_RE
        from piitier.rules.regon import _REGON_9_KEYWORD_RE, _REGON_14_RE

        registry = RecognizerRegistry(supported_languages=["pl"])

        predefined = [
            EmailRecognizer(),
            PhoneRecognizer(),
            CreditCardRecognizer(),
            IbanRecognizer(),
            IpRecognizer(),
        ]
        for r in predefined:
            r.supported_language = "pl"
            registry.add_recognizer(r)

        pesel_recognizer = PatternRecognizer(
            supported_entity="PL_PESEL",
            supported_language="pl",
            patterns=[Pattern(name="pesel_pattern", regex=_PESEL_RE.pattern, score=1.0)],
        )
        nip_recognizer = PatternRecognizer(
            supported_entity="PL_NIP",
            supported_language="pl",
            patterns=[
                Pattern(name="nip_pattern", regex=_NIP_RE.pattern, score=1.0),
                Pattern(
                    name="nip_keyword_pattern",
                    regex=_NIP_KEYWORD_RE.pattern,
                    score=1.0,
                ),
            ],
        )
        regon_recognizer = PatternRecognizer(
            supported_entity="PL_REGON",
            supported_language="pl",
            patterns=[
                Pattern(
                    name="regon_14_pattern",
                    regex=_REGON_14_RE.pattern,
                    score=1.0,
                ),
                Pattern(
                    name="regon_9_keyword_pattern",
                    regex=_REGON_9_KEYWORD_RE.pattern,
                    score=1.0,
                ),
            ],
        )

        registry.add_recognizer(pesel_recognizer)
        registry.add_recognizer(nip_recognizer)
        registry.add_recognizer(regon_recognizer)

        nlp_engine = NoOpNlpEngine(models=[{"lang_code": "pl", "model_name": "none"}])
        self._analyzer = AnalyzerEngine(
            registry=registry, nlp_engine=nlp_engine, supported_languages=["pl"]
        )

    def predict(self, text: str) -> list[Span]:
        """Detect PII spans using Presidio analyzer."""
        if not text:
            return []
        self._init_analyzer()
        analyzer = self._analyzer
        assert analyzer is not None

        results = analyzer.analyze(text=text, language="pl")
        spans: list[Span] = []
        for res in results:
            label = PRESIDIO_LABEL_MAP.get(res.entity_type)
            if label is not None:
                try:
                    spans.append(
                        Span(
                            start=res.start,
                            end=res.end,
                            label=label,
                            source="baseline:presidio",
                            score=float(res.score),
                            status="valid",
                        )
                    )
                except ValueError:
                    pass

        spans.sort(key=lambda s: (s.start, s.end))
        return spans
