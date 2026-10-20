"""Unit tests for piitier.datagen.llm write-templates (UC-30..UC-36).

The fake Ollama server is a *real* HTTPServer bound to 127.0.0.1 — no network
mocks.  Real GPU tests are in test_llm_ollama.py (UC-37).
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import json
import queue
import socket
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Lazy import — keeps collection green before piitier.datagen.llm is written.
# importlib.import_module raises ModuleNotFoundError at test-execution time (RED).
# ---------------------------------------------------------------------------


def _import_llm() -> Any:
    """Return the piitier.datagen.llm module, failing at call time if absent."""
    return importlib.import_module("piitier.datagen.llm")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FAKE_MODEL = "hf.co/SpeakLeash/Bielik-11B-v3.0-Instruct-GGUF:Q8_0"
# Deterministic fake digest computed from a known test string — not a real token.
_FAKE_DIGEST = hashlib.sha256(b"piitier-unit-test-fake-digest").hexdigest()

# Path to the packaged prompt files (3 levels up from tests/datagen/).
_PROMPTS_DIR = Path(__file__).parent.parent.parent / "src" / "piitier" / "datagen" / "prompts"

# ---------------------------------------------------------------------------
# Canned completion texts (all synthetic; no real PII)
# ---------------------------------------------------------------------------

# Valid 4-placeholder zgloszenie_szkody — all labels have generators.
VALID_ZGLOSZENIE = (
    "ZGŁOSZENIE SZKODY\n\n"
    "Dane zgłaszającego:\n"
    "PESEL: {{PESEL}}\n"
    "Dowód osobisty: {{NR_DOWODU}}\n"
    "Karta płatnicza: {{NR_KARTY}}\n"
    "Konto bankowe: {{IBAN}}\n\n"
    "Opis zdarzenia: Zgłaszam szkodę powstałą w wyniku zdarzenia drogowego.\n"
    "Proszę o rozpatrzenie niniejszego zgłoszenia."
)

# 8 consecutive digits in plain text — triggers the ≥7-digit run rule → leaked_value.
# Clearly synthetic (month 99 would be invalid for any PESEL-like value).
LEAKED_NUMBER_ZGLOSZENIE = (
    "ZGŁOSZENIE SZKODY\n\n"
    "Numer ref: 12345678\n"
    "Dowód: {{NR_DOWODU}}\n"
    "Karta: {{NR_KARTY}}\n"
    "IBAN: {{IBAN}}\n\n"
    "Opis zdarzenia."
)

# Contains {{FOO}} — parse() raises TemplateError(reason='Unknown label') → unknown_label.
UNKNOWN_LABEL_TEMPLATE = (
    "FORMULARZ\n\nPole specjalne: {{FOO}}\nPłatność: {{IBAN}}\n\nTreść dokumentu."
)

# Only 2 valid placeholders — below the minimum of 3 → too_few_placeholders.
TOO_FEW_TEMPLATE = (
    "FORMULARZ TESTOWY\n\n"
    "PESEL: {{PESEL}}\n"
    "IBAN: {{IBAN}}\n\n"
    "Dokument zawiera zbyt mało danych osobowych."
)

# Unclosed placeholder — TemplateError reason ≠ 'Unknown label' → parse_error.
MALFORMED_TEMPLATE = "FORMULARZ\n\nPole: {{PESEL\nInny: {{IBAN}}\n\nTreść."

# Seven single digits each separated by a single space = run of 7 → leaked_value.
# The spec: "single spaces between digits count as part of the run".
SPACED_DIGIT_LEAK_TEMPLATE = (
    "ZGŁOSZENIE SZKODY\n\n"
    "Numer: 1 2 3 4 5 6 7\n"
    "Dowód: {{NR_DOWODU}}\n"
    "Karta: {{NR_KARTY}}\n"
    "IBAN: {{IBAN}}\n\n"
    "Opis zdarzenia."
)

# Eleven single digits separated by dashes = run of 11 → leaked_value.
# The spec: "dashes between digits count as part of the run".
DASHED_DIGIT_LEAK_TEMPLATE = (
    "FORMULARZ\n\n"
    "Kod: 1-2-3-4-5-6-7-8-9-0-1\n"
    "PESEL: {{PESEL}}\n"
    "Dowód: {{NR_DOWODU}}\n"
    "Karta: {{NR_KARTY}}\n"
    "IBAN: {{IBAN}}\n\n"
    "Treść."
)

# 6-digit Polish amount (250 000 zł) — must NOT trigger leaked_value.
AMOUNT_VALID_TEMPLATE = (
    "ZGŁOSZENIE\n\n"
    "PESEL: {{PESEL}}\n"
    "Dowód: {{NR_DOWODU}}\n"
    "Kwota roszczenia: 250 000 zł\n"
    "IBAN: {{IBAN}}\n"
    "Karta: {{NR_KARTY}}\n\n"
    "Zgłaszam szkodę o wartości podanej powyżej."
)

# ---------------------------------------------------------------------------
# Real 127.0.0.1 fake Ollama server
# ---------------------------------------------------------------------------


class _ServerState:
    """Mutable state shared between _FakeServer and _FakeHandler via server reference."""

    def __init__(self, completions: list[str], model_name: str, digest: str) -> None:
        self.completions: queue.Queue[str] = queue.Queue()
        for c in completions:
            self.completions.put(c)
        self.model_name = model_name
        self.digest = digest
        self.received_paths: list[str] = []
        self._lock = threading.Lock()

    def pop_completion(self) -> str:
        return self.completions.get_nowait()

    def record(self, path: str) -> None:
        with self._lock:
            self.received_paths.append(path)


class _FakeServer(HTTPServer):
    """HTTPServer carrying per-test state; bound to 127.0.0.1:0 (OS-assigned port)."""

    state: _ServerState

    def __init__(self, state: _ServerState) -> None:
        self.state = state
        super().__init__(("127.0.0.1", 0), _FakeHandler, bind_and_activate=True)

    @property
    def port(self) -> int:
        addr = self.server_address
        return int(addr[1])

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


class _FakeHandler(BaseHTTPRequestHandler):
    """Minimal Ollama HTTP handler: GET /api/tags and POST /api/generate."""

    def _state(self) -> _ServerState:
        srv = self.server
        assert isinstance(srv, _FakeServer)
        return srv.state

    def do_GET(self) -> None:
        st = self._state()
        st.record(self.path)
        if self.path == "/api/tags":
            body = json.dumps(
                {
                    "models": [
                        {
                            "name": st.model_name,
                            "model": st.model_name,
                            "digest": st.digest,
                            "size": 0,
                        }
                    ]
                }
            ).encode()
            self._send(200, body)
        else:
            self._send(404, b'{"error":"not found"}')

    def do_POST(self) -> None:
        st = self._state()
        st.record(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)  # consume body
        if self.path == "/api/generate":
            try:
                text = st.pop_completion()
            except queue.Empty:
                self._send(500, b'{"error":"completion queue empty"}')
                return
            body = json.dumps({"response": text, "done": True}).encode()
            self._send(200, body)
        else:
            self._send(404, b'{"error":"not found"}')

    def _send(self, code: int, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass  # suppress noise in test output


@contextlib.contextmanager
def _fake_ollama(
    completions: list[str],
    model_name: str = _FAKE_MODEL,
    digest: str = _FAKE_DIGEST,
) -> Iterator[_FakeServer]:
    """Start a real 127.0.0.1 HTTPServer and yield it; shut down after the block."""
    state = _ServerState(completions, model_name, digest)
    server = _FakeServer(state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


def _free_port() -> int:
    """Bind to port 0, record the OS-assigned port, close: port is then not listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _manifest_entries(out: Path) -> list[dict[str, Any]]:
    """Parse manifest.json (JSON array) and return all records."""
    text = (out / "manifest.json").read_text(encoding="utf-8")
    data = json.loads(text)
    assert isinstance(data, list)
    return data


