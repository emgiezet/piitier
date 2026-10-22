"""Pure PII value generators using provided random.Random source (PII-2-a)."""

from __future__ import annotations

import calendar
import random
import re
from collections.abc import Callable

from piitier.datagen.people import generate_email, generate_telefon
from piitier.labels import Label
from piitier.rules import iban, id_card, nip, payment_card, pesel, regon

_TELEFON_RE: re.Pattern[str] = re.compile(r"\+48 \d{3} \d{3} \d{3}|\d{3} \d{3} \d{3}|\d{9}")
_EMAIL_RE: re.Pattern[str] = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")

_PESEL_WEIGHTS: tuple[int, ...] = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
_NIP_WEIGHTS: tuple[int, ...] = (6, 5, 7, 2, 3, 4, 5, 6, 7)
_REGON_WEIGHTS_9: tuple[int, ...] = (8, 9, 2, 3, 4, 5, 6, 7)
_REGON_WEIGHTS_14: tuple[int, ...] = (2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8)
_ID_LETTER_VALUES = {chr(ord("A") + i): 10 + i for i in range(26)}
_ID_WEIGHTS_LETTERS: tuple[int, ...] = (7, 3, 1)
_ID_WEIGHTS_DIGITS: tuple[int, ...] = (7, 3, 1, 7, 3)

_PLATE_LETTERS: str = "ABCDEFGHJKLMNPRSTUVWXYZ"
_PLATE_LETTERS_SET: frozenset[str] = frozenset(_PLATE_LETTERS)
_PLATE_CHARS_SET: frozenset[str] = _PLATE_LETTERS_SET | frozenset("0123456789")

_VIN_CHARS: str = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
_VIN_TRANSLITERATION: dict[str, int] = {
    "A": 1,
    "B": 2,
    "C": 3,
    "D": 4,
    "E": 5,
    "F": 6,
    "G": 7,
    "H": 8,
    "J": 1,
    "K": 2,
    "L": 3,
    "M": 4,
    "N": 5,
    "P": 7,
    "R": 9,
    "S": 2,
    "T": 3,
    "U": 4,
    "V": 5,
    "W": 6,
    "X": 7,
    "Y": 8,
    "Z": 9,
}
for _d in range(10):
    _VIN_TRANSLITERATION[str(_d)] = _d

_VIN_WEIGHTS: tuple[int, ...] = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)

_NR_UMOWY_RE: re.Pattern[str] = re.compile(r"^UM/(?:201[5-9]|202[0-6])/\d{7}$")
_NR_POLISY_RE: re.Pattern[str] = re.compile(r"^(?:PL|UB)\d{10}$")
_NR_SZKODY_RE: re.Pattern[str] = re.compile(r"^(?:SZK|CLM)\d{8}$")
_NR_REJESTRACYJNY_RE: re.Pattern[str] = re.compile(r"^[A-Z]{2}[A-Z0-9]{3,5}$")
_VIN_RE: re.Pattern[str] = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
_NR_KW_RE: re.Pattern[str] = re.compile(r"^[A-Z]{2}\d/\d{6}/(?:201[5-9]|202[0-6])$")


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


def generate_nr_umowy(rng: random.Random) -> str:
    """Generate a valid NR_UMOWY string (UM/{YYYY}/{7 digits}, years 2015-2026)."""
    year = rng.randint(2015, 2026)
    serial = rng.randint(0, 9999999)
    return f"UM/{year}/{serial:07d}"


def validate_nr_umowy(v: str) -> bool:
    return bool(_NR_UMOWY_RE.fullmatch(v))


def generate_nr_polisy(rng: random.Random) -> str:
    """Generate a valid NR_POLISY string ({PL|UB}{10 digits})."""
    prefix = rng.choice(["PL", "UB"])
    digits = "".join(rng.choice("0123456789") for _ in range(10))
    return f"{prefix}{digits}"


def validate_nr_polisy(v: str) -> bool:
    return bool(_NR_POLISY_RE.fullmatch(v))


def generate_nr_szkody(rng: random.Random) -> str:
    """Generate a valid NR_SZKODY string ({SZK|CLM}{8 digits})."""
    prefix = rng.choice(["SZK", "CLM"])
    digits = "".join(rng.choice("0123456789") for _ in range(8))
    return f"{prefix}{digits}"


def validate_nr_szkody(v: str) -> bool:
    return bool(_NR_SZKODY_RE.fullmatch(v))


def generate_nr_rejestracyjny(rng: random.Random) -> str:
    """Generate a valid NR_REJESTRACYJNY plate (^[A-Z]{2}[A-Z0-9]{3,5}$, >=2 digits, no I/O/Q)."""
    while True:
        l1 = rng.choice(_PLATE_LETTERS)
        l2 = rng.choice(_PLATE_LETTERS)
        body_len = rng.choice([3, 4, 5])
        body = "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ0123456789") for _ in range(body_len))
        plate = f"{l1}{l2}{body}"
        if sum(1 for c in plate if c.isdigit()) >= 2:
            return plate


