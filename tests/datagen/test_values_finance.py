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


def test_uc38_generators_and_validators_100_draws() -> None:
    """UC-38: 100 draws per generator with Random(42) pass validators without exceptions."""
    labels = [
        Label.NR_UMOWY,
        Label.NR_POLISY,
        Label.NR_SZKODY,
        Label.NR_REJESTRACYJNY,
        Label.VIN,
        Label.NR_KW,
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
    t = Template(template_id="unknown-test", doc_type="test", text="Test {{LEK}}.")
    with pytest.raises(TemplateError):
        render(t, seed=42)


def test_uc43_build_check_manifest_with_new_templates(tmp_path: Path) -> None:
    """UC-43: build passes, check returns 0, span_counts include new labels."""
    from piitier.datagen.build import _PACKAGED_TEMPLATES_DIR, build, check

    out_dir = tmp_path / "dataset"
    build(_PACKAGED_TEMPLATES_DIR, out=out_dir, n=30, seed=123)

    exit_code, stderr = check(out_dir)
    assert exit_code == 0
    assert stderr == ""

    manifest_data = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    records = manifest_data if isinstance(manifest_data, list) else [manifest_data]
    new_labels = {"NR_UMOWY", "NR_POLISY", "NR_SZKODY", "NR_REJESTRACYJNY", "VIN", "NR_KW"}
    found_any = False
    for rec in records:
        counts = rec.get("span_counts", {})
        if any(lbl in counts for lbl in new_labels):
            found_any = True
            break
    assert found_any is True


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
                                "name": llm._DEFAULT_MODEL,
                                "model": llm._DEFAULT_MODEL,
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
        import os

        os.environ["OLLAMA_HOST"] = srv.url
        res = llm.write_templates(doc_type="zgloszenie_szkody", count=1, out=tmp_path)
        assert res.get("rejected", {}) == {}
    finally:
        srv.shutdown()
        thread.join(timeout=2.0)


def test_uc45_prompt_label_list_matches_supported_labels() -> None:
    """UC-45: prompt for each doc_type lists all labels from _SUPPORTED_LABELS."""
    from piitier.datagen.llm import _SUPPORTED_LABELS

    prompts_dir = Path(__file__).parent.parent.parent / "src" / "piitier" / "datagen" / "prompts"
    for prompt_file in prompts_dir.glob("*.txt"):
        content = prompt_file.read_text(encoding="utf-8")
        assert "21 obsługiwanych znaczników" in content
        for lbl in _SUPPORTED_LABELS:
            assert f"{{{{{lbl.name}}}}}" in content
