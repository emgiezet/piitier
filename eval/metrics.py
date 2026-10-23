"""Evaluation metrics module (eval/metrics.py) — PII-4-d.

Czyste funkcje ewaluacji: precision/recall encji (strict i partial),
recall ważony ryzykiem, leak rate, wierność tekstu, spójność numeracji, throughput.
"""

from __future__ import annotations

import math
import resource
from dataclasses import dataclass
from typing import Literal

from piitier.labels import Label
from piitier.spans import Span


@dataclass(frozen=True)
class EntityPRF:
    precision: float
    recall: float
    f1: float


def _spans_match(g: Span, p: Span, match: Literal["strict", "partial"]) -> bool:
    if g.label != p.label:
        return False
    if match == "strict":
        return g.start == p.start and g.end == p.end
    else:
        return max(g.start, p.start) < min(g.end, p.end)


def entity_metrics(
    gold: list[Span],
    pred: list[Span],
    match: Literal["strict", "partial"] = "strict",
) -> EntityPRF:
    """Compute micro EntityPRF (precision, recall, f1) for gold vs pred spans.

    strict: same label and identical [start, end).
    partial: same label and any non-empty overlap [start, end).
    Zero-gold and zero-pred -> P/R/F1 = 0.0.
    """
    if not gold and not pred:
        return EntityPRF(0.0, 0.0, 0.0)
    if not gold or not pred:
        return EntityPRF(0.0, 0.0, 0.0)

    matched_gold: set[int] = set()
    matched_pred: set[int] = set()

    for p_idx, p in enumerate(pred):
        for g_idx, g in enumerate(gold):
            if g_idx not in matched_gold and _spans_match(g, p, match):
                matched_gold.add(g_idx)
                matched_pred.add(p_idx)
                break

    tp = len(matched_pred)
    precision = tp / len(pred) if len(pred) > 0 else 0.0
    recall = tp / len(gold) if len(gold) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0.0 else 0.0

    return EntityPRF(precision=precision, recall=recall, f1=f1)


def entity_metrics_by_label(
    gold: list[Span],
    pred: list[Span],
    match: Literal["strict", "partial"] = "strict",
) -> dict[Label, EntityPRF]:
    """Compute EntityPRF per label for labels appearing in gold OR pred."""
    all_labels = {s.label for s in gold} | {s.label for s in pred}
    result: dict[Label, EntityPRF] = {}
    for lbl in sorted(all_labels, key=lambda lbl_item: lbl_item.name):
        g_lbl = [s for s in gold if s.label == lbl]
        p_lbl = [s for s in pred if s.label == lbl]
        result[lbl] = entity_metrics(g_lbl, p_lbl, match)
    return result


GROUP_WEIGHTS: dict[str, float] = {
    "Identyfikatory państwowe": 1.0,
    "Finanse": 1.0,
    "Ubezpieczenia": 0.9,
    "Kontakt i lokalizacja": 0.8,
    "Zdrowie — art. 9 RODO": 0.8,
    "Identyfikacja osoby": 0.6,
}


def group_for_label(label: Label) -> str:
    """Map Label to its risk group name from TAXONOMY.md."""
    if label in {
        Label.OSOBA,
        Label.IMIE,
        Label.NAZWISKO,
        Label.DATA_URODZENIA,
        Label.WIEK,
        Label.PLEC,
    }:
        return "Identyfikacja osoby"
    if label in {
        Label.PESEL,
        Label.NR_DOWODU,
        Label.NR_PASZPORTU,
        Label.NR_PRAWA_JAZDY,
        Label.NIP,
        Label.REGON,
    }:
        return "Identyfikatory państwowe"
    if label in {
        Label.ADRES,
        Label.KOD_POCZTOWY,
        Label.MIEJSCOWOSC,
        Label.TELEFON,
        Label.EMAIL,
        Label.IP,
        Label.GEO,
    }:
        return "Kontakt i lokalizacja"
    if label in {
        Label.IBAN,
        Label.NR_RACHUNKU,
        Label.NR_KARTY,
        Label.CVV,
        Label.NR_UMOWY,
        Label.KWOTA,
        Label.DOCHOD,
    }:
        return "Finanse"
    if label in {
        Label.NR_POLISY,
        Label.NR_SZKODY,
        Label.NR_REJESTRACYJNY,
        Label.VIN,
        Label.NR_KW,
    }:
        return "Ubezpieczenia"
    if label in {
        Label.DANE_ZDROWOTNE,
        Label.ROZPOZNANIE,
        Label.ICD10,
        Label.LEK,
        Label.NR_DOKUMENTACJI,
        Label.PLACOWKA,
        Label.LEKARZ,
        Label.NPWZ,
    }:
        return "Zdrowie — art. 9 RODO"
    raise ValueError(f"Unknown label: {label}")


