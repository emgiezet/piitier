"""Tests for coreference-based entity numbering (PII-6-b).

Covers UC-118 through UC-125 from specs/PII-6-b/spec.md.

Fixtures are fully synthetic: no real person names, PESELs, IBANs or addresses.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

import piitier
from piitier.coref import Coreferencer
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
