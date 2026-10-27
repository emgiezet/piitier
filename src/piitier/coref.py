"""Mention coreference and numbered entity assignment (PII-6-b).

Assigns each span of a numbered label (OSOBA, IMIE, NAZWISKO, ADRES, LEKARZ)
an integer entity index, starting at 1 in order of first appearance.
Same entity → same index.  Different entities → different indices.
Numbering is per-label (OSOBA indices are independent of ADRES indices).

Entity key rules
----------------
- ADRES: case-fold + collapsed whitespace; no lemmatisation.
- All other numbered labels: Morfeusz 2 lemma of each token, case-folded;
  unknown token (tag ``ign``) → case-folded surface form.
  Leading title tokens are stripped before computing the key.

Merge rule (OSOBA, LEKARZ only)
--------------------------------
A mention consisting of a lone surname or an initial + surname attaches to
an earlier entity of the **same label** whose surname lemma matches (and
whose first-name lemma starts with the initial, when an initial is present),
**only when exactly one such candidate exists**.  With zero or multiple
candidates the mention receives a new index.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from piitier.labels import Label
from piitier.spans import Span

if TYPE_CHECKING:
    import morfeusz2 as _morfeusz2_t

# ---------------------------------------------------------------------------
# Title sequences to strip from the start of a name span.
# Listed longest-first so the greedy prefix match works correctly.
# All entries are pre-case-folded.
# ---------------------------------------------------------------------------

_TITLE_SEQS: tuple[tuple[str, ...], ...] = (
    ("lek.", "med."),
    ("dr.",),
    ("dr",),
    ("lek.",),
    ("prof.",),
    ("pani",),
    ("pan",),
    ("mgr",),
    ("inż.",),
)

# Labels that use the merge rule (lone surname / initial+surname).
_MERGE_LABELS: frozenset[Label] = frozenset({Label.OSOBA, Label.LEKARZ})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _strip_titles(tokens: list[str]) -> list[str]:
    """Remove leading title tokens (case-insensitively) and return the rest."""
    i = 0
    while i < len(tokens):
        matched = False
        for seq in _TITLE_SEQS:
            n = len(seq)
            if i + n <= len(tokens):
                if all(tokens[i + k].casefold() == seq[k] for k in range(n)):
                    i += n
                    matched = True
                    break
        if not matched:
            break
    return tokens[i:]


def _is_initial(token: str) -> bool:
    """Return True when *token* is a single-letter initial (e.g. ``'J.'`` or ``'J'``)."""
    cf = token.casefold()
    if len(cf) == 2 and cf[1] == "." and cf[0].isalpha():
        return True
    if len(cf) == 1 and cf[0].isalpha():
        return True
    return False


def _get_lemma(morf: "_morfeusz2_t.Morfeusz", token: str) -> str:
    """Return a stable case-folded lemma base for *token* using Morfeusz 2.

    Strategy: collect the base form (part before the colon subparadigm suffix)
    of every non-``ign`` interpretation, then return the shortest base.  When
    multiple bases share the minimum length, the most-frequent (mode) among
    those is returned; alphabetical order breaks remaining ties deterministically.
    Falls back to the case-folded surface when all interpretations are ``ign``.

    This correctly maps inflected Polish names to their citation form, e.g.
    ``"Jana"`` (genitive) → ``"jan"`` (same as the nominative ``"Jan"``).
    """
    results = morf.analyse(token)
    bases: list[str] = []
    for _start, _end, interp in results:
        if interp[2] != "ign":
            bases.append(interp[1].split(":")[0].casefold())
    if not bases:
        return token.casefold()
    min_len = min(len(b) for b in bases)
    candidates = [b for b in bases if len(b) == min_len]
    counts = Counter(candidates)
    max_count = counts.most_common(1)[0][1]
    best = sorted(b for b, c in counts.items() if c == max_count)
    return best[0]


# ---------------------------------------------------------------------------
# Coreferencer
# ---------------------------------------------------------------------------


class Coreferencer:
    """Assigns entity indices to numbered-label spans via lemma-based coreference.

    One Morfeusz 2 instance is created lazily on the first call that requires
    lemmatisation, and reused for all subsequent calls.
    """

    def __init__(self) -> None:
        self._morf: "_morfeusz2_t.Morfeusz | None" = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assign(self, text: str, spans: list[Span]) -> dict[tuple[int, int], int]:
        """Return a mapping from ``(start, end)`` to entity index for numbered spans.

        Non-numbered labels (PESEL, IBAN, …) are absent from the result.
        Indices start at 1 and increase in order of first appearance, per label.
        """
        result: dict[tuple[int, int], int] = {}

        # Group numbered spans by label, preserving document order.
        label_spans: dict[Label, list[Span]] = {}
        for span in sorted(spans, key=lambda s: s.start):
            if span.label.numbered:
                label_spans.setdefault(span.label, []).append(span)

        for label, label_span_list in label_spans.items():
            self._assign_label(text, label, label_span_list, result)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_morf(self) -> "_morfeusz2_t.Morfeusz":
        """Return the shared Morfeusz instance, creating it on first access."""
        if self._morf is None:
            import morfeusz2  # deferred: not imported for rules-only paths

            self._morf = morfeusz2.Morfeusz()
        return self._morf

    def _assign_label(
        self,
        text: str,
        label: Label,
        spans: list[Span],
        result: dict[tuple[int, int], int],
    ) -> None:
        """Assign entity indices for all *spans* of one *label*, updating *result*."""
        use_lemma = label != Label.ADRES
        morf = self._get_morf() if use_lemma else None

        next_idx = 1
        key_to_idx: dict[str, int] = {}
        # For OSOBA/LEKARZ: track per-entity (index, first_lemma, surname_lemma).
        entities: list[tuple[int, str | None, str | None]] = []

        for span in spans:
            pos_key = (span.start, span.end)
            span_text = text[span.start : span.end]

            if label == Label.ADRES:
                entity_key = " ".join(span_text.casefold().split())
                tokens: list[str] = []
            else:
                assert morf is not None
                tokens = _strip_titles(span_text.split())

                if not tokens:
                    # Degenerate: span was all titles.
                    entity_key = span_text.casefold()
                elif label in _MERGE_LABELS and (
                    len(tokens) == 1 or (len(tokens) == 2 and _is_initial(tokens[0]))
                ):
                    # Try to attach this partial mention to an existing entity.
                    merged_idx = self._merge_lookup(morf, tokens, entities)
                    if merged_idx is not None:
                        result[pos_key] = merged_idx
                        continue
                    # No unique candidate → compute lemma key normally.
                    entity_key = " ".join(_get_lemma(morf, t) for t in tokens)
                else:
                    entity_key = " ".join(_get_lemma(morf, t) for t in tokens)

            if entity_key in key_to_idx:
                result[pos_key] = key_to_idx[entity_key]
            else:
                result[pos_key] = next_idx
                key_to_idx[entity_key] = next_idx
                if label in _MERGE_LABELS and morf is not None:
                    first_l, sur_l = self._name_lemmas(morf, tokens)
                    entities.append((next_idx, first_l, sur_l))
                next_idx += 1

    @staticmethod
    def _merge_lookup(
        morf: "_morfeusz2_t.Morfeusz",
        tokens: list[str],
        entities: list[tuple[int, str | None, str | None]],
    ) -> int | None:
        """Return the entity index to merge into, or ``None`` if no unique candidate."""
        if len(tokens) == 1:
            # Lone surname: match entities with the same surname lemma.
            surname_l = _get_lemma(morf, tokens[0])
            candidates = [e for e in entities if e[2] == surname_l]
            return candidates[0][0] if len(candidates) == 1 else None

        # Initial + surname: match on surname lemma and first-name initial.
        initial = tokens[0][0].casefold()
        surname_l = _get_lemma(morf, tokens[1])
        candidates = [
            e for e in entities if e[2] == surname_l and (e[1] is None or e[1].startswith(initial))
        ]
        return candidates[0][0] if len(candidates) == 1 else None

    @staticmethod
    def _name_lemmas(
        morf: "_morfeusz2_t.Morfeusz",
        tokens: list[str],
    ) -> tuple[str | None, str | None]:
        """Return ``(first_lemma, surname_lemma)`` for entity tracking.

        For a single token, ``first_lemma`` is ``None``.
        For an initial+surname pair, ``first_lemma`` is ``None`` (initial unknown).
        For a full name (≥ 2 non-initial tokens), ``first_lemma`` is the first token's
        lemma and ``surname_lemma`` is the last token's lemma.
        """
        if not tokens:
            return None, None
        if len(tokens) == 1:
            return None, _get_lemma(morf, tokens[0])
        if len(tokens) == 2 and _is_initial(tokens[0]):
            return None, _get_lemma(morf, tokens[1])
        return _get_lemma(morf, tokens[0]), _get_lemma(morf, tokens[-1])
