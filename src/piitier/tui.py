"""Local two-pane comparison of detected text and its anonymized replacements."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import ClassVar

from rich.cells import cell_len
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, RichLog, Static

from piitier import Anonymizer
from piitier.loaders import PdfNoTextError, get_loader
from piitier.spans import Span


def _column_after(fragment: str, column: int) -> int:
    """Find the terminal column after a fragment, resetting at the last newline."""
    last_newline = fragment.rfind("\n")
    if last_newline >= 0:
        return cell_len(fragment[last_newline + 1 :])
    return column + cell_len(fragment)


def build_diff(
    text: str, spans: list[Span], active: int
) -> tuple[Text, Text, list[tuple[int, int, int, int]]]:
    """Render both sides and record corresponding line/column targets."""
    before = Text()
    after = Text()
    lines: list[tuple[int, int, int, int]] = []
    cursor = before_line = after_line = before_col = after_col = 0
    for index, span in enumerate(spans):
        unchanged = text[cursor : span.start]
        before.append(unchanged)
        after.append(unchanged)
        before_line += unchanged.count("\n")
        after_line += unchanged.count("\n")
        before_col = _column_after(unchanged, before_col)
        after_col = _column_after(unchanged, after_col)
        lines.append((before_line, after_line, before_col, after_col))

        original = text[span.start : span.end]
        replacement = span.label.placeholder
        before.append(original, style="bold white on red" if index == active else "bold red")
        after.append(replacement, style="bold black on green" if index == active else "bold green")
        before_line += original.count("\n")
        after_line += replacement.count("\n")
        before_col = _column_after(original, before_col)
        after_col = _column_after(replacement, after_col)
        cursor = span.end

    before.append(text[cursor:])
    after.append(text[cursor:])
    return before, after, lines


class AnonymizationDiffApp(App[None]):
    """Navigate detected replacements without writing the source document to disk."""

    TITLE = "Porównanie anonimizacji"
    CSS = """
    #panes { height: 1fr; }
    .pane { width: 1fr; height: 1fr; }
    .pane-title { height: 1; text-style: bold; text-align: center; }
    RichLog { height: 1fr; border: round $primary; }
    #status { height: 1; text-align: center; }
    """
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("up", "previous_change", "Poprzednia", priority=True),
        Binding("left", "previous_change", "Poprzednia", priority=True),
        Binding("down", "next_change", "Następna", priority=True),
        Binding("right", "next_change", "Następna", priority=True),
        Binding("q", "quit", "Wyjście"),
    ]

    def __init__(self, text: str, spans: list[Span]) -> None:
        super().__init__()
        self.text = text
        self.spans = sorted(spans, key=lambda span: span.start)
        self.active = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="panes"):
            with Vertical(classes="pane"):
                yield Static("PRZED · wykryte fragmenty", classes="pane-title")
                yield RichLog(id="before", min_width=1, auto_scroll=False, wrap=False)
            with Vertical(classes="pane"):
                yield Static("PO · zamaskowane etykiety", classes="pane-title")
                yield RichLog(id="after", min_width=1, auto_scroll=False, wrap=False)
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._show_selection()

    def action_next_change(self) -> None:
        if self.spans:
            self.active = (self.active + 1) % len(self.spans)
            self._show_selection()

    def action_previous_change(self) -> None:
        if self.spans:
            self.active = (self.active - 1) % len(self.spans)
            self._show_selection()

    def _show_selection(self) -> None:
        before, after, lines = build_diff(self.text, self.spans, self.active)
        before_pane = self.query_one("#before", RichLog)
        after_pane = self.query_one("#after", RichLog)
        before_pane.clear().write(before)
        after_pane.clear().write(after)
        status = self.query_one("#status", Static)
        if not self.spans:
            status.update("Brak wykrytych fragmentów do zamaskowania")
            return
        status.update(
            f"{self.active + 1} / {len(self.spans)} · {self.spans[self.active].label.name}"
        )
        self.call_after_refresh(self._scroll_to_selection, *lines[self.active])

    def _scroll_to_selection(
        self, before_line: int, after_line: int, before_col: int, after_col: int
    ) -> None:
        before_pane = self.query_one("#before", RichLog)
        after_pane = self.query_one("#after", RichLog)
        before_pane.scroll_to(
            x=max(0, before_col - before_pane.size.width // 2),
            y=max(0, before_line - before_pane.size.height // 2),
            animate=False,
        )
        after_pane.scroll_to(
            x=max(0, after_col - after_pane.size.width // 2),
            y=max(0, after_line - after_pane.size.height // 2),
            animate=False,
        )


def compare_file(input_path: Path, model: Path, threshold: float, device: str) -> int:
    """Detect once, display locally, and keep document text out of errors/output."""
    if not model.is_dir():
        print(f"model not found: {model}", file=sys.stderr)
        return 2
    if not (0.0 <= threshold <= 1.0):
        print("invalid threshold (expected a number in [0, 1])", file=sys.stderr)
        return 2
    if not input_path.is_file():
        print(f"not found: {input_path}", file=sys.stderr)
        return 2
    loader = get_loader(input_path)
    if loader is None:
        print(f"unsupported file type: {input_path.suffix}", file=sys.stderr)
        return 2
    try:
        text = loader(input_path)
    except PdfNoTextError:
        print("PDF has no text layer", file=sys.stderr)
        return 3
    except (OSError, ValueError, UnicodeError):
        print(f"could not read: {input_path}", file=sys.stderr)
        return 2
    try:
        spans = Anonymizer(model=model, threshold=threshold, device=device).detect(text)
    except (OSError, ValueError, ImportError):
        print(f"model error: {model}", file=sys.stderr)
        return 2
    AnonymizationDiffApp(text, spans).run()
    return 0
