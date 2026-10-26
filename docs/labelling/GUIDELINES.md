# Wytyczne anotacji PL-PII-Bench

Dokument opisuje, co anotujemy, jak wyznaczamy granice spanów, czego nie anotujemy
oraz jak postępujemy przy rozbieżnościach. Źródłem definicji etykiet jest
`docs/TAXONOMY.md`; żadna zmiana etykiety nie może być wprowadzona wyłącznie
w tym pliku.

---

## 1. Grupy encji i przykłady

Każda sekcja poniżej odpowiada jednej z sześciu grup taksonomii. Dla każdej grupy
podajemy przykłady fikcyjne — co anotujemy (Pozytywne) i czego nie anotujemy
(Negatywne).

---

### Identyfikacja osoby

Obejmuje: OSOBA, IMIE, NAZWISKO, DATA_URODZENIA, WIEK, PLEC.

**Kiedy pełne imię i nazwisko występują razem**, anotujemy je jako jeden span OSOBA.
**Kiedy tylko imię** — IMIE. **Kiedy tylko nazwisko** — NAZWISKO.

Pozytywne:
- `Jan Kowalski` → `OSOBA` (pełne imię + nazwisko w jednym miejscu)
- `Maria Wiśniewska` → `OSOBA` (pełne imię + nazwisko w jednym miejscu)
- `Anna` → `IMIE` (tylko imię, bez nazwiska w pobliżu)
- `Nowak` → `NAZWISKO` (tylko nazwisko, bez imienia w pobliżu)
- `ur. 12.03.1985` → `DATA_URODZENIA` (data urodzenia)
- `lat 42` → `WIEK` (wiek osoby)

Negatywne:
- `Dyrektor Generalny` → nie anotujemy (stanowisko zawodowe, poza zakresem MVP)
- `klienta` → nie anotujemy (ogólny rzeczownik, nie identyfikuje osoby)

---

### Identyfikatory państwowe

Obejmuje: PESEL, NR_DOWODU, NR_PASZPORTU, NR_PRAWA_JAZDY, NIP, REGON.

Pozytywne:
- `44051401359` → `PESEL` (numer PESEL z poprawną sumą kontrolną)
- `ABC123456` → `NR_DOWODU` (numer dowodu osobistego)
- `PL1234567` → `NR_PASZPORTU` (numer paszportu)
- `5261040828` → `NIP` (numer identyfikacji podatkowej)

Negatywne:
- `nr umowy 2024/001` → nie anotujemy jako PESEL (format różny od PESEL)
- `Polska` → nie anotujemy (nazwa kraju, nie identyfikator państwowy)

---

### Kontakt i lokalizacja

Obejmuje: ADRES, KOD_POCZTOWY, MIEJSCOWOSC, TELEFON, EMAIL, IP, GEO.

Pozytywne:
- `ul. Marszałkowska 10/2, 00-001 Warszawa` → `ADRES` (pełny adres)
- `jan.kowalski@example.com` → `EMAIL` (adres e-mail)
- `+48 123 456 789` → `TELEFON` (numer telefonu)
- `Kraków` → `MIEJSCOWOSC` (nazwa miejscowości identyfikująca lokalizację osoby)

Negatywne:
- `Polska` → nie anotujemy jako MIEJSCOWOSC (kraj, nie miejscowość osoby)
- `www.bank.pl` → nie anotujemy (adres strony firmy, nie dane kontaktowe osoby)

---

### Finanse

Obejmuje: IBAN, NR_RACHUNKU, NR_KARTY, CVV, NR_UMOWY, KWOTA, DOCHOD.

**KWOTA i DOCHOD**: span obejmuje liczbę i przylegający token waluty, gdy jest
obecny w tekście. Przykłady formatów: `1 234,56 PLN`, `8500 zł`, `EUR 200`.

Pozytywne:
- `PL61109010140000071219812874` → `IBAN` (numer IBAN)
- `1500 PLN` → `KWOTA` (kwota z walutą — waluta wchodzi do spanu)
- `8500 PLN netto` → `DOCHOD` (dochód z walutą — waluta wchodzi do spanu; słowo `netto` nie należy do spanu)
- `UM/2026/44` → `NR_UMOWY` (numer umowy)

Negatywne:
- `30%` → nie anotujemy (procent, nie kwota w walucie)
- `Rachunek 001` → nie anotujemy jako IBAN (numer wewnętrzny bez struktury IBAN)

---

### Ubezpieczenia

Obejmuje: NR_POLISY, NR_SZKODY, NR_REJESTRACYJNY, VIN, NR_KW.

Pozytywne:
- `POL/2026/999` → `NR_POLISY` (numer polisy ubezpieczeniowej)
- `SZK/2026/12` → `NR_SZKODY` (numer szkody)
- `WA1234B` → `NR_REJESTRACYJNY` (numer rejestracyjny pojazdu)
- `WW1A/00123456/7` → `NR_KW` (numer księgi wieczystej)

Negatywne:
- `ubezpieczenie OC` → nie anotujemy (rodzaj ubezpieczenia, nie numer)
- `2026` → nie anotujemy (sam rok, nie numer polisy)

