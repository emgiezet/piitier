"""Payment-card detector and Luhn checksum validator.

Candidate patterns:
- 16 digits, contiguous or in 4 groups of 4 separated by spaces or dashes.
- Contiguous runs of 13-15 or 17-19 digits that pass the Luhn check.

The span covers separators when they are present.

Context boundaries (false-positive suppression):
- Ungrouped candidates immediately preceded by ``digit + '.'`` or followed by
  ``'.' + digit`` are suppressed as decimal fragments, e.g. ``0.9937050359712231``.
- Ungrouped candidates with adjacent letters are suppressed only when their whole
  alphanumeric/underscore token is ASCII hexadecimal (optionally ``0x``/``0X``
  prefixed), e.g. ``cc4111111111111111ff`` or ``abc4111111111111111``.
- These narrow exclusions avoid matching report floats and hex hashes. Commas can
  delimit CSV fields: adjacent ``digit + ','`` or ``',' + digit`` makes a candidate
  ``suspect``, never absent. Non-hex word/underscore adjacency also means ``suspect``
  (OCR-glued cards). Checksum-invalid 16-digit shapes remain ``suspect``.
- Grouped cards are not decimal/hex fragments. A trailing sentence period is not
  a decimal boundary and remains accepted.
"""

from __future__ import annotations

import re

from piitier.labels import Label
from piitier.spans import Span

# Digit guards prevent extracting a candidate from a longer contiguous digit run.
# Context is classified after matching so commas and OCR-glued words cannot hide cards.
_CARD_16_RE = re.compile(r"(?<!\d)(\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4})(?!\d)")
_CARD_LONG_RE = re.compile(r"(?<!\d)(\d{13,15}|\d{17,19})(?!\d)")
_HEX_TOKEN_RE = re.compile(r"(?:0[xX])?[0-9a-fA-F]+")


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
    """Return ``True`` iff *value* passes Luhn validation.

    Pure function: no I/O, no globals, no logging.

    Args:
        value: Card number string with optional spaces/dashes between digit groups.
    """
    clean = _strip_separators(value)
    if len(clean) not in range(13, 20):
        return False
    return _luhn_check(clean)


def _context_status(text: str, start: int, end: int, *, grouped: bool = False) -> str | None:
    """Return a context status, or ``None`` for a decimal/hex fragment."""
    left_numeric = start >= 2 and text[start - 2].isdigit()
    right_numeric = end + 1 < len(text) and text[end + 1].isdigit()
    if not grouped and (
        (left_numeric and text[start - 1] == ".") or (right_numeric and text[end] == ".")
    ):
        return None

    word_glued = (start > 0 and (text[start - 1].isalpha() or text[start - 1] == "_")) or (
        end < len(text) and (text[end].isalpha() or text[end] == "_")
    )
    if word_glued:
        left, right = start, end
        while left > 0 and (text[left - 1].isalnum() or text[left - 1] == "_"):
            left -= 1
        while right < len(text) and (text[right].isalnum() or text[right] == "_"):
            right += 1
        if not grouped and _HEX_TOKEN_RE.fullmatch(text, left, right):
            return None
        return "suspect"

    if (left_numeric and text[start - 1] == ",") or (right_numeric and text[end] == ","):
        return "suspect"
    return "valid"


def find(text: str) -> list[Span]:
    """Return every payment-card candidate span found in *text*.

    A 16-digit card shape that fails Luhn is returned with ``status="suspect"``.
    Other supported lengths require Luhn validation. Ambiguous contexts are also
    ``suspect``; only the decimal/hex contexts documented above are suppressed.

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

        context = _context_status(text, match.start(), match.end(), grouped=len(raw) != 16)
        if context is None:
            continue

        # 16-digit cards are candidates by shape; checksum decides status
        luhn_valid = _luhn_check(clean)
        status = context if luhn_valid else "suspect"

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

        # Only consider runs that are 13-15 or 17-19 digits and pass Luhn
        if len(clean) not in range(13, 16) and len(clean) not in range(17, 20):
            continue
        if not clean.isdigit():
            continue
        if not _luhn_check(clean):
            continue

        context = _context_status(text, match.start(), match.end())
        if context is None:
            continue

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
                    status=context,
                )
            )

    spans.sort(key=lambda s: s.start)
    return spans
