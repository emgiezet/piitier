---
ticket: PII-31
title: Conservative surname lemmatisation for entity numbering
kind: bugfix
status: draft
stacks: [python]
---

# PII-31 — Conservative surname lemmatisation

## Problem

Selecting the shortest Morfeusz base confuses surnames with geographic names,
adjectives and punctuation. One person's inflected mentions split into different
indices, feminine surnames attach to men, and unrelated hyphenated surnames collapse.
The existing ASCII Zielinski fixture does not exercise dictionary interpretations.

## Scope

In:
- Correct surname keys in `src/piitier/coref.py`, with real Morfeusz evidence.
- Regression and parametrised paradigm tests in `tests/test_coref.py`, including
  `Anonymizer(predictor=<stub>).mask` without model downloads.
- Singular nominative, genitive, dative and instrumental forms of at least 20
  surname families, masculine and feminine, including -ski/-cki/-dzki and
  Nowak, Woźniak, Stępień and Kozieł.
- Retain competing bases and merge only with a unique compatible earlier entity;
  never select a shortest base or use an ambiguous mention to bridge people.
- Resolve first-name/surname roles and compatible singular case/gender within a
  full mention, including the 24-pair common-surname regression probe.
- Preserve IMIE/NAZWISKO inflections, lowercase mentions, vocatives with an
  undeclined surname, middle names and ordinary noun modifiers.
- Restrict comparisons to surname-index candidates and reuse exact resolved
  keys; identical unresolved keys reuse their first assigned index.

Out:
- Inflected titles (`pana`, `panu`) and surname-first order.
- The pre-existing initial wildcard: `J. Kowalski; Adam Kowalski; M. Kowalski`
  remains indexed 1/2/1; resolving initial-only identities is not part of this fix.
- Changes to renderers, Anonymizer, TUI, detectors, dependencies or changelog.
- Guessing undocumented inflections or equating distinct surname bases:
  Morfeusz generates Kozieła/Koziełowi/Koziełem for Kozieł, while Kozła
  has the surname base Kozioł, not Kozieł.

Change budget: 1000 added lines, 3 files, 2 modules

## Context

- `.claude/playbooks/pipeline-core.md`, `specs/PII-6-b/spec.md`.
- `src/piitier/coref.py::_get_lemma`, `Coreferencer.assign`, `_merge_lookup`.
- `tests/test_coref.py::_DynamicStub`, `test_uc125_fidelity_zero_chars_outside_spans`.
- `src/piitier/render.py::mask`, `src/piitier/__init__.py::Anonymizer.mask`
  are unchanged consumers.
- Observed analyses: Zieliński includes geographic Zielińsk; Kowalskiej includes
  adjective kowalski and surname Kowalska; Kowalska-Nowak has lexical edges
  0→1 and 2→3 separated by punctuation 1→2. Instrumental Zielińskim has both
  singular masculine and plural feminine interpretations.
- Follow-up analyses: Wilka has surname Wilk and given name Wilek; Krzysztofa,
  Pawła, Stanisława, Henryka and Ryszarda each have male oblique and female
  nominative given-name readings. Barbara/Barbarze also admit male Barbar.
  Dudka is nominative Dudka or genitive Dudek. Compatible case/gender from
  the other part of a full mention resolves these without frequency guesses.
- Mazura has surname readings Mazur and Mazuro with identical
  `subst:sg:gen.acc:m1` tags. Retain both: a lone earlier compatible Mazur
  resolves the mention, but two compatible earlier people require a new index.
- Likewise, Roberta admits Robert/Roberto and Dudka admits Dudek/Dudka.
  Full-mention case/gender still separates nominative women and distinct
  nominative surnames before matching candidate base sets.

## Acceptance criteria

