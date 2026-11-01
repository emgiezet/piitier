"""Mask decoded JSON string values through spans in the original serialization."""

from __future__ import annotations

import json
import re
import warnings
from collections.abc import Callable
from dataclasses import dataclass, replace

from piitier.fusion import fuse
from piitier.render import mask as render_mask
from piitier.spans import Span

_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')
_NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_INT = re.compile(r"[0-9]+")


class NumericPiiError(ValueError):
    """A numeric token in JSON was recognised as PII; carries no value."""


class JsonSelectorError(ValueError):
    """A JSON path selector is outside the supported restricted jq subset."""


@dataclass(frozen=True)
class JsonValue:
    """One JSON value with its jq path and source range in the original text.

    Fields
    ------
    path:
        Tuple of object keys, array indices and ``None`` wildcards describing
        the value's position.  The root value has path ``()``.
    start, end:
        Half-open character offsets into the original *serialized* text.
        String ranges include the surrounding quotes; container ranges
        include braces/brackets; numeric/boolean/null ranges cover the token.
    kind:
        ``"object"``, ``"array"``, ``"string"``, ``"number"``, ``"bool"``,
        or ``"null"``.
    value:
        Decoded string for ``"string"``, raw spelling for ``"number"``,
        ``"true"``/``"false"`` for ``"bool"``, and ``None`` otherwise.
    """

    path: tuple[str | int | None, ...]
    start: int
    end: int
    kind: str
    value: str | None


@dataclass(frozen=True)
class JsonSkipPlan:
    """Unioned source ranges to leave untouched and selectors that matched nothing."""

    protected_ranges: list[tuple[int, int]]
    unknown_selectors: list[str]


def _reject_constant(value: str) -> None:
    raise ValueError("invalid JSON")


def validate_json(text: str) -> None:
    """Validate one JSON document without echoing parser input or converting numbers."""
    try:
        json.loads(
            text.removeprefix("\ufeff"),
            parse_int=lambda value: None,
            parse_float=lambda value: None,
            parse_constant=_reject_constant,
        )
    except (ValueError, RecursionError):
        raise ValueError("invalid JSON") from None


