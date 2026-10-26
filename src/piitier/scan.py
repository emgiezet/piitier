"""Find checksum-valid identifiers in files and report them by position, never by value.

Used by the ``piitier scan`` command and the ``piitier-scan`` pre-commit hook. Only rule spans
with ``status="valid"`` count: a value that passes its checksum is the kind a real document
contains, whereas ``suspect`` shapes (failed checksum) are too common in ordinary text to block
a commit on. Known synthetic values are listed in an allowlist as fingerprints, so the
allowlist itself never stores an identifier.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from piitier.labels import Label
from piitier.rules import detect_all


@dataclass(frozen=True)
class Finding:
    """One checksum-valid identifier: where it is and what it is, without the value."""

    path: Path
    line: int
    column: int
    label: Label
    fingerprint: str


def fingerprint(label: Label, value: str) -> str:
    """Return ``sha256("<LABEL>:<value>")`` as hex — the allowlist entry for a value."""
    return hashlib.sha256(f"{label.name}:{value}".encode()).hexdigest()


def read_allowlist(path: Path) -> frozenset[str]:
    """Read fingerprints, one per line; blank lines and ``#`` comments are ignored."""
    entries: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            entries.add(line)
    return frozenset(entries)


def scan_text(text: str, path: Path) -> list[Finding]:
    """Return a finding for every ``valid`` rule span in *text*, with 1-based line and column."""
    findings: list[Finding] = []
    for span in detect_all(text):
        if span.status != "valid":
            continue
        line_start = text.rfind("\n", 0, span.start) + 1
        findings.append(
            Finding(
                path=path,
                line=text.count("\n", 0, span.start) + 1,
                column=span.start - line_start + 1,
                label=span.label,
                fingerprint=fingerprint(span.label, text[span.start : span.end]),
            )
        )
    return findings


def scan_file(path: Path) -> list[Finding] | None:
    """Scan one file; return ``None`` when it is binary or not valid UTF-8 (skipped)."""
    data = path.read_bytes()
    if b"\x00" in data:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return scan_text(text, path)
