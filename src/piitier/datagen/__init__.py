"""Synthetic data generation module (PII-2-a)."""

from __future__ import annotations

from piitier.datagen.render import Document, SyntheticSpan, render
from piitier.datagen.template import Placeholder, Template, TemplateError, parse
from piitier.datagen.values import generate_value

__all__ = [
    "Template",
    "TemplateError",
    "Placeholder",
    "parse",
    "Document",
    "SyntheticSpan",
    "render",
    "generate_value",
]