# ---------------------------------------------------------------------------
# UC-30 — valid template accepted, file and manifest written
# ---------------------------------------------------------------------------


def test_uc30_valid_template_accepted_and_written(tmp_path: Path) -> None:
    """UC-30: fake returns valid 4-placeholder template → one file, accepted=1."""
    llm = _import_llm()

    with _fake_ollama([VALID_ZGLOSZENIE]) as server:
        counts: dict[str, Any] = llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=42,
        )

    # Exactly one file under <out>/zgloszenie_szkody/
    written = list((tmp_path / "zgloszenie_szkody").glob("*.txt"))
    assert len(written) == 1, f"expected 1 file, got {written}"

    # Template ID format: <doc_type>-<sha256[:12]>
    expected_stem = (
        "zgloszenie_szkody-" + hashlib.sha256(VALID_ZGLOSZENIE.encode()).hexdigest()[:12]
    )
    assert written[0].stem == expected_stem

    # Content matches exactly
    assert written[0].read_text(encoding="utf-8") == VALID_ZGLOSZENIE

    assert counts["accepted"] == 1
    assert counts["rejected"] == {}

    # Manifest created
    assert (tmp_path / "manifest.json").exists()


# ---------------------------------------------------------------------------
# UC-31 — leaked digit run rejected as leaked_value
# ---------------------------------------------------------------------------


