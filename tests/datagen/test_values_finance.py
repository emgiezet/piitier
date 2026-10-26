"""Tests for PII-3-a finance/insurance generators and templates (UC-38..UC-45)."""

from __future__ import annotations

import json
import random
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from piitier.datagen import Template, TemplateError, render, values
from piitier.labels import Label

_FAKE_MODEL = "hf.co/SpeakLeash/Bielik-11B-v3.0-Instruct-GGUF:Q8_0"


def test_uc38_generators_and_validators_100_draws() -> None:
    """UC-38: 100 draws per generator with Random(42) pass validators without exceptions."""
    labels = [
        Label.NR_UMOWY,
        Label.NR_POLISY,
        Label.NR_SZKODY,
        Label.NR_REJESTRACYJNY,
        Label.VIN,
        Label.NR_KW,
        Label.KWOTA,
    ]
    for lbl in labels:
        rng = random.Random(42)
        gen = values._GENERATORS[lbl]
        val_fn = values._VALIDATORS[lbl]
        for _ in range(100):
            val = gen(rng)
            assert isinstance(val, str)
            assert val != ""
            assert val_fn(val) is True


def test_uc39_vin_properties() -> None:
    """UC-39: VIN has ZZ prefix, no I/O/Q, 17 chars, valid ISO 3779 check digit."""
    rng = random.Random(123)
    for _ in range(50):
        vin = values.generate_value(Label.VIN, rng)
        assert vin.startswith("ZZ")
        assert len(vin) == 17
        for char in "IOQ":
            assert char not in vin
        assert values.validate_vin(vin) is True


def test_uc40_determinism() -> None:
    """UC-40: same seed gives identical values; different seed gives different values."""
    lbls = [
        Label.NR_UMOWY,
        Label.NR_POLISY,
        Label.NR_SZKODY,
        Label.NR_REJESTRACYJNY,
        Label.VIN,
        Label.NR_KW,
    ]
    for lbl in lbls:
        val1 = values.generate_value(lbl, random.Random(100))
        val2 = values.generate_value(lbl, random.Random(100))
        val3 = values.generate_value(lbl, random.Random(101))
        assert val1 == val2
        assert val1 != val3


def test_uc41_render_all_six_new_labels() -> None:
    """UC-41: render() with 6 new labels returns valid spans and exact text slicing."""
    template_text = (
        "Umowa: {{NR_UMOWY}}, Polisa: {{NR_POLISY}}, Szkoda: {{NR_SZKODY}}, "
        "Rejestracja: {{NR_REJESTRACYJNY}}, VIN: {{VIN}}, KW: {{NR_KW}}."
    )
    t = Template(template_id="finance-all", doc_type="test", text=template_text)
    doc = render(t, seed=42)
    assert len(doc.spans) == 6
    for span in doc.spans:
        assert span.source == "synthetic"
        assert span.status == "valid"
        assert doc.text[span.start : span.end] == span.text
        assert values._VALIDATORS[span.label](span.text) is True


def test_uc42_unsupported_label_raises_template_error() -> None:
    """UC-42: template with unknown/unsupported label raises TemplateError."""
    t = Template(template_id="unknown-test", doc_type="test", text="Test {{WIEK}}.")
    with pytest.raises(TemplateError):
        render(t, seed=42)


def test_uc43_build_check_manifest_with_new_templates(tmp_path: Path) -> None:
    """UC-43: build passes, check returns 0, span_counts include new labels."""
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
    new_labels = {"NR_UMOWY", "NR_POLISY", "NR_SZKODY", "NR_REJESTRACYJNY", "VIN", "NR_KW"}
    for lbl in new_labels:
        assert lbl in span_counts, f"{lbl} missing from manifest span_counts"


