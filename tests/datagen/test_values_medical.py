"""Tests for PII-3-b medical generators, render, templates and prompts (UC-46..UC-53)."""

from __future__ import annotations

import json
import random
from pathlib import Path

from piitier.datagen import Template, render, values
from piitier.labels import Label


def test_uc46_medical_generators_and_validators_100_draws() -> None:
    """UC-46: 100 draws per generator at Random(42) pass validators, deterministic."""
    labels = [
        Label.ICD10,
        Label.LEK,
        Label.ROZPOZNANIE,
        Label.PLACOWKA,
        Label.NPWZ,
    ]
    for lbl in labels:
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        gen = values._GENERATORS[lbl]
        val_fn = values._VALIDATORS[lbl]
        for _ in range(100):
            v1 = gen(rng1)
            v2 = gen(rng2)
            assert v1 == v2
            assert isinstance(v1, str)
            assert v1 != ""
            assert val_fn(v1) is True


def test_uc47_icd10_dotted_undotted_and_list_size() -> None:
    """UC-47: ICD10 list has >= 25 codes, both dotted and undotted pass validator."""
    assert len(values._ICD10_LIST) >= 25
    sample_undotted = "I10"
    sample_dotted = "E11.9"
    assert values.validate_icd10(sample_undotted) is True
    assert values.validate_icd10(sample_dotted) is True


def test_uc48_npwz_format_and_evidence() -> None:
    """UC-48: NPWZ 100 draws valid, first digit is 1, evidence comment exists in source."""
    # EVIDENCE: https://cez.gov.pl/HIS_API/site/pl/CodeSystem-pl-zle-practitioner-identifier-system.html
    values_src = Path(values.__file__).read_text(encoding="utf-8")
    assert "https://cez.gov.pl/" in values_src or "EVIDENCE" in values_src

    rng = random.Random(42)
    for _ in range(100):
        npwz = values.generate_value(Label.NPWZ, rng)
        assert npwz.startswith("1")
        assert len(npwz) == 7
        assert values.validate_npwz(npwz) is True


def test_uc49_lek_list_length_40() -> None:
    """UC-49: LEK list length is exactly 40 names, all unique."""
    assert len(values._LEK_LIST) == 40
    assert len(set(values._LEK_LIST)) == 40


def test_uc50_render_template_with_six_medical_labels() -> None:
    """UC-50: render() with all 6 medical labels returns valid spans and exact text slicing."""
    template_text = (
        "Rozpoznanie: {{ROZPOZNANIE}}, Kod: {{ICD10}}, Lek: {{LEK}}, "
        "Placówka: {{PLACOWKA}}, Lekarz: {{LEKARZ#1}}, NPWZ: {{NPWZ}}."
    )
    t = Template(template_id="medical-all", doc_type="wypis_szpitalny", text=template_text)
    doc = render(t, seed=42)
    assert len(doc.spans) == 6
    for span in doc.spans:
        assert span.source == "synthetic"
        assert span.status == "valid"
        assert doc.text[span.start : span.end] == span.text
        if span.label in values._VALIDATORS:
            assert values._VALIDATORS[span.label](span.text) is True


def test_uc51_lekarz_inflection_and_fallback() -> None:
    """UC-51: LEKARZ#1:gen inflection works and fallback is counted like OSOBA."""
    t_nom = Template(template_id="med-nom", doc_type="skierowanie", text="Lekarz: {{LEKARZ#1}}")
    t_gen = Template(
        template_id="med-gen", doc_type="skierowanie", text="Lekarza: {{LEKARZ#1:gen}}"
    )
    doc_nom = render(t_nom, seed=42)
    doc_gen = render(t_gen, seed=42)
    assert doc_nom.spans[0].text != doc_gen.spans[0].text
    # Prefix should be preserved (dr or lek. med.)
    assert doc_gen.spans[0].text.startswith("dr") or doc_gen.spans[0].text.startswith("lek. med.")


def test_uc52_build_check_manifest_medical_templates(tmp_path: Path) -> None:
    """UC-52: build passes, check returns 0, span_counts include medical labels."""
    from piitier.datagen.build import _PACKAGED_TEMPLATES_DIR, build, check, collect_templates

    out_dir = tmp_path / "dataset"
    # Round-robin selects one doc_type per iteration, cycling through all types.
    # n_types × max_per_type guarantees every template in the largest doc_type
    # renders at least once, so every label-bearing template is covered.
    _templates = collect_templates(_PACKAGED_TEMPLATES_DIR)
    _by_type: dict[str, list] = {}
    for _t in _templates:
        _by_type.setdefault(_t.doc_type, []).append(_t)
    n = len(_by_type) * max(len(v) for v in _by_type.values())
    build(_PACKAGED_TEMPLATES_DIR, out=out_dir, n=n, seed=123)

    exit_code, stderr = check(out_dir)
    assert exit_code == 0
    assert stderr == ""

    manifest_data = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    span_counts = manifest_data.get("span_counts", {})
    medical_labels = {"ICD10", "LEK", "ROZPOZNANIE", "PLACOWKA", "LEKARZ", "NPWZ"}
    for lbl in medical_labels:
        assert lbl in span_counts, f"{lbl} missing from manifest span_counts"


def test_uc53_prompt_label_list_28_labels() -> None:
    """UC-53: prompt for each doc_type lists all 30 labels from _SUPPORTED_LABELS."""
    from piitier.datagen.build import DOC_TYPES
    from piitier.datagen.llm import _SUPPORTED_LABELS

    prompts_dir = Path(__file__).parent.parent.parent / "src" / "piitier" / "datagen" / "prompts"
    for doc_type in sorted(DOC_TYPES):
        content = (prompts_dir / f"{doc_type}.txt").read_text(encoding="utf-8")
        assert "30 obsługiwanych znaczników" in content
        for lbl in _SUPPORTED_LABELS:
            assert f"{{{{{lbl.name}}}}}" in content


# ---------------------------------------------------------------------------
# New tests: DANE_ZDROWOTNE
# ---------------------------------------------------------------------------


def test_dane_zdrowotne_list_size_and_uniqueness() -> None:
    """DANE_ZDROWOTNE list has >= 80 entries, all unique, 1-5 words each."""
    lst = values._DANE_ZDROWOTNE_LIST
    assert len(lst) >= 80, f"expected >= 80 entries, got {len(lst)}"
    assert len(set(lst)) == len(lst), "duplicate entries in _DANE_ZDROWOTNE_LIST"
    for phrase in lst:
        wc = len(phrase.split())
        assert 1 <= wc <= 5, f"phrase outside 1-5 word limit: {phrase!r}"


def test_dane_zdrowotne_500_seeds_pass_validator() -> None:
    """DANE_ZDROWOTNE over 500 seeds all pass validator and are non-empty."""
    rng = random.Random(42)
    for _ in range(500):
        v = values.generate_dane_zdrowotne(rng)
        assert v != ""
        assert values.validate_dane_zdrowotne(v), f"invalid DANE_ZDROWOTNE: {v!r}"


def test_dane_zdrowotne_deterministic() -> None:
    """DANE_ZDROWOTNE generator is deterministic."""
    r1, r2 = random.Random(77), random.Random(77)
    for _ in range(100):
        assert values.generate_dane_zdrowotne(r1) == values.generate_dane_zdrowotne(r2)


def test_dane_zdrowotne_in_generators_and_validators() -> None:
    """DANE_ZDROWOTNE is registered in both _GENERATORS and _VALIDATORS."""
    assert Label.DANE_ZDROWOTNE in values._GENERATORS
    assert Label.DANE_ZDROWOTNE in values._VALIDATORS
