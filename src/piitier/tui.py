"""Local two-pane comparison of detected text and its anonymized replacements."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, ClassVar, cast

from pypdf.errors import PdfReadError
from rich.cells import cell_len
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    RichLog,
    Static,
)

from piitier import Anonymizer
from piitier.csvskip import (
    filter_spans,
    parse_csv_field_ranges,
    plan_skips,
    sniff_delimiter,
)
from piitier.jsonmask import detect_json
from piitier.loaders import (
    IncorrectPasswordError,
    PasswordRequiredError,
    PdfNoTextError,
    get_loader,
    load_with_password,
)
from piitier.render import mask as render_mask
from piitier.spans import Span
from piitier.xlsx import RenderedWorkbook, mask_workbook, protected_ranges, render_workbook


class PasswordPromptApp(App[str | None]):
    """Short-lived interactive password prompt application for encrypted PDFs."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("ctrl+c", "interrupt", "Interrupt", show=False, priority=True),
    ]

    CSS = """
    Screen {
        align: center middle;
    }
    #dialog {
        width: 50;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }
    #filename {
        text-style: bold;
        margin-bottom: 1;
    }
    #status {
        margin-bottom: 1;
    }
    #buttons {
        layout: horizontal;
        align: center middle;
        margin-top: 1;
    }
    Button {
        margin: 0 1;
    }
    """

    def __init__(self, path: Path, attempt: int, incorrect: bool) -> None:
        super().__init__()
        self.pdf_path = path
        self.attempt = attempt
        self.incorrect = incorrect
        self.interrupted = False

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(f"Plik: {self.pdf_path.name}", id="filename", markup=False)
            status_text = (
                f"Błędne hasło (próba {self.attempt}/3)"
                if self.incorrect
                else f"Podaj hasło do pliku (próba {self.attempt}/3)"
            )
            yield Static(status_text, id="status")
            yield Input(password=True, placeholder="Hasło", id="password-input")
            with Horizontal(id="buttons"):
                yield Button("Unlock", id="unlock", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#password-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "unlock":
            self._submit()
        elif event.button.id == "cancel":
            self._cancel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def key_escape(self) -> None:
        self._cancel()

    def action_interrupt(self) -> None:
        self.interrupted = True
        self._cancel()

    def _submit(self) -> None:
        inp = self.query_one("#password-input", Input)
        val = inp.value
        inp.value = ""
        self.exit(val)

    def _cancel(self) -> None:
        inp = self.query_one("#password-input", Input)
        inp.value = ""
        self.exit(None)


def tui_password_prompt(path: Path, attempt: int, incorrect: bool) -> str | None:
    """Prompt interactively via Textual when stdin and stdout are terminals."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return None
    app = PasswordPromptApp(path, attempt, incorrect)
    value = app.run()
    if app.interrupted:
        raise KeyboardInterrupt
    return value


def _column_after(fragment: str, column: int) -> int:
    """Find the terminal column after a fragment, resetting at the last newline."""
    last_newline = fragment.rfind("\n")
    if last_newline >= 0:
        return cell_len(fragment[last_newline + 1 :])
    return column + cell_len(fragment)


def build_diff(
    text: str,
    spans: list[Span],
    active: int,
    numbering: dict[tuple[int, int], int] | None = None,
) -> tuple[Text, Text, list[tuple[int, int, int, int]]]:
    """Render both sides and record corresponding line/column targets."""
    from piitier.render import _resolve_placeholder

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
        if numbering is not None and span.label.numbered:
            idx = numbering.get((span.start, span.end))
            replacement = (
                _resolve_placeholder(span.label.placeholder, idx)
                if idx is not None
                else span.label.placeholder
            )
        else:
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


class ColumnSelectionScreen(Screen[None]):
    """Preview table records and select columns by position, not header name."""

    def __init__(
        self,
        title: str,
        headers: list[str],
        preview_rows: list[list[str]],
        apply_skips: Callable[[list[str]], list[Span]],
    ) -> None:
        super().__init__()
        self.title_text = title
        self.headers = headers
        self.preview_rows = preview_rows
        self.apply_skips = apply_skips

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="table-columns"):
            with Vertical(id="table-wrap"):
                yield Static(self.title_text, classes="pane-title")
                yield DataTable(id="table-preview", zebra_stripes=True)
            with Vertical(id="table-selectors"):
                yield Static("MASKUJ KOLUMNY", classes="pane-title")
                yield Static("Odznaczone: bez zmian")
                with VerticalScroll(id="table-checkboxes"):
                    for index, header in enumerate(self.headers):
                        yield Checkbox(f"{index + 1}. {header}", value=True, id=f"mask-{index + 1}")
        yield Static("", id="table-error")
        yield Button("Anonimizuj", id="anonymize", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#table-preview", DataTable)
        if self.headers:
            table.add_columns(
                *(f"{index + 1}. {header}" for index, header in enumerate(self.headers))
            )
            for row in self.preview_rows:
                table.add_row(
                    *(
                        row[index].replace("\r", "↵").replace("\n", "↵") if index < len(row) else ""
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
            app.spans = sorted(self.apply_skips(selectors), key=lambda span: span.start)
            if app._numbering_fn is not None:
                app._numbering = app._numbering_fn(app.text, app.spans)
        except (OSError, ValueError, ImportError):
            self.query_one("#table-error", Static).update("Nie udało się uruchomić anonimizacji")
            return
        app.skipped = selectors
        app.pop_screen()
        app.call_after_refresh(app._show_selection)


def _padded_headers(first_row: list[str], width: int) -> list[str]:
    return [first_row[i] if i < len(first_row) else f"Kolumna {i + 1}" for i in range(width)]


def csv_selection_screen(text: str, detector: Callable[[str], list[Span]]) -> ColumnSelectionScreen:
    """Column selection for CSV text: preview of the first 50 records after the header."""
    parsed = parse_csv_field_ranges(text, sniff_delimiter(text))
    first_row = [cell.value for cell in parsed.rows[0]] if parsed.rows else []
    width = max((len(row) for row in parsed.rows), default=0)

    def apply_skips(selectors: list[str]) -> list[Span]:
        return filter_spans(detector(text), plan_skips(parsed, selectors).protected_ranges)

    return ColumnSelectionScreen(
        "PODGLĄD CSV · pierwsze 50 wierszy",
        _padded_headers(first_row, width),
        [[cell.value for cell in row] for row in parsed.rows[1:51]],
        apply_skips,
    )


def xlsx_selection_screen(
    rendered: RenderedWorkbook, detector: Callable[[str], list[Span]]
) -> ColumnSelectionScreen:
    """Column selection for a workbook: preview of sheet 1, masking applies to every sheet."""
    rows: list[list[str]] = []
    for cell in rendered.cells:
        if cell.sheet_index != 0 or not 2 <= cell.row <= 51:
            continue
        while len(rows) < cell.row - 1:
            rows.append([])
        rows[cell.row - 2].append(cell.text)

    def apply_skips(selectors: list[str]) -> list[Span]:
        return filter_spans(detector(rendered.text), protected_ranges(rendered, selectors)[0])

    return ColumnSelectionScreen(
        f"PODGLĄD XLSX · arkusz {rendered.sheet_titles[0]} z {len(rendered.sheet_titles)}"
        " · pierwsze 50 wierszy",
        _padded_headers(list(rendered.headers[0]), rendered.width),
        rows,
        apply_skips,
    )


class AnonymizationDiffApp(App[None]):
    """Navigate detected replacements without writing the source document to disk."""

    TITLE = "Porównanie anonimizacji"
    CSS = """
    #panes { height: 1fr; }
    .pane { width: 1fr; height: 1fr; }
    .pane-title { height: 1; text-style: bold; text-align: center; }
    RichLog { height: 1fr; border: round $primary; }
    #status { height: 1; text-align: center; }
    #table-columns { height: 1fr; }
    #table-wrap { width: 1fr; }
    #table-preview { height: 1fr; border: round $primary; }
    #table-selectors { width: 34; border: round $primary; padding: 0 1; }
    #table-checkboxes { height: 1fr; }
    #table-error { height: 1; }
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
        Binding("ctrl+c", "interrupt", "Interrupt", show=False, priority=True),
    ]

    def action_interrupt(self) -> None:
        self.interrupted = True
        self.exit()

    def __init__(
        self,
        text: str,
        spans: list[Span],
        *,
        source_path: Path | None = None,
        detector: Callable[[str], list[Span]] | None = None,
        numbering: dict[tuple[int, int], int] | None = None,
        numbering_fn: Callable[[str, list[Span]], dict[tuple[int, int], int]] | None = None,
        rendered: RenderedWorkbook | None = None,
    ) -> None:
        super().__init__()
        self.interrupted = False
        self.text = text
        self.spans = sorted(spans, key=lambda span: span.start)
        self.active = 0
        self.source_path = source_path
        self.detector = detector
        self._numbering = numbering
        self._numbering_fn = numbering_fn
        self.rendered = rendered
        self.skipped: list[str] = []
        self.export_suffix = ".xlsx" if rendered is not None else ".csv"

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="panes"):
            with Vertical(classes="pane"):
                yield Static("PRZED · wykryte fragmenty", classes="pane-title")
                yield RichLog(id="before", min_width=1, auto_scroll=False, wrap=False)
            with Vertical(classes="pane"):
                yield Static("PO · zamaskowane etykiety", classes="pane-title")
                yield RichLog(id="after", min_width=1, auto_scroll=False, wrap=False)
        if self.source_path is not None:
            with Horizontal(id="export-controls"):
                yield Input(
                    value=f"{self.source_path.stem}_anonymised{self.export_suffix}",
                    placeholder=f"Nazwa pliku {self.export_suffix[1:].upper()}",
                    id="export-filename",
                )
                yield Button("Eksportuj", id="export", variant="primary")
            yield Static("", id="export-status")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._show_selection()
        if self.source_path is not None:
            assert self.detector is not None, "column selection needs a detector"
            if self.rendered is not None:
                self.push_screen(xlsx_selection_screen(self.rendered, self.detector))
            else:
                self.push_screen(csv_selection_screen(self.text, self.detector))

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in {"next_change", "previous_change"} and (
            isinstance(self.screen, ColumnSelectionScreen) or isinstance(self.focused, Input)
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
        if event.button.id != "export" or self.source_path is None:
            return
        name = self.query_one("#export-filename", Input).value.strip()
        status = self.query_one("#export-status", Static)
        kind = self.export_suffix[1:].upper()
        if not name or "/" in name or "\\" in name or not name.lower().endswith(self.export_suffix):
            status.update(f"Podaj nazwę pliku {kind} bez ścieżki")
            return
        target = self.source_path.parent / name
        if target.resolve() == self.source_path.resolve():
            status.update("Nie można nadpisać pliku źródłowego")
            return
        if self.rendered is not None:
            self._export_workbook(target, status)
            return
        try:
            raw = self.source_path.read_bytes()
            encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
            try:
                raw.decode(encoding)
            except UnicodeDecodeError:
                encoding = "cp1250"
            data = render_mask(self.text, self.spans, self._numbering).encode(encoding)
            with target.open("xb") as output:
                output.write(data)
        except FileExistsError:
            status.update("Plik już istnieje")
        except (OSError, ValueError):
            status.update("Nie udało się zapisać pliku")
        else:
            status.update("Zapisano plik CSV")

    def _export_workbook(self, target: Path, status: Static) -> None:
        assert self.source_path is not None and self.detector is not None
        if target.exists():
            status.update("Plik już istnieje")
            return
        try:
            converted = mask_workbook(
                self.source_path,
                target,
                detector=self.detector,
                skip_columns=self.skipped,
                numbering=self._numbering,
            )
        except (OSError, ValueError):
            status.update("Nie udało się zapisać pliku")
        else:
            status.update(f"Zapisano plik XLSX · formuły zamienione na tekst: {converted}")

    def _show_selection(self) -> None:
        before, after, lines = build_diff(self.text, self.spans, self.active, self._numbering)
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


def compare_file(
    input_path: Path,
    model: str | Path,
    threshold: float,
    device: str,
    revision: str | None = None,
) -> int:
    """Detect once, display locally, and keep document text out of errors/output."""
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
    suffix = input_path.suffix.lower()
    rendered: RenderedWorkbook | None = None
    try:
        if suffix == ".xlsx":
            rendered = render_workbook(input_path)
            text = rendered.text
        else:
            text = load_with_password(input_path, prompt=tui_password_prompt)
    except PdfNoTextError:
        print("PDF has no text layer", file=sys.stderr)
        return 3
    except PdfReadError:
        print(f"could not read PDF: {input_path}", file=sys.stderr)
        return 2
    except (PasswordRequiredError, IncorrectPasswordError) as e:
        print(str(e), file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print(f"cannot decode: {input_path}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError):
        print(f"could not read: {input_path}", file=sys.stderr)
        return 2

    try:
        anonymizer = Anonymizer(model=model, revision=revision, threshold=threshold, device=device)
        if suffix in (".csv", ".xlsx"):
            app = AnonymizationDiffApp(
                text,
                [],
                source_path=input_path,
                detector=anonymizer.detect,
                numbering_fn=anonymizer.assign,
                rendered=rendered,
            )
        elif suffix == ".json":
            spans, numbering = detect_json(
                text,
                detector=anonymizer.detect,
                numbering_fn=anonymizer.assign,
            )
            app = AnonymizationDiffApp(text, spans, numbering=numbering)
        else:
            spans = anonymizer.detect(text)
            numbering = anonymizer.assign(text, spans)
            app = AnonymizationDiffApp(text, spans, numbering=numbering)
    except (OSError, ValueError, ImportError):
        print(f"model error: could not load or run: {model}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130

    try:
        app.run()
        if app.interrupted:
            return 130
    except KeyboardInterrupt:
        return 130
    return 0