def validate_nr_rejestracyjny(v: str) -> bool:
    if not _NR_REJESTRACYJNY_RE.fullmatch(v):
        return False
    if v[0] not in _PLATE_LETTERS_SET or v[1] not in _PLATE_LETTERS_SET:
        return False
    for c in v[2:]:
        if c not in _PLATE_CHARS_SET:
            return False
    if sum(1 for c in v if c.isdigit()) < 2:
        return False
    return True


def generate_vin(rng: random.Random) -> str:
    """Generate a valid 17-char VIN with WMI starting with ZZ and ISO 3779 check digit."""
    wmi = "ZZ" + rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ0123456789")
    vds_prefix = "".join(rng.choice(_VIN_CHARS) for _ in range(5))
    vis = "".join(rng.choice(_VIN_CHARS) for _ in range(8))
    partial = wmi + vds_prefix + "0" + vis
    total = sum(_VIN_TRANSLITERATION[c] * w for c, w in zip(partial, _VIN_WEIGHTS))
    rem = total % 11
    check = "X" if rem == 10 else str(rem)
    return wmi + vds_prefix + check + vis


def validate_vin(v: str) -> bool:
    if not _VIN_RE.fullmatch(v):
        return False
    if not v.startswith("ZZ"):
        return False
    try:
        total = sum(_VIN_TRANSLITERATION[c] * w for c, w in zip(v, _VIN_WEIGHTS))
    except KeyError:
        return False
    rem = total % 11
    expected_check = "X" if rem == 10 else str(rem)
    return v[8] == expected_check


def generate_nr_kw(rng: random.Random) -> str:
    """Generate a valid NR_KW string ({2 letters}{1 digit}/{6 digits}/{YYYY})."""
    letters = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(2))
    digit = rng.choice("0123456789")
    serial = f"{rng.randint(0, 999999):06d}"
    year = rng.randint(2015, 2026)
    return f"{letters}{digit}/{serial}/{year}"


def validate_nr_kw(v: str) -> bool:
    return bool(_NR_KW_RE.fullmatch(v))


_ICD10_LIST: tuple[str, ...] = (
    "I10",
    "I10.0",
    "J06.9",
    "J06",
    "E11.9",
    "E11",
    "J18.9",
    "J18",
    "K29.7",
    "K29",
    "M54.5",
    "M54",
    "N39.0",
    "N39",
    "R51",
    "J02.9",
    "J02",
    "J20.9",
    "J20",
    "R07.9",
    "R07",
    "I21.9",
    "I21",
    "E03.9",
    "E03",
    "F32.9",
    "F32",
    "G43.9",
    "G43",
    "L20.9",
    "L20",
)
_ICD10_RE: re.Pattern[str] = re.compile(r"^[A-Z]\d{2}(\.\d{1,2})?$")

_LEK_LIST: tuple[str, ...] = (
    "paracetamol",
    "ibuprofen",
    "amoksycylina",
    "kwas acetylosalicylowy",
    "metamizol",
    "ketoprofen",
    "diklofenak",
    "pantoprazol",
    "omeprazol",
    "ramipryl",
    "peryndopryl",
    "amlodypina",
    "bisoprolol",
    "metoprolol",
    "atorwastatyna",
    "rozuwastatyna",
    "acenokumarol",
    "furosemid",
    "spironolakton",
    "hydrochlorotiazyd",
    "metformina",
    "insulina",
    "salbutamol",
    "budesonid",
    "flutykazon",
    "montelukast",
    "cetyryzyna",
    "loratadyna",
    "hydroksyzyna",
    "sertralina",
    "escitalopram",
    "fluoksetyna",
    "mirtazapina",
    "diazepam",
    "zolpidem",
    "tramadol",
    "kwas foliowy",
    "witamina d3",
    "witamina c",
    "claritromycyna",
)

_ROZPOZNANIE_LIST: tuple[str, ...] = (
    "nadciśnienie tętnicze",
    "ostre zapalenie oskrzeli",
    "cukrzyca typu 2",
    "infekcja górnych dróg oddechowych",
    "ból pleców",
    "przewlekłe zapalenie żołądka",
    "zapalenie pęcherza moczowego",
    "migrena",
    "stan po zawale serca",
    "lumbago",
    "nerwica lękowa",
    "astma oskrzelowa",
    "choroba refluksowa przełyku",
    "niedoczynność tarczycy",
    "depresja",
    "zmiany zwyrodnieniowe stawów",
    "grypa",
    "covid-19",
    "zapalenie zatok przynosowych",
    "zespół jelita drażliwego",
)

