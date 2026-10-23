"""Baseline systems registry and protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from eval.baselines.bardsai_v2 import BardsaiV2System
from eval.baselines.piitier_systems import NerSystem, RulesSystem
from eval.baselines.presidio_pl import PresidioSystem
from eval.baselines.privacy_filter import PrivacyFilterSystem
from piitier.labels import Label
from piitier.spans import Span


@runtime_checkable
class System(Protocol):
    """Protocol for comparison systems."""

    name: str
    unmapped: frozenset[Label]

    def predict(self, text: str) -> list[Span]:
        """Detect PII spans in text."""
        ...


_SYSTEM_FACTORIES: dict[str, Any] = {
    "rules": RulesSystem,
    "ner": NerSystem,
    "presidio": PresidioSystem,
    "bardsai-v2": BardsaiV2System,
    "privacy-filter": PrivacyFilterSystem,
}


def get_system(name: str, **kwargs: object) -> System:
    """Return system instance for given name with optional kwargs.

    Raises KeyError with available names if name is unknown.
    """
    if name not in _SYSTEM_FACTORIES:
        raise KeyError(
            f"Unknown system {name!r}. Available systems: {sorted(_SYSTEM_FACTORIES.keys())}"
        )
    system: System = _SYSTEM_FACTORIES[name](**kwargs)
    return system


__all__ = ["System", "get_system"]
