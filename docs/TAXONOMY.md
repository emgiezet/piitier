# PII entity taxonomy: piitier

Single source of entity types for the entire project. Any change requires a simultaneous update to `src/piitier/labels.py` (enum `Label`); a CI synchronisation test catches any divergence.

Columns: **Group** — one of six risk areas; **Entity** — symbol matching the `Label` enum member name (no diacritics, ASCII); **Placeholder** — string inserted in place of the entity; **Method** — detection method for MVP.

## Entity types

| Group | Entity | Placeholder | Method |
|-------|--------|-------------|--------|
| Personal identification | OSOBA | [OSOBA_n] | NER |
| Personal identification | IMIE | [IMIĘ_n] | NER |
| Personal identification | NAZWISKO | [NAZWISKO_n] | NER |
| Personal identification | DATA_URODZENIA | [DATA_URODZENIA] | NER |
| Personal identification | WIEK | [WIEK] | NER |
| Personal identification | PLEC | [PŁEĆ] | NER |
| State identifiers | PESEL | [PESEL] | rule + checksum |
| State identifiers | NR_DOWODU | [NR_DOWODU] | rule + checksum |
| State identifiers | NR_PASZPORTU | [NR_PASZPORTU] | rule |
| State identifiers | NR_PRAWA_JAZDY | [NR_PRAWA_JAZDY] | rule |
| State identifiers | NIP | [NIP] | rule + checksum |
| State identifiers | REGON | [REGON] | rule + checksum |
| Contact and location | ADRES | [ADRES_n] | NER |
| Contact and location | KOD_POCZTOWY | [KOD_POCZTOWY] | rule |
| Contact and location | MIEJSCOWOSC | [MIEJSCOWOŚĆ] | NER |
| Contact and location | TELEFON | [TELEFON] | rule |
| Contact and location | EMAIL | [EMAIL] | rule |
| Contact and location | IP | [IP] | rule |
| Contact and location | GEO | [GEO] | NER |
| Finance | IBAN | [IBAN] | rule + mod97 |
| Finance | NR_RACHUNKU | [NR_RACHUNKU] | rule |
| Finance | NR_KARTY | [NR_KARTY] | rule + Luhn |
| Finance | CVV | [CVV] | rule |
| Finance | NR_UMOWY | [NR_UMOWY] | rule + NER |
| Finance | KWOTA | [KWOTA] | NER |
| Finance | DOCHOD | [DOCHÓD] | NER |
| Insurance | NR_POLISY | [NR_POLISY] | configurable patterns + NER |
| Insurance | NR_SZKODY | [NR_SZKODY] | configurable patterns + NER |
| Insurance | NR_REJESTRACYJNY | [NR_REJESTRACYJNY] | rule |
| Insurance | VIN | [VIN] | rule |
| Insurance | NR_KW | [NR_KW] | rule |
| Health — Art. 9 GDPR | DANE_ZDROWOTNE | [DANE_ZDROWOTNE] | NER |
| Health — Art. 9 GDPR | ROZPOZNANIE | [ROZPOZNANIE] | NER + dictionaries |
| Health — Art. 9 GDPR | ICD10 | [ICD10] | rule + dictionaries |
| Health — Art. 9 GDPR | LEK | [LEK] | NER + dictionaries |
| Health — Art. 9 GDPR | NR_DOKUMENTACJI | [NR_DOKUMENTACJI] | rule |
| Health — Art. 9 GDPR | PLACOWKA | [PLACÓWKA] | NER |
| Health — Art. 9 GDPR | LEKARZ | [LEKARZ_n] | NER |
| Health — Art. 9 GDPR | NPWZ | [NPWZ] | rule |

## Format notes

| Entity | Note |
|--------|------|
| KWOTA | Span includes the adjacent currency token when present in the text: `1500 PLN`, `1 234,56 zł`. Generated formats: `1 234,56` (space+comma), `1234,56`, `1234.56`, `1.234,56`, `1500` (integer) — each optionally with currency (`PLN`, `zł`, `EUR`, `€`). |
| DOCHOD | Same formats and currency convention as KWOTA (monthly or annual income). |
| NR_POLISY | Accepts legacy (`PL0123456789`, `UB0123456789`) and slash formats: `POL/RRRR/N{1,6}`, `PL/RRRR/NNNNNNN` (years 2015–2026). |
| NR_SZKODY | Accepts legacy (`SZK12345678`, `CLM12345678`) and slash formats: `SZK/RRRR/N{1,6}`, `CLM/RRRR/NNNNNN` (years 2015–2026). |


Total entity types: **39** in 6 groups.

## Roadmap — categories outside MVP scope

None have a `Label` member; the MVP model does not detect them. They may appear in future releases.

**Art. 9/10 GDPR — special categories:**
- Ethnic or racial origin
- Political opinions
- Religious or philosophical beliefs
- Trade union membership
- Sexual orientation or data on sex life
- Biometric data (where used for identification)
- Data on criminal convictions and offences

**Quasi-identifiers:**
- Job title / professional title
- Employer / institution name
- Rare life events linked to a person
- Event dates (other than DATA_URODZENIA)

## Risk weights

Group weights for risk-weighted recall (`eval/metrics.py`; `test_uc80` verifies consistency with this table):

| Group | Weight |
|-------|--------|
| State identifiers | 1.0 |
| Finance | 1.0 |
| Insurance | 0.9 |
| Contact and location | 0.8 |
| Health — Art. 9 GDPR | 0.8 |
| Personal identification | 0.6 |
