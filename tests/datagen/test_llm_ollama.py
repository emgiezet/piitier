"""Integration tests for piitier.datagen.llm write-templates with real Ollama (UC-37).

Marked with @pytest.mark.integration — requires a running local Ollama instance
with Bielik 11B Q8_0 model installed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_uc37_real_ollama_cli_workflow(tmp_path: Path) -> None:
    """UC-37: write-templates CLI -> build CLI -> check CLI with real Ollama."""
    model_tag = "hf.co/SpeakLeash/Bielik-11B-v3.0-Instruct-GGUF:Q8_0"
    ollama_url = "http://127.0.0.1:11434"

    templates_dir = tmp_path / "templates"
    res_wt = subprocess.run(
        [
            sys.executable,
            "-m",
            "piitier.datagen",
            "write-templates",
            "--doc-type",
            "zgloszenie_szkody",
            "--count",
            "3",
            "--out",
            str(templates_dir),
            "--model",
            model_tag,
            "--ollama-url",
            ollama_url,
            "--seed",
            "42",
            "--temperature",
            "0.2",
        ],
        capture_output=True,
        text=True,
    )
    assert res_wt.returncode == 0, f"write-templates failed: {res_wt.stderr}"

    manifest_file = templates_dir / "manifest.json"
    assert manifest_file.exists()
    records = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert isinstance(records, list) and len(records) > 0
    last_record = records[-1]
    accepted = last_record.get("accepted", 0)
    rejected = last_record.get("rejected", {})
    assert accepted >= 1, f"accepted={accepted}, rejected={rejected}"

    dataset_out = tmp_path / "dataset"
    res_build = subprocess.run(
        [
            sys.executable,
            "-m",
            "piitier.datagen",
            "build",
            "--templates",
            str(templates_dir),
            "--n",
            "10",
            "--seed",
            "42",
            "--out",
            str(dataset_out),
        ],
        capture_output=True,
        text=True,
    )
    assert res_build.returncode == 0, f"build failed: {res_build.stderr}"

    res_check = subprocess.run(
        [
            sys.executable,
            "-m",
            "piitier.datagen",
            "check",
            str(dataset_out),
        ],
        capture_output=True,
        text=True,
    )
    assert res_check.returncode == 0, f"check failed: {res_check.stderr}"
