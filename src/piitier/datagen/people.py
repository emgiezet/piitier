"""Person, address and contact generators for synthetic Polish PII data (PII-2-b).

Each call to make_person / make_address / generate_email creates a **local**
Faker('pl_PL') instance and seeds it via seed_instance() from the document
RNG — no module-level shared Faker state, no global RNG side effects.

Birth dates are generated from fixed year bounds (1940–2005) so that output
never depends on the wall clock.
"""

from __future__ import annotations

import calendar
import random
from dataclasses import dataclass
from datetime import date

from faker import Faker

from piitier.labels import Label
from piitier.rules import pesel as pesel_rules

_PESEL_WEIGHTS: tuple[int, ...] = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)

# (century_base, month_offset) pairs matching PESEL spec
_CENTURY_TABLE: tuple[tuple[int, int], ...] = (
    (1900, 0),
    (2000, 20),
    (2100, 40),
    (2200, 60),
    (1800, 80),
)


# ---------------------------------------------------------------------------
# Data records
# ---------------------------------------------------------------------------


@dataclass
class PersonRecord:
    """All fields that a person entity shares across OSOBA/IMIE/NAZWISKO/DATA_URODZENIA/PESEL."""

    sex: str  # 'M' or 'F'
    first_name: str
    last_name: str
    birth_date: date
    pesel: str  # formatted string (may include spaces or dashes)


@dataclass
class AddressRecord:
    """All fields that an address entity shares across ADRES/KOD_POCZTOWY/MIEJSCOWOSC."""

    street: str  # street name + building number
    postcode: str  # XX-XXX
    town: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_pesel(rng: random.Random, birth_date: date, sex: str) -> str:
    """Construct a valid, formatted PESEL string consistent with birth_date and sex.

    Digit 9 (0-indexed) encodes sex: even → female, odd → male.
    The constructed compact digits are validated against the canonical PESEL
    validator before formatting; a ValueError is raised on any arithmetic defect.
    A format variant (compact / spaced / dashed) is chosen from the document RNG
    so that rendered PESELs have the same diversity as the structured generator.
    """
    year, month, day = birth_date.year, birth_date.month, birth_date.day

    century_base, month_offset = 1900, 0
    for base, offset in _CENTURY_TABLE:
        if base <= year < base + 100:
            century_base, month_offset = base, offset
            break

    yy = year - century_base
    encoded_month = month + month_offset

    # Positions 6-8: 3-digit random serial prefix
    # Position 9: sex digit — even (F) or odd (M)
    serial_prefix = rng.randint(0, 999)
    sex_digit = rng.choice([0, 2, 4, 6, 8] if sex == "F" else [1, 3, 5, 7, 9])

    base_str = f"{yy:02d}{encoded_month:02d}{day:02d}{serial_prefix:03d}{sex_digit}"
    total = sum(w * int(d) for w, d in zip(_PESEL_WEIGHTS, base_str))
    check = (10 - total % 10) % 10
    raw = base_str + str(check)

    if not pesel_rules.is_valid(raw):
        raise ValueError(
            f"_build_pesel produced an invalid PESEL {raw!r} for "
            f"birth_date={birth_date!r}, sex={sex!r}; this is a bug"
        )

    variant = rng.choice(["compact", "spaced", "dashed"])
    if variant == "spaced":
        return f"{raw[0:2]} {raw[2:4]} {raw[4:6]} {raw[6:10]} {raw[10]}"
    if variant == "dashed":
        return f"{raw[0:2]}-{raw[2:4]}-{raw[4:6]}-{raw[6:10]}-{raw[10]}"
    return raw


# ---------------------------------------------------------------------------
# Person generation
# ---------------------------------------------------------------------------