| id | actor | action | expected observable result | test |
|----|-------|--------|----------------------------|------|
| UC-230 | integrator | mask `Marek Zieliński … Marka Zielińskiego … M. Zielińskiemu` and Kamiński/Górski/Stępień equivalents | all three mentions have index 1 through assign/render and Anonymizer.mask | unit |
| UC-231 | integrator | key nominative/genitive/dative/instrumental forms from the 20-family masculine/feminine table | each paradigm shares its case-folded surname citation key and one index | unit |
| UC-232 | integrator | mask `Jan Kowalski i Anna Kowalska. Wypłata dla Kowalskiej.` and `Anna Kowalska. Wypłata dla Kowalskiej.`; repeat Kozłowska/Wiśniewska | feminine mention attaches only to Anna, masculine inflections still attach to Jan, in both public masking paths | unit |
| UC-233 | integrator | mask `Jan Kowalski-Nowak oraz Jan Zieliński-Wiśniewski.` and `Anna Kowalska-Nowak … Anny Kowalskiej-Nowak` | distinct double surnames get indices 1/2; inflected same double surname gets 1/1, including Anonymizer.mask | unit |
| UC-234 | integrator | key punctuation-bearing surnames and unknown names | no lexical token becomes punctuation; hyphen components survive; unknown names retain case-folded surface | unit |
| UC-235 | integrator | resolve a surname with multiple earlier candidates or competing singular surname bases | no arbitrary attachment to one person; unresolved inflection receives a fresh index | unit |
| UC-236 | integrator | repeat assignment with reordered spans and fresh instances, alongside ADRES, unnumbered labels and IMIE pairs Paweł/Pawła, Robert/Roberta, Władysław/Władysława, Józef/Józefa, Bogdan/Bogdana, Barbara/Barbarze | deterministic first-appearance numbering keyed by original offsets; each given-name pair shares index 1 and other label contracts stay unchanged | unit |
| UC-237 | integrator | mask all defect sentences with a predictor stub | exact expected text, no `_n`, and zero changed characters outside detected spans | unit |
| UC-238 | integrator | mask the 24 common-surname full-name pairs, including Wilk, Mazur, Wójcik, Krawczyk, Wróbel, Dudek, Gołąb, Kubiak, Jabłońska and Olszewska | all 24 pairs share index 1; Mazura has exactly one compatible earlier person in this table | unit |
| UC-239 | integrator | mask distinct people with homographic first-name inflections or Dudek/Dudka surnames | nominative women are not equated with men's oblique mentions; distinct nominative surnames retain separate indices; original different-person probe stays empty | unit |
| UC-240 | integrator | mask full Wilk mention followed by lone Wilka or initial plus Wilka | surname evidence wins over given-name Wilek; unique surname candidate receives the earlier index | unit |
| UC-241 | integrator | mask Robert/Roberta, Albert/Alberta, Alfred/Alfreda, Bruno/Brunona, Otto/Ottona and Hugo/Hugona with inflected surnames | each inflected mention attaches to its unique compatible earlier person despite competing given-name bases | unit |
| UC-242 | integrator | mask Piotr Wilk/Piotrze Wilk and Jan Nowak/Janie Nowak; also Jan Nowak/Jana Nowak/Jana Nowaka/Janie Nowak | vocative relaxation merges only with exactly one earlier surname-compatible entity; the four-mention sequence is indexed 1/2/1/3 | unit |
| UC-243 | integrator | mask lowercase and mixed-case personal names | lowercase jan kowalski/jana kowalskiego shares one index; feminine forms remain distinct from masculine ones | unit |
| UC-244 | integrator | mask Jan Maria Kowalski/Jana Marii Kowalskiego and Jan Kowalski junior/Jana Kowalskiego juniora | middle names inflect independently of the person's gender; ordinary noun modifiers retain their lemma; both pairs share index 1 | unit |
| UC-245 | integrator | mask Jan/Jana, Aleksander/Aleksandra, Daniel/Daniela, Stanisław/Stanisława with a shared surname; Adam Jan/Adam Jana; Jan Dudek/Jan Dudka; plural Kowalskich or feminine Kowalskiej after Jan Kowalski | every distinct-person pair keeps separate indices; plural and feminine partial surnames do not attach to Jan | unit |
| UC-246 | integrator | mask standalone Dudek/Dudka or several compatible earlier people followed by repeated identical unresolved mentions | unique earlier Dudek permits merging; the first unresolved mention gets a fresh index and identical unresolved keys reuse that index for OSOBA, IMIE and NAZWISKO | unit |
| UC-247 | integrator | follow an initially ambiguous mention by one disambiguating person and then a different compatible-once person | matching narrows candidate sets, so the initial ambiguity cannot bridge two distinct people | unit |
| UC-248 | integrator | assign N distinct surnames, then repeated exact full names with a shared surname | matching-call counts are linear for distinct surnames; repeated exact keys do not rescan surname buckets; no wall-clock assertion in tests | unit |

## Known splits

- Kozieł → Kozła remains split: Morfeusz returns surname
  `('Kozła', 'Kozioł:Sm1', 'subst:sg:gen.acc:m1', ['nazwisko'], [])`;
  the Kozieł base occurs only as geographic/common-noun evidence for this
  spelling. Dictionary surname inflections Kozieła/Koziełowi/Koziełem merge.
- `Piotr Wilk; Piotra Wilk` remains split, like `Jan Nowak; Jana Nowak`:
  `('Piotra', 'Piotr:Sm1', 'subst:sg:gen.acc:m1', ['imię', 'nazwisko'], [])`
  has no case/gender agreement with the masculine nominative Wilk reading
  `('Wilk', 'Wilk:Sm1', 'subst:sg:nom:m1', ['nazwisko'], [])`.
  Only a vocative can relax this case mismatch, and only with one earlier
  surname-compatible entity.
- Zero or multiple compatible earlier entities remain unresolved by design.
  For example Mazura has both surname bases Mazur and Mazuro with the same
  singular genitive/accusative masculine tag; no frequency rule chooses one.
  No listed round-three regression pair remains a known split.

## Non-functional

- Existing tests remain unmodified and pass; no logs of names or document text.
- Use the existing lazy Morfeusz instance; no additional runtime dependencies.
- Prefer splitting to attributing one person's mention to another person.
- Ambiguous full mentions attach only to the unique compatible **earlier**
  entity. Partitioning can therefore depend on mention order; evidence is not
  propagated backwards. Candidate sets narrow after a merge, never union,
  so an ambiguous mention cannot bridge two distinct people.
- Keep the surname candidate index synchronized when narrowing removes bases.
  Cache morphological keys only within one assignment; no names persist in a
  cache across documents.

## Open questions

None. This document remains draft pending human approval.
