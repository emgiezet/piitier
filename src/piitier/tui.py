"""Local two-pane comparison of detected text and its anonymized replacements."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, ClassVar, cast

from rich.cells import cell_len
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Checkbox, DataTable, Footer, Header, Input, RichLog, Static

from piitier import Anonymizer
from piitier.csvskip import (
    ParseResult,
    filter_spans,
    parse_csv_field_ranges,
    plan_skips,
    sniff_delimiter,
)
from piitier.loaders import PdfNoTextError, get_loader
from piitier.render import mask as render_mask
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


class CsvSelectionScreen(Screen[None]):
    """Preview CSV records and select columns by position, not header name."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.parsed: ParseResult = parse_csv_field_ranges(text, sniff_delimiter(text))
        first_row = self.parsed.rows[0] if self.parsed.rows else []
        self.headers = [
            first_row[index].value if index < len(first_row) else f"Kolumna {index + 1}"
            for index in range(max((len(row) for row in self.parsed.rows), default=0))
        ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="csv-columns"):
            with Vertical(id="csv-table-wrap"):
                yield Static("PODGLĄD CSV · pierwsze 50 wierszy", classes="pane-title")
                yield DataTable(id="csv-preview", zebra_stripes=True)
            with Vertical(id="csv-selectors"):
                yield Static("MASKUJ KOLUMNY", classes="pane-title")
                yield Static("Odznaczone: bez zmian")
                with VerticalScroll(id="csv-checkboxes"):
                    for index, header in enumerate(self.headers):
                        yield Checkbox(f"{index + 1}. {header}", value=True, id=f"mask-{index + 1}")
        yield Static("", id="csv-error")
        yield Button("Anonimizuj", id="anonymize", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#csv-preview", DataTable)
        if self.headers:
            table.add_columns(
                *(f"{index + 1}. {header}" for index, header in enumerate(self.headers))
            )
            for row in self.parsed.rows[1:51]:
                table.add_row(
                    *(
                        row[index].value.replace("\r", "↵").replace("\n", "↵")
                        if index < len(row)
                        else ""
                        for index in range(len(self.headers))
                    )
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "anonymize":
            return
        app = cast(AnonymizationDiffApp, self.app)
        selectors = [
            str(index + 1)
            for index in range(len(self.headers))
            if not self.query_one(f"#mask-{index + 1}", Checkbox).value
        ]
        try:
            assert app.detector is not None
            ranges = plan_skips(self.parsed, selectors).protected_ranges
            app.spans = sorted(
                filter_spans(app.detector(app.text), ranges), key=lambda span: span.start
            )
        except (OSError, ValueError, ImportError):
            self.query_one("#csv-error", Static).update("Nie udało się uruchomić anonimizacji")
            return
        app.pop_screen()
        app.call_after_refresh(app._show_selection)


class AnonymizationDiffApp(App[None]):
    """Navigate detected replacements without writing the source document to disk."""

    TITLE = "Porównanie anonimizacji"
    CSS = """
    #panes { height: 1fr; }
    .pane { width: 1fr; height: 1fr; }
    .pane-title { height: 1; text-style: bold; text-align: center; }
    RichLog { height: 1fr; border: round $primary; }
    #status { height: 1; text-align: center; }
    #csv-columns { height: 1fr; }
    #csv-table-wrap { width: 1fr; }
    #csv-preview { height: 1fr; border: round $primary; }
    #csv-selectors { width: 34; border: round $primary; padding: 0 1; }
    #csv-checkboxes { height: 1fr; }
    #csv-error { height: 1; }
    #anonymize { width: 100%; }
    #export-controls { height: 3; }
    #export-filename { width: 1fr; }
    #export-status { height: 1; }
    """
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("up", "previous_change", "Poprzednia", priority=True),
        Binding("left", "previous_change", "Poprzednia", priority=True),
        Binding("down", "next_change", "Następna", priority=True),
        Binding("right", "next_change", "Następna", priority=True),
        Binding("q", "quit", "Wyjście"),
    ]

    def __init__(
        self,
        text: str,
        spans: list[Span],
        *,
        csv_path: Path | None = None,
        detector: Callable[[str], list[Span]] | None = None,
    ) -> None:
        super().__init__()
        self.text = text
        self.spans = sorted(spans, key=lambda span: span.start)
        self.active = 0
        self.csv_path = csv_path
        self.detector = detector

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="panes"):
            with Vertical(classes="pane"):
                yield Static("PRZED · wykryte fragmenty", classes="pane-title")
                yield RichLog(id="before", min_width=1, auto_scroll=False, wrap=False)
            with Vertical(classes="pane"):
                yield Static("PO · zamaskowane etykiety", classes="pane-title")
                yield RichLog(id="after", min_width=1, auto_scroll=False, wrap=False)
        if self.csv_path is not None:
            with Horizontal(id="export-controls"):
                yield Input(
                    value=f"{self.csv_path.stem}_anonymised.csv",
                    placeholder="Nazwa pliku CSV",
                    id="export-filename",
                )
                yield Button("Eksportuj", id="export", variant="primary")
            yield Static("", id="export-status")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._show_selection()
        if self.csv_path is not None:
            self.push_screen(CsvSelectionScreen(self.text))

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in {"next_change", "previous_change"} and (
            isinstance(self.screen, CsvSelectionScreen) or isinstance(self.focused, Input)
        ):
            return False
        return True

    def action_next_change(self) -> None:
        if self.spans:
            self.active = (self.active + 1) % len(self.spans)
            self._show_selection()

    def action_previous_change(self) -> None:
        if self.spans:
            self.active = (self.active - 1) % len(self.spans)
            self._show_selection()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "export" or self.csv_path is None:
            return
        name = self.query_one("#export-filename", Input).value.strip()
        status = self.query_one("#export-status", Static)
        if not name or "/" in name or "\\" in name or not name.lower().endswith(".csv"):
            status.update("Podaj nazwę pliku CSV bez ścieżki")
            return
        target = self.csv_path.parent / name
        if target.resolve() == self.csv_path.resolve():
            status.update("Nie można nadpisać pliku źródłowego")
            return
        try:
            raw = self.csv_path.read_bytes()
            encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
            try:
                raw.decode(encoding)
            except UnicodeDecodeError:
                encoding = "cp1250"
            data = render_mask(self.text, self.spans).encode(encoding)
            with target.open("xb") as output:
                output.write(data)
        except FileExistsError:
            status.update("Plik już istnieje")
        except (OSError, ValueError):
            status.update("Nie udało się zapisać pliku")
        else:
            status.update("Zapisano plik CSV")

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
        anonymizer = Anonymizer(model=model, threshold=threshold, device=device)
        if input_path.suffix.lower() == ".csv":
            app = AnonymizationDiffApp(text, [], csv_path=input_path, detector=anonymizer.detect)
        else:
            app = AnonymizationDiffApp(text, anonymizer.detect(text))
    except (OSError, ValueError, ImportError):
        print(f"model error: {model}", file=sys.stderr)
        return 2
    app.run()
    return 0
