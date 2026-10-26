---
ticket: PII-12
title: Zasady współpracy i szablon pull requesta
status: approved
stacks: [python]
---

# PII-12 — CONTRIBUTING i szablon PR

<!-- approved: owner instruction in session, 2026-10-26 ("adopt the good things from warda"). -->

## Problem

Zasady pracy (spec przed kodem, UC w nazwach testów, bramki, prywatność, przegląd przed merge'em)
istnieją tylko w `CLAUDE.md` i plikach dla agentów. Człowiek otwierający PR nie ma listy
kontrolnej, więc łatwo pominąć dowód weryfikacji, test, który pada na kodzie sprzed poprawki,
albo sprawdzenie, że do repo nie trafiły prawdziwe dane.

## Scope

In:
- `CONTRIBUTING.md`: przepływ pracy (ticket → spec `approved` → gałąź → PR → przegląd → merge),
  nazewnictwo gałęzi z `.claude/sdlc.md`, instalacja hooków, polecenia weryfikacji, zasady
  danych (tylko syntetyczne, `raw_data/` i szablony pochodne lokalnie, `.pii-allowlist`),
  zasady testów (UC w nazwach; testy poprawki padają na kodzie sprzed niej), gdzie zapisywać
  wyniki (`FINDINGS.md`, `eval/reports/`).
- `.github/PULL_REQUEST_TEMPLATE.md`: ticket i spec, pokrycie UC, dowody weryfikacji, lista
  kontrolna prywatności i danych, wpływ na model/benchmark.

Out:
- Zmiany kodu, CI (`.github/workflows/`), hooków i szablonów zgłoszeń.

Change budget: 150 added lines, 3 files, 2 modules

## Context

- `CLAUDE.md` — niezmienniki 1–8, router zadań; `.claude/sdlc.md` — nazwy gałęzi, etykieta PR.
- `.claude/rules/python.md` — blok weryfikacji; `.pre-commit-config.yaml`, `.github/workflows/ci.yml`.
- `FINDINGS.md`, sekcja Process.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-153 | kontrybutor | czyta `CONTRIBUTING.md` | zawiera sekcje: przepływ pracy, gałęzie, hooki i weryfikacja (z poleceniami z `.claude/rules/python.md`), dane i prywatność, testy, wyniki | unit |
| UC-154 | kontrybutor | otwiera PR na GitHubie | treść PR jest wstępnie wypełniona szablonem z sekcjami: spec/UC, weryfikacja, prywatność, wpływ na model | unit (test sprawdza sekcje pliku) |

## Open questions

Brak.
