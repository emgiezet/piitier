"""Tests for coreference-based entity numbering (PII-6-b).

Covers UC-118 through UC-125 from specs/PII-6-b/spec.md.

Fixtures are fully synthetic: no real person names, PESELs, IBANs or addresses.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import piitier
import piitier.coref as coref_module
from piitier.coref import Coreferencer, _get_lemma
from piitier.labels import Label
from piitier.render import mask as render_mask
from piitier.spans import Span

# ---------------------------------------------------------------------------
# Load eval/metrics dynamically (same pattern as tests/eval/test_metrics.py)
# ---------------------------------------------------------------------------

_metrics_path = Path(__file__).resolve().parents[1] / "eval" / "metrics.py"
_spec_obj = importlib.util.spec_from_file_location("eval.metrics", _metrics_path)
assert _spec_obj is not None
_metrics_mod: types.ModuleType = importlib.util.module_from_spec(_spec_obj)
sys.modules.setdefault("eval.metrics", _metrics_mod)
assert _spec_obj.loader is not None
_spec_obj.loader.exec_module(_metrics_mod)

numbering_consistency = _metrics_mod.numbering_consistency
NumberingStats = _metrics_mod.NumberingStats


# ---------------------------------------------------------------------------
# Helper: build a Span with sane defaults
# ---------------------------------------------------------------------------


def _span(start: int, end: int, label: Label) -> Span:
    return Span(start, end, label, "model:ner", 1.0, "valid")


# ---------------------------------------------------------------------------
# UC-118: three inflected forms of the same OSOBA -> all [OSOBA_1]
# ---------------------------------------------------------------------------


def test_uc118_three_inflected_forms_one_entity() -> None:
    """UC-118: Jan Kowalski / Jana Kowalskiego / J. Kowalskiemu -> all [OSOBA_1]."""
    text = "Jan Kowalski Jana Kowalskiego J. Kowalskiemu"
    # offsets:
    # "Jan Kowalski"     [0, 12)
    # " "                [12, 13)
    # "Jana Kowalskiego" [13, 29)
    # " "                [29, 30)
    # "J. Kowalskiemu"   [30, 44)
    assert text[0:12] == "Jan Kowalski"
    assert text[13:29] == "Jana Kowalskiego"
    assert text[30:44] == "J. Kowalskiemu"

    spans = [
        _span(0, 12, Label.OSOBA),
        _span(13, 29, Label.OSOBA),
        _span(30, 44, Label.OSOBA),
    ]

    c = Coreferencer()
    numbering = c.assign(text, spans)

    assert numbering == {(0, 12): 1, (13, 29): 1, (30, 44): 1}

    rendered = render_mask(text, spans, numbering)
    assert rendered == "[OSOBA_1] [OSOBA_1] [OSOBA_1]"
    assert "_n" not in rendered


# ---------------------------------------------------------------------------
# UC-119: two different people -> [OSOBA_1] and [OSOBA_2]
# ---------------------------------------------------------------------------


def test_uc119_two_people_distinct_indices() -> None:
    """UC-119: Jan Kowalski -> [OSOBA_1], Anna Kowalska -> [OSOBA_2]."""
    text = "Jan Kowalski Anna Kowalska"
    assert text[0:12] == "Jan Kowalski"
    assert text[13:26] == "Anna Kowalska"

    spans = [_span(0, 12, Label.OSOBA), _span(13, 26, Label.OSOBA)]

    c = Coreferencer()
    numbering = c.assign(text, spans)

    assert numbering[(0, 12)] == 1
    assert numbering[(13, 26)] == 2

    rendered = render_mask(text, spans, numbering)
    assert rendered == "[OSOBA_1] [OSOBA_2]"


# ---------------------------------------------------------------------------
# UC-120: lone surname merges when one candidate; gets new index when two
# ---------------------------------------------------------------------------


def test_uc120_lone_surname_merges_single_candidate() -> None:
    """UC-120a: Jan Kowalski -> [OSOBA_1]; Kowalskiego -> [OSOBA_1] (one candidate)."""
    text = "Jan Kowalski Kowalskiego"
    assert text[0:12] == "Jan Kowalski"
    assert text[13:24] == "Kowalskiego"

    spans = [_span(0, 12, Label.OSOBA), _span(13, 24, Label.OSOBA)]

    c = Coreferencer()
    numbering = c.assign(text, spans)

    assert numbering[(0, 12)] == 1
    assert numbering[(13, 24)] == 1  # merges with entity 1


def test_uc120_lone_surname_new_index_two_candidates() -> None:
    """UC-120b: Jan Kowalski, Adam Kowalski -> ambiguous; lone Kowalskiego -> [OSOBA_3]."""
    text = "Jan Kowalski Adam Kowalski Kowalskiego"
    assert text[0:12] == "Jan Kowalski"
    assert text[13:26] == "Adam Kowalski"
    assert text[27:38] == "Kowalskiego"

    spans = [
        _span(0, 12, Label.OSOBA),
        _span(13, 26, Label.OSOBA),
        _span(27, 38, Label.OSOBA),
    ]

    c = Coreferencer()
    numbering = c.assign(text, spans)

    assert numbering[(0, 12)] == 1
    assert numbering[(13, 26)] == 2
    assert numbering[(27, 38)] == 3  # two candidates -> new index


# ---------------------------------------------------------------------------
# UC-121: IMIE and NAZWISKO numbered independently
# ---------------------------------------------------------------------------


def test_uc121_imie_nazwisko_numbered_independently() -> None:
    """UC-121: separate IMIE/NAZWISKO spans; each label numbered independently."""
    # "Jan Kowalski Jana Kowalskiego Anna Nowak"
    #  0   4         13  18           30   35
    text = "Jan Kowalski Jana Kowalskiego Anna Nowak"
    assert text[0:3] == "Jan"
    assert text[4:12] == "Kowalski"
    assert text[13:17] == "Jana"
    assert text[18:29] == "Kowalskiego"
    assert text[30:34] == "Anna"
    assert text[35:40] == "Nowak"

    spans = [
        _span(0, 3, Label.IMIE),
        _span(4, 12, Label.NAZWISKO),
        _span(13, 17, Label.IMIE),
        _span(18, 29, Label.NAZWISKO),
        _span(30, 34, Label.IMIE),
        _span(35, 40, Label.NAZWISKO),
    ]

    c = Coreferencer()
    numbering = c.assign(text, spans)

    # IMIE: "Jan"/"Jana" -> same lemma -> index 1; "Anna" -> index 2
    assert numbering[(0, 3)] == 1  # Jan   -> IMIE_1
    assert numbering[(13, 17)] == 1  # Jana  -> IMIE_1
    assert numbering[(30, 34)] == 2  # Anna  -> IMIE_2

    # NAZWISKO: "Kowalski"/"Kowalskiego" -> same lemma -> index 1; "Nowak" -> index 2
    assert numbering[(4, 12)] == 1  # Kowalski    -> NAZWISKO_1
    assert numbering[(18, 29)] == 1  # Kowalskiego -> NAZWISKO_1
    assert numbering[(35, 40)] == 2  # Nowak       -> NAZWISKO_2

    rendered = render_mask(text, spans, numbering)
    assert "[IMIĘ_1]" in rendered
    assert "[IMIĘ_2]" in rendered
    assert "[NAZWISKO_1]" in rendered
    assert "[NAZWISKO_2]" in rendered


# ---------------------------------------------------------------------------
# UC-122: OSOBA and ADRES repeated -> same index; PESEL and IBAN unnumbered
# ---------------------------------------------------------------------------


def test_uc122_numbered_per_label_unnumbered_unchanged() -> None:
    """UC-122: OSOBA and ADRES each repeated get the same index; PESEL/IBAN excluded."""
    # "Jan Kowalski ul. Marszalkowska 1 Jan Kowalski ul. Marszalkowska 1 X Y"
    # Using ASCII address to avoid encoding complexity in test offsets.
    text = "Jan Kowalski ul. Marszalkowska 1 Jan Kowalski ul. Marszalkowska 1 X Y"
    assert text[0:12] == "Jan Kowalski"
    # "ul. Marszalkowska 1" = 19 chars
    assert text[13:32] == "ul. Marszalkowska 1"
    assert text[33:45] == "Jan Kowalski"
    assert text[46:65] == "ul. Marszalkowska 1"
    assert text[66:67] == "X"
    assert text[68:69] == "Y"

    p1 = _span(0, 12, Label.OSOBA)
    a1 = _span(13, 32, Label.ADRES)
    p2 = _span(33, 45, Label.OSOBA)
    a2 = _span(46, 65, Label.ADRES)
    pesel = Span(66, 67, Label.PESEL, "rule", 1.0, "valid")
    iban = Span(68, 69, Label.IBAN, "rule", 1.0, "valid")

    c = Coreferencer()
    numbering = c.assign(text, [p1, a1, p2, a2, pesel, iban])

    assert numbering[(0, 12)] == 1  # OSOBA first occurrence
    assert numbering[(33, 45)] == 1  # same entity
    assert numbering[(13, 32)] == 1  # ADRES first occurrence
    assert numbering[(46, 65)] == 1  # same address

    # Non-numbered labels must be absent.
    assert (66, 67) not in numbering  # PESEL
    assert (68, 69) not in numbering  # IBAN

    rendered = render_mask(text, [p1, a1, p2, a2, pesel, iban], numbering)
    assert rendered.count("[OSOBA_1]") == 2
    assert rendered.count("[ADRES_1]") == 2
    assert "[PESEL]" in rendered
    assert "[IBAN]" in rendered


# ---------------------------------------------------------------------------
# UC-123: titles stripped before matching -> LEKARZ merged
# ---------------------------------------------------------------------------


def test_uc123_lekarz_title_stripped_same_entity() -> None:
    """UC-123: 'dr Marek Zielinski' and 'lek. Marek Zielinski' -> both [LEKARZ_1]."""
    # Use ASCII to keep offset calculation simple.
    text = "dr Marek Zielinski lek. Marek Zielinski"
    assert text[0:18] == "dr Marek Zielinski"
    assert text[19:39] == "lek. Marek Zielinski"

    spans = [_span(0, 18, Label.LEKARZ), _span(19, 39, Label.LEKARZ)]

    c = Coreferencer()
    numbering = c.assign(text, spans)

    assert numbering[(0, 18)] == 1
    assert numbering[(19, 39)] == 1

    rendered = render_mask(text, spans, numbering)
    assert rendered == "[LEKARZ_1] [LEKARZ_1]"


# ---------------------------------------------------------------------------
# UC-124: out-of-dictionary word -> surface form used; case-folded deduplication
# ---------------------------------------------------------------------------


def test_uc124_oov_name_case_fold_deduplication() -> None:
    """UC-124: 'John Smithson' and 'JOHN SMITHSON' share one entity index."""
    text = "John Smithson JOHN SMITHSON"
    assert text[0:13] == "John Smithson"
    assert text[14:27] == "JOHN SMITHSON"

    spans = [_span(0, 13, Label.OSOBA), _span(14, 27, Label.OSOBA)]

    c = Coreferencer()
    numbering = c.assign(text, spans)

    assert numbering[(0, 13)] == 1
    assert numbering[(14, 27)] == 1

    rendered = render_mask(text, spans, numbering)
    assert rendered == "[OSOBA_1] [OSOBA_1]"


# ---------------------------------------------------------------------------
# UC-125: 0 changed characters outside spans (property) + numbering_consistency
# ---------------------------------------------------------------------------


class _DynamicStub:
    """Predictor stub whose returned spans can be overridden per test call."""

    def __init__(self) -> None:
        self._spans: list[Span] = []

    def set(self, spans: list[Span]) -> None:
        self._spans = spans

    def predict(self, text: str) -> list[Span]:
        del text  # unused; stub returns pre-set spans
        return self._spans


_stub = _DynamicStub()
_anon_prop = piitier.Anonymizer(predictor=_stub)

_numbered_labels = [lbl for lbl in Label if lbl.numbered]


@st.composite
def _text_and_spans(draw: st.DrawFn) -> tuple[str, list[Span]]:
    """Generate (text, non-overlapping spans of numbered labels)."""
    text = draw(
        st.text(
            alphabet=st.characters(blacklist_categories=("Cs",)),
            min_size=0,
            max_size=80,
        )
    )
    n = len(text)
    if n == 0:
        return text, []

    raw_positions = sorted(draw(st.lists(st.integers(0, n), min_size=0, max_size=12, unique=True)))
    spans: list[Span] = []
    i = 0
    while i + 1 < len(raw_positions):
        start, end = raw_positions[i], raw_positions[i + 1]
        if start < end:
            label = draw(st.sampled_from(_numbered_labels))
            spans.append(Span(start, end, label, "model:ner", 1.0, "valid"))
            i += 2
        else:
            i += 1

    return text, spans


def _fidelity_outside_spans(original: str, rendered: str, spans: list[Span]) -> int:
    """Count characters outside spans that differ between original and rendered."""
    sorted_spans = sorted(spans, key=lambda s: s.start)
    orig_pos = 0
    res_pos = 0
    mismatches = 0

    for i, span in enumerate(sorted_spans):
        chunk_len = span.start - orig_pos
        if chunk_len > 0:
            orig_chunk = original[orig_pos : span.start]
            res_chunk = rendered[res_pos : res_pos + chunk_len]
            for oc, rc in zip(orig_chunk, res_chunk):
                if oc != rc:
                    mismatches += 1
            if len(res_chunk) < chunk_len:
                mismatches += chunk_len - len(res_chunk)
            res_pos += chunk_len

        # Advance past the rendered placeholder in the output.
        next_start = sorted_spans[i + 1].start if i + 1 < len(sorted_spans) else len(original)
        after_chunk = original[span.end : next_start]
        if after_chunk:
            found = rendered.find(after_chunk, res_pos)
            if found != -1:
                res_pos = found
            else:
                res_pos += len(span.label.placeholder)
        else:
            res_pos += len(span.label.placeholder)

        orig_pos = span.end

    # Tail after all spans.
    tail = original[orig_pos:]
    res_tail = rendered[res_pos : res_pos + len(tail)]
    for oc, rc in zip(tail, res_tail):
        if oc != rc:
            mismatches += 1
    if len(res_tail) < len(tail):
        mismatches += len(tail) - len(res_tail)

    return mismatches


@given(data=_text_and_spans())
@settings(max_examples=40)
def test_uc125_fidelity_zero_chars_outside_spans(data: tuple[str, list[Span]]) -> None:
    """UC-125: characters outside spans are byte-identical through Anonymizer.mask."""
    text, spans = data
    _stub.set(spans)
    detected = _anon_prop.detect(text)
    rendered = _anon_prop.mask(text)
    assert _fidelity_outside_spans(text, rendered, detected) == 0


def test_uc125_numbering_consistency_on_uc118_output() -> None:
    """UC-125: numbering_consistency on UC-118-style output reports consistent 1/1.

    Text has 'Jan Kowalski' appearing twice; both receive [OSOBA_1].
    Trailing punctuation ensures _walk_alignment locates the last placeholder
    (the metric falls back to the template placeholder when the span is at EOF).
    same_entity_consistent == same_entity_total == 1.
    """
    # Note: trailing "." ensures orig_next_chunk is non-empty for the last span
    # so _walk_alignment can locate the actual numbered placeholder in the output.
    text = "Jan Kowalski i Jan Kowalski."
    assert text[0:12] == "Jan Kowalski"
    assert text[15:27] == "Jan Kowalski"
    assert text[27:28] == "."

    spans = [_span(0, 12, Label.OSOBA), _span(15, 27, Label.OSOBA)]

    class _FixedStub:
        def predict(self, _text: str) -> list[Span]:
            return spans

    anon = piitier.Anonymizer(predictor=_FixedStub())
    rendered = anon.mask(text)

    assert rendered == "[OSOBA_1] i [OSOBA_1]."

    stats = numbering_consistency(
        rendered=rendered,
        spans=spans,
        labels_numbered={Label.OSOBA},
        original=text,
        masked_spans=spans,
    )

    assert stats.same_entity_total == 1
    assert stats.same_entity_consistent == 1


# PII-31: citation, genitive, dative, instrumental; all fixtures are synthetic.
_ADJECTIVAL_SURNAMES = [
    ("Kowalski", "Kowalska"),
    ("Wiśniewski", "Wiśniewska"),
    ("Zieliński", "Zielińska"),
    ("Kamiński", "Kamińska"),
    ("Lewandowski", "Lewandowska"),
    ("Dąbrowski", "Dąbrowska"),
    ("Szymański", "Szymańska"),
    ("Kozłowski", "Kozłowska"),
    ("Jankowski", "Jankowska"),
    ("Wojciechowski", "Wojciechowska"),
    ("Kwiatkowski", "Kwiatkowska"),
    ("Górski", "Górska"),
    ("Grabowski", "Grabowska"),
    ("Pawłowski", "Pawłowska"),
    ("Sawicki", "Sawicka"),
    ("Zawadzki", "Zawadzka"),
]
_NOUN_SURNAMES = [
    ("Nowak", "Nowaka", "Nowakowi", "Nowakiem"),
    ("Woźniak", "Woźniaka", "Woźniakowi", "Woźniakiem"),
    ("Stępień", "Stępnia", "Stępniowi", "Stępniem"),
    ("Kozieł", "Kozieła", "Koziełowi", "Koziełem"),
]
_SURNAME_PARADIGMS = (
    [(male, male + "ego", male + "emu", male + "m") for male, _female in _ADJECTIVAL_SURNAMES]
    + [
        (female, female[:-1] + "iej", female[:-1] + "iej", female[:-1] + "ą")
        for _male, female in _ADJECTIVAL_SURNAMES
    ]
    + _NOUN_SURNAMES
    + [(nom,) * 4 for nom, *_ in _NOUN_SURNAMES]
)


def _mention_spans(text: str, mentions: list[str]) -> list[Span]:
    spans = []
    offset = 0
    for mention in mentions:
        start = text.index(mention, offset)
        offset = start + len(mention)
        spans.append(_span(start, offset, Label.OSOBA))
    return spans


def _assert_masking_paths(text: str, mentions: list[str], expected: str) -> None:
    spans = _mention_spans(text, mentions)
    numbering = Coreferencer().assign(text, spans)
    assert render_mask(text, spans, numbering=numbering) == expected
    stub = _DynamicStub()
    stub.set(spans)
    anon = piitier.Anonymizer(predictor=stub)
    detected = anon.detect(text)
    rendered = anon.mask(text)
    assert rendered == expected
    assert "_n" not in rendered
    assert _fidelity_outside_spans(text, rendered, detected) == 0


@pytest.mark.parametrize(
    ("nom", "gen", "dat"),
    [
        ("Zieliński", "Zielińskiego", "Zielińskiemu"),
        ("Kamiński", "Kamińskiego", "Kamińskiemu"),
        ("Górski", "Górskiego", "Górskiemu"),
        ("Stępień", "Stępnia", "Stępniowi"),
    ],
)
def test_uc230_uc237_inflected_person_both_masking_paths(nom: str, gen: str, dat: str) -> None:
    mentions = [f"Marek {nom}", f"Marka {gen}", f"M. {dat}"]
    _assert_masking_paths(" … ".join(mentions), mentions, "[OSOBA_1] … [OSOBA_1] … [OSOBA_1]")


@pytest.mark.parametrize("forms", _SURNAME_PARADIGMS)
def test_uc231_surname_paradigm_has_one_key_and_index(
    forms: tuple[str, str, str, str],
) -> None:
    coref = Coreferencer()
    morf = coref._get_morf()
    assert [_get_lemma(morf, form) for form in forms] == [forms[0].casefold()] * 4
    text = " … ".join(forms)
    spans = _mention_spans(text, list(forms))
    assert list(coref.assign(text, spans).values()) == [1, 1, 1, 1]


@pytest.mark.parametrize(
    ("male", "female", "female_gen"),
    [
        ("Kowalski", "Kowalska", "Kowalskiej"),
        ("Kozłowski", "Kozłowska", "Kozłowskiej"),
        ("Wiśniewski", "Wiśniewska", "Wiśniewskiej"),
    ],
)
def test_uc232_uc237_feminine_surname_never_attaches_to_man(
    male: str, female: str, female_gen: str
) -> None:
    mentions = [f"Jan {male}", f"Anna {female}", female_gen]
    _assert_masking_paths(
        f"{mentions[0]} i {mentions[1]}. Wypłata dla {female_gen}.",
        mentions,
        "[OSOBA_1] i [OSOBA_2]. Wypłata dla [OSOBA_2].",
    )
    _assert_masking_paths(
        f"Anna {female}. Wypłata dla {female_gen}.",
        [f"Anna {female}", female_gen],
        "[OSOBA_1]. Wypłata dla [OSOBA_1].",
    )
    _assert_masking_paths(
        f"Jan {male} … Jana {male}ego",
        [f"Jan {male}", f"Jana {male}ego"],
        "[OSOBA_1] … [OSOBA_1]",
    )


def test_uc232_masculine_surname_never_attaches_to_woman() -> None:
    _assert_masking_paths(
        "Anna Kowalska i Jan Kowalski. Wypłata dla Kowalskiego.",
        ["Anna Kowalska", "Jan Kowalski", "Kowalskiego"],
        "[OSOBA_1] i [OSOBA_2]. Wypłata dla [OSOBA_2].",
    )


def test_uc233_uc237_different_hyphenated_surnames_stay_distinct() -> None:
    _assert_masking_paths(
        "Jan Kowalski-Nowak oraz Jan Zieliński-Wiśniewski.",
        ["Jan Kowalski-Nowak", "Jan Zieliński-Wiśniewski"],
        "[OSOBA_1] oraz [OSOBA_2].",
    )


def test_uc233_uc237_hyphenated_surname_inflections_merge() -> None:
    _assert_masking_paths(
        "Anna Kowalska-Nowak … Anny Kowalskiej-Nowak",
        ["Anna Kowalska-Nowak", "Anny Kowalskiej-Nowak"],
        "[OSOBA_1] … [OSOBA_1]",
    )


@pytest.mark.parametrize(
    ("token", "key"),
    [
        ("Kowalska-Nowak", "kowalska-nowak"),
        ("Kowalskiej-Nowak", "kowalska-nowak"),
        ("Kowalski,", "kowalski"),
        ("Zielińskiego.", "zieliński"),
        ("(Wiśniewskiej)", "wiśniewska"),
        ("SMITHSON", "smithson"),
        ("Xyzzq-Źźqq", "xyzzq-źźqq"),
    ],
)
def test_uc234_lexical_token_never_becomes_punctuation(token: str, key: str) -> None:
    assert _get_lemma(Coreferencer()._get_morf(), token) == key


def test_uc235_ambiguous_singular_bases_do_not_choose_a_person() -> None:
    # Mazura has two distinct singular surname bases: Mazur and Mazuro.
    _assert_masking_paths(
        "Jan Mazur i Adam Mazuro. Wypłata dla Mazura.",
        ["Jan Mazur", "Adam Mazuro", "Mazura"],
        "[OSOBA_1] i [OSOBA_2]. Wypłata dla [OSOBA_3].",
    )
    assert _get_lemma(Coreferencer()._get_morf(), "Mazura") == "mazura"


def test_uc235_same_surname_multiple_people_stays_ambiguous() -> None:
    _assert_masking_paths(
        "Marek Zieliński i Maciej Zieliński … M. Zielińskiemu",
        ["Marek Zieliński", "Maciej Zieliński", "M. Zielińskiemu"],
        "[OSOBA_1] i [OSOBA_2] … [OSOBA_3]",
    )


def test_uc235_koziel_does_not_merge_with_koziol() -> None:
    _assert_masking_paths(
        "Jan Kozieł i Jan Kozioł … Jana Kozła",
        ["Jan Kozieł", "Jan Kozioł", "Jana Kozła"],
        "[OSOBA_1] i [OSOBA_2] … [OSOBA_2]",
    )


def test_uc236_offsets_and_other_labels_unchanged_across_instances() -> None:
    text = "Zieliński; Zielińskiego; TEST  ADRES; test adres; 90051512340"
    values = ["Zieliński", "Zielińskiego", "TEST  ADRES", "test adres", "90051512340"]
    labels = [Label.NAZWISKO, Label.NAZWISKO, Label.ADRES, Label.ADRES, Label.PESEL]
    spans = [
        _span(text.index(value), text.index(value) + len(value), label)
        for value, label in zip(values, labels, strict=True)
    ]
    expected = {(span.start, span.end): 1 for span in spans[:-1]}
    for coref in (Coreferencer(), Coreferencer()):
        assert coref.assign(text, list(reversed(spans))) == expected
        assert render_mask(text, spans, numbering=expected) == (
            "[NAZWISKO_1]; [NAZWISKO_1]; [ADRES_1]; [ADRES_1]; [PESEL]"
        )


@pytest.mark.parametrize(
    ("first", "inflected", "expected_index"),
    [
        ("Piotr Wilk", "Piotra Wilka", 1),
        ("Adam Baran", "Adama Barana", 1),
        ("Maria Lis", "Marii Lis", 1),
        # Only one earlier compatible person resolves Mazur/Mazuro ambiguity.
        ("Tomasz Mazur", "Tomasza Mazura", 1),
        ("Krzysztof Wójcik", "Krzysztofa Wójcika", 1),
        ("Ewa Kaczmarek", "Ewy Kaczmarek", 1),
        ("Jan Kowalczyk", "Jana Kowalczyka", 1),
        ("Paweł Krawczyk", "Pawła Krawczyka", 1),
        ("Andrzej Piotrowski", "Andrzeja Piotrowskiego", 1),
        ("Katarzyna Zając", "Katarzyny Zając", 1),
        ("Michał Król", "Michała Króla", 1),
        ("Stanisław Wróbel", "Stanisława Wróbla", 1),
        ("Tomasz Dudek", "Tomasza Dudka", 1),
        ("Agnieszka Sikora", "Agnieszki Sikory", 1),
        ("Marcin Wieczorek", "Marcina Wieczorka", 1),
        ("Zofia Jabłońska", "Zofii Jabłońskiej", 1),
        ("Jakub Majewski", "Jakuba Majewskiego", 1),
        ("Barbara Olszewska", "Barbarze Olszewskiej", 1),
        ("Grzegorz Pietrzak", "Grzegorzowi Pietrzakowi", 1),
        ("Henryk Gołąb", "Henryka Gołębia", 1),
        ("Jerzy Kot", "Jerzego Kota", 1),
        ("Anna Nowak", "Annie Nowak", 1),
        ("Ryszard Kubiak", "Ryszarda Kubiaka", 1),
        ("Józef Szewczyk", "Józefem Szewczykiem", 1),
    ],
)
def test_uc238_common_surname_full_name_pairs(
    first: str, inflected: str, expected_index: int
) -> None:
    _assert_masking_paths(
        f"{first}; {inflected}",
        [first, inflected],
        f"[OSOBA_1]; [OSOBA_{expected_index}]",
    )


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("Jan Kowalski", "Jan Kowal"),
        ("Anna Nowak", "Anna Nowakowska"),
        ("Piotr Wilk", "Piotr Wilczek"),
        ("Adam Mazur", "Adam Mazurek"),
        ("Jan Lis", "Jan Lisowski"),
        ("Ewa Król", "Ewa Królik"),
        ("Krzysztof Wójcik", "Krzysztofa Wójcik"),
        ("Paweł Krawczyk", "Pawła Krawczyk"),
        ("Stanisław Wróbel", "Stanisława Wróbel"),
        ("Henryk Gołąb", "Henryka Gołąb"),
        ("Ryszard Kubiak", "Ryszarda Kubiak"),
        ("Barbara Olszewska", "Barbar Olszewski"),
        ("Tomasz Dudek", "Tomasz Dudka"),
    ],
)
def test_uc239_distinct_people_survive_grammatical_disambiguation(first: str, second: str) -> None:
    _assert_masking_paths(f"{first}; {second}", [first, second], "[OSOBA_1]; [OSOBA_2]")


@pytest.mark.parametrize("mention", ["Wilka", "P. Wilka"])
def test_uc240_partial_surname_does_not_take_given_name_reading(mention: str) -> None:
    _assert_masking_paths(f"Piotr Wilk; {mention}", ["Piotr Wilk", mention], "[OSOBA_1]; [OSOBA_1]")


@pytest.mark.parametrize(
    ("first", "inflected"),
    [
        ("Paweł", "Pawła"),
        ("Robert", "Roberta"),
        ("Władysław", "Władysława"),
        ("Józef", "Józefa"),
        ("Bogdan", "Bogdana"),
        ("Barbara", "Barbarze"),
    ],
)
def test_uc236_imie_inflections_preserve_numbering(first: str, inflected: str) -> None:
    text = f"{first}; {inflected}"
    spans = [
        _span(0, len(first), Label.IMIE),
        _span(len(first) + 2, len(text), Label.IMIE),
    ]
    numbering = Coreferencer().assign(text, spans)
    assert render_mask(text, spans, numbering=numbering) == "[IMIĘ_1]; [IMIĘ_1]"


@pytest.mark.parametrize(
    ("first", "inflected"),
    [
        ("Robert Nowak", "Roberta Nowaka"),
        ("Albert Nowak", "Alberta Nowaka"),
        ("Alfred Nowak", "Alfreda Nowaka"),
        ("Bruno Nowak", "Brunona Nowaka"),
        ("Otto Nowak", "Ottona Nowaka"),
        ("Hugo Nowak", "Hugona Nowaka"),
        ("Robert Kaczmarczyk", "Roberta Kaczmarczyka"),
    ],
)
def test_uc241_unique_earlier_person_resolves_given_name_homographs(
    first: str, inflected: str
) -> None:
    _assert_masking_paths(f"{first}; {inflected}", [first, inflected], "[OSOBA_1]; [OSOBA_1]")


@pytest.mark.parametrize(
    ("first", "vocative"),
    [("Piotr Wilk", "Piotrze Wilk"), ("Jan Nowak", "Janie Nowak")],
)
def test_uc242_vocative_allows_undeclined_surname(first: str, vocative: str) -> None:
    _assert_masking_paths(f"{first}; {vocative}", [first, vocative], "[OSOBA_1]; [OSOBA_1]")


@pytest.mark.parametrize(
    ("first", "inflected"),
    [
        ("jan kowalski", "jana kowalskiego"),
        ("JAN KOWALSKI", "jana kowalskiego"),
        ("anna kowalska", "anny kowalskiej"),
    ],
)
def test_uc243_lowercase_names_keep_their_person(first: str, inflected: str) -> None:
    _assert_masking_paths(f"{first}; {inflected}", [first, inflected], "[OSOBA_1]; [OSOBA_1]")


@pytest.mark.parametrize(
    ("first", "inflected"),
    [
        ("Jan Maria Kowalski", "Jana Marii Kowalskiego"),
        ("Jan Kowalski junior", "Jana Kowalskiego juniora"),
        ("Jan Kowalski senior", "Jana Kowalskiego seniora"),
    ],
)
def test_uc244_middle_names_and_noun_modifiers_inflect(first: str, inflected: str) -> None:
    _assert_masking_paths(f"{first}; {inflected}", [first, inflected], "[OSOBA_1]; [OSOBA_1]")


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("Jan Nowak", "Jana Nowak"),
        ("Aleksander Nowak", "Aleksandra Nowak"),
        ("Daniel Nowak", "Daniela Nowak"),
        ("Stanisław Nowak", "Stanisława Nowak"),
        ("Adam Jan", "Adam Jana"),
        ("Jan Dudek", "Jan Dudka"),
        ("Jan Kowalski", "Kowalskich"),
        ("Jan Kowalski", "Kowalskiej"),
        ("jan kowalski", "kowalskiej"),
    ],
)
def test_uc245_distinct_people_and_plural_surnames_never_merge(first: str, second: str) -> None:
    _assert_masking_paths(f"{first}; {second}", [first, second], "[OSOBA_1]; [OSOBA_2]")


@pytest.mark.parametrize(
    ("label", "mentions", "expected"),
    [
        (Label.NAZWISKO, ["Dudek", "Dudka"], "[NAZWISKO_1]; [NAZWISKO_1]"),
        (
            Label.NAZWISKO,
            ["Mazur", "Mazuro", "Mazura"],
            "[NAZWISKO_1]; [NAZWISKO_2]; [NAZWISKO_3]",
        ),
        (
            Label.IMIE,
            ["Robert", "Roberto", "Roberta"],
            "[IMIĘ_1]; [IMIĘ_2]; [IMIĘ_3]",
        ),
    ],
)
def test_uc246_standalone_names_use_unique_earlier_candidate(
    label: Label, mentions: list[str], expected: str
) -> None:
    text = "; ".join(mentions)
    spans = [_span(span.start, span.end, label) for span in _mention_spans(text, mentions)]
    numbering = Coreferencer().assign(text, spans)
    assert render_mask(text, spans, numbering=numbering) == expected


def test_uc246_full_name_with_two_earlier_candidates_stays_ambiguous() -> None:
    _assert_masking_paths(
        "Robert Nowak; Roberto Nowak; Roberta Nowaka",
        ["Robert Nowak", "Roberto Nowak", "Roberta Nowaka"],
        "[OSOBA_1]; [OSOBA_2]; [OSOBA_3]",
    )


def test_uc247_ambiguous_mention_cannot_bridge_distinct_people() -> None:
    _assert_masking_paths(
        "Roberta Nowaka; Robert Nowak; Roberto Nowak",
        ["Roberta Nowaka", "Robert Nowak", "Roberto Nowak"],
        "[OSOBA_1]; [OSOBA_1]; [OSOBA_2]",
    )


def test_uc247_partial_mention_cannot_bridge_distinct_surnames() -> None:
    _assert_masking_paths(
        "Mazura; Mazur; Mazuro",
        ["Mazura", "Mazur", "Mazuro"],
        "[OSOBA_1]; [OSOBA_1]; [OSOBA_2]",
    )


@pytest.mark.parametrize(
    ("mentions", "expected"),
    [
        (
            ["Jan Nowak", "Jana Nowak", "Jana Nowaka", "Janie Nowak"],
            "[OSOBA_1]; [OSOBA_2]; [OSOBA_1]; [OSOBA_3]",
        ),
        (["Jana Nowak", "Janie Nowak"], "[OSOBA_1]; [OSOBA_2]"),
        (
            ["Jan Nowak", "Jan Kowalski", "Janie Nowak"],
            "[OSOBA_1]; [OSOBA_2]; [OSOBA_1]",
        ),
        (
            ["Jan Kowalski-Nowak", "Jan Kowalski-Wilk", "Janie Kowalski-Nowak"],
            "[OSOBA_1]; [OSOBA_2]; [OSOBA_1]",
        ),
    ],
)
def test_uc242_vocative_requires_one_earlier_surname_candidate(
    mentions: list[str], expected: str
) -> None:
    _assert_masking_paths("; ".join(mentions), mentions, expected)


@pytest.mark.parametrize(
    ("label", "mentions", "expected"),
    [
        (
            Label.OSOBA,
            ["Jan Kowalski", "Adam Kowalski", "Kowalskiego", "Kowalskiego"],
            "[OSOBA_1]; [OSOBA_2]; [OSOBA_3]; [OSOBA_3]",
        ),
        (
            Label.IMIE,
            ["Robert", "Roberto", "Roberta", "Roberta"],
            "[IMIĘ_1]; [IMIĘ_2]; [IMIĘ_3]; [IMIĘ_3]",
        ),
        (
            Label.NAZWISKO,
            ["Mazur", "Mazuro", "Mazura", "Mazura"],
            "[NAZWISKO_1]; [NAZWISKO_2]; [NAZWISKO_3]; [NAZWISKO_3]",
        ),
        (
            Label.OSOBA,
            ["Robert Nowak", "Roberto Nowak", "Roberta Nowaka", "Roberta Nowaka"],
            "[OSOBA_1]; [OSOBA_2]; [OSOBA_3]; [OSOBA_3]",
        ),
        (
            Label.OSOBA,
            ["Jan Nowak", "Jana Nowak", "Janie Nowak", "Janie Nowak"],
            "[OSOBA_1]; [OSOBA_2]; [OSOBA_3]; [OSOBA_3]",
        ),
        (Label.OSOBA, ["Janie Nowak", "Janie Nowak"], "[OSOBA_1]; [OSOBA_1]"),
    ],
)
def test_uc246_identical_unresolved_mentions_reuse_their_index(
    label: Label, mentions: list[str], expected: str
) -> None:
    text = "; ".join(mentions)
    spans = [_span(span.start, span.end, label) for span in _mention_spans(text, mentions)]
    numbering = Coreferencer().assign(text, spans)
    assert render_mask(text, spans, numbering=numbering) == expected


@pytest.fixture
def _matching_calls(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls = [0]
    original = coref_module._keys_match

    def counted(left: coref_module._MentionKey, right: coref_module._MentionKey) -> bool:
        calls[0] += 1
        return original(left, right)

    monkeypatch.setattr(coref_module, "_keys_match", counted)
    return calls


@pytest.mark.parametrize("count", [50, 200])
def test_uc248_distinct_surnames_require_linear_matching_work(
    count: int, _matching_calls: list[int]
) -> None:
    mentions = [f"Jan Nowak{index}" for index in range(count)]
    text = "; ".join(mentions)
    spans = _mention_spans(text, mentions)
    numbering = Coreferencer().assign(text, spans)
    assert list(numbering.values()) == list(range(1, count + 1))
    assert _matching_calls[0] <= 2 * count


def test_uc248_exact_full_keys_do_not_rescan_surname_bucket(
    _matching_calls: list[int],
) -> None:
    count = 50
    people = [f"Person{index} Nowak" for index in range(count)]
    mentions = people * 5
    text = "; ".join(mentions)
    spans = _mention_spans(text, mentions)
    numbering = Coreferencer().assign(text, spans)
    assert list(numbering.values()) == list(range(1, count + 1)) * 5
    # The first pass needs comparisons within the shared surname bucket;
    # repeated exact keys must not repeat that work.
    assert _matching_calls[0] <= count * (count - 1) // 2 + count


# QA note: feminine indeclinable noun surnames merge correctly (UC-232).
def test_uc232_indeclinable_noun_surname_feminine_forms_merge() -> None:
    """UC-232: indeclinable feminine forms of unisex noun surnames merge.

    A woman with a consonant-ending surname keeps the same surname across cases
    (genitive ``Anny Turek``, dative ``Annie Turek``).  These forms share the
    base with the nominative and must merge with the earlier entity.
    """
    _assert_masking_paths(
        "Anna Turek i Anny Turek. List dla Annie Turek.",
        ["Anna Turek", "Anny Turek", "Annie Turek"],
        "[OSOBA_1] i [OSOBA_1]. List dla [OSOBA_1].",
    )
    _assert_masking_paths(
        "Dorota Kaczmarek i Doroty Kaczmarek.",
        ["Dorota Kaczmarek", "Doroty Kaczmarek"],
        "[OSOBA_1] i [OSOBA_1].",
    )


def test_uc232_unknown_inflected_form_gets_new_index() -> None:
    """UC-232: a form not recognised as a singular surname reading is conservative.

    ``Turki`` is not a valid feminine oblique singular of the indeclinable
    surname ``Turek`` (it is the plural / ``Turka`` paradigm).  With zero
    compatible singular surname candidates, the conservative behaviour required
    by the spec is to assign a fresh index.
    """
    _assert_masking_paths(
        "Anna Turek. Spotkałem Anny Turki.",
        ["Anna Turek", "Anny Turki"],
        "[OSOBA_1]. Spotkałem [OSOBA_2].",
    )