def _skip_ws(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    return index


def _parse_json_string(text: str, index: int) -> tuple[str, int]:
    match = _STRING.match(text, index)
    if match is None:
        raise ValueError("invalid JSON")
    return json.loads(match.group()), match.end()


def _parse_value(
    text: str,
    index: int,
    path: tuple[str | int | None, ...],
    values: list[JsonValue],
) -> int:
    index = _skip_ws(text, index)
    if index >= len(text):
        raise ValueError("invalid JSON")
    ch = text[index]

    if ch == '"':
        match = _STRING.match(text, index)
        if match is None:
            raise ValueError("invalid JSON")
        token = match.group()
        values.append(JsonValue(path, index, match.end(), "string", json.loads(token)))
        return match.end()

    if ch == "-" or ch.isdigit():
        match = _NUMBER.match(text, index)
        if match is None:
            raise ValueError("invalid JSON")
        token = match.group()
        values.append(JsonValue(path, index, index + len(token), "number", token))
        return index + len(token)

    if text.startswith("true", index):
        end = index + 4
        values.append(JsonValue(path, index, end, "bool", "true"))
        return end

    if text.startswith("false", index):
        end = index + 5
        values.append(JsonValue(path, index, end, "bool", "false"))
        return end

    if text.startswith("null", index):
        end = index + 4
        values.append(JsonValue(path, index, end, "null", None))
        return end

    if ch == "{":
        start = index
        index += 1
        index = _skip_ws(text, index)
        if index < len(text) and text[index] == "}":
            values.append(JsonValue(path, start, index + 1, "object", None))
            return index + 1
        while True:
            index = _skip_ws(text, index)
            key_match = _STRING.match(text, index)
            if key_match is None:
                raise ValueError("invalid JSON")
            key = json.loads(key_match.group())
            index = key_match.end()
            index = _skip_ws(text, index)
            if index >= len(text) or text[index] != ":":
                raise ValueError("invalid JSON")
            index += 1
            index = _parse_value(text, index, path + (key,), values)
            index = _skip_ws(text, index)
            if index < len(text) and text[index] == ",":
                index += 1
                continue
            if index < len(text) and text[index] == "}":
                values.append(JsonValue(path, start, index + 1, "object", None))
                return index + 1
            raise ValueError("invalid JSON")

    if ch == "[":
        start = index
        index += 1
        index = _skip_ws(text, index)
        if index < len(text) and text[index] == "]":
            values.append(JsonValue(path, start, index + 1, "array", None))
            return index + 1
        child_index = 0
        while True:
            index = _parse_value(text, index, path + (child_index,), values)
            child_index += 1
            index = _skip_ws(text, index)
            if index < len(text) and text[index] == ",":
                index += 1
                continue
            if index < len(text) and text[index] == "]":
                values.append(JsonValue(path, start, index + 1, "array", None))
                return index + 1
            raise ValueError("invalid JSON")

    raise ValueError("invalid JSON")


def parse_json_values(text: str) -> list[JsonValue]:
    """Return every JSON value with its source range, decoded string and jq path.

    Containers appear in the returned list after their children so that every
    descendant range is known when the container value is emitted.  Source
    offsets are relative to *text* and include a leading UTF-8 BOM if present.
    """
    validate_json(text)
    base = 1 if text.startswith("\ufeff") else 0
    index = _skip_ws(text, base)
    values: list[JsonValue] = []
    try:
        next_index = _parse_value(text, index, (), values)
    except RecursionError:
        raise ValueError("JSON nesting is too deep") from None
    next_index = _skip_ws(text, next_index)
    if next_index != len(text):
        raise ValueError("invalid JSON")
    return values


def parse_json_selector(selector: str) -> tuple[str | int | None, ...]:
    """Parse a restricted jq path into a tuple of segments.

    Root ``"."`` becomes ``()``.  Dotted identifiers, JSON-quoted keys,
    bracket-quoted keys, non-negative integer indices and ``[]`` array wildcards
    are supported.  Pipes, functions, filters, commas outside quoted keys,
    slices and negative indices raise :class:`JsonSelectorError` without
    echoing the input.
    """
    if not selector.startswith("."):
        raise JsonSelectorError("unsupported JSON path selector")
    if selector == ".":
        return ()
    segments: list[str | int | None] = []
    index = 1
    try:
        while index < len(selector):
            if index > 1 and selector[index] == ".":
                index += 1
                if index == len(selector) or selector[index] == "[":
                    raise ValueError
            elif index > 1 and selector[index] != "[":
                raise ValueError
            if selector[index] == "[":
                index += 1
                if index == len(selector):
                    raise ValueError
                if selector[index] == "]":
                    segments.append(None)
                    index += 1
                    continue
                if selector[index] == '"':
                    key, index = _parse_json_string(selector, index)
                    segments.append(key)
                else:
                    match = _INT.match(selector, index)
                    if match is None:
                        raise ValueError
                    segments.append(int(match.group()))
                    index = match.end()
                if index == len(selector) or selector[index] != "]":
                    raise ValueError
                index += 1
            elif selector[index] == '"':
                key, index = _parse_json_string(selector, index)
                segments.append(key)
            else:
                match = _IDENT.match(selector, index)
                if match is None:
                    raise ValueError
                segments.append(match.group())
                index = match.end()
    except (ValueError, RecursionError):
        raise JsonSelectorError("unsupported JSON path selector") from None
    return tuple(segments)


def _path_matches(
    selector: tuple[str | int | None, ...],
    value_path: tuple[str | int | None, ...],
) -> bool:
    if len(selector) > len(value_path):
        return False
    for sel, seg in zip(selector, value_path):
        if sel is None:
            if not isinstance(seg, int):
                return False
        elif sel != seg:
            return False
    return True


def _union_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not ranges:
        return []
    sorted_ranges = sorted(ranges)
    merged: list[list[int]] = [list(sorted_ranges[0])]
    for start, end in sorted_ranges[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1][1] = max(last_end, end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def plan_json_skips(values: list[JsonValue], selectors: list[str]) -> JsonSkipPlan:
    """Compute source ranges to protect for a list of jq selectors.

    A selector matching an object or array protects all of its descendant
    string values.  Matching a string value protects only that value.
    Overlapping protected ranges are unioned.  Selectors that match no value
    are returned as unknown.
    """
    protected: list[tuple[int, int]] = []
    unknown: list[str] = []
    for selector in selectors:
        path = parse_json_selector(selector)
        matched = False
        for value in values:
            if _path_matches(path, value.path):
                matched = True
                if value.kind not in {"object", "array"}:
                    protected.append((value.start, value.end))
        if not matched:
            unknown.append(selector)
    return JsonSkipPlan(protected_ranges=_union_ranges(protected), unknown_selectors=unknown)


def _is_jq_identifier(key: str) -> bool:
    return bool(_IDENT.fullmatch(key))


def _path_to_jq(path: tuple[str | int | None, ...]) -> str:
    if not path:
        return "."
    result = "."
    for index, segment in enumerate(path):
        if isinstance(segment, int):
            result += f"[{segment}]"
        elif segment is None:
            result += "[]"
        else:
            if index:
                result += "."
            result += (
                segment if _is_jq_identifier(segment) else json.dumps(segment, ensure_ascii=False)
            )
    return result


def json_selectors(values: list[JsonValue]) -> list[str]:
    """Return canonical jq path strings for every selectable value.

    Concrete indexed paths are listed, together with deduplicated wildcard
    counterparts where array indices appear.  Wildcard variants precede the
    indexed options they generalise.  Weird object keys are JSON-quoted.
    """
    groups: dict[
        tuple[str | None, ...],
        set[tuple[str | int | None, ...]],
    ] = {}
    for value in values:
        signature = tuple(None if isinstance(segment, int) else segment for segment in value.path)
        groups.setdefault(signature, set()).add(value.path)

    result: list[str] = []
    for signature in sorted(groups, key=_path_to_jq):
        paths = groups[signature]
        has_wildcard = any(segment is None for segment in signature)
        if has_wildcard:
            result.append(_path_to_jq(signature))
        for concrete in sorted(paths, key=lambda p: tuple(str(segment) for segment in p)):
            result.append(_path_to_jq(concrete))
    return result


def _inside(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    for range_start, range_end in ranges:
        if range_start <= start and end <= range_end:
            return True
    return False


def _source_boundaries(token: str, start: int) -> list[int]:
    """Map decoded character boundaries to source offsets, including surrogate pairs."""
    index = 1  # opening quote
    boundaries = [start + index]
    while index < len(token) - 1:
        width = 1
        if token[index] == "\\":
            width = 2
            if token[index + 1] == "u":
                width = 6
                if (
                    0xD800 <= int(token[index + 2 : index + 6], 16) <= 0xDBFF
                    and token[index + 6 : index + 8] == "\\u"
                    and 0xDC00 <= int(token[index + 8 : index + 12], 16) <= 0xDFFF
                ):
                    width = 12
        index += width
        boundaries.append(start + index)
    return boundaries


def detect_json(
    text: str,
    *,
    detector: Callable[[str], list[Span]],
    numbering_fn: Callable[[str, list[Span]], dict[tuple[int, int], int]] | None = None,
    skip_fields: list[str] | None = None,
    on_unknown_field: Callable[[str], None] | None = None,
) -> tuple[list[Span], dict[tuple[int, int], int] | None]:
    """Detect each value independently and assign numbering across decoded document values.

    Returned spans and numbering keys index the original serialized JSON. Keys
    and non-string values never reach the detector.  Numeric tokens are passed
    to *detector* first; any detection raises :class:`NumericPiiError` before
    skip filtering.  Selected string values and descendants of selected
    containers are omitted from detection while preserving source formatting.
    """
    values = parse_json_values(text)

    # Fail closed on numeric PII before any skip logic can hide it.
    for value in values:
        if value.kind == "number" and detector(value.value or ""):
            raise NumericPiiError("numeric PII detected in JSON")

    protected_ranges: list[tuple[int, int]] = []
    if skip_fields:
        plan = plan_json_skips(values, skip_fields)
        protected_ranges = plan.protected_ranges
        if on_unknown_field is not None:
            for selector in plan.unknown_selectors:
                on_unknown_field(selector)
        elif plan.unknown_selectors:
            for _selector in plan.unknown_selectors:
                warnings.warn("JSON selector matched no values")

    source_spans: list[Span] = []
    decoded_spans: list[Span] = []
    decoded_values: list[str] = []
    offset = 0
    for value in values:
        if value.kind != "string":
            continue
        skipped = protected_ranges and _inside(value.start, value.end, protected_ranges)
        if not skipped and value.value:
            spans = fuse(detector(value.value), [])
            if spans:
                token = text[value.start : value.end]
                boundaries = _source_boundaries(token, value.start)
                for span in spans:
                    source_spans.append(
                        replace(span, start=boundaries[span.start], end=boundaries[span.end])
                    )
                    if numbering_fn is not None:
                        decoded_spans.append(
                            replace(span, start=offset + span.start, end=offset + span.end)
                        )
        if numbering_fn is not None:
            decoded_values.append(value.value if value.value is not None else "")
            offset += len(decoded_values[-1]) + 1

    if numbering_fn is None:
        return source_spans, None
    numbering = numbering_fn("\n".join(decoded_values), decoded_spans)
    source_numbering = {
        (source.start, source.end): numbering[(decoded.start, decoded.end)]
        for source, decoded in zip(source_spans, decoded_spans, strict=True)
        if (decoded.start, decoded.end) in numbering
    }
    return source_spans, source_numbering


def mask_json(
    text: str,
    *,
    detector: Callable[[str], list[Span]],
    numbering_fn: Callable[[str, list[Span]], dict[tuple[int, int], int]] | None = None,
    skip_fields: list[str] | None = None,
    on_unknown_field: Callable[[str], None] | None = None,
) -> str:
    """Replace only detected value content, preserving every other source character.

    Detectable numeric PII raises :class:`NumericPiiError`.  Unsupported selectors
    raise :class:`JsonSelectorError`.  Unmatched selectors are reported through
    *on_unknown_field* or a content-free warning.
    """
    spans, numbering = detect_json(
        text,
        detector=detector,
        numbering_fn=numbering_fn,
        skip_fields=skip_fields,
        on_unknown_field=on_unknown_field,
    )
    return render_mask(text, spans, numbering)
