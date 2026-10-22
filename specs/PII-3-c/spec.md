---
ticket: PII-3-c
title: Augmentacja OCR/diacrytyczna z przeliczaniem offsetów
status: approved
stacks: [python]
depends-on: PII-2-a
---

# PII-3-c — augmentacja OCR/diacrytyczna z przeliczaniem offsetów

## Problem

Playbook `synthetic-data.md` (krok 5) wymaga augmentacji (brakujące diakrytyki, mylenia
OCR 0/O i 1/l, dzielenie grup cyfr spacjami, uppercase) po wstrzyknięciu wartości,
z przeliczeniem każdego przesuniętego offsetu. Ten moduł nie istnieje, więc dane nie
odwzorowują realnych uszkodzeń dokumentów.

## Scope

In:
- Nowy moduł `src/piitier/datagen/augment.py`:
  ```python
  def augment(doc: Document, rng: random.Random,
              transforms: frozenset[str] | None = None) -> Document
  ```
  `transforms=None` → wszystkie; zbiór: `{"strip_diacritics", "ocr_confusions",
  "space_digit_groups", "uppercase"}`.
  - `strip_diacritics`: ą→a, ć→c, ę→e, ł→l, ń→n, ó→o, ś→s, ź/ż→z (wielkie i małe).
  - `ocr_confusions`: zamiany znak w znak 0↔O oraz 1↔l (wielkość liter zachowana),
    stochastycznie (prob. ~0.3 na znak) tylko w miejscach występowania tych znaków.
  - `space_digit_groups`: wewnątrz spanów liczbowych wstawia pojedyncze spacje co 3 cyfry
    (np. PESEL `90051512345` → `900 515 123 45`? — co 3 od lewej); offsety i `span.text`
    przeliczone.
  - `uppercase`: cały dokument na wielkie litery (polskie reguły `str.upper()`).
  - Każda transformacja modyfikuje tekst i przelicza **każdy** span: `start`/`end`
    przesuwane o delta, `span.text = nowy_tekst[start:end]`.
  - Zwraca `Document` o tych samych `template_id`, `doc_type`, `seed`,
    `inflection_fallbacks`; `spans` ponownie posortowane po `start`.
  - Deterministyczne z `rng`; transformacje stosowane w stałej kolejności
    (sortowane alfabetycznie nazw).
- Testy w `tests/datagen/test_augment.py` (UC-54…UC-59): każda transformacja ma własny
  test offsetowy; test pomocniczy `assert_offsets(doc)` po każdej operacji.

Out: integracja z `build`/CLI (to PII-3-d), zmiany `render`/`values`/`people`/`inflect`,
nowe zależności, transformacje przekształcające tekst na różnej długości niż wynik
(zamiana znak w znak jest jednoznakowa; `space_digit_groups` tylko rośnie w prawo —
przeliczać od lewej).

## Acceptance criteria

- UC-54: po każdej transformacji i po wszystkich naraz dla 100 dokumentów (różne szablony,
  seed stały): każdy span spełnia `text[start:end] == span.text`, `0 <= start < end`,
  spójność kolejności.
- UC-55: `strip_diacritics` zamienia wszystkie polskie diakrytyki (test na pełnym
  alfabecie małym i wielkim) i zero innych znaków.
- UC-56: `ocr_confusions` zamienia wyłącznie 0↔O i 1↔l (test na tekście z licznymi
  innymi znakami; asercja braku zmian pozostałych).
- UC-57: `space_digit_groups` dzieli wyłącznie cyfry wewnątrz spanów liczbowych
  (PESEL, IBAN), tekst poza spanami bez zmian.
- UC-58: determinizm: ten sam `rng` seed → identyczny wynik (tekst + spany), inny seed →
  inny (tam gdzie transformacja jest stochastyczna).
- UC-59: `transforms=frozenset()` → dokument identyczny bajt w bajt z oryginałem.

Change budget: 300 added lines, 3 files, 2 modules