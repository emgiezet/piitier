"""Unit tests for baseline systems and decoders (UC-85, UC-88)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

import piitier
from piitier.labels import Label

# Dynamically load eval/baselines modules to mirror test_metrics.py pattern
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

_baselines_mod = sys.modules["eval.baselines"]
_piitier_sys_mod = sys.modules["eval.baselines.piitier_systems"]
_presidio_mod = sys.modules["eval.baselines.presidio_pl"]
_bardsai_mod = sys.modules["eval.baselines.bardsai_v2"]
_privacy_mod = sys.modules["eval.baselines.privacy_filter"]

get_system = _baselines_mod.get_system
RulesSystem = _piitier_sys_mod.RulesSystem
PresidioSystem = _presidio_mod.PresidioSystem
BardsaiV2System = _bardsai_mod.BardsaiV2System
PrivacyFilterSystem = _privacy_mod.PrivacyFilterSystem
PRESIDIO_LABEL_MAP = _presidio_mod.PRESIDIO_LABEL_MAP
BARDSAI_LABEL_MAP = _bardsai_mod.BARDSAI_LABEL_MAP
PRIVACY_FILTER_LABEL_MAP = _privacy_mod.PRIVACY_FILTER_LABEL_MAP
decode_bilou = _privacy_mod.decode_bilou


def test_uc85_rules_system_and_registry() -> None:
    """UC-85: get_system('rules'), KeyError on unknown, label maps, and unmapped coverage."""
    rules_sys = get_system("rules")
    assert type(rules_sys).__name__ == "RulesSystem"
    assert rules_sys.name == "rules"

    # Test predict matches piitier.detect on PESEL + IBAN text
    text = "PESEL: 44051401359, IBAN: PL61109010140000071219812874"
    spans_sys = rules_sys.predict(text)
    spans_detect = piitier.detect(text)
    assert spans_sys == spans_detect

    # Unknown system name -> KeyError with available names
    with pytest.raises(KeyError) as exc_info:
        get_system("nonexistent-system")
    assert "nonexistent-system" in str(exc_info.value)
    assert "rules" in str(exc_info.value)

    # Label maps values are members of Label
    for lmap_name, lmap in [
        ("presidio", PRESIDIO_LABEL_MAP),
        ("bardsai-v2", BARDSAI_LABEL_MAP),
        ("privacy-filter", PRIVACY_FILTER_LABEL_MAP),
    ]:
        for raw, lbl in lmap.items():
            assert isinstance(lbl, Label), f"{lmap_name} map value {lbl} is not a Label enum member"

    # External adapters unmapped coverage
    for name, sys_cls, lmap in [
        ("presidio", PresidioSystem, PRESIDIO_LABEL_MAP),
        ("bardsai-v2", BardsaiV2System, BARDSAI_LABEL_MAP),
        ("privacy-filter", PrivacyFilterSystem, PRIVACY_FILTER_LABEL_MAP),
    ]:
        sys_inst = sys_cls()
        unmapped = sys_inst.unmapped
        expected_unmapped = frozenset(lbl for lbl in Label if lbl not in lmap.values())
        assert unmapped == expected_unmapped
        assert unmapped.issubset(set(Label))


def test_uc88_decode_bilou_and_maps() -> None:
    """UC-88: decode_bilou on manual fixture, ignored invalid I-, and Label members check."""
    # All 6 privacy-filter label map values are members of Label
    for raw, lbl in PRIVACY_FILTER_LABEL_MAP.items():
        assert isinstance(lbl, Label)
    assert len(PRIVACY_FILTER_LABEL_MAP) == 6

    # Manual fixture test for decode_bilou
    offset_mapping = [
        (0, 0),  # special token
        (0, 5),  # S-private_person
        (10, 15),  # B-private_email
        (15, 20),  # I-private_email
        (20, 25),  # L-private_email
        (30, 35),  # I-private_phone (without B -> should be ignored)
        (40, 45),  # S-private_phone
    ]
    id2label = {
        0: "O",
        1: "S-private_person",
        2: "B-private_email",
        3: "I-private_email",
        4: "L-private_email",
        5: "I-private_phone",
        6: "S-private_phone",
    }
    probs = [
        [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.9, 0.1, 0.0, 0.0, 0.0, 0.0],  # (0,5): S-private_person, score 0.9
        [0.0, 0.0, 0.8, 0.0, 0.0, 0.0, 0.0],  # (10,15): B-private_email
        [0.0, 0.0, 0.0, 0.85, 0.0, 0.0, 0.0],  # (15,20): I-private_email
        [
            0.0,
            0.0,
            0.0,
            0.0,
            0.9,
            0.0,
            0.0,
        ],  # (20,25): L-private_email -> combined (10,25), avg score (0.8+0.85+0.9)/3 = 0.85
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.5, 0.0],  # (30,35): I-private_phone without B -> ignored
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.95],  # (40,45): S-private_phone, score 0.95
    ]

    decoded = decode_bilou(offset_mapping=offset_mapping, probs=probs, id2label=id2label)
    assert len(decoded) == 3
    assert decoded[0] == (0, 5, "private_person", 0.9)
    assert decoded[1] == (10, 25, "private_email", pytest.approx(0.85))
    assert decoded[2] == (40, 45, "private_phone", 0.95)
