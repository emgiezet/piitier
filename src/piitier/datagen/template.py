"""Template parser for synthetic data generation (PII-2-a)."""

from __future__ import annotations

from dataclasses import dataclass

from piitier.labels import Label


@dataclass(frozen=True)
class Template:
    template_id: str
    doc_type: str
    text: str


class TemplateError(Exception):
    """Raised when a template is malformed or contains an unknown/unsupported label."""

    def __init__(
        self,
        template_id: str,
        offset: int,
        reason: str | None = None,
        message: str | None = None,
    ) -> None:
        msg = reason or message or "Template error"
        super().__init__(f"Template {template_id} error at offset {offset}: {msg}")
        self.template_id = template_id
        self.offset = offset
        self.reason = reason or message


@dataclass(frozen=True)
class Placeholder:
    label: Label
    entity: str | None
    case: str | None
    offset: int


_VALID_CASES = frozenset({"nom", "gen", "dat", "acc", "inst", "loc", "voc"})


def parse(template: Template) -> list[str | Placeholder]:
    """Parse template text into literal string segments and Placeholder objects."""
    text = template.text
    result: list[str | Placeholder] = []
    i = 0
    n = len(text)
    while i < n:
        start = text.find("{{", i)
        if start == -1:
            if i < n:
                result.append(text[i:])
            break
        if start > i:
            result.append(text[i:start])

        end = text.find("}}", start + 2)
        if end == -1:
            raise TemplateError(template.template_id, start, "Unclosed placeholder")

        content = text[start + 2 : end]
        if not content:
            raise TemplateError(template.template_id, start, "Empty placeholder")

        label_part = content
        entity_part: str | None = None
        case_part: str | None = None

        if ":" in content:
            parts = content.split(":", 1)
            label_part = parts[0]
            case_part = parts[1]
            if case_part not in _VALID_CASES:
                raise TemplateError(template.template_id, start, "Invalid case")

        if "#" in label_part:
            parts = label_part.split("#", 1)
            label_part = parts[0]
            entity_part = parts[1]
            if not entity_part or not entity_part.isdigit():
                raise TemplateError(template.template_id, start, "Invalid entity ID")

        if case_part is not None and entity_part is None:
            raise TemplateError(template.template_id, start, "Case specifier requires entity ID")

        try:
            label = Label[label_part]
        except KeyError:
            raise TemplateError(template.template_id, start, "Unknown label")

        result.append(Placeholder(label=label, entity=entity_part, case=case_part, offset=start))
        i = end + 2

    return result
