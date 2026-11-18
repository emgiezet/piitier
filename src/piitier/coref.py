"""Mention coreference and numbered entity assignment (PII-6-b).

Assigns each span of a numbered label (OSOBA, IMIE, NAZWISKO, ADRES, LEKARZ)
an integer entity index, starting at 1 in order of first appearance.
Same entity → same index.  Different entities → different indices.
Numbering is per-label (OSOBA indices are independent of ADRES indices).

Entity key rules
----------------
- ADRES: case-fold + collapsed whitespace; no lemmatisation.
- All other numbered labels: singular personal-name bases from Morfeusz 2,
  case-folded and constrained by role, case and gender in full mentions.
  Hyphenated names retain each component. Unknown words use their case-folded
  surface; competing bases remain candidates until a unique earlier match.
  Leading title tokens are stripped before computing the key.

Merge rule (OSOBA, LEKARZ only)
--------------------------------
A mention consisting of a lone surname or an initial + surname attaches to
an earlier entity of the **same label** whose surname lemma matches (and
whose first-name lemma starts with the initial, when an initial is present),
**only when exactly one such candidate exists**.  With zero or multiple
candidates the mention receives a new index.
Full mentions and standalone IMIE/NAZWISKO spans likewise require one compatible
earlier entity. Merging narrows candidate sets rather than adding aliases.
"""

from __future__ import annotations

from dataclasses import dataclass
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


# Preserve token and hyphen boundaries without expanding ambiguous combinations.
type _TokenKey = tuple[frozenset[str], ...]
type _MentionKey = tuple[_TokenKey, ...]


@dataclass(frozen=True, slots=True)
class _Mention:
    key: _MentionKey
    surname_index: int
    relaxed_vocative: bool = False

    @property
    def surname(self) -> _TokenKey:
        return self.key[self.surname_index]


def _name_readings(
    morf: "_morfeusz2_t.Morfeusz",
    token: str,
    qualifier: str,
    *,
    strict: bool = False,
) -> dict[str, set[tuple[str, str]]]:
    """Map singular bases to (case, gender), preferring the requested name role."""
    given_names: dict[str, set[tuple[str, str]]] = {}
    surnames: dict[str, set[tuple[str, str]]] = {}
    nouns: dict[str, set[tuple[str, str]]] = {}
    lexical_edges: set[tuple[int, int]] = set()
    surfaces = (token,) if token == token.title() or qualifier == "noun" else (token, token.title())
    for surface in surfaces:
        for start, end, interp in morf.analyse(surface):
            tag = interp[2]
            if tag == "interp":
                continue
            lexical_edges.add((start, end))
            fields = tag.split(":")
            if len(fields) < 4 or fields[0] != "subst" or "sg" not in fields[1].split("."):
                continue
            base = interp[1].split(":")[0].casefold()
            features = {
                (case, gender) for case in fields[2].split(".") for gender in fields[3].split(".")
            }
            if "imię" in interp[3]:
                given_names.setdefault(base, set()).update(features)
            if "nazwisko" in interp[3]:
                surnames.setdefault(base, set()).update(features)
            if "nazwa_pospolita" in interp[3] or not interp[3]:
                nouns.setdefault(base, set()).update(features)
        if given_names or surnames:
            break

    if len(lexical_edges) != 1:
        return {}
    if qualifier == "noun":
        return nouns
    preferred, alternative = (
        (surnames, given_names) if qualifier == "nazwisko" else (given_names, surnames)
    )
    return preferred if strict else preferred or alternative or nouns


def _get_lemma(
    morf: "_morfeusz2_t.Morfeusz",
    token: str,
    *,
    qualifier: str = "nazwisko",
    features: set[tuple[str, str]] | None = None,
) -> str:
    """Return a unique name base compatible with its role and grammatical context.

    Singular name qualifiers exclude geographic names, generic adjectives and
    plural feminine readings of masculine instrumental forms. Hyphens have their
    own Morfeusz edges, so preserve components rather than selecting punctuation.
    Competing compatible bases fall back to the surface, never shortest or mode.
    """
    if "-" in token:
        return "-".join(
            _get_lemma(morf, part, qualifier=qualifier, features=features)
            for part in token.split("-")
        )
    readings = _name_readings(morf, token, qualifier)
    candidates = [
        base for base, evidence in readings.items() if features is None or evidence & features
    ]
    return candidates[0] if len(candidates) == 1 else token.casefold()


