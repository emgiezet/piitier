"""Integration tests for baseline systems requiring external

libraries or model downloads (UC-86, UC-87).
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import pytest

from piitier.labels import Label

# Dynamically load eval/baselines modules
_root = Path(__file__).resolve().parents[2]
_baselines_dir = _root / "eval" / "baselines"

for mod_name in ["__init__", "piitier_systems", "presidio_pl", "bardsai_v2", "privacy_filter"]:
    if mod_name == "__init__":
        full_name = "eval.baselines"
        path = _baselines_dir / "__init__.py"
    else:
        full_name = f"eval.baselines.{mod_name}"
        path = _baselines_dir / f"{mod_name}.py"

    spec = importlib.util.spec_from_file_location(full_name, path)
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = mod
        spec.loader.exec_module(mod)

_presidio_mod = sys.modules["eval.baselines.presidio_pl"]
_bardsai_mod = sys.modules["eval.baselines.bardsai_v2"]

PresidioSystem = _presidio_mod.PresidioSystem
BardsaiV2System = _bardsai_mod.BardsaiV2System
BARDSAI_LABEL_MAP = _bardsai_mod.BARDSAI_LABEL_MAP


@pytest.mark.integration
def test_uc86_presidio_system_integration() -> None:
    """UC-86: PresidioSystem predict on Polish document containing PESEL, IBAN, email."""
    system = PresidioSystem()
    text = (
        "Jan Kowalski mieszka w Warszawie. "
        "Jego PESEL to 44051401359, konto bankowe IBAN: PL61109010140000071219812874, "
        "a email kontaktowy: jan.kowalski@example.com."
    )
    spans = system.predict(text)
    assert len(spans) >= 3

    for span in spans:
        assert isinstance(span.label, Label)
        assert span.start >= 0
        assert span.end <= len(text)
        assert span.start < span.end
        assert span.status == "valid"
        assert span.source == "baseline:presidio"


@pytest.mark.integration
def test_uc87_bardsai_v2_system_integration() -> None:
    """UC-87: BardsaiV2System predict on Polish sentence with model download (~1.2GB)."""
    start_time = time.time()
    system = BardsaiV2System()
    text = "Nazywam się Jan Kowalski, mój numer PESEL to 44051401359."
    spans = system.predict(text)
    elapsed = time.time() - start_time
    print(f"\n[UC-87] BardsaiV2System wall time: {elapsed:.2f}s")

    assert isinstance(spans, list)
    for span in spans:
        assert isinstance(span.label, Label)
        assert span.label in BARDSAI_LABEL_MAP.values()
        assert span.start >= 0
        assert span.end <= len(text)
        assert span.start < span.end
        assert span.source == "baseline:bardsai-v2"
