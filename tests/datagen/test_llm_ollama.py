"""Integration tests for piitier.datagen.llm write-templates with real Ollama (UC-37).

Marked with @pytest.mark.integration — requires a running local Ollama instance
with Bielik 11B Q8_0 model installed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_uc37_real_ollama_cli_workflow(tmp_path: Path) -> None:
    """UC-37: write-templates CLI -> build CLI -> check CLI with real Ollama."""
    model_tag = "hf.co/SpeakLeash/Bielik-11B-v3.0-Instruct-GGUF:Q8_0"
    ollama_url = "http://127.0.0.1:11434"

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
            str(tmp_path / "templates"),
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

    dataset_out = tmp_path / "dataset"
    res_build = subprocess.run(
        [
            sys.executable,
            "-m",
            "piitier.datagen",
            "build",
            "--templates",
            str(tmp_path / "templates"),
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
