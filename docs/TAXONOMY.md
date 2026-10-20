# Taksonomia encji PII — piitier

Pojedyncze źródło typów encji dla całego projektu. Każda zmiana w tej tabeli wymaga
jednoczesnej zmiany w `src/piitier/labels.py` (enum `Label`) i odwrotnie — test synchronizacji
w CI wykryje rozbieżność.

Kolumny: **Grupa** — jeden z sześciu obszarów ryzyka; **Encja** — symbol odpowiadający
nazwie члена enuma `Label` (bez polskich liter, ASCII); **Placeholder** — ciąg wstawiany w
miejsce encji; **Metoda** — sposób detekcji na MVP.

## Typy encji

| Grupa | Encja | Placeholder | Metoda |
|-------|-------|-------------|--------|
| Identyfikacja osoby | OSOBA | [OSOBA_n] | NER |
| Identyfikacja osoby | IMIE | [IMIĘ_n] | NER |
| Identyfikacja osoby | NAZWISKO | [NAZWISKO_n] | NER |
| Identyfikacja osoby | DATA_URODZENIA | [DATA_URODZENIA] | NER |
| Identyfikacja osoby | WIEK | [WIEK] | NER |
| Identyfikacja osoby | PLEC | [PŁEĆ] | NER |
| Identyfikatory państwowe | PESEL | [PESEL] | reguła + suma kontrolna |
| Identyfikatory państwowe | NR_DOWODU | [NR_DOWODU] | reguła + suma kontrolna |
| Identyfikatory państwowe | NR_PASZPORTU | [NR_PASZPORTU] | reguła |
| Identyfikatory państwowe | NR_PRAWA_JAZDY | [NR_PRAWA_JAZDY] | reguła |
| Identyfikatory państwowe | NIP | [NIP] | reguła + suma kontrolna |
| Identyfikatory państwowe | REGON | [REGON] | reguła + suma kontrolna |
| Kontakt i lokalizacja | ADRES | [ADRES_n] | NER |
| Kontakt i lokalizacja | KOD_POCZTOWY | [KOD_POCZTOWY] | reguła |
| Kontakt i lokalizacja | MIEJSCOWOSC | [MIEJSCOWOŚĆ] | NER |
| Kontakt i lokalizacja | TELEFON | [TELEFON] | reguła |
| Kontakt i lokalizacja | EMAIL | [EMAIL] | reguła |
| Kontakt i lokalizacja | IP | [IP] | reguła |
| Kontakt i lokalizacja | GEO | [GEO] | NER |
| Finanse | IBAN | [IBAN] | reguła + mod97 |
| Finanse | NR_RACHUNKU | [NR_RACHUNKU] | reguła |
| Finanse | NR_KARTY | [NR_KARTY] | reguła + Luhn |
| Finanse | CVV | [CVV] | reguła |
| Finanse | NR_UMOWY | [NR_UMOWY] | reguła + NER |
| Finanse | KWOTA | [KWOTA] | NER |
| Finanse | DOCHOD | [DOCHÓD] | NER |
| Ubezpieczenia | NR_POLISY | [NR_POLISY] | konfigurowalne wzorce + NER |
| Ubezpieczenia | NR_SZKODY | [NR_SZKODY] | konfigurowalne wzorce + NER |
| Ubezpieczenia | NR_REJESTRACYJNY | [NR_REJESTRACYJNY] | reguła |
| Ubezpieczenia | VIN | [VIN] | reguła |
| Ubezpieczenia | NR_KW | [NR_KW] | reguła |
| Zdrowie — art. 9 RODO | DANE_ZDROWOTNE | [DANE_ZDROWOTNE] | NER |
| Zdrowie — art. 9 RODO | ROZPOZNANIE | [ROZPOZNANIE] | NER + słowniki |
| Zdrowie — art. 9 RODO | ICD10 | [ICD10] | reguła + słowniki |
| Zdrowie — art. 9 RODO | LEK | [LEK] | NER + słowniki |
| Zdrowie — art. 9 RODO | NR_DOKUMENTACJI | [NR_DOKUMENTACJI] | reguła |
| Zdrowie — art. 9 RODO | PLACOWKA | [PLACÓWKA] | NER |
| Zdrowie — art. 9 RODO | LEKARZ | [LEKARZ_n] | NER |
| Zdrowie — art. 9 RODO | NPWZ | [NPWZ] | reguła |

Łączna liczba typów: **39** w 6 grupach.

## Roadmap — kategorie poza zakresem MVP

Poniższe kategorie nie mają członka w enumie `Label` i nie są wykrywane przez model MVP.
Pojawią się w przyszłych iteracjach.

**Art. 9/10 RODO — kategorie szczególne:**
- Pochodzenie etniczne lub rasowe
- Poglądy polityczne
- Przekonania religijne lub światopoglądowe
- Przynależność do związków zawodowych
- Orientacja seksualna lub dane o życiu seksualnym
- Dane biometryczne (o ile służą identyfikacji)
- Dane o wyrokach skazujących i naruszeniach prawa

**Quasi-identyfikatory:**
- Stanowisko / tytuł zawodowy
- Pracodawca / nazwa instytucji
- Rzadkie zdarzenia życiowe powiązane z osobą
- Daty zdarzeń (inne niż DATA_URODZENIA)
