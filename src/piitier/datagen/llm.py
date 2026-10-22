"""Local Ollama synthetic template writer (PII-2-e)."""

from __future__ import annotations

import hashlib
import http.client
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import piitier
from piitier.datagen.render import _ADDRESS_LABELS, _PERSON_LABELS
from piitier.datagen.template import Placeholder, Template, TemplateError, parse
from piitier.datagen.values import _GENERATORS


class OllamaURLError(Exception):
    """Raised when an invalid or non-loopback Ollama URL is provided."""


class OllamaUnreachableError(Exception):
    """Raised when Ollama server cannot be reached."""


_ALLOWED_DOC_TYPES = frozenset(
    {
        "zgloszenie_szkody",
        "umowa_kredytowa",
        "wyciag",
        "wypis_szpitalny",
        "mail_klienta",
        "polisa",
        "skierowanie",
        "transkrypcja_infolinii",
    }
)

_SUPPORTED_LABELS = frozenset(_GENERATORS) | _PERSON_LABELS | _ADDRESS_LABELS


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        raise OllamaURLError("refusing redirect")


def _get_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _NoRedirectHandler(),
    )


def _validate_ollama_url(url_str: str) -> None:
    try:
        parsed = urlparse(url_str)
    except Exception as e:
        raise OllamaURLError("refusing non-loopback ollama url") from e

    if parsed.scheme not in ("http", "https"):
        raise OllamaURLError("refusing non-loopback ollama url")

    if parsed.username or parsed.password or "@" in parsed.netloc:
        raise OllamaURLError("refusing non-loopback ollama url")

    hostname = parsed.hostname
    if not hostname:
        raise OllamaURLError("refusing non-loopback ollama url")

    if hostname.lower() not in ("localhost", "127.0.0.1", "::1", "[::1]"):
        raise OllamaURLError("refusing non-loopback ollama url")


