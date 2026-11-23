# PL-PII-Bench annotation guidelines

This document describes what to annotate, how to determine span boundaries, what to skip, and how to handle disagreements. The authoritative source of label definitions is `docs/TAXONOMY.md`; do not introduce label changes in this file.

---

## 1. Entity groups and examples

Each section below covers one of the six taxonomy groups. For each group there are fictional examples: what to annotate (Positive) and what not to annotate (Negative). All values are synthetic.

---

### Person identification

Covers: OSOBA, IMIE, NAZWISKO, DATA_URODZENIA, WIEK, PLEC.

Annotate the full name as a single OSOBA span when first and last name appear together. When only a first name is present, use IMIE; when only a last name, use NAZWISKO.

The DATA_URODZENIA span covers only the date itself. The preceding word `ur.` or `ur` is not included in the span (consistent with `bench/v1` and datagen templates). For WIEK, span the numeric value with its unit (`42 lata`), but not preceding descriptive words.

Positive:
- `Jan Kowalski` → `OSOBA` (full first and last name in one place)
- `Maria Wiśniewska` → `OSOBA` (full first and last name in one place)
- `Anna` → `IMIE` (first name only, no last name nearby)
- `Nowak` → `NAZWISKO` (last name only, no first name nearby)
- `12.03.1985` → `DATA_URODZENIA` (date only; `ur. ` is outside the span)
- `42 lata` → `WIEK` (age value with unit)

Negative:
- `Dyrektor Generalny` → not annotated (job title, outside MVP scope)
- `klienta` → not annotated (generic noun, does not identify a person)

---

### Government identifiers

Covers: PESEL, NR_DOWODU, NR_PASZPORTU, NR_PRAWA_JAZDY, NIP, REGON.

Positive:
- `44051401359` → `PESEL` (PESEL number with valid check digit)
- `ABC123456` → `NR_DOWODU` (national ID number)
- `PL1234567` → `NR_PASZPORTU` (passport number)
- `5261040828` → `NIP` (tax identification number)

Negative:
- `numer wewnętrzny AK/2024/001` → not annotated as PESEL (this is NR_UMOWY)
- `Polska` → not annotated (country name, not a government identifier)

---

### Contact and location

Covers: ADRES, KOD_POCZTOWY, MIEJSCOWOSC, TELEFON, EMAIL, IP, GEO.

