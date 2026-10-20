"""Payment-card detector and Luhn checksum validator.

Candidate patterns:
- 16 digits, contiguous or in 4 groups of 4 separated by spaces or dashes.
- Contiguous runs of 13-15 or 17-19 digits that pass the Luhn check.

The span covers separators when they are present.
"""

from __future__ import annotations

import re

from piitier.labels import Label
from piitier.spans import Span

# Pattern: 16 digits with optional separators (spaces or dashes) in groups of 4
# Lookbehind/lookahead: not preceded/followed by a digit
_CARD_16_RE = re.compile(
    r"(?<!\d)"
    r"(\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4})"
    r"(?!\d)"
)

# Pattern: 13-15 or 17-19 contiguous digits
_CARD_LONG_RE = re.compile(
    r"(?<!\d)"
    r"(\d{13,15}|\d{17,19})"
    r"(?!\d)"
)


def _strip_separators(value: str) -> str:
    """Remove space and dash separator characters, leaving only digits."""
    return value.replace(" ", "").replace("-", "")


def _luhn_check(digits: str) -> bool:
    """Return ``True`` iff *digits* pass the Luhn checksum.

    Args:
        digits: String of digits only (no separators).
    """
    if not digits.isdigit() or len(digits) < 13 or len(digits) > 19:
        return False

    total = 0
    for i, digit in enumerate(reversed(digits)):
        n = int(digit)
        # Double every second digit (from the right, so every other position in the loop)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n

    return total % 10 == 0


def is_valid(value: str) -> bool:
    """Return ``True`` iff *value* is a 16-digit card or passes Luhn validation.

    Pure function: no I/O, no globals, no logging.

    Args:
        value: Card number string with optional spaces/dashes between digit groups.
    """
    clean = _strip_separators(value)

    # 16 digits: always valid by shape
    if len(clean) == 16 and clean.isdigit():
        return True

    # 13-15 or 17-19 digits: valid only if Luhn passes
    if len(clean) in range(13, 16) or len(clean) in range(17, 20):
        return _luhn_check(clean)

    return False


def find(text: str) -> list[Span]:
    """Return every payment-card candidate span found in *text*.

    A 16-digit card (by shape) or a long digit run (13-15 or 17-19 digits) that
    fails Luhn is returned with ``status="suspect"`` — it is never dropped
    (CLAUDE.md invariant 6).

    Offsets are in original-input character positions: ``text[span.start:span.end]``
    reproduces the matched token including any separator characters.
    """
    spans: list[Span] = []
    seen_ranges = set()  # Track (start, end) to avoid duplicates

    # Find 16-digit patterns first
    for match in _CARD_16_RE.finditer(text):
        raw = match.group(1)
        clean = _strip_separators(raw)

        # Skip if the cleaned version isn't exactly 16 digits
        if len(clean) != 16 or not clean.isdigit():
            continue

        # 16-digit cards are valid by shape
        status = "valid"

        span_key = (match.start(), match.end())
        if span_key not in seen_ranges:
            seen_ranges.add(span_key)
            spans.append(
                Span(
                    start=match.start(),
                    end=match.end(),
                    label=Label.NR_KARTY,
                    source="rule",
                    score=1.0,
                    status=status,
                )
            )

    # Find longer digit runs (13-15 or 17-19 digits) that pass Luhn
    for match in _CARD_LONG_RE.finditer(text):
        raw = match.group(1)
        clean = _strip_separators(raw)

        # Only consider runs that are 13-15 or 17-19 digits
        if len(clean) not in range(13, 16) and len(clean) not in range(17, 20):
            continue
        if not clean.isdigit():
            continue

        span_key = (match.start(), match.end())
        if span_key not in seen_ranges:
            luhn_valid = _luhn_check(clean)
            status = "valid" if luhn_valid else "suspect"
            seen_ranges.add(span_key)
            spans.append(
                Span(
                    start=match.start(),
                    end=match.end(),
                    label=Label.NR_KARTY,
                    source="rule",
                    score=1.0,
                    status=status,
                )
            )

    spans.sort(key=lambda s: s.start)
    return spans