_PLACOWKA_RE: re.Pattern[str] = re.compile(
    r"^Szpital (?:Wojewódzki|Miejski|Kliniczny|Specjalistyczny) im\. .+ w .+$"
)

# EVIDENCE: https://cez.gov.pl/HIS_API/site/pl/CodeSystem-pl-zle-practitioner-identifier-system.html
# EVIDENCE: https://nil.org.pl/rejestry/centralny-rejestr-lekarzy/zasady-weryfikowania-nr-prawa-wykonywania-zawodu
# NPWZ (Numer Prawa Wykonywania Zawodu) format for medical professionals consists of 7 digits,
# where the first digit represents the profession code (1 for physicians / lekarz).
_NPWZ_RE: re.Pattern[str] = re.compile(r"^1\d{6}$")


def generate_icd10(rng: random.Random) -> str:
    """Generate an ICD-10 code from in-repo fact list."""
    return rng.choice(_ICD10_LIST)


def validate_icd10(v: str) -> bool:
    return bool(_ICD10_RE.fullmatch(v))


def generate_lek(rng: random.Random) -> str:
    """Generate a generic drug name (INN) from in-repo fact list (exact 40 names)."""
    return rng.choice(_LEK_LIST)


def validate_lek(v: str) -> bool:
    return v in _LEK_LIST


def generate_rozpoznanie(rng: random.Random) -> str:
    """Generate a diagnosis phrase from in-repo fact list."""
    return rng.choice(_ROZPOZNANIE_LIST)


def validate_rozpoznanie(v: str) -> bool:
    return v in _ROZPOZNANIE_LIST


def generate_placowka(rng: random.Random) -> str:
    """Generate a hospital/placówka name using Faker pl_PL seeded from rng."""
    from faker import Faker

    fake = Faker("pl_PL")
    fake.seed_instance(rng.getrandbits(32))
    h_type = rng.choice(
        ["Szpital Wojewódzki", "Szpital Miejski", "Szpital Kliniczny", "Szpital Specjalistyczny"]
    )
    last_name = fake.last_name_male()
    town = fake.city()
    return f"{h_type} im. {last_name} w {town}"


def validate_placowka(v: str) -> bool:
    return bool(_PLACOWKA_RE.fullmatch(v))


def generate_npwz(rng: random.Random) -> str:
    """Generate a 7-digit NPWZ for a physician starting with 1."""
    digits = "".join(rng.choice("0123456789") for _ in range(6))
    return f"1{digits}"


def validate_npwz(v: str) -> bool:
    return bool(_NPWZ_RE.fullmatch(v))


_GENERATORS: dict[Label, Callable[[random.Random], str]] = {
    Label.PESEL: generate_pesel,
    Label.NIP: generate_nip,
    Label.REGON: generate_regon,
    Label.IBAN: generate_iban,
    Label.NR_DOWODU: generate_nr_dowodu,
    Label.NR_KARTY: generate_nr_karty,
    Label.TELEFON: generate_telefon,
    Label.EMAIL: generate_email,
    Label.NR_UMOWY: generate_nr_umowy,
    Label.NR_POLISY: generate_nr_polisy,
    Label.NR_SZKODY: generate_nr_szkody,
    Label.NR_REJESTRACYJNY: generate_nr_rejestracyjny,
    Label.VIN: generate_vin,
    Label.NR_KW: generate_nr_kw,
    Label.ICD10: generate_icd10,
    Label.LEK: generate_lek,
    Label.ROZPOZNANIE: generate_rozpoznanie,
    Label.PLACOWKA: generate_placowka,
    Label.NPWZ: generate_npwz,
}

_VALIDATORS: dict[Label, Callable[[str], bool]] = {
    Label.PESEL: lambda v: pesel.is_valid(pesel._strip_separators(v)),
    Label.NIP: lambda v: nip.is_valid(nip._strip_separators(v).upper().removeprefix("PL")),
    Label.REGON: regon.is_valid,
    Label.IBAN: iban.is_valid,
    Label.NR_DOWODU: id_card.is_valid,
    Label.NR_KARTY: payment_card.is_valid,
    Label.TELEFON: lambda v: bool(_TELEFON_RE.fullmatch(v)),
    Label.EMAIL: lambda v: bool(_EMAIL_RE.fullmatch(v)),
    Label.NR_UMOWY: validate_nr_umowy,
    Label.NR_POLISY: validate_nr_polisy,
    Label.NR_SZKODY: validate_nr_szkody,
    Label.NR_REJESTRACYJNY: validate_nr_rejestracyjny,
    Label.VIN: validate_vin,
    Label.NR_KW: validate_nr_kw,
    Label.ICD10: validate_icd10,
    Label.LEK: validate_lek,
    Label.ROZPOZNANIE: validate_rozpoznanie,
    Label.PLACOWKA: validate_placowka,
    Label.NPWZ: validate_npwz,
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
