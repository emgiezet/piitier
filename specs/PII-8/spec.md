---
ticket: PII-8
title: Higiena repozytorium — licencja, CI, pre-commit i skan identyfikatorów
status: approved
stacks: [python]
---

# PII-8 — Higiena repozytorium: licencja, CI, pre-commit i skan identyfikatorów

<!-- approved: owner instruction in session, 2026-10-26 ("add the suggestions"), after the
     warda comparison. -->

## Problem

`pyproject.toml` deklaruje Apache-2.0, ale w repozytorium nie ma pliku `LICENSE` ani `NOTICE`,
co blokuje publikację na Hugging Face. Wszystkie bramki jakości uruchamia się wyłącznie lokalnie:
nie ma CI ani hooków commitowych, więc nic nie zatrzymuje sekretu, klucza prywatnego ani
prawdziwego identyfikatora z ważną sumą kontrolną przed commitem. W PII-5 do repozytorium o mało
nie trafiły szablony pochodne z dokumentów pracodawcy.

## Scope

In:
- `LICENSE` (kanoniczny tekst Apache-2.0) i `NOTICE`.
- Podkomenda `piitier scan [--allowlist PLIK] [--write-allowlist PLIK] ŚCIEŻKA...`: zgłasza
  identyfikatory z regułami o `status="valid"` w plikach tekstowych jako `ścieżka:linia:kolumna:
  ETYKIETA`, nigdy z wartością. Allowlista: odciski `sha256("<ETYKIETA>:<wartość>")`, po jednym w
  linii, `#` = komentarz.
- `.pii-allowlist` z odciskami syntetycznych wartości obecnych dziś w repozytorium.
- `.pre-commit-config.yaml`: gitleaks, `detect-private-key`, `check-added-large-files`,
  `check-merge-conflict`, ruff format + check, mypy, `piitier scan` (z wyłączeniem plików
  generowanych: `uv.lock`, `eval/reports/*.json`), pytest `-m "not integration"` na etapie
  pre-push. Narzędzia Pythona przez `uv run` (jedno źródło wersji: `uv.lock`).
- `.github/workflows/ci.yml`: na `pull_request` i `push` do `main`: `uv sync --frozen`,
  `pre-commit run --all-files`, `pytest -q -m "not integration"`.
- `FINDINGS.md`: wyniki i decyzje do tej pory, z odnośnikami do źródeł.

Out:
- Zmiana detektorów (m.in. reguła kart dopasowuje 16 cyfr wewnątrz liczb dziesiętnych — osobny
  ticket), testy integracyjne w CI (wymagają Hub i GPU), codespell/markdownlint (polski tekst).
- Złoty zbiór, protokół ewaluacji, kalibracja (osobne tickety).

Change budget: 400 added lines (bez tekstu licencji), 12 files, 4 modules

## Context

- `src/piitier/cli.py::main` — parser podkomend (`mask`).
- `src/piitier/rules/__init__.py::detect_all` — detektory i `status`.
- `.claude/sdlc.md` — CI poza zakresem agentów, chyba że spec go dotyczy (ten spec dotyczy).
- `CLAUDE.md` niezmiennik 2 (zero prawdziwych danych w repo), `.claude/rules/python.md`
  (nigdy nie logować wartości PII).

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-126 | wydawca | czyta `LICENSE` i `NOTICE` | `LICENSE` ma SHA-256 kanonicznego tekstu Apache-2.0 (`cfc7749b…3d30`); `NOTICE` podaje projekt i właściciela praw | unit |
| UC-127 | deweloper | `piitier scan plik.txt` z PESEL o ważnej sumie, spoza allowlisty | exit 1; stdout zawiera `plik.txt:<linia>:<kolumna>: PESEL`; ani stdout, ani stderr nie zawiera wartości | unit |
| UC-128 | deweloper | jw. z odciskiem tej wartości w `--allowlist` | exit 0, brak zgłoszeń | unit |
| UC-129 | deweloper | `piitier scan` na pliku z PESEL o błędnej sumie, pliku bez identyfikatorów i pliku binarnym | exit 0; plik binarny / nie-UTF-8 pominięty bez błędu | unit |
| UC-130 | deweloper | `piitier scan --write-allowlist A.txt pliki…`, potem `piitier scan --allowlist A.txt pliki…` | `A.txt` zawiera posortowane unikalne odciski (bez wartości); drugi przebieg exit 0 | unit |
| UC-131 | deweloper | `uv run pre-commit run --all-files` na drzewie gałęzi | wszystkie hooki przechodzą; dodanie do pliku ważnego PESEL spoza allowlisty powoduje porażkę hooka `piitier-scan` | manual |
| UC-132 | recenzent | otwiera PR do `main` | workflow `ci` uruchamia się i przechodzi (pre-commit + testy jednostkowe) | manual |

## Non-functional

- `piitier scan` nie importuje torch/transformers (tylko reguły).
- Komunikaty `scan` zawierają ścieżki, pozycje i etykiety — nigdy wartości.

## Open questions

Brak.
