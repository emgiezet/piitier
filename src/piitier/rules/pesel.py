"""PESEL detector and checksum validator.

PESEL is the Polish national identification number (11 digits).

Checksum
--------
Weights ``(1, 3, 7, 9, 1, 3, 7, 9, 1, 3)`` are applied to the first 10 digits.
The check digit at position 10 must equal ``(10 - sum % 10) % 10``.

Birth-date encoding
-------------------
Month encodes the century by adding an offset to the calendar month (1–12):

* +0  → 1900–1999  (encoded month 01–12)
* +20 → 2000–2099  (encoded month 21–32)
* +40 → 2100–2199  (encoded month 41–52)
* +60 → 2200–2299  (encoded month 61–72)
* +80 → 1800–1899  (encoded month 81–92)

Phone-number exclusion
----------------------
A candidate immediately following ``+`` is never a PESEL (``+48…`` pattern).
Candidates whose raw digits start with ``00`` (international country-code prefix)
are also excluded.
"""

from __future__ import annotations

import re
from datetime import date

from piitier.labels import Label
from piitier.spans import Span

_WEIGHTS: tuple[int, ...] = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)

# One separator character (space, tab, or dash) is optional between any two digits.
_SEP = r"[ \t-]?"

# Lookbehind: not preceded by a digit or by '+' (phone-number prefix exclusion).
# Lookahead:  not followed by an optional separator then a digit (prevents a
#             12+-digit run from matching at the first 11 positions).
_PESEL_RE = re.compile(
    r"(?<![\d+])"
    r"(\d(?:" + _SEP + r"\d){10})"
    r"(?!" + _SEP + r"\d)",
)


def _strip_separators(value: str) -> str:
    """Remove space, tab, and dash separator characters, leaving only digits."""
    return value.replace(" ", "").replace("\t", "").replace("-", "")


def _valid_calendar_date(year: int, month: int, day: int) -> bool:
    """Return ``True`` if ``(year, month, day)`` is a valid calendar date."""
    try:
        date(year, month, day)
        return True
    except ValueError:
        return False


def _decode_birth_date(digits: str) -> tuple[int, int, int] | None:
    """Decode birth ``(year, month, day)`` from an 11-digit PESEL string.

    Returns ``None`` when the encoded month does not fall in any recognised
    century range (e.g. encoded month 13 or 93).
    """
    yy = int(digits[0:2])
    encoded_month = int(digits[2:4])
    day = int(digits[4:6])

    if 1 <= encoded_month <= 12:
        return 1900 + yy, encoded_month, day
    if 21 <= encoded_month <= 32:
        return 2000 + yy, encoded_month - 20, day
    if 41 <= encoded_month <= 52:
        return 2100 + yy, encoded_month - 40, day
    if 61 <= encoded_month <= 72:
        return 2200 + yy, encoded_month - 60, day
    if 81 <= encoded_month <= 92:
        return 1800 + yy, encoded_month - 80, day
    return None


def _checksum_ok(digits: str) -> bool:
    """Return ``True`` when the 11th digit is the correct PESEL check digit."""
    total = sum(w * int(d) for w, d in zip(_WEIGHTS, digits))
    return (10 - total % 10) % 10 == int(digits[10])


def is_valid(value: str) -> bool:
    """Return ``True`` iff *value* passes both PESEL checksum and birth-date validation.

    Pure function: no I/O, no globals, no logging.

    Args:
        value: Exactly 11 digit characters; separators must be stripped before calling.
    """
    if len(value) != 11 or not value.isdigit():
        return False
    if not _checksum_ok(value):
        return False
    decoded = _decode_birth_date(value)
    if decoded is None:
        return False
    year, month, day = decoded
    return _valid_calendar_date(year, month, day)


def find(text: str) -> list[Span]:
    """Return every PESEL candidate span found in *text*.

    A candidate whose checksum or birth date fails validation is returned with
    ``status="suspect"`` — it is never dropped (CLAUDE.md invariant 6).

    Offsets are in original-input character positions: ``text[span.start:span.end]``
    reproduces the matched token including any separator characters.
    """
    spans: list[Span] = []
    for match in _PESEL_RE.finditer(text):
        raw = match.group(1)
        digits = _strip_separators(raw)

        # Phone-number exclusion: sequences whose raw digits start with the
        # international-dialling prefix 00 are treated as phone numbers.
        if digits.startswith("00"):
            continue

        checksum_valid = _checksum_ok(digits)
        date_valid = False
        decoded = _decode_birth_date(digits)
        if decoded is not None:
            year, month, day = decoded
            date_valid = _valid_calendar_date(year, month, day)

        status = "valid" if (checksum_valid and date_valid) else "suspect"
        spans.append(
            Span(
                start=match.start(),
                end=match.end(),
                label=Label.PESEL,
                source="rule",
                score=1.0,
                status=status,
            )
        )
    return spans