Positive:
- `ul. Marszałkowska 10/2, 00-001 Warszawa` → `ADRES` (full address)
- `jan.kowalski@example.com` → `EMAIL` (email address)
- `+48 123 456 789` → `TELEFON` (phone number)
- `Kraków` → `MIEJSCOWOSC` (city name identifying a person's location)

Negative:
- `Polska` → not annotated as MIEJSCOWOSC (country, not a person's city)
- `www.example-bank.pl` → not annotated (company website, not personal contact data)

---

### Finance

Covers: IBAN, NR_RACHUNKU, NR_KARTY, CVV, NR_UMOWY, KWOTA, DOCHOD.

For KWOTA and DOCHOD, span the number and the adjacent currency token together. Example formats: `1 234,56 PLN`, `8500 zł`, `EUR 200`. The words `netto`/`brutto` are not included in the span.

Positive:
- `PL61109010140000071219812874` → `IBAN` (IBAN number)
- `1500 PLN` → `KWOTA` (amount with currency — currency is included in the span)
- `8500 PLN` → `DOCHOD` (income with currency — currency is included in the span)
- `UM/2026/44` → `NR_UMOWY` (contract number)

Negative:
- `30%` → not annotated (percentage, not a currency amount)
- `numer klienta 001` → not annotated as IBAN (no IBAN structure)

---

### Insurance

Covers: NR_POLISY, NR_SZKODY, NR_REJESTRACYJNY, VIN, NR_KW.

Positive:
- `POL/2026/999` → `NR_POLISY` (insurance policy number)
- `SZK/2026/12` → `NR_SZKODY` (claim number)
- `WA1234B` → `NR_REJESTRACYJNY` (vehicle registration number)
- `WW1A/00123456/7` → `NR_KW` (land registry number)

Negative:
- `ubezpieczenie OC` → not annotated (insurance type, not a number)
- `2026` → not annotated (year only, not a policy number)

---

### Health (Art. 9 GDPR)

Covers: DANE_ZDROWOTNE, ROZPOZNANIE, ICD10, LEK, NR_DOKUMENTACJI, PLACOWKA,
LEKARZ, NPWZ.

The title `dr` or `lek. med.` belongs inside the LEKARZ span, consistent with the
training corpus (`src/piitier/datagen/render.py`) and bench v1 data.
Example: `dr Jan Nowicki` → the LEKARZ span covers the whole string including the title.

ROZPOZNANIE covers the clinical description of a health condition. An ICD-10 code, if
present in the text, gets a separate ICD10 span; ROZPOZNANIE does not require a code.

Positive:
- `dr Jan Nowicki` → `LEKARZ` (title + first and last name, title inside the span)
- `lek. med. Anna Zielińska` → `LEKARZ` (title + first and last name, title inside the span)
- `Nadciśnienie tętnicze` → `ROZPOZNANIE` (medical diagnosis, no ICD code)
- `Centrum Medyczne Salus` → `PLACOWKA` (name of a fictional medical facility)

Negative:
- `dr` (title only, no first or last name) → not annotated as LEKARZ
- `leczenie` → not annotated (generic noun, not sensitive data)

---

## 2. Span boundaries

### General rules

- A span is a contiguous character range `[start, end)` in the original document text.
- The range covers exactly those characters that are part of the entity, without leading
  or trailing spaces and punctuation, unless they are an integral part of the value
  (e.g. a separator in an IBAN number).

### Detailed rules

| Entity | Boundary rule |
|--------|--------------|
| KWOTA, DOCHOD | Span covers the number and the adjacent currency token: `1500 PLN`, `8 500,00 zł`. Words outside the value (`netto`, `brutto`) are not included in the span. |
| LEKARZ | Title `dr` or `lek. med.` is included in the span: `dr Jan Nowicki` — the whole string is LEKARZ. |
| OSOBA | Full first and last name → one OSOBA span. First name only → IMIE. Last name only → NAZWISKO. |
| DATA_URODZENIA | Span covers the date only: `12.03.1985`. The preceding word `ur.` or `ur` **is not** included in the span (consistent with bench v1 and datagen templates). |
| WIEK | Span covers the value with its unit: `42 lata`. Descriptive words (`wiek:`, `ma`) are not included in the span. |
| ADRES | The entire address in one span, including postcode and city if they are contiguous: `ul. Prosta 5, 30-001 Kraków`. |

### Nesting

The MVP model does not support nested spans. When one expression could take multiple labels (e.g. PESEL contains a date of birth), choose the label that is more specific or rated higher in risk according to the weights in `docs/TAXONOMY.md`. Record a disputed span in the `notes` field of the record.

---

## 3. What we do not annotate

Do not annotate the following categories; they are outside the MVP scope:

- Job title and professional title (e.g. `Dyrektor`, `Prezes`).
- Name of an employer or commercial institution (e.g. a fictional bank name as a company,
  not as a medical facility — PLACOWKA is annotated).
- Dates of events other than date of birth (e.g. date of contract signing).
- General descriptions of life events without a clinical diagnosis.
- Special-category Art. 9/10 GDPR data without an assigned enum: political views,
  trade union membership, sexual orientation, etc.
  (full list in `docs/TAXONOMY.md` section "Roadmap").

---

## 4. Disputes: adjudication procedure

1. Each annotator works independently, without seeing the other person's annotations.
2. Run `python -m eval.agreement` to compute F1 and kappa. A kappa result below 0.7
   flags the pair for adjudication; adjudication is however always required — the
   `adjudicated_by` field must be filled in for every record.
3. The curator resolves each disputed span and records one sentence of justification
   in the `notes` field (example: `"span LEKARZ: title dr included per GUIDELINES §2"`).
4. The adjudication result goes into the `spans` field as the gold version;
   the original annotations stay in the `annotations` field.

---

## 5. Time budget

| Task | Estimated time |
|------|---------------|
| Annotating one document (up to 500 characters) | 5–10 min |
| Annotating one document (500–1500 characters) | 10–20 min |
| Adjudicating one dispute (one span) | 2–5 min |
| Reviewing guidelines before first annotation | 30 min |

Total budget for 500 documents (two annotations + adjudication for ~10% of disputes,
i.e. ~50 documents × ~5 min = ~4 h for adjudication):
- annotation: 500 × 2 × 7.5 min ≈ **125 h** (midpoint of 5–10 min range)
- adjudication: ~4 h
- total: **approx. 130–170 h**.