def make_person(
    rng: random.Random,
    avoid_full_names: frozenset[str] = frozenset(),
) -> PersonRecord:
    """Generate a PersonRecord from the document RNG.

    A per-call Faker('pl_PL') instance is created and seeded via
    ``seed_instance(rng.getrandbits(32))``; no global Faker state is touched.

    If the generated full name collides with ``avoid_full_names``, up to 30
    re-rolls are attempted.  If all 30 attempts collide a RuntimeError is raised
    rather than silently returning a duplicate identity.

    Birth year is drawn from [1940, 2005] — a fixed range independent of
    wall-clock time so that output is reproducible across calendar days.
    """
    fake = Faker("pl_PL")
    sex: str = "M"
    first_name: str = ""
    last_name: str = ""

    for _ in range(30):
        faker_seed = rng.getrandbits(32)
        fake.seed_instance(faker_seed)
        sex = rng.choice(["M", "F"])
        if sex == "M":
            first_name = fake.first_name_male()
            last_name = fake.last_name_male()
        else:
            first_name = fake.first_name_female()
            last_name = fake.last_name_female()
        if f"{first_name} {last_name}" not in avoid_full_names:
            break
    else:
        raise RuntimeError(
            f"make_person: could not generate a unique full name in 30 attempts "
            f"(avoid_full_names contains {len(avoid_full_names)} name(s))"
        )

    # Birth date: deterministic fixed-range, no wall-clock dependency
    year = rng.randint(1940, 2005)
    month = rng.randint(1, 12)
    _, max_day = calendar.monthrange(year, month)
    day = rng.randint(1, max_day)
    birth_date = date(year, month, day)

    pesel = _build_pesel(rng, birth_date, sex)

    return PersonRecord(
        sex=sex,
        first_name=first_name,
        last_name=last_name,
        birth_date=birth_date,
        pesel=pesel,
    )


def get_person_field(label: Label, record: PersonRecord) -> str:
    """Return the rendered value for a person-group label from a PersonRecord."""
    if label is Label.OSOBA:
        return f"{record.first_name} {record.last_name}"
    if label is Label.IMIE:
        return record.first_name
    if label is Label.NAZWISKO:
        return record.last_name
    if label is Label.DATA_URODZENIA:
        d = record.birth_date
        return f"{d.day:02d}.{d.month:02d}.{d.year}"
    if label is Label.PESEL:
        return record.pesel
    raise ValueError(f"Not a person-group label: {label.name}")


# ---------------------------------------------------------------------------
# Address generation
# ---------------------------------------------------------------------------


def make_address(rng: random.Random) -> AddressRecord:
    """Generate an AddressRecord from the document RNG.

    A per-call Faker('pl_PL') instance is created and seeded.  The street value
    is composed explicitly from street_name() + building_number() so that a
    house number (digit) is always present.
    """
    fake = Faker("pl_PL")
    faker_seed = rng.getrandbits(32)
    fake.seed_instance(faker_seed)

    street = f"{fake.street_name()} {fake.building_number()}"
    postcode = fake.postcode()
    town = fake.city()

    return AddressRecord(street=street, postcode=postcode, town=town)


def get_address_field(label: Label, record: AddressRecord) -> str:
    """Return the rendered value for an address-group label from an AddressRecord.

    ADRES returns the full composed address — ``street, postcode town`` — so
    that the postcode and town values (rendered via their own label spans) are
    substrings of the ADRES span, proving they were composed from one record.
    """
    if label is Label.ADRES:
        return f"{record.street}, {record.postcode} {record.town}"
    if label is Label.KOD_POCZTOWY:
        return record.postcode
    if label is Label.MIEJSCOWOSC:
        return record.town
    raise ValueError(f"Not an address-group label: {label.name}")


# ---------------------------------------------------------------------------
# Contact generators
# ---------------------------------------------------------------------------


def generate_telefon(rng: random.Random) -> str:
    """Generate a Polish phone number in one of three accepted shapes.

    All shapes produce exactly 9 phone digits, which cannot be misdetected as
    an 11-digit PESEL or a 10-digit NIP.  The +48 international prefix uses
    the PESEL lookbehind exclusion (``(?<!+)``) to prevent false matches.
    """
    digits = [rng.randint(0, 9) for _ in range(9)]
    g1 = f"{digits[0]}{digits[1]}{digits[2]}"
    g2 = f"{digits[3]}{digits[4]}{digits[5]}"
    g3 = f"{digits[6]}{digits[7]}{digits[8]}"
    variant = rng.choice(["intl", "spaced", "compact"])
    if variant == "intl":
        return f"+48 {g1} {g2} {g3}"
    if variant == "spaced":
        return f"{g1} {g2} {g3}"
    return f"{g1}{g2}{g3}"


def generate_email(rng: random.Random) -> str:
    """Generate a syntactically valid email via a per-call Faker('pl_PL') instance."""
    fake = Faker("pl_PL")
    faker_seed = rng.getrandbits(32)
    fake.seed_instance(faker_seed)
    return fake.email()
