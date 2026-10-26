"""Span fusion: merge rule-based and NER spans into non-overlapping output.

Implements the precedence rules from ``.claude/playbooks/pipeline-core.md``
(section "Fusion precedence"):

1. A rule span with ``status="valid"`` beats any overlapping NER span.
   Rule spans are identified by ``source == "rule"`` or
   ``source.startswith("rule:")``.
2. Otherwise the type-priority table decides: higher group weight from
   ``docs/TAXONOMY.md`` wins; equal weight → longer span wins; equal length
   → earlier ``start`` wins.
3. NER spans with ``score < threshold`` are dropped (``score == threshold``
   is kept). Rule spans are never threshold-filtered.
4. Every output span covers only characters that were covered by some input
   span; no character covered by any input span is left uncovered.
5. Adjacent output spans are NOT merged. Every output span keeps the
   ``source`` and ``status`` of its winning input span.

Complexity: O(n log n) via an event-sweep with a lazy-deletion max-heap.

Sync test: ``tests/test_fusion.py::test_weights_match_taxonomy`` asserts
that ``GROUP_WEIGHTS`` equals the table parsed from ``docs/TAXONOMY.md``.
"""

from __future__ import annotations

import heapq
import math
from collections import defaultdict
from typing import Any

from piitier.labels import Label
from piitier.spans import Span

# ---------------------------------------------------------------------------
# Group weights from docs/TAXONOMY.md "Wagi ryzyka" table.
# Sync test: tests/test_fusion.py::test_weights_match_taxonomy
# ---------------------------------------------------------------------------

GROUP_WEIGHTS: dict[str, float] = {
    "Identyfikatory państwowe": 1.0,
    "Finanse": 1.0,
    "Ubezpieczenia": 0.9,
    "Kontakt i lokalizacja": 0.8,
    "Zdrowie — art. 9 RODO": 0.8,
    "Identyfikacja osoby": 0.6,
}

# Map from each Label member to its risk-group name.
_LABEL_GROUP: dict[Label, str] = {
    # Identyfikacja osoby
    Label.OSOBA: "Identyfikacja osoby",
    Label.IMIE: "Identyfikacja osoby",
    Label.NAZWISKO: "Identyfikacja osoby",
    Label.DATA_URODZENIA: "Identyfikacja osoby",
    Label.WIEK: "Identyfikacja osoby",
    Label.PLEC: "Identyfikacja osoby",
    # Identyfikatory państwowe
    Label.PESEL: "Identyfikatory państwowe",
    Label.NR_DOWODU: "Identyfikatory państwowe",
    Label.NR_PASZPORTU: "Identyfikatory państwowe",
    Label.NR_PRAWA_JAZDY: "Identyfikatory państwowe",
    Label.NIP: "Identyfikatory państwowe",
    Label.REGON: "Identyfikatory państwowe",
    # Kontakt i lokalizacja
    Label.ADRES: "Kontakt i lokalizacja",
    Label.KOD_POCZTOWY: "Kontakt i lokalizacja",
    Label.MIEJSCOWOSC: "Kontakt i lokalizacja",
    Label.TELEFON: "Kontakt i lokalizacja",
    Label.EMAIL: "Kontakt i lokalizacja",
    Label.IP: "Kontakt i lokalizacja",
    Label.GEO: "Kontakt i lokalizacja",
    # Finanse
    Label.IBAN: "Finanse",
    Label.NR_RACHUNKU: "Finanse",
    Label.NR_KARTY: "Finanse",
    Label.CVV: "Finanse",
    Label.NR_UMOWY: "Finanse",
    Label.KWOTA: "Finanse",
    Label.DOCHOD: "Finanse",
    # Ubezpieczenia
    Label.NR_POLISY: "Ubezpieczenia",
    Label.NR_SZKODY: "Ubezpieczenia",
    Label.NR_REJESTRACYJNY: "Ubezpieczenia",
    Label.VIN: "Ubezpieczenia",
    Label.NR_KW: "Ubezpieczenia",
    # Zdrowie — art. 9 RODO
    Label.DANE_ZDROWOTNE: "Zdrowie — art. 9 RODO",
    Label.ROZPOZNANIE: "Zdrowie — art. 9 RODO",
    Label.ICD10: "Zdrowie — art. 9 RODO",
    Label.LEK: "Zdrowie — art. 9 RODO",
    Label.NR_DOKUMENTACJI: "Zdrowie — art. 9 RODO",
    Label.PLACOWKA: "Zdrowie — art. 9 RODO",
    Label.LEKARZ: "Zdrowie — art. 9 RODO",
    Label.NPWZ: "Zdrowie — art. 9 RODO",
}


def label_weight(label: Label) -> float:
    """Return the group risk weight for *label* from the TAXONOMY Wagi ryzyka table."""
    return GROUP_WEIGHTS[_LABEL_GROUP[label]]


def _is_valid_rule(span: Span) -> bool:
    """Return ``True`` when *span* is a rule-based span with ``status="valid"``.

    Rule detectors emit ``source="rule"``; ``"rule:<name>"`` is also accepted
    for any legacy or test spans.
    """
    return (span.source == "rule" or span.source.startswith("rule:")) and span.status == "valid"


