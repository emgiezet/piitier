# QA report — PII-30

Verdict: PASS

## Suite output

```
$ uv run pytest -q -m "not integration"
1136 passed, 51 deselected, 1 warning in 53.81s
```

(51 deselected are `integration` tests; one undefined-metric warning from `tests/training/test_training_fixes.py::test_finding4_seqeval_strict_mode`.)

## UC coverage

| UC | actor | summary | covered by test(s) | verdict |
|---|---|---|---|---|
| UC-218 | text caller | comma/semicolon/space delimiter variants, valid card masked | `test_uc218_mask_preserves_delimiter_fields`, `test_uc218_comma_on_one_side_makes_valid_card_suspect` | pass |
| UC-219 | text caller | invalid 16-digit card between comma-numeric fields is suspect, exact offsets | `test_uc219_invalid_comma_card_is_suspect_and_masked` | pass |
| UC-220 | OCR caller | word-glued 16-digit card (non-hex) is suspect and replaced | `test_uc220_nonhex_word_glued_card_is_suspect`, `test_uc220_grouped_card_is_not_a_hex_fragment`, `test_uc220_word_glued_both_sides_nonhex_is_suspect_and_masked` | pass |
| UC-221 | CSV caller | CSV cells with 16-digit cards and 14-digit `30569309025904` | `test_uc221_mask_csv_preserves_neighboring_cells`, `test_uc221_14_digit_csv_preserves_surrounding_text` | pass |
| UC-222 | text caller | space/dash-grouped cards next to numeric comma fields | `test_uc222_grouped_comma_card_keeps_exact_span` | pass |
| UC-223 | report caller | dot-decimal fragments suppressed; sentence period and grouped cards remain | `test_uc223_dot_decimal_fragments_stay_undetected`, `test_uc223_nondecimal_card_punctuation_is_not_suppressed`, `test_uc223_dot_decimal_fragments_with_single_digit_tail` | pass |
| UC-224 | hash caller | complete hex tokens suppressed; non-hex words become suspect | `test_uc224_hex_tokens_stay_undetected`, `test_uc220_nonhex_word_glued_card_is_suspect` | pass |
| UC-225 | text caller | 14/15-digit cards beside commas or non-hex words, fusion labels | `test_uc225_other_supported_lengths_keep_context_recall`, `test_uc225_other_supported_lengths_mask_with_fusion` | pass |

## Findings (non-blocking)

### 1. `_context_status` returns `suspect` for word-glued cards even when the whole alphanumeric token is hex and the match itself is non-grouped

- **Location:** `src/piitier/rules/payment_card.py:88-101`
- **Observation:** The hex suppression check is `if not grouped and _HEX_TOKEN_RE.fullmatch(text, left, right): return None`. For a grouped 16-digit card such as `4111 1111 1111 1111` wrapped in `abc...ff`, `grouped=True` and the hex guard is skipped, so the span is correctly reported as `suspect` rather than suppressed. This is the intended behaviour per the spec (“grouped cards are not decimal/hex fragments”) and is covered by `test_uc220_grouped_card_is_not_a_hex_fragment`.

### 2. ASCII hex tokens (`cc…ff`, `AB…EF`, `0x…`) are suppressed as `NR_KARTY` but the IBAN detector may still claim the same character range

- **Location:** `src/piitier/rules/payment_card.py:99` and `src/piitier/rules/iban.py:121-128` (foreign IBAN compact pattern)
- **Observation:** For inputs such as `cc4111111111111111ff` and `AB4111111111111111EF`, `payment_card.find` returns no `NR_KARTY` span (correct, UC-224). However, `piitier.detect` returns an overlapping `IBAN suspect` span that covers the entire token and wins in masking, producing `[IBAN]`. This behaviour is caused by the IBAN rule matching two letters + 18 digits + two letters and is outside the PII-30 scope, which only changes payment-card boundaries. It existed on the base branch and is not a regression introduced by the card-delimiter changes.

### 3. Edge case: decimal fragment with a single-digit tail is suppressed

- **Location:** `src/piitier/rules/payment_card.py:89-91`
- **Observation:** `4111111111111111.2` and `0.4111111111111112` produce no card span, consistent with the spec’s dot-decimal exclusion. A new regression test was added because this single-digit-tail variant was not explicitly covered by the existing `test_uc223_dot_decimal_fragments_stay_undetected` cases.

## Not verified

- **Full integration tests** (`-m integration`) were not run per the single gate requested (`uv run pytest -q -m "not integration"`).
- **Pre-commit / Ruff / mypy** were not run; only the requested pytest gate was executed.
- **IBAN-overlap on hex tokens** is noted as a non-blocking finding and was not fixed because it is outside the PII-30 change set and unrelated to payment-card delimiters.

## Tests added

- `tests/rules/test_payment_card.py::test_uc218_comma_on_one_side_makes_valid_card_suspect`
- `tests/rules/test_payment_card.py::test_uc220_word_glued_both_sides_nonhex_is_suspect_and_masked`
- `tests/rules/test_payment_card.py::test_uc223_dot_decimal_fragments_with_single_digit_tail`