def write_templates(
    doc_type: str,
    count: int,
    out: Path,
    model: str = "hf.co/SpeakLeash/Bielik-11B-v3.0-Instruct-GGUF:Q8_0",
    ollama_url: str = "http://127.0.0.1:11434",
    seed: int | None = None,
    temperature: float = 0.2,
) -> dict[str, Any]:
    if (
        not isinstance(doc_type, str)
        or doc_type not in _ALLOWED_DOC_TYPES
        or "/" in doc_type
        or "\\" in doc_type
        or ".." in doc_type
        or Path(doc_type).is_absolute()
    ):
        raise ValueError(f"Invalid doc_type: {doc_type}")

    _validate_ollama_url(ollama_url)

    prompts_dir = Path(__file__).parent / "prompts"
    prompt_file = prompts_dir / f"{doc_type}.txt"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found for doc_type: {doc_type}")
    prompt_bytes = prompt_file.read_bytes()
    prompt_sha256 = hashlib.sha256(prompt_bytes).hexdigest()
    prompt_text = prompt_bytes.decode("utf-8")

    # Load and validate existing manifest.json if present (must be valid JSON array, reject blank)
    manifest_path = out / "manifest.json"
    manifest_records: list[dict[str, Any]] = []
    if manifest_path.exists():
        m_content = manifest_path.read_text(encoding="utf-8")
        if not m_content.strip():
            raise ValueError("Manifest is blank or whitespace-only")
        try:
            parsed_json = json.loads(m_content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed existing manifest: {e}") from e

        if not isinstance(parsed_json, list):
            raise ValueError("Manifest must be a JSON array")
        manifest_records = parsed_json

    # Deduplicate against ALL template files under out (across all doc_types)
    seen_hashes: set[str] = set()
    if out.exists():
        for p_file in out.glob("**/*.txt"):
            if p_file.is_file():
                try:
                    content = p_file.read_bytes()
                    h = hashlib.sha256(content).hexdigest()
                    seen_hashes.add(h)
                except Exception as e:
                    raise ValueError(f"Unreadable template file: {p_file}") from e

    opener = _get_opener()
    tags_url = f"{ollama_url.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(tags_url, method="GET")
        with opener.open(req, timeout=10) as resp:
            raw_body = resp.read().decode("utf-8")
            try:
                data = json.loads(raw_body)
            except json.JSONDecodeError as e:
                raise OllamaUnreachableError(f"ollama not reachable at {ollama_url}") from e

            if not isinstance(data, dict):
                raise OllamaUnreachableError(f"ollama not reachable at {ollama_url}")

            digest: str | None = None
            norm_model = model.strip() if isinstance(model, str) else None
            if not norm_model:
                raise OllamaUnreachableError(f"ollama not reachable at {ollama_url}")
            norm_model_latest = norm_model + ":latest" if ":" not in norm_model else norm_model

            models_list = data.get("models", [])
            if not isinstance(models_list, list):
                raise OllamaUnreachableError(f"ollama not reachable at {ollama_url}")

            for m in models_list:
                if not isinstance(m, dict):
                    continue
                m_name = m.get("name")
                m_model = m.get("model")
                if isinstance(m_name, str) and isinstance(m_model, str):
                    s_name = m_name.strip()
                    s_model = m_model.strip()
                    if s_name in (norm_model, norm_model_latest) or s_model in (
                        norm_model,
                        norm_model_latest,
                    ):
                        d_val = m.get("digest")
                        if isinstance(d_val, str) and d_val.strip():
                            digest = d_val.strip()
                        break
            if not isinstance(digest, str) or not digest:
                raise OllamaUnreachableError(f"ollama not reachable at {ollama_url}")
    except (OSError, urllib.error.URLError, TimeoutError, http.client.HTTPException) as e:
        raise OllamaUnreachableError(f"ollama not reachable at {ollama_url}") from e
    except (OllamaURLError, OllamaUnreachableError):
        raise
    except Exception as e:
        raise OllamaUnreachableError(f"ollama not reachable at {ollama_url}") from e

    accepted = 0
    rejected: dict[str, int] = {
        "parse_error": 0,
        "unknown_label": 0,
        "too_few_placeholders": 0,
        "leaked_value": 0,
        "duplicate": 0,
    }

    generate_url = f"{ollama_url.rstrip('/')}/api/generate"

    for _ in range(count):
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt_text,
            "stream": False,
        }
        options: dict[str, Any] = {}
        if seed is not None:
            options["seed"] = seed
        if temperature is not None:
            options["temperature"] = temperature
        if options:
            payload["options"] = options

        try:
            req = urllib.request.Request(
                generate_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with opener.open(req, timeout=120) as resp:
                raw_res = resp.read().decode("utf-8")
                try:
                    res_data = json.loads(raw_res)
                except json.JSONDecodeError as e:
                    raise OllamaUnreachableError(f"ollama not reachable at {ollama_url}") from e
                if not isinstance(res_data, dict):
                    raise OllamaUnreachableError(f"ollama not reachable at {ollama_url}")
                text = res_data.get("response")
                if not isinstance(text, str):
                    raise OllamaUnreachableError(
                        f"ollama not reachable at {ollama_url}: non-string response"
                    )
        except (OSError, urllib.error.URLError, TimeoutError, http.client.HTTPException) as e:
            raise OllamaUnreachableError(f"ollama not reachable at {ollama_url}") from e
        except (OllamaURLError, OllamaUnreachableError):
            raise
        except Exception as e:
            raise OllamaUnreachableError(f"ollama not reachable at {ollama_url}") from e

        # 1. Parse as template
        try:
            parts = parse(Template(template_id="pending", doc_type=doc_type, text=text))
        except TemplateError as exc:
            if exc.reason == "Unknown label":
                rejected["unknown_label"] += 1
            else:
                rejected["parse_error"] += 1
            continue

        # Extract placeholder objects and literal chunks
        placeholders = [ph for ph in parts if isinstance(ph, Placeholder)]
        literals = [lit for lit in parts if isinstance(lit, str)]

        # Check every label is in _SUPPORTED_LABELS
        has_unknown = False
        for ph in placeholders:
            if ph.label not in _SUPPORTED_LABELS:
                has_unknown = True
                break
        if has_unknown:
            rejected["unknown_label"] += 1
            continue

        # 2. At least 3 placeholders (count only Placeholder objects)
        if len(placeholders) < 3:
            rejected["too_few_placeholders"] += 1
            continue

        # 3. Leaked value check: validate each parsed literal separately
        leaked = False
        for lit in literals:
            spans = piitier.detect(lit)
            has_digit_run = bool(re.search(r"\d(?:[ \-]?\d){6,}", lit))
            if spans or has_digit_run:
                leaked = True
                break
        if leaked:
            rejected["leaked_value"] += 1
            continue

        # 4. Duplicate check against ALL template files under out
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if h in seen_hashes:
            rejected["duplicate"] += 1
            continue

        # Accepted
        seen_hashes.add(h)
        accepted += 1
        template_id = f"{doc_type}-{h[:12]}"
        doc_dir = out / doc_type
        doc_dir.mkdir(parents=True, exist_ok=True)
        target_file = doc_dir / f"{template_id}.txt"
        target_file.write_text(text, encoding="utf-8")

    # Append invocation record to manifest records array
    new_record = {
        "model": model,
        "digest": digest,
        "prompt_sha256": prompt_sha256,
        "temperature": temperature,
        "seed": seed,
        "accepted": accepted,
        "rejected": {k: v for k, v in rejected.items() if v > 0},
    }
    manifest_records.append(new_record)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest_records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    return {
        "accepted": accepted,
        "rejected": {k: v for k, v in rejected.items() if v > 0},
    }
