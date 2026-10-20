"""IBAN detector and checksum validator using mod 97.

Supports Polish NRB (PL-prefixed or bare 26-digit format) and foreign IBANs
(2 letters + 2 digits + 11-30 alphanumerics).
"""

from __future__ import annotations

import re

from piitier.labels import Label
from piitier.spans import Span


def _strip_spaces(value: str) -> str:
    """Remove space characters, leaving only alphanumerics."""
    return value.replace(" ", "")


def _char_to_number(char: str) -> str:
    """Convert a letter to its numeric representation for mod 97.

    A=10, B=11, ..., Z=35.
    """
    if char.isdigit():
        return char
    return str(ord(char.upper()) - ord("A") + 10)


def _mod97(iban_digits: str) -> int:
    """Calculate mod 97 for IBAN checksum validation.

    Move first 4 characters to the end, convert all letters to numbers,
    then compute mod 97.
    """
    # Rearrange: move first 4 chars (CC + check digits) to the end
    rearranged = iban_digits[4:] + iban_digits[:4]

    # Convert all letters to numbers
    numeric = "".join(_char_to_number(c) for c in rearranged)

    # Compute mod 97
    return int(numeric) % 97


def is_valid(value: str) -> bool:
    """Return True iff *value* is a valid IBAN or bare Polish NRB.

    Accepts:
    - Polish NRB: PL + 26 digits, or bare 26 digits
    - Foreign IBAN: 2 letters + 2 digits + 11-30 alphanumerics

    All formats accept spaces between digit groups. Checksum validation
    uses mod 97 (result must equal 1).
    """
    if not value or not isinstance(value, str):
        return False

    # Remove spaces for processing
    clean = _strip_spaces(value)

    # Polish IBAN with PL prefix
    if clean.upper().startswith("PL"):
        if len(clean) != 28:  # PL + 26 digits
            return False
        iban_digits = clean
    # Bare Polish NRB (26 digits, treat as PL + 26 digits for validation)
    elif len(clean) == 26 and clean.isdigit():
        iban_digits = "PL" + clean
    # Foreign IBAN: 2 letters + 2 digits + 11-30 alphanumerics
    elif len(clean) >= 15 and len(clean) <= 34:
        # Check format: 2 letters, 2 digits, rest alphanumerics
        if not (clean[:2].isalpha() and clean[2:4].isdigit()):
            return False
        # Verify rest are alphanumeric
        if not all(c.isalnum() for c in clean[4:]):
            return False
        iban_digits = clean
    else:
        return False

    # Verify all characters are alphanumeric (after spaces are removed)
    if not all(c.isalnum() for c in iban_digits):
        return False

    # Validate checksum: mod 97 must equal 1
    return _mod97(iban_digits) == 1


# Regex patterns for IBAN detection
# Polish IBAN: PL + 26 digits, with optional spaces between digit groups
# Bare Polish NRB: 26 digits, with optional spaces between groups
# Foreign IBAN: 2 letters + 2 digits + 11-30 alphanumerics, optionally spaced

_SEP = r"[ ]?"  # Single space separator between digit groups

# Polish NRB with PL prefix: PL + groups of 4 digits
_PL_IBAN_RE = re.compile(
    r"(?<![A-Z0-9])"  # Not preceded by alphanumeric (word boundary for uppercase)
    r"(PL[0-9]{2}(?:" + _SEP + r"[0-9]{4}){6})"
    r"(?![A-Z0-9])",
    re.IGNORECASE,
)

# Bare Polish NRB: 26 digits in groups of 4 with optional spaces
_BARE_NRB_RE = re.compile(
    r"(?<![A-Z0-9])"
    r"([0-9]{2}(?:" + _SEP + r"[0-9]{4}){6})"
    r"(?![A-Z0-9])",
)

# Foreign IBAN: 2 letters + 2 digits + up to 30 alphanumerics
# Allow grouping: typically 4-digit groups separated by spaces
# Last group can be 1-4 characters
_FOREIGN_IBAN_RE = re.compile(
    r"(?<![A-Z0-9])"
    r"([A-Z]{2}[0-9]{2}(?:" + _SEP + r"[A-Z0-9]{4})*(?:" + _SEP + r"[A-Z0-9]{1,4})?)"
    r"(?![A-Z0-9])",
    re.IGNORECASE,
)


def find(text: str) -> list[Span]:
    """Return every IBAN candidate span found in *text*.

    A candidate whose checksum fails is returned with status='suspect'
    and is never dropped (invariant 6).

    Offsets are in original-input character positions: text[span.start:span.end]
    reproduces the matched token including any spaces.
    """
    spans: list[Span] = []
    covered_ranges: list[tuple[int, int]] = []

    def _is_overlapping(start: int, end: int) -> bool:
        """Check if a span overlaps with already-covered ranges."""
        for c_start, c_end in covered_ranges:
            if start < c_end and end > c_start:
                return True
        return False

    # Find Polish IBANs (with PL prefix)
    for match in _PL_IBAN_RE.finditer(text):
        raw = match.group(1)
        if not _is_overlapping(match.start(1), match.end(1)):
            checksum_valid = is_valid(raw)
            status = "valid" if checksum_valid else "suspect"
            spans.append(
                Span(
                    start=match.start(1),
                    end=match.end(1),
                    label=Label.IBAN,
                    source="rule",
                    score=1.0,
                    status=status,
                )
            )
            covered_ranges.append((match.start(1), match.end(1)))

    # Find bare Polish NRBs (26 digits without PL prefix)
    for match in _BARE_NRB_RE.finditer(text):
        raw = match.group(1)
        # Verify this is exactly 26 digits and passes mod 97
        digits_only = _strip_spaces(raw)
        if len(digits_only) == 26 and not _is_overlapping(match.start(1), match.end(1)):
            checksum_valid = is_valid(raw)
            status = "valid" if checksum_valid else "suspect"
            spans.append(
                Span(
                    start=match.start(1),
                    end=match.end(1),
                    label=Label.IBAN,
                    source="rule",
                    score=1.0,
                    status=status,
                )
            )
            covered_ranges.append((match.start(1), match.end(1)))

    # Find foreign IBANs (not Polish, not bare NRB)
    for match in _FOREIGN_IBAN_RE.finditer(text):
        raw = match.group(1)
        clean = _strip_spaces(raw)

        # Skip if it matches the Polish patterns (already handled above)
        if clean.upper().startswith("PL") or (len(clean) == 26 and clean.isdigit()):
            continue

        # Foreign IBAN: must have 2-letter country code + 2-digit check + 11-30 alphanumerics
        if (
            len(clean) >= 15
            and len(clean) <= 34
            and clean[:2].isalpha()
            and clean[2:4].isdigit()
            and not _is_overlapping(match.start(1), match.end(1))
        ):
            checksum_valid = is_valid(raw)
            status = "valid" if checksum_valid else "suspect"
            spans.append(
                Span(
                    start=match.start(1),
                    end=match.end(1),
                    label=Label.IBAN,
                    source="rule",
                    score=1.0,
                    status=status,
                )
            )
            covered_ranges.append((match.start(1), match.end(1)))

    return spans
