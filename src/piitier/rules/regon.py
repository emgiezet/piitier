"""REGON detector and checksum validator.

REGON (Rejestr Gospodarki Narodowej) is the Polish business registry number.
Two variants: 9-digit (REGON-9) and 14-digit (REGON-14).

Checksum
--------
REGON-9: Weights ``(8, 9, 2, 3, 4, 5, 6, 7)`` are applied to the first 8 digits.
         Check digit = sum % 11.

REGON-14: Weights ``(2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8)`` are applied to the first 13 digits.
          Check digit = sum % 11, where 10 → 0.

Format variants
---------------
- REGON-14: 14 contiguous digits (candidate by shape, no keyword needed)
- REGON-9: 9 contiguous digits **only** after the keyword ``REGON`` (because a bare 9-digit run
  is usually a phone number).

Bare 9-digit runs without the REGON keyword are not REGON candidates.
"""

from __future__ import annotations

import re

from piitier.labels import Label
from piitier.spans import Span

_WEIGHTS_9: tuple[int, ...] = (8, 9, 2, 3, 4, 5, 6, 7)
_WEIGHTS_14: tuple[int, ...] = (2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8)

# Pattern for REGON-14 (14 contiguous digits).
# Lookbehind: not preceded by a digit.
# Lookahead: not followed by a digit.
_REGON_14_RE = re.compile(r"(?<!\d)(\d{14})(?!\d)")
# Pattern for REGON-9 after the REGON keyword.
# The keyword can be followed by optional separators (space, tab, dash, colon, etc.).
# We accept any non-digit characters as separators.
_REGON_9_KEYWORD_RE = re.compile(
    r"(?:REGON)[\s:,-]*(\d{9})",
    re.IGNORECASE,
)


def _checksum_ok_9(digits: str) -> bool:
    """Return ``True`` when the REGON-9 check digit is correct.

    Args:
        digits: Exactly 9 digit characters.
    """
    if len(digits) != 9 or not digits.isdigit():
        return False
    total = sum(w * int(d) for w, d in zip(_WEIGHTS_9, digits[:8]))
    check = total % 11
    return check == int(digits[8])


def _checksum_ok_14(digits: str) -> bool:
    """Return ``True`` when the REGON-14 check digit is correct.

    Args:
        digits: Exactly 14 digit characters.
    """
    if len(digits) != 14 or not digits.isdigit():
        return False
    total = sum(w * int(d) for w, d in zip(_WEIGHTS_14, digits[:13]))
    check = total % 11
    # 10 maps to 0
    check = 0 if check == 10 else check
    return check == int(digits[13])


def is_valid(value: str) -> bool:
    """Return ``True`` iff *value* passes REGON checksum validation.

    Pure function: no I/O, no globals, no logging.

    Args:
        value: Exactly 9 or 14 digit characters.
    """
    if len(value) == 9:
        return _checksum_ok_9(value)
    elif len(value) == 14:
        return _checksum_ok_14(value)
    return False


def find(text: str) -> list[Span]:
    """Return every REGON candidate span found in *text*.

    A candidate whose checksum fails validation is returned with ``status="suspect"`` —
    it is never dropped (CLAUDE.md invariant 6).

    Offsets are in original-input character positions: ``text[span.start:span.end]``
    reproduces the matched token.
    """
    spans: list[Span] = []

    # First pass: REGON-9 after keyword.
    for match in _REGON_9_KEYWORD_RE.finditer(text):
        digits = match.group(1)
        checksum_valid = _checksum_ok_9(digits)
        status = "valid" if checksum_valid else "suspect"

        spans.append(
            Span(
                start=match.start(1),
                end=match.end(1),
                label=Label.REGON,
                source="rule",
                score=1.0,
                status=status,
            )
        )

    # Second pass: REGON-14 (bare 14-digit runs).
    for match in _REGON_14_RE.finditer(text):
        digits = match.group(1)
        checksum_valid = _checksum_ok_14(digits)
        status = "valid" if checksum_valid else "suspect"

        spans.append(
            Span(
                start=match.start(),
                end=match.end(),
                label=Label.REGON,
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