def _priority_key(span: Span) -> tuple[int, float, int, int]:
    """Return a comparison key: higher tuple = higher precedence.

    Tie-breaking order:
    1. Valid rule span (1) beats NER / suspect rule (0).
    2. Higher group weight from TAXONOMY.
    3. Longer span.
    4. Earlier start (negated so that smaller ``start`` → larger key value).
    """
    return (
        int(_is_valid_rule(span)),
        label_weight(span.label),
        span.end - span.start,
        -span.start,
    )


def fuse(
    rule_spans: list[Span],
    ner_spans: list[Span],
    threshold: float = 0.0,
) -> list[Span]:
    """Merge rule-based and NER spans into a non-overlapping, sorted list.

    Uses an O(n log n) event-sweep with a lazy-deletion max-heap: spans are
    added/removed as the sweep crosses their start/end positions, and the
    winner for each inter-event segment is the top of the heap.

    Args:
        rule_spans: Spans produced by deterministic rule detectors.
        ner_spans:  Spans produced by the NER model (carry a meaningful
                    ``score`` value).
        threshold:  Minimum inclusive score for NER spans in ``[0, 1]``.
                    Spans with ``score < threshold`` are discarded before
                    fusion.  Rule spans are never filtered by threshold.
                    Raises ``ValueError`` for NaN or values outside ``[0, 1]``.

    Returns:
        Non-overlapping list of :class:`~piitier.spans.Span` objects sorted
        by ``start``.  Every character that was covered by any input span is
        covered by exactly one output span.  Adjacent output spans are **not**
        merged even when they share a label or source.

    Raises:
        ValueError: If *threshold* is NaN or outside ``[0, 1]``.
    """
    if math.isnan(threshold) or not (0.0 <= threshold <= 1.0):
        raise ValueError(f"threshold must be a finite value in [0, 1]; got {threshold!r}")

    # Step 1: filter NER spans below threshold (>= is kept).
    ner_filtered = [s for s in ner_spans if s.score >= threshold]

    # Step 2: collect all candidate spans.
    all_spans: list[Span] = list(rule_spans) + ner_filtered
    if not all_spans:
        return []

    # Step 3: build event maps — spans grouped by their start and end positions.
    span_starts: dict[int, list[Span]] = defaultdict(list)
    span_ends: dict[int, list[Span]] = defaultdict(list)
    for s in all_spans:
        span_starts[s.start].append(s)
        span_ends[s.end].append(s)

    breakpoints: list[int] = sorted(span_starts.keys() | span_ends.keys())

    # Step 4: sweep left-to-right, maintaining a lazy-deletion max-heap.
    #
    # Heap entries are 6-tuples:
    #   (neg_valid, neg_weight, neg_length, start, span_id, span)
    # where span_id = id(span) guarantees uniqueness so Python never attempts
    # to compare the Span object.  min-heap on negated priority → max-priority.
    heap: list[Any] = []
    active_ids: set[int] = set()  # id(span) for live spans

    winner_seq: list[tuple[int, int, Span]] = []

    for i, bp in enumerate(breakpoints):
        # Remove spans whose interval has closed at this position.
        for s in span_ends[bp]:
            active_ids.discard(id(s))

        # Add spans whose interval opens at this position.
        for s in span_starts[bp]:
            k = _priority_key(s)
            sid = id(s)
            # Negate all key components for max-heap via Python's min-heap.
            # k = (is_valid, weight, length, -start)
            # neg = (-is_valid, -weight, -length, start) since -(-start)=start
            heapq.heappush(heap, (-k[0], -k[1], -k[2], -k[3], sid, s))
            active_ids.add(sid)

        # Determine winner for segment [bp, next_bp).
        if i + 1 < len(breakpoints):
            next_bp = breakpoints[i + 1]
            # Drain stale entries (spans that have been removed from active_ids).
            while heap and heap[0][4] not in active_ids:
                heapq.heappop(heap)
            if heap:
                winner: Span = heap[0][5]
                winner_seq.append((bp, next_bp, winner))

    if not winner_seq:
        return []

    # Step 5: coalesce consecutive segments owned by the **same input span**.
    # Object identity ensures that two fragments of a loser that straddle a
    # winner are NOT coalesced even though they share label/source.
    result: list[Span] = []
    cur_start, cur_end, cur_span = winner_seq[0]

    for seg_start, seg_end, winner in winner_seq[1:]:
        if winner is cur_span and seg_start == cur_end:
            # Same input span, adjacent segment → extend the current output span.
            cur_end = seg_end
        else:
            result.append(
                Span(
                    cur_start,
                    cur_end,
                    cur_span.label,
                    cur_span.source,
                    cur_span.score,
                    cur_span.status,
                )
            )
            cur_start, cur_end, cur_span = seg_start, seg_end, winner

    result.append(
        Span(
            cur_start,
            cur_end,
            cur_span.label,
            cur_span.source,
            cur_span.score,
            cur_span.status,
        )
    )

    return result