def _keys_match(left: _MentionKey, right: _MentionKey) -> bool:
    """Require a shared base at every corresponding token and hyphen component."""
    return len(left) == len(right) and all(
        len(a) == len(b) and all(x & y for x, y in zip(a, b, strict=True))
        for a, b in zip(left, right, strict=True)
    )


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
        """Compare only surname-index candidates, preserving exact/unresolved keys."""
        morf = self._get_morf() if label != Label.ADRES else None
        addresses: dict[str, int] = {}
        entities: list[_Mention] = []
        by_surname: dict[str, set[int]] = {}
        exact: dict[_MentionKey, int] = {}
        unresolved: dict[tuple[_MentionKey, bool], int] = {}
        parsed: dict[tuple[str, ...], _Mention] = {}

        def store(index: int, mention: _Mention) -> None:
            new_bases = {base for part in mention.surname for base in part}
            old_bases = (
                {base for part in entities[index - 1].surname for base in part}
                if index <= len(entities)
                else set()
            )
            for base in old_bases - new_bases:
                bucket = by_surname[base]
                bucket.remove(index)
                if not bucket:
                    del by_surname[base]
            for base in new_bases - old_bases:
                by_surname.setdefault(base, set()).add(index)
            if index <= len(entities):
                entities[index - 1] = mention
            else:
                entities.append(mention)
            if not mention.relaxed_vocative and all(
                len(bases) == 1 for token in mention.key for bases in token
            ):
                exact[mention.key] = index

        def surname_candidates(mention: _Mention) -> set[int]:
            candidates: set[int] | None = None
            for part in mention.surname:
                matching: set[int] = set()
                for base in part:
                    matching.update(by_surname.get(base, ()))
                candidates = matching if candidates is None else candidates & matching
                if not candidates:
                    return set()
            return candidates or set()

        for span in spans:
            pos_key = (span.start, span.end)
            span_text = text[span.start : span.end]
            if label == Label.ADRES:
                address = " ".join(span_text.casefold().split())
                if address not in addresses:
                    addresses[address] = len(addresses) + 1
                result[pos_key] = addresses[address]
                continue

            assert morf is not None
            tokens = _strip_titles(span_text.split())
            surface_key = tuple(tokens) if tokens else (span_text.casefold(),)
            mention = parsed.get(surface_key)
            if mention is None:
                mention = self._token_candidates(morf, tokens, label)
                if not mention.key:
                    mention = _Mention(((frozenset({span_text.casefold()}),),), 0)
                parsed[surface_key] = mention
            unresolved_key = (mention.key, mention.relaxed_vocative)
            prior = unresolved.get(unresolved_key)
            if prior is not None:
                result[pos_key] = prior
                continue
            if not mention.relaxed_vocative and mention.key in exact:
                result[pos_key] = exact[mention.key]
                continue

            candidates = surname_candidates(mention)
            blocked_vocative = False
            if mention.relaxed_vocative:
                candidates = {
                    index
                    for index in candidates
                    if _keys_match((entities[index - 1].surname,), (mention.surname,))
                }
                blocked_vocative = len(candidates) != 1
                if not blocked_vocative and mention.key in exact:
                    result[pos_key] = exact[mention.key]
                    continue

            partial = label in _MERGE_LABELS and (
                len(tokens) == 1 or (len(tokens) == 2 and _is_initial(tokens[0]))
            )
            matches: list[int] = []
            if partial:
                merged = self._merge_lookup(tokens, mention, entities, candidates)
                if merged is not None:
                    result[pos_key] = merged
                    old = entities[merged - 1]
                    key = list(old.key)
                    key[old.surname_index] = tuple(
                        a & b for a, b in zip(old.surname, mention.surname, strict=True)
                    )
                    store(merged, _Mention(tuple(key), old.surname_index, old.relaxed_vocative))
                    continue
            elif not blocked_vocative:
                matches = [
                    index
                    for index in candidates
                    if _keys_match(entities[index - 1].key, mention.key)
                ]
                if len(matches) == 1:
                    index = matches[0]
                    old = entities[index - 1]
                    result[pos_key] = index
                    # Narrow, never union: an ambiguous mention must not bridge people.
                    narrowed = tuple(
                        tuple(a & b for a, b in zip(before, after, strict=True))
                        for before, after in zip(old.key, mention.key, strict=True)
                    )
                    store(index, _Mention(narrowed, old.surname_index, old.relaxed_vocative))
                    continue
            if blocked_vocative:
                # Do not store the guessed first-name base as an exact identity.
                key = list(mention.key)
                key[0] = tuple(frozenset({part.casefold()}) for part in tokens[0].split("-"))
                mention = _Mention(tuple(key), mention.surname_index, True)
            index = len(entities) + 1
            store(index, mention)
            result[pos_key] = index
            if (
                partial
                or blocked_vocative
                or len(matches) > 1
                or any(len(bases) > 1 for token in mention.key for bases in token)
            ):
                unresolved[unresolved_key] = index

    @staticmethod
    def _merge_lookup(
        tokens: list[str],
        mention: _Mention,
        entities: list[_Mention],
        candidates: set[int],
    ) -> int | None:
        """Attach a partial mention only to one surname/initial-compatible entity."""
        initial = tokens[0][0].casefold() if len(tokens) == 2 else None
        matching = [
            index
            for index in candidates
            if _keys_match((entities[index - 1].surname,), (mention.surname,))
            and (
                initial is None
                or len(entities[index - 1].key) == 1
                or any(
                    _is_initial(base) or base.startswith(initial)
                    for base in entities[index - 1].key[0][0]
                )
            )
        ]
        return matching[0] if len(matching) == 1 else None

    @staticmethod
    def _token_candidates(
        morf: "_morfeusz2_t.Morfeusz", tokens: list[str], label: Label
    ) -> _Mention:
        """Retain compatible bases without guessing among name homographs."""
        full = label in _MERGE_LABELS and len(tokens) > 1 and not _is_initial(tokens[0])
        surname_index = len(tokens) - 1
        first_features: set[tuple[str, str]] | None = None
        surname_features: set[tuple[str, str]] | None = None
        relaxed_vocative = False
        if full:
            # Ordinary modifiers after the surname are not surname context.
            surname_index = next(
                (
                    index
                    for index in range(len(tokens) - 1, 0, -1)
                    if any(
                        _name_readings(morf, part, "nazwisko", strict=True)
                        for part in tokens[index].split("-")
                    )
                ),
                surname_index,
            )
            first = _name_readings(morf, tokens[0], "imię")
            first_evidence = {item for evidence in first.values() for item in evidence}
            shared = first_evidence or None
            surname_evidence: set[tuple[str, str]] | None = None
            for part in tokens[surname_index].split("-"):
                readings = _name_readings(morf, part, "nazwisko")
                evidence = {item for values in readings.values() for item in values}
                if evidence:
                    shared = evidence if shared is None else shared & evidence
                    surname_evidence = (
                        evidence if surname_evidence is None else surname_evidence & evidence
                    )
            first_features = surname_features = shared
            if shared == set() and surname_evidence:
                # In direct address the given name can be vocative while the
                # surname stays nominative. Do not relax other case mismatches.
                vocative = {
                    (case, gender)
                    for case, gender in first_evidence
                    if case == "voc" and ("nom", gender) in surname_evidence
                }
                if vocative:
                    first_features = vocative
                    surname_features = {("nom", gender) for _case, gender in vocative}
                    relaxed_vocative = True

        key: list[_TokenKey] = []
        for index, token in enumerate(tokens):
            role = "imię" if label == Label.IMIE or (full and index < surname_index) else "nazwisko"
            features = surname_features if index == surname_index else first_features
            parts: list[frozenset[str]] = []
            for part in token.split("-"):
                if full and index > surname_index:
                    parts.append(
                        frozenset({_get_lemma(morf, part, qualifier="noun", features=features)})
                    )
                    continue
                readings = _name_readings(morf, part, role)
                if full and 0 < index < surname_index and features is not None:
                    # A man's middle name may be feminine (Jan Maria).
                    cases = {case for case, _gender in features}
                    bases = frozenset(
                        base
                        for base, evidence in readings.items()
                        if any(case in cases for case, _gender in evidence)
                    )
                else:
                    bases = frozenset(
                        base
                        for base, evidence in readings.items()
                        if features is None or evidence & features
                    )
                parts.append(bases or frozenset({part.casefold()}))
            key.append(tuple(parts))
        return _Mention(tuple(key), surname_index, relaxed_vocative)
