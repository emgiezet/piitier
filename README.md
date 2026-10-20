# piitier

Polish PII anonymiser for regulated sectors (fintech, insurtech, medtech).

## Installation

```bash
uv sync
uv run python -c "import piitier; print(piitier.__version__)"
```

## Usage

```python
from piitier import Label, Span

# Create a span representing detected PII
span = Span(
    start=0,
    end=11,
    label=Label.PESEL,
    source="rule:pesel",
    score=1.0,
    status="valid"
)

print(f"Found {span.label.name} at [{span.start}, {span.end})")
print(f"Placeholder: {span.label.placeholder}")
```

## License

Apache 2.0