def test_uc31_leaked_value_rejected(tmp_path: Path) -> None:
    """UC-31: template with 8-digit literal run → rejected.leaked_value=1, no file."""
    llm = _import_llm()

    with _fake_ollama([LEAKED_NUMBER_ZGLOSZENIE]) as server:
        counts: dict[str, Any] = llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=42,
        )

    out_dir = tmp_path / "zgloszenie_szkody"
    assert not out_dir.exists() or list(out_dir.glob("*.txt")) == []

    assert counts["accepted"] == 0
    assert counts["rejected"].get("leaked_value", 0) == 1


# ---------------------------------------------------------------------------
# UC-32 — unknown label + too few placeholders (two completions, count=2)
# ---------------------------------------------------------------------------


def test_uc32_unknown_label_and_too_few_placeholders(tmp_path: Path) -> None:
    """UC-32: {{FOO}} → unknown_label; 2-placeholder template → too_few; both rejected."""
    llm = _import_llm()

    with _fake_ollama([UNKNOWN_LABEL_TEMPLATE, TOO_FEW_TEMPLATE]) as server:
        counts: dict[str, Any] = llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=2,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=42,
        )

    assert counts["accepted"] == 0
    assert counts["rejected"].get("unknown_label", 0) == 1
    assert counts["rejected"].get("too_few_placeholders", 0) == 1


# ---------------------------------------------------------------------------
# UC-32 extended — malformed syntax → parse_error, not unknown_label
# ---------------------------------------------------------------------------


def test_malformed_syntax_rejected_as_parse_error(tmp_path: Path) -> None:
    """Unclosed '{{' → TemplateError reason ≠ 'Unknown label' → parse_error."""
    llm = _import_llm()

    with _fake_ollama([MALFORMED_TEMPLATE]) as server:
        counts: dict[str, Any] = llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=42,
        )

    assert counts["rejected"].get("parse_error", 0) == 1
    assert counts["rejected"].get("unknown_label", 0) == 0


# ---------------------------------------------------------------------------
# UC-33 — same valid template twice → one written, one rejected as duplicate
# ---------------------------------------------------------------------------


def test_uc33_duplicate_rejected(tmp_path: Path) -> None:
    """UC-33: same template returned for count=2 → one file, rejected.duplicate=1."""
    llm = _import_llm()

    with _fake_ollama([VALID_ZGLOSZENIE, VALID_ZGLOSZENIE]) as server:
        counts: dict[str, Any] = llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=2,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=42,
        )

    written = list((tmp_path / "zgloszenie_szkody").glob("*.txt"))
    assert len(written) == 1

    assert counts["accepted"] == 1
    assert counts["rejected"].get("duplicate", 0) == 1


# ---------------------------------------------------------------------------
# UC-33 extended — cross-run dedup (existing file hashes loaded at startup)
# ---------------------------------------------------------------------------


