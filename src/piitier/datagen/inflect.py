"""Name inflection via Morfeusz 2 for synthetic Polish PII data (PII-2-c).

Public API: inflect(name, case, sex) -> str
Internal:   _inflect(name, case, sex) -> tuple[str, bool]

License: https://morfeusz.sgjp.pl/doc/license/ (BSD 2-Clause)
"""

from __future__ import annotations

import re
from functools import lru_cache

import morfeusz2


@lru_cache(maxsize=1)
def _get_morfeusz() -> morfeusz2.Morfeusz:
    return morfeusz2.Morfeusz()


def _gender_token(sex: str) -> str:
    return "m1" if sex.lower() == "m" else "f"


def _tag_matches(tag: str, case: str, gender: str) -> bool:
    if tag == "ign":
        return False
    parts = tag.split(":")
    if not parts or parts[0] != "subst":
        return False
    has_sg = any("sg" in seg.split(".") for seg in parts)
    has_case = any(case in seg.split(".") for seg in parts)
    has_gender = any(gender in seg.split(".") for seg in parts)
    return has_sg and has_case and has_gender


@lru_cache(maxsize=4096)
def _inflect_part(part: str, case: str, sex: str) -> tuple[str, bool]:
    gender = _gender_token(sex)
    candidates = _get_morfeusz().generate(part)
    for entry in candidates:
        if _tag_matches(entry[2], case, gender):
            return entry[0], False
    return part, True


def _inflect(name: str, case: str, sex: str) -> tuple[str, bool]:
    """Return *(surface_form, is_fallback)* for *name* (supports multi-word names)."""
    tokens = re.split(r"(\s+)", name)
    if not tokens:
        return name, True
    inflected_tokens: list[str] = []
    any_fallback = False
    for t in tokens:
        if not t:
            continue
        if t.isspace():
            inflected_tokens.append(t)
        else:
            form, fb = _inflect_part(t, case, sex)
            inflected_tokens.append(form)
            if fb:
                any_fallback = True
    return "".join(inflected_tokens), any_fallback


def inflect(name: str, case: str, sex: str) -> str:
    """Return the inflected surface form of *name* for the given grammatical case."""
    form, _ = _inflect(name, case, sex)
    return form
