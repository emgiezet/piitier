"""CONTRIBUTING.md and the PR template stay complete and in sync with the rules (PII-12)."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _headings(path: Path) -> list[str]:
    return re.findall(r"^#{2,3} (.+)$", path.read_text(encoding="utf-8"), flags=re.MULTILINE)


def test_uc153_contributing_has_required_sections_and_rule_commands() -> None:
    text = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert _headings(REPO_ROOT / "CONTRIBUTING.md") == [
        "Workflow",
        "Hooks and verification",
        "Data and privacy",
        "Tests",
        "Results",
    ]
    rules = (REPO_ROOT / ".claude" / "rules" / "python.md").read_text(encoding="utf-8")
    for command in (
        "uv sync --frozen",
        'uv run pytest -q -m "not integration"',
        "uv run pytest -q -m integration",
    ):
        assert command in rules, f"rule file no longer contains {command!r}"
        assert command in text, f"CONTRIBUTING.md is missing {command!r}"
    assert "ai/<TICKET>-<slug>" in text
    assert "ai/<TICKET>-<slug>" in (REPO_ROOT / ".claude" / "sdlc.md").read_text(encoding="utf-8")


def test_uc154_pr_template_has_required_sections() -> None:
    template = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
    assert _headings(template) == [
        "Ticket and spec",
        "UC coverage",
        "Verification",
        "Privacy and data",
        "Model and benchmark impact",
        "Notes",
    ]
    text = template.read_text(encoding="utf-8")
    assert "uv run pre-commit run --all-files" in text
    assert "fail on the code before the fix" in text
