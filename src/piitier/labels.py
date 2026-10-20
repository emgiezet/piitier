"""PII entity labels matching docs/TAXONOMY.md exactly."""

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class LabelInfo:
    """Metadata for a PII label."""

    placeholder: str
    numbered: bool


class Label(Enum):
    """PII entity types."""

    # Identyfikacja osoby
    OSOBA = LabelInfo(placeholder="[OSOBA_n]", numbered=True)
    IMIĘ = LabelInfo(placeholder="[IMIĘ_n]", numbered=True)
    NAZWISKO = LabelInfo(placeholder="[NAZWISKO_n]", numbered=True)
    DATA_URODZENIA = LabelInfo(placeholder="[DATA_URODZENIA]", numbered=False)
    WIEK = LabelInfo(placeholder="[WIEK]", numbered=False)
    PŁEĆ = LabelInfo(placeholder="[PŁEĆ]", numbered=False)

    # Identyfikatory państwowe
    PESEL = LabelInfo(placeholder="[PESEL]", numbered=False)
    NR_DOWODU = LabelInfo(placeholder="[NR_DOWODU]", numbered=False)
    NR_PASZPORTU = LabelInfo(placeholder="[NR_PASZPORTU]", numbered=False)
    NR_PRAWA_JAZDY = LabelInfo(placeholder="[NR_PRAWA_JAZDY]", numbered=False)
    NIP = LabelInfo(placeholder="[NIP]", numbered=False)
    REGON = LabelInfo(placeholder="[REGON]", numbered=False)

    # Kontakt i lokalizacja
    ADRES = LabelInfo(placeholder="[ADRES_n]", numbered=True)
    KOD_POCZTOWY = LabelInfo(placeholder="[KOD_POCZTOWY]", numbered=False)
    MIEJSCOWOŚĆ = LabelInfo(placeholder="[MIEJSCOWOŚĆ]", numbered=False)
    TELEFON = LabelInfo(placeholder="[TELEFON]", numbered=False)
    EMAIL = LabelInfo(placeholder="[EMAIL]", numbered=False)
    IP = LabelInfo(placeholder="[IP]", numbered=False)
    GEO = LabelInfo(placeholder="[GEO]", numbered=False)

    # Finanse
    IBAN = LabelInfo(placeholder="[IBAN]", numbered=False)
    NR_RACHUNKU = LabelInfo(placeholder="[NR_RACHUNKU]", numbered=False)
    NR_KARTY = LabelInfo(placeholder="[NR_KARTY]", numbered=False)
    CVV = LabelInfo(placeholder="[CVV]", numbered=False)
    NR_UMOWY = LabelInfo(placeholder="[NR_UMOWY]", numbered=False)
    KWOTA = LabelInfo(placeholder="[KWOTA]", numbered=False)
    DOCHÓD = LabelInfo(placeholder="[DOCHÓD]", numbered=False)

    # Ubezpieczenia
    NR_POLISY = LabelInfo(placeholder="[NR_POLISY]", numbered=False)
    NR_SZKODY = LabelInfo(placeholder="[NR_SZKODY]", numbered=False)
    NR_REJESTRACYJNY = LabelInfo(placeholder="[NR_REJESTRACYJNY]", numbered=False)
    VIN = LabelInfo(placeholder="[VIN]", numbered=False)
    NR_KW = LabelInfo(placeholder="[NR_KW]", numbered=False)

    # Zdrowie
    DANE_ZDROWOTNE = LabelInfo(placeholder="[DANE_ZDROWOTNE]", numbered=False)
    ROZPOZNANIE = LabelInfo(placeholder="[ROZPOZNANIE]", numbered=False)
    ICD10 = LabelInfo(placeholder="[ICD10]", numbered=False)
    LEK = LabelInfo(placeholder="[LEK]", numbered=False)
    NR_DOKUMENTACJI = LabelInfo(placeholder="[NR_DOKUMENTACJI]", numbered=False)
    PLACÓWKA = LabelInfo(placeholder="[PLACÓWKA]", numbered=False)
    LEKARZ = LabelInfo(placeholder="[LEKARZ_n]", numbered=True)
    NPWZ = LabelInfo(placeholder="[NPWZ]", numbered=False)

    @property
    def placeholder(self) -> str:
        """Get the placeholder string for this label."""
        return self.value.placeholder

    @property
    def numbered(self) -> bool:
        """True if this label uses numbered placeholders like [OSOBA_n]."""
        return self.value.numbered
