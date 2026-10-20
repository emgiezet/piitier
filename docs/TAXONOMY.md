# PII Entity Taxonomy

This is the single source of truth for all entity types, their categories, placeholders, and detection methods.

| Group | Entity | Placeholder | Detection | Numbered | Notes |
|-------|--------|-------------|-----------|----------|-------|
| Identyfikacja osoby | OSOBA | [OSOBA_n] | NER | yes | Full person reference |
| Identyfikacja osoby | IMIĘ | [IMIĘ_n] | NER | yes | Given name |
| Identyfikacja osoby | NAZWISKO | [NAZWISKO_n] | NER | yes | Family name |
| Identyfikacja osoby | DATA_URODZENIA | [DATA_URODZENIA] | NER | no | Birth date |
| Identyfikacja osoby | WIEK | [WIEK] | NER | no | Age |
| Identyfikacja osoby | PŁEĆ | [PŁEĆ] | NER | no | Gender |
| Identyfikatory państwowe | PESEL | [PESEL] | Rule | no | Polish national identity number |
| Identyfikatory państwowe | NR_DOWODU | [NR_DOWODU] | Rule | no | ID card number |
| Identyfikatory państwowe | NR_PASZPORTU | [NR_PASZPORTU] | Rule | no | Passport number |
| Identyfikatory państwowe | NR_PRAWA_JAZDY | [NR_PRAWA_JAZDY] | Rule | no | Driver's license number |
| Identyfikatory państwowe | NIP | [NIP] | Rule | no | Tax ID (10 digits, checksum) |
| Identyfikatory państwowe | REGON | [REGON] | Rule | no | Business registration number |
| Kontakt i lokalizacja | ADRES | [ADRES_n] | NER | yes | Full address |
| Kontakt i lokalizacja | KOD_POCZTOWY | [KOD_POCZTOWY] | Rule | no | Postal code |
| Kontakt i lokalizacja | MIEJSCOWOŚĆ | [MIEJSCOWOŚĆ] | NER | no | City/locality |
| Kontakt i lokalizacja | TELEFON | [TELEFON] | Rule | no | Phone number |
| Kontakt i lokalizacja | EMAIL | [EMAIL] | Rule | no | Email address |
| Kontakt i lokalizacja | IP | [IP] | Rule | no | IP address |
| Kontakt i lokalizacja | GEO | [GEO] | NER | no | Geographic location |
| Finanse | IBAN | [IBAN] | Rule | no | International bank account number |
| Finanse | NR_RACHUNKU | [NR_RACHUNKU] | Rule | no | Bank account number |
| Finanse | NR_KARTY | [NR_KARTY] | Rule | no | Payment card number |
| Finanse | CVV | [CVV] | Rule | no | Card security code |
| Finanse | NR_UMOWY | [NR_UMOWY] | Rule | no | Contract number |
| Finanse | KWOTA | [KWOTA] | NER | no | Monetary amount |
| Finanse | DOCHÓD | [DOCHÓD] | NER | no | Income |
| Ubezpieczenia | NR_POLISY | [NR_POLISY] | Rule | no | Policy number |
| Ubezpieczenia | NR_SZKODY | [NR_SZKODY] | Rule | no | Claim number |
| Ubezpieczenia | NR_REJESTRACYJNY | [NR_REJESTRACYJNY] | Rule | no | Vehicle registration |
| Ubezpieczenia | VIN | [VIN] | Rule | no | Vehicle identification number |
| Ubezpieczenia | NR_KW | [NR_KW] | Rule | no | Land register number |
| Zdrowie | DANE_ZDROWOTNE | [DANE_ZDROWOTNE] | NER | no | Health data (Art. 9) |
| Zdrowie | ROZPOZNANIE | [ROZPOZNANIE] | NER | no | Diagnosis |
| Zdrowie | ICD10 | [ICD10] | Rule | no | ICD-10 code |
| Zdrowie | LEK | [LEK] | Rule | no | Medicine/drug name |
| Zdrowie | NR_DOKUMENTACJI | [NR_DOKUMENTACJI] | Rule | no | Medical record number |
| Zdrowie | PLACÓWKA | [PLACÓWKA] | NER | no | Healthcare facility |
| Zdrowie | LEKARZ | [LEKARZ_n] | NER | yes | Physician/healthcare provider |
| Zdrowie | NPWZ | [NPWZ] | Rule | no | Healthcare provider registration |
