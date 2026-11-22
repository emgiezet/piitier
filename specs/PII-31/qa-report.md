# QA Report — PII-31 (PR #33)

Verdict: **PASS**

The implementation under review (`7e41ce0` plus changelog commit `198315b`) correctly fixes the shortest-Morfeusz-base keying bugs described in PII-31 and preserves all existing PII-6-b contracts. Every PII-31 UC has at least one passing test carrying its id, the required gate is green, and hand-verification of invented Polish names found no wrong merges or wrong splits for forms that exist in the language.

## UC coverage

| UC id | Covered by test(s) | Note |
|-------|--------------------|------|
| UC-118 | `test_uc118_three_inflected_forms_one_entity` | pre-existing |
| UC-119 | `test_uc119_two_people_distinct_indices` | pre-existing |
| UC-120 | `test_uc120_lone_surname_merges_single_candidate`, `test_uc120_lone_surname_new_index_two_candidates` | pre-existing |
| UC-121 | `test_uc121_imie_nazwisko_numbered_independently` | pre-existing |
| UC-122 | `test_uc122_numbered_per_label_unnumbered_unchanged` | pre-existing |
| UC-123 | `test_uc123_lekarz_title_stripped_same_entity` | pre-existing |
| UC-124 | `test_uc124_oov_name_case_fold_deduplication` | pre-existing |
| UC-125 | `test_uc125_fidelity_zero_chars_outside_spans`, `test_uc125_numbering_consistency_on_uc118_output` | pre-existing |
| UC-230 | `test_uc230_uc237_inflected_person_both_masking_paths` | Zieliński/Kamiński/Górski/Stępień |
| UC-231 | `test_uc231_surname_paradigm_has_one_key_and_index` | 40 paradigms (adj + noun) |
| UC-232 | `test_uc232_uc237_feminine_surname_never_attaches_to_man`, `test_uc232_masculine_surname_never_attaches_to_woman`, `test_uc232_indeclinable_noun_surname_feminine_forms_merge`, `test_uc232_unknown_inflected_form_gets_new_index` | 3 families + reverse + indeclinable noun surnames |
| UC-233 | `test_uc233_uc237_different_hyphenated_surnames_stay_distinct`, `test_uc233_uc237_hyphenated_surname_inflections_merge` | double-barrelled |
| UC-234 | `test_uc234_lexical_token_never_becomes_punctuation` | punctuation edge cases |
| UC-235 | `test_uc235_ambiguous_singular_bases_do_not_choose_a_person`, `test_uc235_same_surname_multiple_people_stays_ambiguous`, `test_uc235_koziel_does_not_merge_with_koziol` | Mazur/Mazuro, Zieliński, Kozieł/Kozioł |
| UC-236 | `test_uc236_offsets_and_other_labels_unchanged_across_instances`, `test_uc236_imie_inflections_preserve_numbering` | offsets, IMIE pairs, fresh instances |
| UC-237 | exercised through `_assert_masking_paths` in many PII-31 tests | both `Coreferencer.assign+render_mask` and `Anonymizer(predictor=stub).mask` |
| UC-238 | `test_uc238_common_surname_full_name_pairs` | 24 pairs, Mazur with one earlier person |
| UC-239 | `test_uc239_distinct_people_survive_grammatical_disambiguation` | 13 distinct-person probes |
| UC-240 | `test_uc240_partial_surname_does_not_take_given_name_reading` | Wilka, P. Wilka |
| UC-241 | `test_uc241_unique_earlier_person_resolves_given_name_homographs` | 7 homographic given-name pairs |
| UC-242 | `test_uc242_vocative_allows_undeclined_surname`, `test_uc242_vocative_requires_one_earlier_surname_candidate` | vocative relaxation and limits |
| UC-243 | `test_uc243_lowercase_names_keep_their_person` | 3 cases |
| UC-244 | `test_uc244_middle_names_and_noun_modifiers_inflect` | middle names, junior/senior |
| UC-245 | `test_uc245_distinct_people_and_plural_surnames_never_merge` | 9 distinct-person/plural probes |
| UC-246 | `test_uc246_standalone_names_use_unique_earlier_candidate`, `test_uc246_full_name_with_two_earlier_candidates_stays_ambiguous`, `test_uc246_identical_unresolved_mentions_reuse_their_index` | Dudek, Mazur, Robert, exact repeated keys |
| UC-247 | `test_uc247_ambiguous_mention_cannot_bridge_distinct_people`, `test_uc247_partial_mention_cannot_bridge_distinct_surnames` | narrowing candidate sets |
| UC-248 | `test_uc248_distinct_surnames_require_linear_matching_work`, `test_uc248_exact_full_keys_do_not_rescan_surname_bucket` | complexity assertions |

## Suite output

Required gate:

```text
$ uv run pytest -q -m "not integration"
1210 passed, 51 deselected, 1 warning in 56.14s
```

Per-module output for `tests/test_coref.py`:

```text
$ uv run pytest -q -m "not integration" tests/test_coref.py
161 passed in 3.14s
```

## Notes from hand-verification

During hand-verification I initially tried `Anny Turki` after `Anna Turek` and observed `[OSOBA_2]`. This looked like a wrong split, but Polish surnames ending in a consonant (e.g. *Turek*, *Kaczmarek*, *Nowak*) are indeclinable for women: the correct genitive/dative forms are *Anny Turek*, *Doroty Kaczmarek*. The form *Turki* belongs to the plural / *Turka* paradigm, not to a woman named *Turek*. Assigning a new index to an unknown/ungrammatical form is therefore the conservative behaviour required by the spec. I added passing UC-232 tests that confirm the correct indeclinable forms merge and that the unknown form gets a new index.

## Not verified

- Real NER model end-to-end behaviour on production documents (only synthetic spans and predictor stubs were used).
- Backward-compatibility of serialized outputs or downstream consumers other than `render.mask` / `Anonymizer.mask`.
- Performance on documents with very long spans or thousands of mentions (only the algorithmic-complexity assertions in UC-248 were checked).
- Non-Polish lemmatisation beyond the existing `_get_lemma` OOV fallback path.