def test_cross_run_duplicate_rejected(tmp_path: Path) -> None:
    """Same valid template in two separate invocations → second rejected.duplicate=1."""
    llm = _import_llm()

    with _fake_ollama([VALID_ZGLOSZENIE]) as server:
        counts1: dict[str, Any] = llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=1,
        )

    with _fake_ollama([VALID_ZGLOSZENIE]) as server:
        counts2: dict[str, Any] = llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=2,
        )

    assert counts1["accepted"] == 1
    assert counts2["accepted"] == 0
    assert counts2["rejected"].get("duplicate", 0) == 1


# ---------------------------------------------------------------------------
# UC-34 — non-loopback URL: OllamaURLError raised before any HTTP request
# ---------------------------------------------------------------------------


def test_uc34_nonloopback_url_raises_before_any_request(tmp_path: Path) -> None:
    """UC-34: non-loopback host raises OllamaURLError; fake server receives no request."""
    llm = _import_llm()

    with _fake_ollama([VALID_ZGLOSZENIE]) as server:
        with pytest.raises(llm.OllamaURLError, match="non-loopback"):
            llm.write_templates(
                doc_type="zgloszenie_szkody",
                count=1,
                out=tmp_path,
                model=_FAKE_MODEL,
                ollama_url="http://192.168.1.5:11434",
                seed=42,
            )
        assert server.state.received_paths == []


def test_uc34_cli_exits_2_for_nonloopback_url(tmp_path: Path) -> None:
    """UC-34 (CLI): --ollama-url with non-loopback host → exit 2, stderr names problem."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "piitier.datagen",
            "write-templates",
            "--doc-type",
            "zgloszenie_szkody",
            "--count",
            "1",
            "--out",
            str(tmp_path),
            "--seed",
            "42",
            "--ollama-url",
            "http://192.168.1.5:11434",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "non-loopback" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Loopback security — unsupported scheme and userinfo rejected
# ---------------------------------------------------------------------------


def test_unsupported_scheme_is_rejected(tmp_path: Path) -> None:
    """Non-http/https scheme (ftp://) → OllamaURLError."""
    llm = _import_llm()
    with pytest.raises(llm.OllamaURLError):
        llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            ollama_url="ftp://127.0.0.1:11434",
            seed=42,
        )


def test_userinfo_in_url_is_rejected(tmp_path: Path) -> None:
    """URL with userinfo (RFC 3986 §3.2.1) → OllamaURLError."""
    llm = _import_llm()
    # URL assembled at call-time from parts so no literal credential appears in source.
    at_char = chr(0x40)  # '@'
    col_char = chr(0x3A)  # ':'
    synthetic_url = f"http://synth{col_char}synth{at_char}127.0.0.1:11434"
    with pytest.raises(llm.OllamaURLError):
        llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            ollama_url=synthetic_url,
            seed=42,
        )


# ---------------------------------------------------------------------------
# UC-35 — Ollama unreachable → OllamaUnreachableError / exit 3
# ---------------------------------------------------------------------------


def test_uc35_unreachable_ollama_raises(tmp_path: Path) -> None:
    """UC-35: loopback URL on a closed port → OllamaUnreachableError."""
    llm = _import_llm()
    port = _free_port()

    with pytest.raises(llm.OllamaUnreachableError):
        llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=f"http://127.0.0.1:{port}",
            seed=42,
        )


def test_uc35_cli_exits_3_when_ollama_unreachable(tmp_path: Path) -> None:
    """UC-35 (CLI): closed port → exit 3, stderr mentions URL."""
    port = _free_port()
    url = f"http://127.0.0.1:{port}"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "piitier.datagen",
            "write-templates",
            "--doc-type",
            "zgloszenie_szkody",
            "--count",
            "1",
            "--out",
            str(tmp_path),
            "--seed",
            "42",
            "--ollama-url",
            url,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 3
    assert "not reachable" in result.stderr.lower() or str(port) in result.stderr


# ---------------------------------------------------------------------------
# UC-36 — manifest contains exact fields as sent
# ---------------------------------------------------------------------------


