"""piitier — Polish PII anonymiser for regulated sectors."""

__version__ = "0.1.0"

from piitier.labels import Label
from piitier.spans import Span

__all__ = ["__version__", "Label", "Span"]
