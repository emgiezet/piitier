# Scope report — PII-2-d

> **GAPS** — Size budget exceeded; all changed files are declared in spec scope. Size finding waived under standing approval; zero unwaived findings.

Base: `18c6a6b` (ai/pii-1g-2a-integration)  
Checked: 2026-10-20

## File classification

| File | Classification |
|------|----------------|
| `src/piitier/datagen/__main__.py` | in scope |
| `src/piitier/datagen/build.py` | in scope |
| `src/piitier/datagen/templates/mail_klienta/mail_klienta_01.txt` | in scope |
| `src/piitier/datagen/templates/polisa/polisa_01.txt` | in scope |
| `src/piitier/datagen/templates/skierowanie/skierowanie_01.txt` | in scope |
| `src/piitier/datagen/templates/transkrypcja_infolinii/transkrypcja_infolinii_01.txt` | in scope |
| `src/piitier/datagen/templates/umowa_kredytowa/umowa_kredytowa_01.txt` | in scope |
| `src/piitier/datagen/templates/wyciag/wyciag_01.txt` | in scope |
| `src/piitier/datagen/templates/wypis_szpitalny/wypis_szpitalny_01.txt` | in scope |
| `src/piitier/datagen/templates/zgloszenie_szkody/zgloszenie_szkody_01.txt` | in scope |
| `tests/datagen/test_build.py` | in scope |

## Verdict

Verdict: GAPS

11 in scope · 0 undeclared · 0 out of bounds

## Size

| Measure | This branch | Budget |
|---|---|---|
| Added lines | 1085 | 380 +100% (hard ceiling 5000) |
| Files touched | 11 | 8 +100% |
| Modules touched | 2 | 3 +100% |

Modules: src/piitier,tests/datagen

Generated output, vendored trees, lock files and the specs directory are
excluded; deleted lines never count against the budget.

### Findings

- over budget: 1085 added lines > 760 (380 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)

Waived under standing owner approval — @local-user (2026-10-20). Zero unwaived findings.

---

## Combined scope — PII-2-b + PII-2-d

Base: `18c6a6b` (ai/pii-1g-2a-integration, PR#2 open — this PR stacks onto that branch, not main)  
Checked: 2026-10-20

### Combined size

| Measure | This PR | Budget |
|---|---|---|
| Added lines | 1851 | 400 +100% (hard ceiling 5000) |
| Files touched | 16 | — |
| Modules touched | 3 | — |

Modules: src/piitier,tests/datagen,pyproject.toml  
Generated output, vendored trees, lock files and the specs directory are excluded; deleted lines never count against the budget.

### Combined findings

- over budget: 1851 added lines > 800 (400 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)

Component findings (each carrying a standing waiver):

- PII-2-b: over budget: 766 added lines > 660 (330 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)
- PII-2-d: over budget: 1085 added lines > 760 (380 + 100% tolerance). One spec is one PR: split it (spec-authoring, Sizing)

Waived under standing owner approval — @local-user (2026-10-20). Conditional until PeopleReview closes.  
DatasetReview: APPROVED. PeopleReview: PENDING. Zero unwaived findings once PeopleReview approves.