def test_uc44_llm_write_templates_accepts_new_labels(tmp_path: Path) -> None:
    """UC-44: llm.write_templates accepts template using new labels with rejected == {}."""
    from piitier.datagen import llm

    class Server(HTTPServer):
        def __init__(self, comp: str) -> None:
            self.comp = comp
            super().__init__(("127.0.0.1", 0), Handler, bind_and_activate=True)

        @property
        def port(self) -> int:
            return int(self.server_address[1])

        @property
        def url(self) -> str:
            return f"http://127.0.0.1:{self.port}"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            srv = self.server
            assert isinstance(srv, Server)
            if self.path == "/api/tags":
                body = json.dumps(
                    {
                        "models": [
                            {
                                "name": _FAKE_MODEL,
                                "model": _FAKE_MODEL,
                                "digest": "fake",
                                "size": 0,
                            }
                        ]
                    }
                ).encode()
                self._send(200, body)
            else:
                self._send(404, b"")

        def do_POST(self) -> None:
            srv = self.server
            assert isinstance(srv, Server)
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            if self.path == "/api/generate":
                body = json.dumps({"response": srv.comp, "done": True}).encode()
                self._send(200, body)
            else:
                self._send(404, b"")

        def _send(self, code: int, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    template_using_new = (
        "Zgłoszenie szkody\n\n"
        "Numer szkody: {{NR_SZKODY}}\n"
        "Rejestracja: {{NR_REJESTRACYJNY}}\n"
        "VIN pojazdu: {{VIN}}\n"
        "PESEL: {{PESEL}}\n"
        "IBAN: {{IBAN}}\n\n"
        "Opis zdarzenia kolizji."
    )

    srv = Server(template_using_new)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        res = llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            model=_FAKE_MODEL,
            out=tmp_path,
            ollama_url=srv.url,
        )
        assert res.get("rejected", {}) == {}
    finally:
        srv.shutdown()
        thread.join(timeout=2.0)


def test_uc45_prompt_label_list_matches_supported_labels() -> None:
    """UC-45: prompt for each doc_type lists all labels from _SUPPORTED_LABELS."""
    from piitier.datagen.build import DOC_TYPES
    from piitier.datagen.llm import _SUPPORTED_LABELS

    prompts_dir = Path(__file__).parent.parent.parent / "src" / "piitier" / "datagen" / "prompts"
    for doc_type in sorted(DOC_TYPES):
        content = (prompts_dir / f"{doc_type}.txt").read_text(encoding="utf-8")
        assert "30 obsługiwanych znaczników" in content
        for lbl in _SUPPORTED_LABELS:
            assert f"{{{{{lbl.name}}}}}" in content


# ---------------------------------------------------------------------------
# New tests: KWOTA/DOCHOD formats, currency conventions, NR_SZKODY/NR_POLISY
# ---------------------------------------------------------------------------


def test_kwota_formats_vary_across_seeds() -> None:
    """KWOTA generator produces multiple distinct formats over 500 seeds."""
    import re

    fmt_space = re.compile(r"^\d{1,3}(?: \d{3})+[,.]")
    fmt_dot_thou = re.compile(r"^\d{1,3}(?:\.\d{3})+,")
    fmt_plain_dec = re.compile(r"^\d+[,.]")
    fmt_integer = re.compile(r"^\d+$")
    fmt_with_currency = re.compile(r" (?:PLN|zł|EUR|€)$")

    seen_space = seen_dot = seen_plain = seen_integer = seen_ccy = False
    rng = random.Random(0)
    for _ in range(500):
        v = values.generate_kwota(rng)
        assert values.validate_kwota(v), f"invalid KWOTA: {v!r}"
        seen_space = seen_space or bool(fmt_space.match(v))
        seen_dot = seen_dot or bool(fmt_dot_thou.match(v))
        seen_plain = seen_plain or bool(fmt_plain_dec.match(v))
        seen_integer = seen_integer or bool(fmt_integer.match(v.split()[0]))
        seen_ccy = seen_ccy or bool(fmt_with_currency.search(v))
    assert seen_space, "space-thousands format never generated"
    assert seen_dot, "dot-thousands format never generated"
    assert seen_plain, "plain-decimal format never generated"
    assert seen_integer, "integer format never generated"
    assert seen_ccy, "embedded currency never generated"


