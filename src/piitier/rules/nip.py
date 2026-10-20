"""NIP detector and checksum validator.

NIP (Numer Identyfikacji Podatkowej) is the Polish tax identification number (10 digits).

Checksum
--------
Weights ``(6, 5, 7, 2, 3, 4, 5, 6, 7)`` are applied to the first 9 digits.
The check digit at position 9 must equal ``sum % 11``.
If the sum mod 11 equals 10, the NIP is invalid (never valid).

Format variants
---------------
Candidates by shape:
- 10 contiguous digits (e.g., ``5260001246``)
- Grouped with dashes (e.g., ``526-000-12-46``, ``526-00-01-246``)
- Optional ``PL`` prefix (e.g., ``PL5260001246``)

With keyword:
- After ``NIP`` or ``VAT ID`` (case-insensitive), any single space/tab/dash separators.
- The span covers the number, prefix and separators, but not the keyword.

KRS exclusion
-------------
A 10-digit run preceded by the keyword ``KRS`` within 40 characters is not a NIP candidate.
"""

from __future__ import annotations

import re

from piitier.labels import Label
from piitier.spans import Span

_WEIGHTS: tuple[int, ...] = (6, 5, 7, 2, 3, 4, 5, 6, 7)

# One separator character (space, tab, or dash) is optional between any two digits.
_SEP = r"[ \t-]?"

# Without a keyword, only contiguous digits and the two standard dash layouts
# are candidates. Do not extract a suffix of a longer separated digit run.
_NIP_RE = re.compile(
    r"(?<!\d)(?<!\d[ \t-])"
    r"(PL)?(\d{10}|\d{3}-\d{3}-\d{2}-\d{2}|\d{3}-\d{2}-\d{2}-\d{3})"
    r"(?!" + _SEP + r"\d)",
)

# A keyword permits arbitrary single separators; include an optional PL prefix.
_NIP_KEYWORD_RE = re.compile(
    r"\b(?:NIP|VAT[ \t]+ID)\b[ \t:,-]*"
    r"((?:PL)?\d(?:[ \t-]?\d){9})(?![ \t-]?\d)",
    re.IGNORECASE,
)


def _strip_separators(value: str) -> str:
    """Remove space, tab, and dash separator characters, leaving only digits and PL prefix."""
    return value.replace(" ", "").replace("\t", "").replace("-", "")


def _checksum_ok(digits: str) -> bool:
    """Return ``True`` when the check digit is correct.

    Args:
        digits: Exactly 10 digit characters (no separators, no prefix).
    """
    if len(digits) != 10 or not digits.isdigit():
        return False
    total = sum(w * int(d) for w, d in zip(_WEIGHTS, digits[:9]))
    check = total % 11
    # A check of 10 is never valid
    if check == 10:
        return False
    return check == int(digits[9])


def is_valid(value: str) -> bool:
    """Return ``True`` iff *value* passes NIP checksum validation.

    Pure function: no I/O, no globals, no logging.

    Args:
        value: Exactly 10 digit characters; separators and prefix must be stripped before calling.
    """
    return _checksum_ok(value)


def find(text: str) -> list[Span]:
    """Return every NIP candidate span found in *text*.

    A candidate whose checksum fails validation is returned with ``status="suspect"`` —
    it is never dropped (CLAUDE.md invariant 6).

    Offsets are in original-input character positions: ``text[span.start:span.end]``
    reproduces the matched token including any separator characters and prefix.
    """
    spans: list[Span] = []

    # First pass: keyword-based detection (NIP or VAT ID keyword).
    for match in _NIP_KEYWORD_RE.finditer(text):
        raw = match.group(1)
        digits = _strip_separators(raw).upper().removeprefix("PL")

        # Skip if not exactly 10 digits
        if len(digits) != 10 or not digits.isdigit():
            continue

        match_start = match.start(1)
        preceding_text = text[max(0, match_start - 40) : match_start]
        if re.search(r"\bKRS\b", preceding_text, re.IGNORECASE):
            continue

        checksum_valid = _checksum_ok(digits)
        status = "valid" if checksum_valid else "suspect"

        spans.append(
            Span(
                start=match.start(1),
                end=match.end(1),
                label=Label.NIP,
                source="rule",
                score=1.0,
                status=status,
            )
        )

    # Second pass: shape-based detection (contiguous or grouped digits, with optional PL prefix).
    for match in _NIP_RE.finditer(text):
        # Extract matched components:
        # group(1) is the optional PL prefix (included in the span)
        # group(2) is the 10-digit part with possible separators
        digits_with_seps = match.group(2)  # The 10-digit part with possible separators

        # Strip separators only from the digit part, not the prefix
        digits = _strip_separators(digits_with_seps)

        # Skip if not exactly 10 digits (should not happen with the regex, but be safe)
        if len(digits) != 10 or not digits.isdigit():
            continue

        # KRS exclusion: if preceded by KRS keyword within 40 characters, skip
        match_start = match.start()
        search_start = max(0, match_start - 40)
        preceding_text = text[search_start:match_start]
        if re.search(r"\bKRS\b", preceding_text, re.IGNORECASE):
            continue

        checksum_valid = _checksum_ok(digits)
        status = "valid" if checksum_valid else "suspect"

        spans.append(
            Span(
                start=match.start(),
                end=match.end(),
                label=Label.NIP,
                source="rule",
                score=1.0,
                status=status,
            )
        )

    # Remove duplicates and sort by start offset
    seen = set()
    unique_spans: list[Span] = []
    for span in sorted(spans, key=lambda s: (s.start, s.end)):
        key = (span.start, span.end)
        if key not in seen:
            seen.add(key)
            unique_spans.append(span)

    return unique_spans
