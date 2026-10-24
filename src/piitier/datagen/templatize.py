"""Real-document → placeholder-template harvester (``templatize`` command).

Source PDFs (fictitious test identities, approved for training) are layout donors. Every
value is replaced by a ``{{LABEL}}`` placeholder: a local LLM first *flags* verbatim spans
(CLAUDE.md invariant 5; code decides what to replace), then rule detectors redact what is
left. An acceptance gate re-scans every literal chunk and drops any template that still
carries a value-like string, which would otherwise reach training as unlabelled PII.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from pypdf.errors import PdfReadError

import piitier
from piitier.datagen.build import DOC_TYPES
from piitier.datagen.llm import (
    _SUPPORTED_LABELS,
    OllamaUnreachableError,
    _generate,
    _get_opener,
    _probe_model,
    _validate_ollama_url,
)
from piitier.datagen.template import Placeholder, Template, TemplateError, parse
from piitier.labels import Label
from piitier.loaders import PdfNoTextError, load_pdf

# Taxonomy entries a real policy carries that no rule detector in ``piitier.rules`` covers.
_LLM_LABELS: frozenset[Label] = frozenset(
    {
        Label.OSOBA,
        Label.ADRES,
        Label.MIEJSCOWOSC,
        Label.KOD_POCZTOWY,
        Label.TELEFON,
        Label.EMAIL,
        Label.DATA_URODZENIA,
        Label.NR_POLISY,
        Label.NR_REJESTRACYJNY,
        Label.VIN,
        Label.NR_SZKODY,
        Label.KWOTA,
    }
)
if not _LLM_LABELS <= _SUPPORTED_LABELS:
    raise ValueError(
        "LLM labels without a generator: "
        + ", ".join(sorted(lbl.name for lbl in _LLM_LABELS - _SUPPORTED_LABELS))
    )
_LLM_LABEL_NAMES: frozenset[str] = frozenset(lbl.name for lbl in _LLM_LABELS)

_MAX_CHUNK = 2000
_MIN_CHUNK = 400
_MIN_PLACEHOLDERS = 3
_GENERATE_TIMEOUT = 300
# A full span list for a 2000-character chunk is a few hundred tokens; the cap turns a
# runaway generation into a parse error for one chunk instead of a 5-minute hang.
_MAX_RESPONSE_TOKENS = 1024

_PLACEHOLDER_SPLIT_RE = re.compile(r"(\{\{[^{}]*\}\})")
_DIGIT_RUN_RE = re.compile(r"\d(?:[ \-]?\d){6,}")
_POSTCODE_RE = re.compile(r"\d{2}-\d{3}")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
# Dates other than a birth date are not taxonomy entities: they stay as literal text and
# are blanked out before the digit-run and postcode checks (``02-2023`` looks like ``02-202``).
_DATE_RE = re.compile(
    r"\b(?:\d{2}[-./]\d{2}[-./]\d{4}|\d{4}[-./]\d{2}[-./]\d{2})(?:\s+\d{2}:\d{2}(?::\d{2})?)?\b"
)
# Company register numbers (KRS; the Bulgarian EIK; the Latvian "ujednolicony kod
# identyfikacyjny") are not a taxonomy entity — the NIP detector excludes KRS on purpose —
# so they stay literal and are blanked out before the digit-run check.
# Pattern is tight (#10): keyword + optional "nr" + exactly 9–11 digits, no freeform gap.
# Extended (M1): Latvian / other EU register phrases "wpisana do Rejestru Przedsiębiorstw
# … pod nr NNNNNNNNN" are also company-register identifiers, not PII.
_KRS_NUMBER_RE = re.compile(
    r"\bKRS\b[ \t:.]*(?:(?:pod[ \t]+)?nr[ \t:.]*)?(?:\d{10}(?!\d))"
    r"|\bEIK\b[ \t:.]*\d{9,11}(?!\d)"
    r"|(?:ujednolicony )?kod identyfikacyjny[ \t:]*\d{9,11}(?!\d)"
    # Latvian / other EU registries: "wpisana do Rejestru Przedsiębiorstw Republiki
    # Łotewskiej pod nr 40103424710" and equivalent phrases.
    r"|wpisan[ay]\s+do\s+rejestru\b[^\n.]{0,80}pod\s+nr\s*\d{9,11}(?!\d)"
    r"|Rejestru?\s+Przedsiębiorstw\b[^\n.]{0,80}pod\s+nr\s*\d{9,11}(?!\d)",
    re.IGNORECASE,
)
# Code-side rules run after LLM marking: values whose shape and context are unambiguous are
# not left to the model.
# Fix (#6): one-decimal amounts (12,5 zł) and double-space before currency.
_AMOUNT_RE = re.compile(
    r"(?<![\d.,])(?:\d{1,3}(?:[ .]\d{3})+|\d+)(?:[.,]\d{1,2})?"
    r"(?=[ \t]*(?:zł|złotych|PLN|€|EUR|euro)(?!\w))"
)
# A street with a house number, introduced by a street-type abbreviation.
# Fix (#1, #8): case-insensitive prefix with (?<![\w.]) to avoid domain endings
# (www.pzu.pl); line wrap only when the next line is just a house number.
# Overlap resolution in _redact_literal now keeps the LONGEST span.
_STREET_RE = re.compile(
    r"(?<![\w.])(?i:ul\.|al\.|aleja|os\.|pl\.|plac|rondo)[ \t]*"
    r"[A-ZŁŚŻŹĆŃÓĄĘ0-9][\w.'-]*(?:[ \t]+[\w.'-]+){0,4}?[ \t]*"
    r"(?:\n[ \t]*\d{1,4}[A-Za-z]?(?:/\d{1,4})?(?=[ \t]*(?:,|\n|$))"
    r"|\d{1,4}[A-Za-z]?(?:[/ ]\d{1,4}[A-Za-z]?)?(?![\d-]))"
)
# VIN: 17 characters without I/O/Q, mixing letters and digits, not part of a longer token.
_VIN_RULE_RE = re.compile(
    r"(?<![A-Za-z0-9])(?=[A-Z0-9]{0,16}\d)(?=[A-Z0-9]{0,16}[A-Z])[A-HJ-NPR-Z0-9]{17}(?![A-Za-z0-9])"
)
# Leak check: a VIN-shaped run anywhere, even glued to text by PDF extraction.
_VIN_LEAK_RE = re.compile(
    r"(?=[A-HJ-NPR-Z0-9]{0,16}\d)(?=[A-HJ-NPR-Z0-9]{0,16}[A-Z])[A-HJ-NPR-Z0-9]{17}"
)
# Not inside a longer dash-grouped number (a NIP written ``123-45-67-890``).
_POSTCODE_RULE_RE = re.compile(r"(?<![\d-])\d{2}-\d{3}(?![\d-])")
# No trailing sentence period in the span.
_EMAIL_RULE_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# A phone number needs a phone keyword or ``+`` right before it, or a hotline prefix
# (800/801); a bare 9-digit run may be a customer or policy number.
# Fix (#9): replace lookbehinds with proper word-boundary keyword prefix.
_PHONE_RE = re.compile(
    r"\b(?:tel(?:efon\w*)?|fax|infolinia)\b(?:[ \t]*(?:kom\.?|kontaktowy|komórkowy))?[ \t:.]*"
    r"((?:\+|\()?\d[\d \t()-]{7,16}\d)"
    r"|(?<![\w+])(\+\d{2}[\d \t()-]{7,14}\d|80[01][ \t-]?\d{3}[ \t-]?\d{3})(?![\d-])",
    re.IGNORECASE,
)
# Registration plate keyword rule (TA #5): recognised only after the explicit keyword.
_PLATE_KEYWORD_RE = re.compile(
    r"(?i)(?:numer|nr)[ \t]+rejestracyjny[: \t]*\n?[ \t]*([A-Z]{2,3}[ ]?\d[A-Z0-9]{3,5})\b"
)
# Leak: a plate keyword followed by an unredacted plate string.
_PLATE_LEAK_RE = re.compile(
    r"(?i)(?:numer|nr)[ \t]+rejestracyjny[: \t]*\n?[ \t]*[A-Z]{2,3}[ ]?\d[A-Z0-9]{3,5}\b"
)
# B1: plate immediately before {{VIN}} — code rule in _rule_redact replaces it, and the
# gate catches any survivor.  Shape: 2–3 uppercase letters + digit + 3–5 alphanumerics,
# not preceded by another alphanumeric (prevents matching the middle of a product code).
_PLATE_BEFORE_VIN_RE = re.compile(
    r"(?<![A-Za-z0-9])([A-Z]{2,3}\s?\d[A-Z0-9]{3,5})(?=\s+"
    + re.escape("{{VIN}}")
    + r")",
)
# Gate: plate-shaped token directly before {{VIN}} that the rule missed.
_PLATE_BEFORE_VIN_GATE_RE = re.compile(
    r"(?<![A-Za-z0-9])[A-Z]{2,3}\s?\d[A-Z0-9]{3,5}\s+"
    + re.escape("{{VIN}}")
)
# Leak: street prefix still present in a literal — the street was not redacted.
_STREET_LEAK_RE = re.compile(
    r"(?<![\w.])(?:ul\.|al\.|aleja|os\.|pl\.|plac|rondo)[ \t]+",
    re.IGNORECASE,
)
# Leak (TA #3): foreign or standalone postcode — a 4–5 digit run followed by a Polish-
# capitalised city name, after blanking _DATE_RE and _KRS_NUMBER_RE.
_FOREIGN_POSTCODE_RE = re.compile(r"\b\d{4,5}[ \t]+[A-ZŁŚŻŹĆŃÓĄĘ][a-ząćęłńóśźż]{3,}")
# ``{{ADRES}}`` renders the full ``street, postcode town`` (people.get_address_field), so a
# source layout ``street, postcode city`` must collapse into one ``{{ADRES}}`` or the
# rendered line repeats a second, unrelated postcode and town.
#
# All address-merge patterns are built from Label enum names (#18) so renaming a label
# automatically updates the regex. They all support ``{{ADRES#n}}`` entity IDs.
_TOWN_RE_PAT = (
    r"[A-ZŁŚŻŹĆŃÓĄĘ][a-ząćęłńóśźż]+"
    r"(?:[ -][A-ZŁŚŻŹĆŃÓĄĘ][a-ząćęłńóśźż]+)*"  # multi-word / hyphenated (#7)
)
_ADRES_STEM = re.escape("{{" + Label.ADRES.name)  # \{\{ADRES
_ADRES_ANY = _ADRES_STEM + r"(?:#\d+)?\}\}"  # {{ADRES}} or {{ADRES#n}}
_KOD_PAT = re.escape("{{" + Label.KOD_POCZTOWY.name + "}}")  # \{\{KOD_POCZTOWY\}\}
_MIEJ_PAT = re.escape("{{" + Label.MIEJSCOWOSC.name + "}}")  # \{\{MIEJSCOWOSC\}\}

# Tail merge: {{ADRES[#n]?}} followed by postcode/town parts → keep {{ADRES[#n]?}} (#4, #7).
# The postcode may sit on the next line(s); the town, multi-word or hyphenated.
_ADDRESS_TAIL_PAT = (
    r"("
    + _ADRES_ANY
    + r")(?:"
    + r",?[ \t]*(?:"
    + r"(?:"
    + _KOD_PAT
    + r"|\d{4})"
    + r"(?:[ \t]+(?:"
    + _MIEJ_PAT
    + r"|"
    + _TOWN_RE_PAT
    + r")"
    + r"|[ \t]*\n[ \t]*(?:"
    + _MIEJ_PAT
    + r"|"
    + _TOWN_RE_PAT
    + r")(?=[,\n]|$))?"
    + r"|"
    + _MIEJ_PAT
    + r")"
    + r"|,?[ \t]*\n{1,2}[ \t]*"
    + _KOD_PAT
    + r"(?:,?[ \t]*(?:"
    + _MIEJ_PAT
    + r"|[^\n{}]{0,30}))?(?=\n|$)"
    + r")+"
)
_ADDRESS_TAIL_RE = re.compile(_ADDRESS_TAIL_PAT)
# Head merge (TA #2, #8): [city] {{KOD_POCZTOWY}} [town] or {{MIEJSCOWOSC}} [digits]
# immediately before {{ADRES[#n]?}} → drop the prefix, keep {{ADRES[#n]?}}.
_ADDRESS_HEAD_PAT = (
    r"(?:"
    + r"(?:"
    + _TOWN_RE_PAT
    + r"[ \t,]+)?"  # optional literal city
    + _KOD_PAT
    + r"[,]?[ \t]*"  # {{KOD_POCZTOWY}}
    + r"(?:"
    + _MIEJ_PAT
    + r"|"
    + _TOWN_RE_PAT
    + r")?[ \t,]*"
    + r"|"
    + _MIEJ_PAT
    + r"(?:[ \t]*\d{4})?[,]?[ \t]*"  # {{MIEJSCOWOSC}} [digits]
    + r")(?="
    + _ADRES_ANY
    + r")"
)
_ADDRESS_HEAD_RE = re.compile(_ADDRESS_HEAD_PAT)
# Trailer merge (TA #7): {{ADRES[#n]?}} followed by another {{ADRES[#n]?}} or a bare
# street-name+number (no prefix) → keep the first {{ADRES[#n]?}}.
_ADRES_TRAILER_PAT = (
    r"("
    + _ADRES_ANY
    + r")"
    + r"(?:[,\n ]+(?:"
    + _ADRES_ANY
    + r"|"
    + _TOWN_RE_PAT
    + r"[ \t]+\d{1,4}[A-Za-z]?(?:/\d{1,4})?(?![\d-])"
    + r"))+"
)
_ADRES_TRAILER_RE = re.compile(_ADRES_TRAILER_PAT)
# Overlapping capitalised bigrams: a surviving person, street, or city name.
_BIGRAM_RE = re.compile(
    r"(?=\b([A-ZŁŚŻŹĆŃÓĄĘ][a-ząćęłńóśźż]{2,}\s+[A-ZŁŚŻŹĆŃÓĄĘ][a-ząćęłńóśźż]{2,})\b)"
)

_DATAGEN_DIR = Path(__file__).parent
_ALLOWLIST_FILE = _DATAGEN_DIR / "templatize_allowlist.txt"
# Repository root for reject_dir containment check (#11).
_REPO_ROOT = Path(__file__).resolve().parents[3]

# Reject reasons that drop a chunk (written to ``reject_dir`` for inspection).
_CHUNK_REJECTS = (
    "llm_parse_error",
    "parse_error",
    "unknown_label",
    "too_few_placeholders",
    "leaked_value",
    "llm_bad_label",
    "llm_error",
)

# Uppercase name pairs (``ANDRZEJ CHMIELEWSKI``): _BIGRAM_RE only sees ``Imię Nazwisko``.
_CAPS_BIGRAM_RE = re.compile(r"(?=\b([A-ZŁŚŻŹĆŃÓĄĘ]{3,}[ \t]+[A-ZŁŚŻŹĆŃÓĄĘ]{3,})\b)")
# A bare ALL-CAPS word on its own line that is not allowlisted is likely a split person
# name (``KAROLINA\nOGRODNIK`` printed one per line by some PDF generators) (TA #6).
# A cross-newline bigram regex would also match document-structure words like
# ``POLISA\nPESEL:``; the line-anchor pattern avoids those false positives.
_SOLO_CAPS_LINE_RE = re.compile(r"(?m)^([A-ZŁŚŻŹĆŃÓĄĘ]{3,})$")
# Company/entity-type suffixes that disqualify an OSOBA span (TA #6).
_COMPANY_SUFFIX_RE = re.compile(
    r"(?i)\b(?:sp(?:\.\s*z\s*o\.o\.?)?|s\.a\.|s\.k\.a\.|se\b|gmbh|llc|ltd\.?|b\.v\.)"
)
# Context fixes for mislabelled placeholders (TA #4).
# (a) EIK / "kod identyfikacyjny" followed by {{NR_POLISY}} → strip the placeholder.
_EIK_CONTEXT_RE = re.compile(
    r"(\bEIK\b|(?:ujednolicony )?kod identyfikacyjny)\s*"
    + re.escape("{{" + Label.NR_POLISY.name + "}}"),
    re.IGNORECASE,
)
# (b) "({{NR_POLISY}})" after "Agent:" → {{NIP}}
_AGENT_NIP_RE = re.compile(
    r"(\bAgent:[^\n]*\()" + re.escape("{{" + Label.NR_POLISY.name + "}}") + r"(\))",
    re.IGNORECASE | re.DOTALL,
)
# (c) "Policy no" / "Policy no)" before {{PESEL}} → {{NR_POLISY}}
_POLICY_NO_PESEL_RE = re.compile(
    r"(?i)(Policy no\)?[ \t,]*)" + re.escape("{{" + Label.PESEL.name + "}}"),
)
# Gate (M1/M2): a PESEL or NR_POLISY placeholder directly after a company-register
# keyword is a misidentified public register number, not PII.
_REGISTER_PLACEHOLDER_GATE_RE = re.compile(
    r"(?:Rejestru?\s+Przedsiębiorstw|Republiki\s+Łotewskiej"
    r"|wpisan[ay]\s+do\s+rejestru"
    r"|\bEIK\b|(?:ujednolicony\s+)?kod\s+identyfikacyjny"
    r")[^\n]{0,80}\{\{(?:PESEL|NR_POLISY)\}\}",
    re.IGNORECASE,
)
# Gate (m1): a lowercase word immediately followed by digits after an ADRES placeholder
# is a junk token that slipped through normalisation (e.g. ``{{ADRES#1}} city2111``).
_ADRES_JUNK_SUFFIX_RE = re.compile(
    r"\{\{ADRES(?:#\d+)?\}\}\s+[a-z]+\d+"
)


@functools.cache
def _allowlist() -> frozenset[str]:
    """Capitalised words that are legitimately not PII in Polish policies."""
    words = set()
    for line in _ALLOWLIST_FILE.read_text(encoding="utf-8").splitlines():
        token = line.split("#", 1)[0].strip()
        if token:
            words.add(token)
    return frozenset(words)


def _normalise(text: str) -> str:
    """NBSP → space; drop T E S T stamps and horizontal rule lines; strip trailing
    spaces per line; collapse 3+ newlines to exactly 2.

    PDF text layers often separate digit groups with NBSP, which hides NIPs and phone
    numbers from every detector and from the leak check.
    Stamps (``T E S T``) and rule lines (``---…``) are document-system artefacts; they
    inflate chunk length without contributing template structure (TA #11).
    """
    text = text.replace("\u00a0", " ").replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = re.sub(r"(?m)^T E S T$\n?", "", text)
    text = re.sub(r"(?m)^[-_=]{15,}[ \t]*$\n?", "", text)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text)


def _pack(units: list[str], sep: str) -> list[str]:
    """Greedily join *units* with *sep* into pieces of at most ``_MAX_CHUNK`` characters.

    A single unit longer than the limit becomes its own piece; units are never split.
    """
    pieces: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}{sep}{unit}" if current else unit
        if current and len(candidate) > _MAX_CHUNK:
            pieces.append(current)
            current = unit
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def _segment(text: str) -> list[str]:
    """Split *text* into candidate chunks of at most ``_MAX_CHUNK`` characters.

    Paragraphs (blank-line separated) are packed whole. pypdf output often has no blank
    lines at all, so a paragraph over the limit is packed line by line instead.
    Chunks shorter than ``_MIN_CHUNK`` (headers, footers) are dropped.
    """
    chunks: list[str] = []
    pending: list[str] = []
    for para in text.split("\n\n"):
        if not para.strip():
            continue
        if len(para) <= _MAX_CHUNK:
            pending.append(para)
            continue
        chunks.extend(_pack(pending, "\n\n"))
        pending = []
        chunks.extend(_pack(para.split("\n"), "\n"))
    chunks.extend(_pack(pending, "\n\n"))
    return [c for c in chunks if len(c.strip()) >= _MIN_CHUNK]


def _redact_literal(literal: str) -> str:
    # A structured ID glued to letters (``PL23-P44051401359``) is a fragment of a longer
    # identifier that passed a checksum by chance: leave it, so the gate rejects the chunk.
    _reg_spans = [(m.start(), m.end()) for m in _KRS_NUMBER_RE.finditer(literal)]
    found: list[tuple[int, int, str]] = [
        (s.start, s.end, s.label.name)
        for s in piitier.detect(literal)
        if (s.start == 0 or not literal[s.start - 1].isalnum())
        and not any(rs <= s.start and s.end <= re for rs, re in _reg_spans)
    ]
    found += [
        (m.start(), m.end(), Label.KOD_POCZTOWY.name) for m in _POSTCODE_RULE_RE.finditer(literal)
    ]
    found += [(m.start(), m.end(), Label.EMAIL.name) for m in _EMAIL_RULE_RE.finditer(literal)]
    found += [(m.start(), m.end(), Label.KWOTA.name) for m in _AMOUNT_RE.finditer(literal)]
    found += [(m.start(), m.end(), Label.ADRES.name) for m in _STREET_RE.finditer(literal)]
    found += [(m.start(), m.end(), Label.VIN.name) for m in _VIN_RULE_RE.finditer(literal)]
    for m in _PHONE_RE.finditer(literal):
        group = 1 if m.group(1) else 2
        if 9 <= _digits(m.group(group)) <= 12:
            found.append((m.start(group), m.end(group), Label.TELEFON.name))
    # Registration plate detected by keyword context (TA #5).
    for m in _PLATE_KEYWORD_RE.finditer(literal):
        found.append((m.start(1), m.end(1), Label.NR_REJESTRACYJNY.name))
    sorted_by_len = sorted(found, key=lambda f: -(f[1] - f[0]))
    kept: list[tuple[int, int, str]] = []
    for start, end, label in sorted_by_len:
        if not any(s < end and start < e for s, e, _ in kept):
            kept.append((start, end, label))
    for start, end, label in sorted(kept, reverse=True):
        literal = literal[:start] + "{{" + label + "}}" + literal[end:]
    return literal

def _rule_redact(chunk: str) -> str:
    """Replace every rule-detected span outside existing placeholders with ``{{LABEL}}``.

    Runs after LLM marking, so a policy number the LLM labelled ``NR_POLISY`` is not
    re-labelled ``NIP`` by the checksum-agnostic NIP pattern.  After literal redaction,
    context fixes correct mislabelled placeholders (TA #4).
    """
    parts = _PLACEHOLDER_SPLIT_RE.split(chunk)
    chunk = "".join(_redact_literal(p) if i % 2 == 0 else p for i, p in enumerate(parts))
    # (a) EIK / "kod identyfikacyjny" is a company register number, not a policy number;
    #     the LLM mislabels it because the digit count overlaps NR_POLISY.
    chunk = _EIK_CONTEXT_RE.sub(lambda m: m.group(1), chunk)
    # (b) An agent NIP written in parentheses after "Agent:" is a NIP, not a policy number.
    chunk = _AGENT_NIP_RE.sub(
        lambda m: m.group(1) + "{{" + Label.NIP.name + "}}" + m.group(2), chunk
    )
    # (c) "Policy no" precedes a policy number written in English, not a PESEL.
    chunk = _POLICY_NO_PESEL_RE.sub(
        lambda m: m.group(1) + "{{" + Label.NR_POLISY.name + "}}", chunk
    )
    # (d) Plate immediately before {{VIN}} → NR_REJESTRACYJNY (B1).
    #     _redact_literal only sees the literal segment; after assembly this step
    #     catches a plate that precedes an already-placed {{VIN}} placeholder.
    chunk = _PLATE_BEFORE_VIN_RE.sub(
        "{{" + Label.NR_REJESTRACYJNY.name + "}}", chunk
    )
    return chunk


def _is_birth_date_context(chunk: str, idx: int) -> bool:
    """True when the match at *idx* in *chunk* follows a birth-date label.

    The label (``urodz…``) must precede the date on its own line, or sit on the line above
    when the date starts its line (label-above-value layouts).  Takes the match *index*
    rather than the text string so that a second date on the same line is not confused with
    a birth date (#3 defect a) and so that the first occurrence of the text in the chunk
    is not chosen blindly when the text appears earlier in a non-birth-date context (#3b).

    The prefix is the text between the LAST date or placeholder before *idx* (on the same
    line) and *idx*; this allows the function to be called both before replacement (where
    the prior birth date is a literal) and after replacement (where it is ``{{DATA_URODZENIA}}``),
    so that a policy date on the same line is not mistaken for a birth date.
    """
    line_start = chunk.rfind("\n", 0, idx) + 1
    # Split by both literal dates and existing placeholders to get the local context.
    _SPLIT_PAT = re.compile(r"\{\{[^{}]*\}\}|" + _DATE_RE.pattern)
    prefix = _SPLIT_PAT.split(chunk[line_start:idx])[-1]
    if "urodz" in prefix.lower():
        return True
    if prefix.strip() or line_start == 0:
        return False
    prev_start = chunk.rfind("\n", 0, line_start - 1) + 1
    return "urodz" in chunk[prev_start : line_start - 1].lower()


_NAME_WORD_RE = re.compile(r"[A-ZŁŚŻŹĆŃÓĄĘ][a-ząćęłńóśźż'-]+|[A-ZŁŚŻŹĆŃÓĄĘ'-]{2,}")
_PLATE_RE = re.compile(r"[A-Z]{1,3}[ ]?[A-Z0-9]{3,5}")
_VIN_SHAPE_RE = re.compile(r"[A-HJ-NPR-Z0-9]{17}")
# Rule labels strong enough to override the LLM: checksum plus a distinctive format.
# NIP and REGON are excluded: a 10-digit policy or 9-digit phone number passes by chance.
_OVERRIDE_LABELS = frozenset({Label.PESEL, Label.IBAN, Label.NR_DOWODU, Label.NR_KARTY})


def _digits(text: str) -> int:
    return sum(ch.isdigit() for ch in text)


def _allowed(word: str) -> bool:
    """True when *word* (in any case) is allowlisted vocabulary rather than a name."""
    allow = _allowlist()
    return word in allow or word.capitalize() in allow


def _checksum_label(text: str) -> str | None:
    """Rule label when *text* is exactly one checksum-valid strong structured ID."""
    stripped = text.strip()
    for span in piitier.detect(stripped):
        if (
            span.label in _OVERRIDE_LABELS
            and span.status == "valid"
            and span.start == 0
            and span.end == len(stripped)
        ):
            return span.label.name
    return None


def _has_label_shape(label: str, text: str, chunk: str) -> bool:
    """True when *text* plausibly is a value of *label* (LLM-label sanity check)."""
    t = text.strip()
    if label == Label.OSOBA.name:
        words = t.split()
        # A name is not made of policy vocabulary (``Powszechny Zakład Ubezpieczeń``)
        # and does not end with a company suffix (``Spółka europejska``) (TA #6).
        return (
            2 <= len(words) <= 4
            and all(_NAME_WORD_RE.fullmatch(w) for w in words)
            and not any(_allowed(w) for w in words)
            and not _COMPANY_SUFFIX_RE.search(t)
        )
    if label == Label.MIEJSCOWOSC.name:
        return _digits(t) == 0 and t[:1].isupper()
    if label == Label.ADRES.name:
        return _digits(t) >= 1
    if label == Label.KOD_POCZTOWY.name:
        return bool(_POSTCODE_RULE_RE.fullmatch(t))
    if label == Label.EMAIL.name:
        return bool(_EMAIL_RE.fullmatch(t))
    if label == Label.TELEFON.name:
        return _digits(t) >= 9 and not re.search(r"[^\d\s+()\-/]", t)
    if label == Label.DATA_URODZENIA.name:
        idx = chunk.find(text)
        return bool(_DATE_RE.fullmatch(t)) and (idx >= 0 and _is_birth_date_context(chunk, idx))
    if label in (Label.NR_POLISY.name, Label.NR_SZKODY.name):
        return _digits(t) >= 5 and " " not in t
    if label == Label.NR_REJESTRACYJNY.name:
        return bool(_PLATE_RE.fullmatch(t)) and _digits(t) >= 1
    if label == Label.VIN.name:
        return bool(_VIN_SHAPE_RE.fullmatch(t))
    if label == Label.KWOTA.name:
        # A physical-unit value (``128 km``, ``75 kW``) labelled KWOTA by the LLM
        # would render as an amount; reject it at the shape level (TA #9).
        return _digits(t) >= 1 and not re.search(r"[^\d\s\u00a0.,]", t)
    return True


def _parse_llm_spans(response: str) -> list[Any] | None:
    """Return the ``spans`` list from the model response, or ``None`` if unparseable."""
    start = response.find("{")
    end = response.rfind("}")
    if start == -1 or end < start:
        return None
    try:
        data = json.loads(response[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("spans"), list):
        return None
    spans: list[Any] = data["spans"]
    return spans


def _apply_llm_spans(chunk: str, spans: list[Any]) -> tuple[str, bool, int]:
    """Replace every verbatim occurrence of each flagged span outside existing placeholders.

    Returns ``(new_chunk, had_bad_label, not_verbatim_count)``. The model only flags; code
    decides. A span absent from *chunk* is a hallucination and is skipped. A span whose
    text does not have the shape of its label (a car model as ``NR_SZKODY``, a company as
    ``OSOBA``, a policy date as ``DATA_URODZENIA``) is skipped and counted as a bad label.
    A span that is a checksum-valid structured ID takes the rule detector's label instead.

    Entity linking (#12): OSOBA and ADRES spans with identical text receive the same
    entity id (``{{OSOBA#1}}``).  KWOTA is only replaced where followed by a currency
    symbol (#5) so that a house number is not mislabelled.
    """
    bad_label = False
    valid: list[tuple[str, str]] = []
    for item in spans:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("text"), str)
            or item.get("label") not in _LLM_LABEL_NAMES
        ):
            bad_label = True
            continue
        valid.append((item["text"], item["label"]))

    # Assign entity IDs to OSOBA and ADRES: same text → same number.
    _ENTITY_LABELS = {Label.OSOBA.name, Label.ADRES.name}
    entity_counter: dict[str, int] = {}
    text_to_entity: dict[tuple[str, str], int] = {}
    for text_v, label_v in valid:
        if label_v in _ENTITY_LABELS:
            key = (label_v, text_v.strip())
            if key not in text_to_entity:
                entity_counter[label_v] = entity_counter.get(label_v, 0) + 1
                text_to_entity[key] = entity_counter[label_v]

    original_literals = _PLACEHOLDER_SPLIT_RE.split(chunk)[::2]
    not_verbatim = 0
    parts = _PLACEHOLDER_SPLIT_RE.split(chunk)
    _CURRENCY_RE = re.compile(r"(?=[ \t]*(?:zł|złotych|PLN|€|EUR|euro)(?!\w))")
    for text, label in sorted(valid, key=lambda tl: len(tl[0]), reverse=True):
        if len(text.strip()) < 2:
            continue
        base_re = re.compile(r"(?<!\w)" + re.escape(text) + r"(?!\w)")
        # KWOTA: only replace occurrences followed by a currency symbol (#5).
        if label == Label.KWOTA.name:
            token_re = re.compile(
                r"(?<!\w)"
                + re.escape(text)
                + r"(?!\w)(?=[ \t]*(?:zł|złotych|PLN|€|EUR|euro)(?!\w))"
            )
        else:
            token_re = base_re
        if not any(token_re.search(lit) for lit in original_literals):
            not_verbatim += 1
            continue
        label = _checksum_label(text) or label
        if label in _LLM_LABEL_NAMES and not _has_label_shape(label, text, chunk):
            bad_label = True
            continue
        # Company-register context (M1/M2): if every verbatim occurrence of this span in
        # the chunk sits inside a _KRS_NUMBER_RE match (KRS, EIK, Latvian registry …),
        # keep it literal — it is a public corporate identifier, not personal data.
        _reg_spans = [(m.start(), m.end()) for m in _KRS_NUMBER_RE.finditer(chunk)]
        if _reg_spans:
            _occ = [(m.start(), m.end()) for m in re.finditer(re.escape(text), chunk)]
            if _occ and all(
                any(rs <= o_s and o_e <= r_e for rs, r_e in _reg_spans)
                for o_s, o_e in _occ
            ):
                continue  # keep literal — it is a company register number
        if label in _ENTITY_LABELS:
            entity_id = text_to_entity.get((label, text.strip()), 1)
            placeholder = "{{" + label + "#" + str(entity_id) + "}}"
        else:
            placeholder = "{{" + label + "}}"
        replaced = (
            token_re.sub(lambda _: placeholder, part) if i % 2 == 0 else part
            for i, part in enumerate(parts)
        )
        parts = _PLACEHOLDER_SPLIT_RE.split("".join(replaced))
    return "".join(parts), bad_label, not_verbatim


def _link_entities(chunk: str) -> str:
    """Link ``{{PESEL}}`` and ``{{DATA_URODZENIA}}`` to a nearby ``{{OSOBA#n}}``.

    When an OSOBA is numbered and a PESEL or DATA_URODZENIA appears on the same line
    or the line directly below it, the PESEL/DATA_URODZENIA joins that person's entity
    group.  Ambiguous context (multiple OSOBA#n on the same section) leaves it anonymous.
    """
    osoba_re = re.compile(re.escape("{{" + Label.OSOBA.name) + r"#(\d+)\}\}")
    anon_re = re.compile(
        re.escape("{{" + Label.PESEL.name + "}}")
        + r"|"
        + re.escape("{{" + Label.DATA_URODZENIA.name + "}}")
    )
    osoba_positions = [(m.start(), m.end(), m.group(1)) for m in osoba_re.finditer(chunk)]
    if not osoba_positions:
        return chunk

    def _link(m: re.Match[str]) -> str:
        lbl = Label.PESEL.name if Label.PESEL.name in m.group() else Label.DATA_URODZENIA.name
        pos = m.start()
        line_start = chunk.rfind("\n", 0, pos) + 1
        line_end = chunk.find("\n", pos)
        if line_end == -1:
            line_end = len(chunk)
        matched: list[str] = []
        for os_start, os_end, eid in osoba_positions:
            os_line_start = chunk.rfind("\n", 0, os_start) + 1
            os_line_end = chunk.find("\n", os_start)
            if os_line_end == -1:
                os_line_end = len(chunk)
            if os_line_start == line_start:  # same line
                matched.append(eid)
            elif os_line_end <= line_start <= os_line_end + 1:  # OSOBA line above
                matched.append(eid)
        if len(matched) == 1:
            return "{{" + lbl + "#" + matched[0] + "}}"
        return m.group()  # ambiguous — leave anonymous

    return anon_re.sub(_link, chunk)


def _leaks(literal: str) -> bool:
    """True when *literal* still carries a value-like string."""
    cleaned = _KRS_NUMBER_RE.sub(" ", _DATE_RE.sub(" ", literal))
    if piitier.detect(cleaned):
        return True
    undated = cleaned
    if _DIGIT_RUN_RE.search(undated) or _POSTCODE_RE.search(undated):
        return True
    if _FOREIGN_POSTCODE_RE.search(undated):  # TA #3: foreign 4–5 digit postcodes
        return True
    if _EMAIL_RE.search(literal) or _VIN_LEAK_RE.search(literal):
        return True
    if _STREET_LEAK_RE.search(literal):  # #1: unredacted street prefix
        return True
    if _PLATE_LEAK_RE.search(literal):  # TA #5: plate keyword + plate string
        return True
    # Mixed-case capitalised bigrams (Imię Nazwisko) and ALL-CAPS pairs.
    if any(
        not all(_allowed(word) for word in m.group(1).split())
        for regex in (_BIGRAM_RE, _CAPS_BIGRAM_RE)
        for m in regex.finditer(literal)
    ):
        return True
    # A bare ALL-CAPS word on its own line that is not allowlisted is a split name (TA #6).
    return any(not _allowed(m.group(1)) for m in _SOLO_CAPS_LINE_RE.finditer(literal))


def _gate(chunk: str, doc_type: str) -> str | None:
    """Return the reject reason for *chunk*, or ``None`` when it is an acceptable template."""
    try:
        parts = parse(Template(template_id="pending", doc_type=doc_type, text=chunk))
    except TemplateError as exc:
        return "unknown_label" if exc.reason == "Unknown label" else "parse_error"
    placeholders = [p for p in parts if isinstance(p, Placeholder)]
    if any(p.label not in _SUPPORTED_LABELS for p in placeholders):
        return "unknown_label"
    if len(placeholders) < _MIN_PLACEHOLDERS:
        return "too_few_placeholders"
    # Unlabelled birth date: a date in birth-date context that is still a literal (#2).
    ph_ranges = [(m.start(), m.end()) for m in re.finditer(r"\{\{[^{}]*\}\}", chunk)]
    for m in _DATE_RE.finditer(chunk):
        if not any(s <= m.start() < e for s, e in ph_ranges):
            if _is_birth_date_context(chunk, m.start()):
                return "leaked_value"
    # KWOTA immediately followed by a physical unit is a mislabelled measurement (TA #9).
    for i, part in enumerate(parts):
        if isinstance(part, Placeholder) and part.label == Label.KWOTA and i + 1 < len(parts):
            nxt = parts[i + 1]
            if isinstance(nxt, str) and re.match(r"[ \t]*(?:km|k[wW]|kg|cm)\b", nxt, re.IGNORECASE):
                return "leaked_value"
    # Bare uppercase 3–6 char token on a line adjacent to a "Miejscowość (Place)" label
    # is tester junk that was never properly redacted (TA #10).
    lines = chunk.split("\n")
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if re.fullmatch(r"[A-Z]{3,6}", stripped) and not _allowed(stripped):
            adj = ([lines[idx - 1]] if idx > 0 else []) + (
                [lines[idx + 1]] if idx < len(lines) - 1 else []
            )
            if any(re.search(r"(?i)Miejsco\w+\s*\(", cl) for cl in adj):
                return "leaked_value"
    if any(_leaks(lit) for lit in parts if isinstance(lit, str)):
        return "leaked_value"
    # B1: plate-shaped token directly before {{VIN}} — the code rule should have caught it,
    # but guard against any path where a plate sneaks through to the finished template.
    if _PLATE_BEFORE_VIN_GATE_RE.search(chunk):
        return "leaked_value"
    # M1/M2: a PESEL or NR_POLISY placeholder inside a company-register phrase means the
    # LLM mislabelled a public register number as personal data.
    if _REGISTER_PLACEHOLDER_GATE_RE.search(chunk):
        return "llm_bad_label"
    # m1: a lowercase word immediately followed by digits after an ADRES placeholder is a
    # junk token that was not stripped during normalisation (e.g. ``{{ADRES#1}} city2111``).
    if _ADRES_JUNK_SUFFIX_RE.search(chunk):
        return "leaked_value"
    return None


def _load_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    if not manifest_path.exists():
        return []
    content = manifest_path.read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError("Manifest is blank or whitespace-only")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed existing manifest: {e}") from e
    if not isinstance(parsed, list):
        raise ValueError("Manifest must be a JSON array")
    return parsed


def templatize(
    pdf_dir: Path,
    out: Path,
    *,
    doc_type: str = "polisa",
    limit: int | None = None,
    model: str = "hf.co/SpeakLeash/Bielik-11B-v3.0-Instruct-GGUF:Q8_0",
    ollama_url: str = "http://127.0.0.1:11434",
    temperature: float = 0.0,
    reject_dir: Path | None = None,
    workers: int = 1,
) -> dict[str, Any]:
    """Convert real PDFs in *pdf_dir* into placeholder-only templates under *out*.

    Accepted templates land in ``out/<doc_type>/<doc_type>_pdf_<sha256[:12]>.txt`` and one
    record is appended to ``out/manifest.json``. Rejected chunks are never written under
    *out*; with *reject_dir* (which must lie outside the repository) they are written to
    ``<reject_dir>/<reason>/<sha256[:12]>.txt`` for inspection.

    *workers* LLM requests run concurrently (match Ollama's ``OLLAMA_NUM_PARALLEL``);
    responses are consumed in chunk order, so which files are written does not depend on
    request timing.

    Returns ``{"pdfs_read": int, "accepted": int, "rejected": {reason: count}}``.
    """
    if (
        not isinstance(doc_type, str)
        or doc_type not in DOC_TYPES
        or "/" in doc_type
        or "\\" in doc_type
        or ".." in doc_type
        or Path(doc_type).is_absolute()
    ):
        raise ValueError(f"Invalid doc_type: {doc_type}")
    if workers < 1:
        raise ValueError(f"workers must be >= 1, got {workers}")
    if limit is not None and limit < 1:
        raise ValueError(f"limit must be >= 1, got {limit}")

    _validate_ollama_url(ollama_url)

    pdfs = sorted(pdf_dir.glob("*.pdf")) if pdf_dir.is_dir() else []
    if not pdfs:
        raise ValueError(f"no PDFs in {pdf_dir}")
    if limit is not None:
        pdfs = pdfs[:limit]

    if reject_dir is not None and reject_dir.resolve().is_relative_to(_REPO_ROOT):
        raise ValueError("reject_dir must be outside the repository")

    prompt_file = _DATAGEN_DIR / "prompts" / f"templatize_{doc_type}.txt"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found for doc_type: {doc_type}")
    prompt_bytes = prompt_file.read_bytes()
    prompt_sha256 = hashlib.sha256(prompt_bytes).hexdigest()
    prompt_text = prompt_bytes.decode("utf-8")

    manifest_path = out / "manifest.json"
    manifest_records = _load_manifest(manifest_path)

    seen_hashes: set[str] = set()
    if out.exists():
        for p_file in out.glob("**/*.txt"):
            if p_file.is_file():
                seen_hashes.add(hashlib.sha256(p_file.read_bytes()).hexdigest())

    opener = _get_opener()
    digest = _probe_model(opener, ollama_url, model)

    accepted = 0
    rejected: dict[str, int] = {}

    def reject(reason: str, chunk: str | None = None) -> None:
        rejected[reason] = rejected.get(reason, 0) + 1
        if reject_dir is not None and chunk is not None and reason in _CHUNK_REJECTS:
            h = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
            target = reject_dir / reason / f"{h[:12]}.txt"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(chunk, encoding="utf-8")

    # pypdf logs one warning per page for missing fontTools or a non-PDF header: noise here.
    pypdf_logger = logging.getLogger("pypdf")
    pypdf_level = pypdf_logger.level
    pypdf_logger.setLevel(logging.ERROR)

    def ask(chunk: str) -> str | OllamaUnreachableError:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt_text + chunk,
            "stream": False,
            "options": {
                "temperature": temperature,
                "seed": 0,
                "num_predict": _MAX_RESPONSE_TOKENS,
            },
        }
        try:
            return _generate(opener, ollama_url, payload, _GENERATE_TIMEOUT)
        except OllamaUnreachableError as exc:
            return exc

    pdfs_read = 0
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        for pdf in pdfs:
            pdfs_read += 1
            try:
                text = load_pdf(pdf)
            except PdfNoTextError:
                reject("no_text")
                continue
            except (PdfReadError, ValueError):
                # Not a PDF (e.g. HTML saved as .pdf) or encrypted.
                reject("unreadable")
                continue

            chunks = _segment(_normalise(text))
            for chunk, response in zip(chunks, pool.map(ask, chunks), strict=True):
                if isinstance(response, OllamaUnreachableError):
                    # One stuck or failed call must not end a long run: if the server still
                    # serves the model, drop this chunk; otherwise the probe re-raises.
                    _probe_model(opener, ollama_url, model)
                    reject("llm_error", chunk)
                    continue
                spans = _parse_llm_spans(response)
                if spans is None:
                    reject("llm_parse_error", chunk)
                    continue
                chunk, bad_label, not_verbatim = _apply_llm_spans(chunk, spans)
                chunk = _rule_redact(chunk)
                chunk = _ADDRESS_TAIL_RE.sub(lambda m: m.group(1), chunk)
                chunk = _ADDRESS_HEAD_RE.sub("", chunk)
                chunk = _ADRES_TRAILER_RE.sub(lambda m: m.group(1), chunk)
                chunk = _link_entities(chunk)
                if bad_label:
                    rejected["llm_bad_label"] = rejected.get("llm_bad_label", 0) + 1
                if not_verbatim:
                    rejected["llm_not_verbatim"] = (
                        rejected.get("llm_not_verbatim", 0) + not_verbatim
                    )

                reason = _gate(chunk, doc_type)
                if reason is not None:
                    reject(reason, chunk)
                    continue

                content = chunk if chunk.endswith("\n") else chunk + "\n"
                h = hashlib.sha256(content.encode("utf-8")).hexdigest()
                if h in seen_hashes:
                    reject("duplicate")
                    continue
                seen_hashes.add(h)
                accepted += 1
                target = out / doc_type / f"{doc_type}_pdf_{h[:12]}.txt"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
        pypdf_logger.setLevel(pypdf_level)
        # Record what was written even when the run aborts (Ollama gone, Ctrl-C).
        rejected_nonzero = {k: v for k, v in sorted(rejected.items()) if v > 0}
        manifest_records.append(
            {
                "source": "/".join(pdf_dir.resolve().parts[-3:]),
                "doc_type": doc_type,
                "pdfs_read": pdfs_read,
                "model": model,
                "digest": digest,
                "prompt_sha256": prompt_sha256,
                "temperature": temperature,
                "accepted": accepted,
                "rejected": rejected_nonzero,
            }
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest_records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    return {"pdfs_read": pdfs_read, "accepted": accepted, "rejected": rejected_nonzero}