---

### Zdrowie — art. 9 RODO

Obejmuje: DANE_ZDROWOTNE, ROZPOZNANIE, ICD10, LEK, NR_DOKUMENTACJI, PLACOWKA,
LEKARZ, NPWZ.

**Tytuł `dr` lub `lek. med.` należy do spanu LEKARZ** — zgodnie z korpusem
treningowym (`src/piitier/datagen/render.py`) i danymi bench v1.  
Przykład: `dr Jan Nowicki` → span LEKARZ obejmuje całość.

Pozytywne:
- `dr Jan Nowicki` → `LEKARZ` (tytuł + imię + nazwisko, tytuł wewnątrz spanu)
- `lek. med. Anna Zielińska` → `LEKARZ` (tytuł + imię + nazwisko, tytuł wewnątrz spanu)
- `Nadciśnienie tętnicze` → `ROZPOZNANIE` (rozpoznanie lekarskie)
- `Placówka Medyczna Vita` → `PLACOWKA` (nazwa placówki)

Negatywne:
- `dr` (sam tytuł, bez imienia i nazwiska) → nie anotujemy jako LEKARZ
- `leczenie` → nie anotujemy (ogólny rzeczownik, nie dane wrażliwe)

---

## 2. Granice spanów

### Zasady ogólne

- Span to ciągły zakres znaków `[start, end)` w oryginalnym tekście dokumentu.
- Zakres obejmuje dokładnie te znaki, które są częścią encji — bez wiodących
  ani końcowych spacji, znaków interpunkcyjnych, chyba że są integralną częścią
  wartości (np. separator w numerze IBAN nie jest spacją).

### Reguły szczegółowe

| Encja | Reguła granicy |
|-------|---------------|
| KWOTA, DOCHOD | Span obejmuje liczbę i przylegający token waluty: `1500 PLN`, `8 500,00 zł`. Słowa poza wartością (`netto`, `brutto`) nie wchodzą do spanu. |
| LEKARZ | Tytuł `dr` lub `lek. med.` wchodzi do spanu: `dr Jan Nowicki` — cały ciąg jest LEKARZ. |
| OSOBA | Pełne imię i nazwisko → jeden span OSOBA. Samo imię → IMIE. Samo nazwisko → NAZWISKO. |
| ADRES | Cały adres w jednym spanie, łącznie z kodem pocztowym i miejscowością, jeśli są ciągłe: `ul. Prosta 5, 30-001 Kraków`. |

### Zagnieżdżenia

Model MVP nie obsługuje zagnieżdżonych spanów. Gdy jedno wyrażenie można
przypisać do kilku etykiet (np. PESEL zawiera datę urodzenia), wybieramy
etykietę **bardziej szczegółową** lub **wyżej ocenianą ryzykiem** zgodnie z
wagami w `docs/TAXONOMY.md`. Anotatorzy zaznaczają każdy przypadek
w polu `notes` rekordu.

---

## 3. Czego nie anotujemy

Poniższe kategorie są poza zakresem MVP i **nie powinny** być anotowane:

- Stanowisko / tytuł zawodowy (np. `Dyrektor`, `Prezes`).
- Nazwa pracodawcy lub instytucji (np. `Bank PKO`, `Szpital Miejski`).
- Daty zdarzeń inne niż data urodzenia (np. `data podpisania umowy`).
- Rzadkie zdarzenia życiowe powiązane z osobą (wypadek, choroba przewlekła jako
  ogólny fakt życiowy, bez rozpoznania ICD-10).
- Kategorie szczególne art. 9/10 RODO bez przypisanego enuma: poglądy polityczne,
  przynależność do związków zawodowych, orientacja seksualna itp.
  (pełna lista w `docs/TAXONOMY.md` sekcja „Roadmap").

---

## 4. Spory — procedura adjudykacji

1. **Niezależna anotacja**: każdy annotator pracuje oddzielnie, nie widząc anotacji
   drugiej osoby.
2. **Porównanie automatyczne**: narzędzie `python -m eval.agreement` liczy zgodność
   (F1, kappa). Wynik kappa < 0,7 wymaga adjudykacji.
3. **Adjudykacja**: trzecia osoba (kurator) rozstrzyga każdy sporny span i zapisuje
   **jedno zdanie uzasadnienia** w polu `notes` rekordu (przykład:
   `"span LEKARZ: tytuł dr włączony zgodnie z GUIDELINES §2"`).
4. **Zakończenie**: wynik adjudykacji trafia do pola `spans` jako wersja złota;
   oryginalne anotacje pozostają w polu `annotations`.

---

## 5. Budżet czasu

| Zadanie | Szacowany czas |
|---------|---------------|
| Anotacja jednego dokumentu (do 500 znaków) | 5–10 min |
| Anotacja jednego dokumentu (500–1500 znaków) | 10–20 min |
| Adjudykacja jednego sporu (jeden span) | 2–5 min |
| Przegląd wytycznych przed pierwszą anotacją | 30 min |

Łączny budżet na 500 dokumentów (dwie anotacje + adjudykacja ~10% sporów):
**ok. 250–350 godzin**.