def risk_weighted_recall(gold: list[Span], pred: list[Span]) -> float:
    """Compute risk-weighted recall (strict match). Zero-gold -> 0.0."""
    if not gold:
        return 0.0

    total_weight = 0.0
    matched_weight = 0.0

    matched_gold: set[int] = set()
    for p in pred:
        for g_idx, g in enumerate(gold):
            if g_idx not in matched_gold and _spans_match(g, p, "strict"):
                matched_gold.add(g_idx)
                break

    for g_idx, g in enumerate(gold):
        w = GROUP_WEIGHTS[group_for_label(g.label)]
        total_weight += w
        if g_idx in matched_gold:
            matched_weight += w

    if total_weight == 0.0:
        return 0.0
    return matched_weight / total_weight


DIRECT_IDENTIFIERS: frozenset[Label] = frozenset(
    {
        Label.PESEL,
        Label.NR_DOWODU,
        Label.NR_PASZPORTU,
        Label.NR_PRAWA_JAZDY,
        Label.NIP,
        Label.REGON,
        Label.IBAN,
        Label.NR_RACHUNKU,
        Label.NR_KARTY,
        Label.TELEFON,
        Label.EMAIL,
        Label.IP,
        Label.NR_UMOWY,
        Label.NR_POLISY,
        Label.NR_SZKODY,
        Label.NR_REJESTRACYJNY,
        Label.VIN,
        Label.NR_KW,
        Label.NPWZ,
        Label.NR_DOKUMENTACJI,
    }
)


@dataclass(frozen=True)
class LeakRate:
    docs_leaked: int
    docs_total: int
    values_leaked: int
    values_total: int
    leaked_doc_ids: list[str]


def leak_rate(
    originals: list[str],
    gold_spans: list[list[Span]],
    rendered: list[str],
    doc_ids: list[str] | None = None,
) -> LeakRate:
    """Compute leak rate across documents."""
    if doc_ids is None:
        doc_ids = [str(i) for i in range(len(originals))]

    docs_total = len(originals)
    values_total = 0
    values_leaked = 0
    docs_leaked = 0
    leaked_doc_ids: list[str] = []

    for orig, spans, rend, doc_id in zip(originals, gold_spans, rendered, doc_ids):
        doc_has_direct_leak = False
        for span in spans:
            values_total += 1
            if span.start < 0 or span.end > len(orig) or span.start >= span.end:
                continue
            val = orig[span.start : span.end]
            if not val:
                continue
            is_leaked = rend.find(val) != -1
            if is_leaked:
                values_leaked += 1
                if span.label in DIRECT_IDENTIFIERS:
                    doc_has_direct_leak = True

        if doc_has_direct_leak:
            docs_leaked += 1
            leaked_doc_ids.append(doc_id)

    return LeakRate(
        docs_leaked=docs_leaked,
        docs_total=docs_total,
        values_leaked=values_leaked,
        values_total=values_total,
        leaked_doc_ids=leaked_doc_ids,
    )