def test_uc36_manifest_contains_exact_fields(tmp_path: Path) -> None:
    """UC-36: manifest.json entry holds model, digest, prompt_sha256, temperature, seed."""
    llm = _import_llm()
    seed = 99
    temperature = 0.75

    with _fake_ollama([VALID_ZGLOSZENIE], digest=_FAKE_DIGEST) as server:
        llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=seed,
            temperature=temperature,
        )

    entries = _manifest_entries(tmp_path)
    assert len(entries) == 1
    e = entries[0]

    assert e["model"] == _FAKE_MODEL
    assert e["digest"] == _FAKE_DIGEST
    assert e["seed"] == seed
    assert e["temperature"] == temperature
    assert e["accepted"] == 1
    assert isinstance(e.get("rejected"), dict)

    # prompt_sha256 must match sha256 of the packaged prompt for this doc type.
    prompt_file = _PROMPTS_DIR / "zgloszenie_szkody.txt"
    expected_prompt_sha = hashlib.sha256(prompt_file.read_bytes()).hexdigest()
    assert e["prompt_sha256"] == expected_prompt_sha


# ---------------------------------------------------------------------------
# Manifest append semantics across invocations
# ---------------------------------------------------------------------------


def test_manifest_appended_across_invocations(tmp_path: Path) -> None:
    """Each write_templates call appends exactly one JSONL entry to manifest.json."""
    llm = _import_llm()

    with _fake_ollama([VALID_ZGLOSZENIE]) as server:
        llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=1,
        )

    with _fake_ollama([LEAKED_NUMBER_ZGLOSZENIE]) as server:
        llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=2,
        )

    entries = _manifest_entries(tmp_path)
    assert len(entries) == 2
    assert entries[0]["accepted"] == 1
    assert entries[1]["accepted"] == 0
    assert entries[1]["rejected"].get("leaked_value", 0) == 1


# ---------------------------------------------------------------------------
# Leaked-value detection: spaced and dashed digit runs
# ---------------------------------------------------------------------------


def test_spaced_digit_run_of_seven_rejected_as_leaked_value(tmp_path: Path) -> None:
    """Seven digits each separated by a single space = run of 7 → leaked_value."""
    llm = _import_llm()

    with _fake_ollama([SPACED_DIGIT_LEAK_TEMPLATE]) as server:
        counts: dict[str, Any] = llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=42,
        )

    assert counts["rejected"].get("leaked_value", 0) == 1


def test_dashed_digit_run_rejected_as_leaked_value(tmp_path: Path) -> None:
    """Eleven digits separated by dashes = run of 11 → leaked_value."""
    llm = _import_llm()

    with _fake_ollama([DASHED_DIGIT_LEAK_TEMPLATE]) as server:
        counts: dict[str, Any] = llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=42,
        )

    assert counts["rejected"].get("leaked_value", 0) == 1


def test_six_digit_amount_is_not_leaked(tmp_path: Path) -> None:
    """'250 000 zł' (6 digits, spaces counted) does not trigger leaked_value."""
    llm = _import_llm()

    with _fake_ollama([AMOUNT_VALID_TEMPLATE]) as server:
        counts: dict[str, Any] = llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=42,
        )

    assert counts["accepted"] == 1
    assert counts["rejected"].get("leaked_value", 0) == 0


# ---------------------------------------------------------------------------
# Validation order: unknown_label fires before too_few_placeholders
# ---------------------------------------------------------------------------


def test_unknown_label_checked_before_placeholder_count(tmp_path: Path) -> None:
    """{{FOO}} + {{PESEL}} (only 2 total) → unknown_label fires, not too_few."""
    llm = _import_llm()
    template = "Formularz:\nPole: {{FOO}}\nPESEL: {{PESEL}}\nTreść."

    with _fake_ollama([template]) as server:
        counts: dict[str, Any] = llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=42,
        )

    # parse() raises TemplateError(reason='Unknown label') → unknown_label, not too_few.
    assert counts["rejected"].get("unknown_label", 0) == 1
    assert counts["rejected"].get("too_few_placeholders", 0) == 0


# ---------------------------------------------------------------------------
# No digit-run joining across placeholder boundaries
# ---------------------------------------------------------------------------