def test_dochod_500_seeds_pass_validator() -> None:
    """DOCHOD generator passes validator over 500 seeds."""
    rng = random.Random(7)
    for _ in range(500):
        v = values.generate_dochod(rng)
        assert v != ""
        assert values.validate_dochod(v), f"invalid DOCHOD: {v!r}"


def test_kwota_no_embedded_currency_when_currency_follows() -> None:
    """generate_kwota(rng, currency_follows=True) never embeds a currency token."""
    import re

    ccy_pat = re.compile(r"(?:PLN|zł|EUR|€)")
    rng = random.Random(99)
    for _ in range(500):
        v = values.generate_kwota(rng, currency_follows=True)
        assert not ccy_pat.search(v), (
            f"embedded currency in value when currency_follows=True: {v!r}"
        )
        assert values.validate_kwota(v)


def test_nr_polisy_slash_formats_valid() -> None:
    """NR_POLISY: slash formats POL/YYYY/N and PL/YYYY/NNNNNNN pass validator."""
    assert values.validate_nr_polisy("POL/2025/123")
    assert values.validate_nr_polisy("POL/2015/1")
    assert values.validate_nr_polisy("POL/2026/999999")
    assert values.validate_nr_polisy("PL/2024/1234567")
    # legacy formats still valid
    assert values.validate_nr_polisy("PL0123456789")
    assert values.validate_nr_polisy("UB9876543210")
    # invalid
    assert not values.validate_nr_polisy("POL/1999/123")
    assert not values.validate_nr_polisy("PL/2026/123456")  # 6 digits, not 7


def test_nr_szkody_slash_formats_valid() -> None:
    """NR_SZKODY: slash formats SZK/YYYY/N{1,6} and CLM/YYYY/NNNNNN pass validator."""
    assert values.validate_nr_szkody("SZK/2026/12")
    assert values.validate_nr_szkody("SZK/2015/1")
    assert values.validate_nr_szkody("SZK/2026/999999")
    assert values.validate_nr_szkody("CLM/2024/123456")
    # legacy formats still valid
    assert values.validate_nr_szkody("SZK12345678")
    assert values.validate_nr_szkody("CLM12345678")
    # invalid
    assert not values.validate_nr_szkody("CLM/1990/123456")
    assert not values.validate_nr_szkody("SZK/2026/1234567")  # 7 digits, too many


def test_nr_polisy_500_seeds_pass_validator() -> None:
    """NR_POLISY over 500 seeds all pass validator."""
    rng = random.Random(11)
    for _ in range(500):
        v = values.generate_nr_polisy(rng)
        assert values.validate_nr_polisy(v), f"invalid NR_POLISY: {v!r}"


def test_nr_szkody_500_seeds_pass_validator() -> None:
    """NR_SZKODY over 500 seeds all pass validator."""
    rng = random.Random(22)
    for _ in range(500):
        v = values.generate_nr_szkody(rng)
        assert values.validate_nr_szkody(v), f"invalid NR_SZKODY: {v!r}"


def test_kwota_500_seeds_pass_validator() -> None:
    """KWOTA over 500 seeds (including embedded-currency forms) all pass validator."""
    rng = random.Random(33)
    for _ in range(500):
        v = values.generate_kwota(rng)
        assert values.validate_kwota(v), f"invalid KWOTA: {v!r}"


def test_kwota_dochod_deterministic() -> None:
    """KWOTA and DOCHOD generators are deterministic: same seed → same sequence."""
    r1, r2 = random.Random(555), random.Random(555)
    for _ in range(100):
        assert values.generate_kwota(r1) == values.generate_kwota(r2)
        assert values.generate_dochod(r1) == values.generate_dochod(r2)