def _walk_alignment(
    original: str,
    rendered: str,
    spans: list[Span],
) -> tuple[int, list[tuple[Span, str]]]:
    sorted_spans = sorted(spans, key=lambda s: s.start)
    orig_pos = 0
    res_pos = 0
    mismatches = 0
    span_placeholders: list[tuple[Span, str]] = []

    for i, span in enumerate(sorted_spans):
        gap = span.start - orig_pos
        if gap > 0:
            orig_chunk = original[orig_pos : span.start]
            res_chunk = rendered[res_pos : res_pos + gap]
            for o_c, r_c in zip(orig_chunk, res_chunk):
                if o_c != r_c:
                    mismatches += 1
            if len(res_chunk) < gap:
                mismatches += gap - len(res_chunk)
            res_pos += len(res_chunk)
            orig_pos = span.start

        orig_pos = span.end

        next_orig_pos = len(original) if i == len(sorted_spans) - 1 else sorted_spans[i + 1].start
        orig_next_chunk = original[span.end : next_orig_pos]

        if orig_next_chunk:
            next_pos = rendered.find(orig_next_chunk, res_pos)
            if next_pos != -1:
                ph = rendered[res_pos:next_pos]
                res_pos = next_pos
            else:
                ph = span.label.placeholder
                res_pos += len(ph)
        else:
            ph = span.label.placeholder
            res_pos += len(ph)

        span_placeholders.append((span, ph))

    if orig_pos < len(original):
        orig_tail = original[orig_pos:]
        res_tail = rendered[res_pos:]
        for o_c, r_c in zip(orig_tail, res_tail):
            if o_c != r_c:
                mismatches += 1
        if len(res_tail) < len(orig_tail):
            mismatches += len(orig_tail) - len(res_tail)

    return mismatches, span_placeholders


def fidelity(original: str, rendered: str, spans: list[Span]) -> int:
    """Count character mismatches outside spans between original and rendered."""
    mismatches, _ = _walk_alignment(original, rendered, spans)
    return mismatches


@dataclass(frozen=True)
class NumberingStats:
    same_entity_consistent: int
    same_entity_total: int
    different_entity_distinct: int
    different_entity_total: int


def numbering_consistency(
    rendered: str,
    spans: list[Span],
    labels_numbered: set[Label],
    original: str,
    masked_spans: list[Span],
) -> NumberingStats:
    """Compute numbering consistency stats for numbered entity labels."""
    target_spans = [s for s in spans if s.label in labels_numbered]

    _, span_phs = _walk_alignment(original, rendered, masked_spans)
    masked_span_to_ph = {s: ph for s, ph in span_phs}
    sorted_masked = sorted(masked_spans, key=lambda s: s.start)

    records: list[tuple[Label, str, str]] = []

    for g in target_spans:
        matched_ph: str | None = None
        for m in sorted_masked:
            if max(g.start, m.start) < min(g.end, m.end):
                if m in masked_span_to_ph:
                    matched_ph = masked_span_to_ph[m]
                    break
        if matched_ph is not None:
            val = original[g.start : g.end]
            records.append((g.label, val, matched_ph))

    same_entity_consistent = 0
    same_entity_total = 0
    different_entity_distinct = 0
    different_entity_total = 0

    n = len(records)
    for i in range(n):
        for j in range(i + 1, n):
            lbl_i, v_i, p_i = records[i]
            lbl_j, v_j, p_j = records[j]
            if lbl_i != lbl_j:
                continue

            if v_i == v_j:
                same_entity_total += 1
                if p_i == p_j:
                    same_entity_consistent += 1
            else:
                different_entity_total += 1
                if p_i != p_j:
                    different_entity_distinct += 1

    return NumberingStats(
        same_entity_consistent=same_entity_consistent,
        same_entity_total=same_entity_total,
        different_entity_distinct=different_entity_distinct,
        different_entity_total=different_entity_total,
    )


@dataclass(frozen=True)
class ThroughputStats:
    docs_per_second: float
    p95_latency_seconds: float


def throughput_stats(latencies_seconds: list[float]) -> ThroughputStats:
    """Compute throughput (docs/s) and p95 latency (nearest-rank)."""
    if not latencies_seconds:
        return ThroughputStats(0.0, 0.0)
    total_time = sum(latencies_seconds)
    n = len(latencies_seconds)
    docs_per_second = n / total_time if total_time > 0.0 else 0.0

    sorted_lats = sorted(latencies_seconds)
    idx = math.ceil(0.95 * n) - 1
    idx = max(0, min(idx, n - 1))
    p95 = sorted_lats[idx]

    return ThroughputStats(
        docs_per_second=docs_per_second,
        p95_latency_seconds=p95,
    )


def peak_ram_bytes() -> int:
    """Return peak resident set size in bytes (Linux)."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_maxrss * 1024
