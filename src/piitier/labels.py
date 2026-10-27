"""PII entity type labels.

The enum mirrors ``docs/TAXONOMY.md`` exactly: every member name is ASCII-only
so that ``Label.MIEJSCOWOSC`` works even though the placeholder carries diacritics
(``"[MIEJSCOWOŚĆ]"``).

A CI test (``tests/test_labels.py``) asserts the ``placeholder`` set of this enum
equals the placeholder set parsed from ``docs/TAXONOMY.md``; any drift fails the suite.
"""

from __future__ import annotations

from enum import Enum


class Label(Enum):
    """PII entity type label.

    Each member stores its *placeholder* template string and a *numbered* flag
    that indicates whether multiple occurrences in a document receive a numeric
    suffix (e.g. ``[OSOBA_1]``, ``[OSOBA_2]``).

    Access via::

        Label.PESEL.placeholder   # "[PESEL]"
        Label.OSOBA.numbered      # True
    """

    def __new__(cls, placeholder: str, numbered: bool = False) -> Label:
        obj = object.__new__(cls)
        obj._value_ = placeholder
        return obj

    def __init__(self, placeholder: str, numbered: bool = False) -> None:
        self._placeholder: str = placeholder
        self._numbered: bool = numbered

    @property
    def placeholder(self) -> str:
        """Placeholder template, e.g. ``'[PESEL]'`` or ``'[OSOBA_n]'``."""
        return self._placeholder

    @property
    def numbered(self) -> bool:
        """``True`` when instances are numbered with a suffix (``[OSOBA_1]`` etc.)."""
        return self._numbered

    # ------------------------------------------------------------------ #
    # Group 1 — Personal identification                                    #
    # ------------------------------------------------------------------ #
    OSOBA = ("[OSOBA_n]", True)
    IMIE = ("[IMIĘ_n]", True)
    NAZWISKO = ("[NAZWISKO_n]", True)
    DATA_URODZENIA = ("[DATA_URODZENIA]", False)
    WIEK = ("[WIEK]", False)
    PLEC = ("[PŁEĆ]", False)

    # ------------------------------------------------------------------ #
    # Group 2 — State identifiers                                          #
    # ------------------------------------------------------------------ #
    PESEL = ("[PESEL]", False)
    NR_DOWODU = ("[NR_DOWODU]", False)
    NR_PASZPORTU = ("[NR_PASZPORTU]", False)
    NR_PRAWA_JAZDY = ("[NR_PRAWA_JAZDY]", False)
    NIP = ("[NIP]", False)
    REGON = ("[REGON]", False)

    # ------------------------------------------------------------------ #
    # Group 3 — Contact and location                                       #
    # ------------------------------------------------------------------ #
    ADRES = ("[ADRES_n]", True)
    KOD_POCZTOWY = ("[KOD_POCZTOWY]", False)
    MIEJSCOWOSC = ("[MIEJSCOWOŚĆ]", False)
    TELEFON = ("[TELEFON]", False)
    EMAIL = ("[EMAIL]", False)
    IP = ("[IP]", False)
    GEO = ("[GEO]", False)

    # ------------------------------------------------------------------ #
    # Group 4 — Finance                                                    #
    # ------------------------------------------------------------------ #
    IBAN = ("[IBAN]", False)
    NR_RACHUNKU = ("[NR_RACHUNKU]", False)
    NR_KARTY = ("[NR_KARTY]", False)
    CVV = ("[CVV]", False)
    NR_UMOWY = ("[NR_UMOWY]", False)
    KWOTA = ("[KWOTA]", False)
    DOCHOD = ("[DOCHÓD]", False)

    # ------------------------------------------------------------------ #
    # Group 5 — Insurance                                                  #
    # ------------------------------------------------------------------ #
    NR_POLISY = ("[NR_POLISY]", False)
    NR_SZKODY = ("[NR_SZKODY]", False)
    NR_REJESTRACYJNY = ("[NR_REJESTRACYJNY]", False)
    VIN = ("[VIN]", False)
    NR_KW = ("[NR_KW]", False)

    # ------------------------------------------------------------------ #
    # Group 6 — Health — Art. 9 GDPR                                      #
    # ------------------------------------------------------------------ #
    DANE_ZDROWOTNE = ("[DANE_ZDROWOTNE]", False)
    ROZPOZNANIE = ("[ROZPOZNANIE]", False)
    ICD10 = ("[ICD10]", False)
    LEK = ("[LEK]", False)
    NR_DOKUMENTACJI = ("[NR_DOKUMENTACJI]", False)
    PLACOWKA = ("[PLACÓWKA]", False)
    LEKARZ = ("[LEKARZ_n]", True)
    NPWZ = ("[NPWZ]", False)
