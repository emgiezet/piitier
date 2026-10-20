"""ID-card (dowód osobisty) detector and checksum validator.

Pattern: 3 uppercase letters + 6 digits, with optional space after the letters.
The 4th character (first digit after letters) is the check digit.

Checksum: letters A=10, B=11, ..., Z=35.
Weights: 7,3,1 on letters, 7,3,1,7,3 on digits 5-9 (skipping check digit at position 4).
Check digit = weighted sum mod 10.
"""

from __future__ import annotations

import re

from piitier.labels import Label
from piitier.spans import Span

# Letter to numeric value: A=10, B=11, ..., Z=35
_LETTER_VALUES = {chr(ord("A") + i): 10 + i for i in range(26)}

# Weights for the 3 letters and 5 check digits (skipping the digit at position 4)
_WEIGHTS_LETTERS = (7, 3, 1)
_WEIGHTS_DIGITS = (7, 3, 1, 7, 3)  # Applied to positions 5-9 (skipping position 4)

# Pattern: 3 uppercase letters + optional space + 6 digits
# Lookbehind/lookahead: not preceded/followed by letters or digits
_ID_CARD_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"([A-Z]{3}) ?(\d{6})"
    r"(?![A-Za-z0-9])"
)


def _strip_separator(value: str) -> str:
    """Remove space separator, leaving only letters and digits."""
    return value.replace(" ", "")


def _checksum_ok(letters: str, digits: str) -> bool:
    """Return ``True`` when the digit at position 4 (index 0 in digits) is the correct check digit.

    Args:
        letters: 3 uppercase letters.
        digits: 6 digits (positions 4–9).
    """
    if len(letters) != 3 or len(digits) != 6:
        return False
    if not letters.isupper() or not letters.isalpha():
        return False
    if not digits.isdigit():
        return False

    # Calculate weighted sum of letters
    letter_sum = sum(w * _LETTER_VALUES[letter] for w, letter in zip(_WEIGHTS_LETTERS, letters))

    # Calculate weighted sum of digits (positions 5-9, skipping position 4 which is check digit)
    digit_positions = [1, 2, 3, 4, 5]  # Skip index 0 (the check digit itself)
    digit_sum = sum(w * int(digits[pos]) for w, pos in zip(_WEIGHTS_DIGITS, digit_positions))

    total = (letter_sum + digit_sum) % 10
    check_digit = int(digits[0])  # The check digit is at position 4 (index 0 in digits)
    return total == check_digit


def is_valid(value: str) -> bool:
    """Return ``True`` iff *value* passes ID-card checksum validation.

    Pure function: no I/O, no globals, no logging.

    Args:
        value: String in format "ABC123456" or "ABC 123456" (separators stripped before call).
    """
    # Remove separator for validation
    clean = _strip_separator(value)

    if len(clean) != 9:
        return False

    letters = clean[:3]
    digits = clean[3:]

    if not letters.isupper() or not letters.isalpha():
        return False
    if not digits.isdigit():
        return False

    return _checksum_ok(letters, digits)


def find(text: str) -> list[Span]:
    """Return every ID-card candidate span found in *text*.

    A candidate whose checksum fails validation is returned with
    ``status="suspect"`` — it is never dropped (CLAUDE.md invariant 6).

    Offsets are in original-input character positions: ``text[span.start:span.end]``
    reproduces the matched token including any separator characters.
    """
    spans: list[Span] = []
    for match in _ID_CARD_RE.finditer(text):
        letters = match.group(1)
        digits = match.group(2)

        checksum_valid = _checksum_ok(letters, digits)
        status = "valid" if checksum_valid else "suspect"

        spans.append(
            Span(
                start=match.start(),
                end=match.end(),
                label=Label.NR_DOWODU,
                source="rule",
                score=1.0,
                status=status,
            )
        )

    return spans
