"""Pure PII value generators using provided random.Random source (PII-2-a)."""

from __future__ import annotations

import calendar
import random

from piitier.labels import Label
from piitier.rules import iban, id_card, nip, payment_card, pesel, regon

_PESEL_WEIGHTS: tuple[int, ...] = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
_NIP_WEIGHTS: tuple[int, ...] = (6, 5, 7, 2, 3, 4, 5, 6, 7)
_REGON_WEIGHTS_9: tuple[int, ...] = (8, 9, 2, 3, 4, 5, 6, 7)
_REGON_WEIGHTS_14: tuple[int, ...] = (2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8)
_ID_LETTER_VALUES = {chr(ord("A") + i): 10 + i for i in range(26)}
_ID_WEIGHTS_LETTERS: tuple[int, ...] = (7, 3, 1)
_ID_WEIGHTS_DIGITS: tuple[int, ...] = (7, 3, 1, 7, 3)


def generate_pesel(rng: random.Random) -> str:
    """Generate a valid 11-digit PESEL string with format variants."""
    century_base, month_offset = rng.choice(
        [
            (1900, 0),
            (2000, 20),
            (2100, 40),
            (2200, 60),
            (1800, 80),
        ]
    )
    yy = rng.randint(1, 99)
    actual_year = century_base + yy
    month = rng.randint(1, 12)
    _, max_day = calendar.monthrange(actual_year, month)
    day = rng.randint(1, max_day)
    serial = rng.randint(0, 9999)
    encoded_month = month + month_offset
    base = f"{yy:02d}{encoded_month:02d}{day:02d}{serial:04d}"
    total = sum(w * int(d) for w, d in zip(_PESEL_WEIGHTS, base))
    check = (10 - total % 10) % 10
    full = base + str(check)
    variant = rng.choice(["compact", "spaced", "dashed"])
    if variant == "spaced":
        return f"{full[0:2]} {full[2:4]} {full[4:6]} {full[6:10]} {full[10]}"
    if variant == "dashed":
        return f"{full[0:2]}-{full[2:4]}-{full[4:6]}-{full[6:10]}-{full[10]}"
    return full


def generate_nip(rng: random.Random) -> str:
    """Generate a valid 10-digit NIP string with format variants."""
    while True:
        base = "".join(rng.choice("0123456789") for _ in range(9))
        total = sum(w * int(d) for w, d in zip(_NIP_WEIGHTS, base))
        check = total % 11
        if check != 10:
            break
    full_digits = base + str(check)
    variant = rng.choice(["compact", "dashed1", "dashed2", "pl"])
    if variant == "compact":
        return full_digits
    if variant == "dashed1":
        return f"{full_digits[:3]}-{full_digits[3:6]}-{full_digits[6:8]}-{full_digits[8:]}"
    if variant == "dashed2":
        return f"{full_digits[:3]}-{full_digits[3:5]}-{full_digits[5:7]}-{full_digits[7:]}"
    return f"PL{full_digits}"


def generate_regon(rng: random.Random) -> str:
    """Generate a valid REGON string (9 or 14 digits)."""
    if rng.choice([True, False]):
        base = "".join(rng.choice("0123456789") for _ in range(8))
        total = sum(w * int(d) for w, d in zip(_REGON_WEIGHTS_9, base))
        check = total % 11
        check = 0 if check == 10 else check
        return base + str(check)
    else:
        base = "".join(rng.choice("0123456789") for _ in range(13))
        total = sum(w * int(d) for w, d in zip(_REGON_WEIGHTS_14, base))
        check = total % 11
        check = 0 if check == 10 else check
        return base + str(check)


def generate_iban(rng: random.Random) -> str:
    """Generate a valid Polish IBAN string with format variants."""
    bban = "".join(rng.choice("0123456789") for _ in range(24))
    rem = int(bban + "252100") % 97
    check = 98 - rem
    check_str = f"{check:02d}"
    prefixed = rng.choice([True, False])
    spaced = rng.choice([True, False])
    if prefixed:
        core = f"PL{check_str}{bban}"
        if spaced:
            groups = [bban[i : i + 4] for i in range(0, 24, 4)]
            return f"PL{check_str} " + " ".join(groups)
        return core
    else:
        core = f"{check_str}{bban}"
        if spaced:
            groups = [bban[i : i + 4] for i in range(0, 24, 4)]
            return f"{check_str} " + " ".join(groups)
        return core


def generate_nr_dowodu(rng: random.Random) -> str:
    """Generate a valid ID card number (3 letters + check digit + 5 digits)."""
    letters = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(3))
    payload = "".join(rng.choice("0123456789") for _ in range(5))
    letter_sum = sum(
        w * _ID_LETTER_VALUES[letter] for w, letter in zip(_ID_WEIGHTS_LETTERS, letters)
    )
    digit_sum = sum(w * int(d) for w, d in zip(_ID_WEIGHTS_DIGITS, payload))
    check = (letter_sum + digit_sum) % 10
    digits = str(check) + payload
    spaced = rng.choice([True, False])
    return f"{letters} {digits}" if spaced else f"{letters}{digits}"


def generate_nr_karty(rng: random.Random) -> str:
    """Generate a valid 16-digit payment card number passing Luhn."""
    prefix = rng.choice(["4", "5", "37", "6011"])
    rem_len = 16 - len(prefix) - 1
    middle = "".join(rng.choice("0123456789") for _ in range(rem_len))
    partial = prefix + middle
    total = 0
    for i, digit in enumerate(reversed(partial)):
        n = int(digit)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    check = (10 - (total % 10)) % 10
    full = partial + str(check)
    variant = rng.choice(["compact", "spaces", "dashes"])
    if variant == "spaces":
        return f"{full[0:4]} {full[4:8]} {full[8:12]} {full[12:16]}"
    if variant == "dashes":
        return f"{full[0:4]}-{full[4:8]}-{full[8:12]}-{full[12:16]}"
    return full


_GENERATORS = {
    Label.PESEL: generate_pesel,
    Label.NIP: generate_nip,
    Label.REGON: generate_regon,
    Label.IBAN: generate_iban,
    Label.NR_DOWODU: generate_nr_dowodu,
    Label.NR_KARTY: generate_nr_karty,
}

_VALIDATORS = {
    Label.PESEL: lambda v: pesel.is_valid(pesel._strip_separators(v)),
    Label.NIP: lambda v: nip.is_valid(nip._strip_separators(v).upper().removeprefix("PL")),
    Label.REGON: regon.is_valid,
    Label.IBAN: iban.is_valid,
    Label.NR_DOWODU: id_card.is_valid,
    Label.NR_KARTY: payment_card.is_valid,
}


def generate_value(label: Label, rng: random.Random) -> str:
    """Generate a valid value for the given label using the provided RNG."""
    gen = _GENERATORS.get(label)
    validator = _VALIDATORS.get(label)
    if gen is None or validator is None:
        raise ValueError(f"No generator for {label.name}")
    val = gen(rng)
    if not validator(val):
        raise ValueError(f"Failed to generate valid {label.name}")
    return val
