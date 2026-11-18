"""README installation instructions cover Windows and stay in sync with the rules (PII-14)."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_uc201_readme_documents_installation_per_platform() -> None:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    headings = re.findall(r"^#{2,3} (.+)$", text, flags=re.MULTILINE)
    start = headings.index("Installation")
    assert headings[start : start + 4] == [
        "Installation",
        "Linux and macOS",
        "Windows (PowerShell)",
        "Quick start",
    ]
    for snippet in (
        "winget install --id=astral-sh.uv -e",
        "uv python install 3.12",
        "uv sync",
        "PYTHONIOENCODING",
        "chcp 65001",
        "win_amd64",
    ):
        assert snippet in text, f"README.md is missing {snippet!r}"
    rules = (REPO_ROOT / ".claude" / "rules" / "python.md").read_text(encoding="utf-8")
    for command in ("uv sync --frozen", 'uv run pytest -q -m "not integration"'):
        assert command in rules, f"rule file no longer contains {command!r}"
        assert command in text, f"README.md is missing {command!r}"