def test_placeholder_removal_prevents_cross_boundary_digit_run(tmp_path: Path) -> None:
    """4 digits | placeholder | 4 digits: removal must not create an 8-digit run."""
    llm = _import_llm()
    # After placeholder removal, "1234" and "5678" are separated by the replacement
    # character — they must not merge into a forbidden 8-digit run.
    template = (
        "FORMULARZ\n\n"
        "Ref: 1234{{PESEL}}5678\n"
        "Dowód: {{NR_DOWODU}}\n"
        "Karta: {{NR_KARTY}}\n"
        "IBAN: {{IBAN}}\n\n"
        "Treść."
    )

    with _fake_ollama([template]) as server:
        counts: dict[str, Any] = llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=42,
        )

    # Must not be rejected as leaked_value due to a spurious cross-placeholder join.
    assert counts["rejected"].get("leaked_value", 0) == 0
    assert counts["accepted"] == 1


def test_unsupported_known_label_lek_rejected_as_unknown_label(tmp_path: Path) -> None:
    """Template with {{LEK}} (known Label member, but no generator) → unknown_label."""
    llm = _import_llm()
    template = "Formularz:\nLek: {{LEK}}\nPESEL: {{PESEL}}\nIBAN: {{IBAN}}\nTreść."
    with _fake_ollama([template]) as server:
        counts: dict[str, Any] = llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=42,
        )
    assert counts["rejected"].get("unknown_label", 0) == 1


def test_redirect_request_is_refused(tmp_path: Path) -> None:
    """HTTP redirect from fake server → OllamaURLError."""
    llm = _import_llm()

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:11434/api/tags")
            self.end_headers()

        def do_POST(self) -> None:
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:11434/api/generate")
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), RedirectHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(llm.OllamaURLError, match="refusing redirect"):
            llm.write_templates(
                doc_type="zgloszenie_szkody",
                count=1,
                out=tmp_path,
                model=_FAKE_MODEL,
                ollama_url=f"http://127.0.0.1:{port}",
                seed=42,
            )
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


def test_model_mismatch_raises_unreachable(tmp_path: Path) -> None:
    """Requested model not in /api/tags → OllamaUnreachableError."""
    llm = _import_llm()
    with _fake_ollama([VALID_ZGLOSZENIE], model_name="other-model", digest="abc") as server:
        with pytest.raises(llm.OllamaUnreachableError):
            llm.write_templates(
                doc_type="zgloszenie_szkody",
                count=1,
                out=tmp_path,
                model="nonexistent-model",
                ollama_url=server.url,
                seed=42,
            )


def test_malformed_existing_manifest_raises_value_error(tmp_path: Path) -> None:
    """Malformed manifest.json (not a JSON array) → ValueError."""
    llm = _import_llm()
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"not": "a list"}', encoding="utf-8")

    with _fake_ollama([VALID_ZGLOSZENIE]) as server:
        with pytest.raises(ValueError, match="Manifest must be a JSON array"):
            llm.write_templates(
                doc_type="zgloszenie_szkody",
                count=1,
                out=tmp_path,
                model=_FAKE_MODEL,
                ollama_url=server.url,
                seed=42,
            )


def test_cross_doc_type_deduplication(tmp_path: Path) -> None:
    """Template written under one doc_type is deduplicated when generated under another."""
    llm = _import_llm()
    with _fake_ollama([VALID_ZGLOSZENIE]) as server:
        counts1 = llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=1,
        )
    assert counts1["accepted"] == 1

    with _fake_ollama([VALID_ZGLOSZENIE]) as server:
        counts2 = llm.write_templates(
            doc_type="umowa_kredytowa",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=2,
        )
    assert counts2["accepted"] == 0
    assert counts2["rejected"].get("duplicate", 0) == 1


def test_proxy_environment_is_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Proxy environment variables must be ignored by the zero-proxy opener."""
    llm = _import_llm()
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:9999")
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:9999")

    with _fake_ollama([VALID_ZGLOSZENIE]) as server:
        counts = llm.write_templates(
            doc_type="zgloszenie_szkody",
            count=1,
            out=tmp_path,
            model=_FAKE_MODEL,
            ollama_url=server.url,
            seed=42,
        )
    assert counts["accepted"] == 1
