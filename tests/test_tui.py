"""Synthetic data only: the two-pane view never logs document contents."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import openpyxl
import pytest
from rich.text import Text
from textual.widgets import Checkbox, DataTable, Input, RichLog, Static

import piitier
from piitier.labels import Label
from piitier.spans import Span
from piitier.tui import AnonymizationDiffApp, ColumnSelectionScreen, build_diff
from piitier.xlsx import render_workbook


def span(start: int, end: int, label: Label) -> Span:
    return Span(start, end, label, "rule", 1.0, "valid")


def styles_at(text: Text, offset: int) -> list[str]:
    return [str(style.style) for style in text.spans if style.start <= offset < style.end]


def test_diff_preserves_unchanged_text_and_marks_replacements_green() -> None:
    original = "Literal [EMAIL] <tag> ABC\ncode XYZ end"
    changes = [span(22, 25, Label.PESEL), span(31, 34, Label.EMAIL)]

    before, after, lines = build_diff(original, changes, active=0)

    assert before.plain == original
    assert after.plain == "Literal [EMAIL] <tag> [PESEL]\ncode [EMAIL] end"
    assert lines == [(0, 0, 22, 22), (1, 1, 5, 5)]
    assert any("on red" in style for style in styles_at(before, 22))
    assert any("on green" in style for style in styles_at(after, 22))
    assert styles_at(before, 8) == []  # literal bracketed text is not a finding
    assert any("green" in style for style in styles_at(after, after.plain.rindex("[EMAIL]")))


def test_diff_tracks_different_line_offsets_after_multiline_replacement() -> None:
    original = "A\nSECRET\nCONTINUED\nB\nOTHER"
    changes = [span(2, 18, Label.ADRES), span(21, 26, Label.NIP)]

    before, after, lines = build_diff(original, changes, active=1)

    assert before.plain == original
    assert after.plain == "A\n[ADRES_n]\nB\n[NIP]"
    assert lines == [(1, 1, 0, 0), (4, 3, 0, 0)]
    assert any("on green" in style for style in styles_at(after, after.plain.index("[NIP]")))


def test_arrows_navigate_findings_and_scroll_both_panes() -> None:
    original = "FIRST\n" + "unchanged\n" * 45 + "SECOND"
    first = span(0, 5, Label.PESEL)
    last = span(original.index("SECOND"), len(original), Label.EMAIL)
    app = AnonymizationDiffApp(original, [first, last])

    async def exercise() -> None:
        async with app.run_test(size=(100, 20)) as pilot:
            before = app.query_one("#before", RichLog)
            after = app.query_one("#after", RichLog)
            assert app.active == 0
            assert before.scroll_y == after.scroll_y == 0

            await pilot.press("down")
            await pilot.pause()
            assert app.active == 1
            assert before.scroll_y > 0
            assert after.scroll_y > 0
            assert before.scroll_y == after.scroll_y

            await pilot.press("up")
            await pilot.pause()
            assert app.active == 0
            assert before.scroll_y == after.scroll_y == 0

            await pilot.press("left")  # previous from first wraps to last
            assert app.active == 1
            await pilot.press("right")  # next wraps to first
            assert app.active == 0

    asyncio.run(exercise())


def test_arrow_navigation_reveals_changes_on_long_unwrapped_lines() -> None:
    original = "FIRST " + "x" * 120 + " SECOND"
    app = AnonymizationDiffApp(
        original,
        [span(0, 5, Label.PESEL), span(original.index("SECOND"), len(original), Label.EMAIL)],
    )

    async def exercise() -> None:
        async with app.run_test(size=(80, 16)) as pilot:
            await pilot.press("down")
            await pilot.pause()
            before = app.query_one("#before", RichLog)
            after = app.query_one("#after", RichLog)
            assert before.scroll_x > 0
            assert after.scroll_x > 0

    asyncio.run(exercise())


def test_no_findings_keeps_original_in_both_panes() -> None:
    app = AnonymizationDiffApp("Just literal [PESEL], not a detected value", [])

    async def exercise() -> None:
        async with app.run_test() as pilot:
            await pilot.press("right", "down", "left")
            assert app.active == 0
            status = str(app.query_one("#status", Static).render())
            assert status == "Brak wykrytych fragmentów do zamaskowania"

    asyncio.run(exercise())


def test_compare_rejects_missing_model_without_printing_document(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("PRIVATE TEST TEXT", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "piitier.cli",
            "compare",
            str(source),
            "--model",
            str(tmp_path / "missing"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "PRIVATE TEST TEXT" not in result.stderr + result.stdout


def test_csv_preview_selects_columns_to_mask_before_export(tmp_path: Path) -> None:
    text = "ID;ID;Notes\r\n90051512340;90051512340;90051512340\r\n"
    source = tmp_path / "in.csv"
    source.write_bytes(text.encode())
    app = AnonymizationDiffApp(text, [], source_path=source, detector=piitier.detect)

    async def exercise() -> None:
        async with app.run_test(size=(110, 30)) as pilot:
            assert isinstance(app.screen, ColumnSelectionScreen)
            table = app.screen.query_one("#table-preview", DataTable)
            assert table.get_row_at(0) == ["90051512340"] * 3
            assert len(app.screen.query(Checkbox)) == 3
            assert all(checkbox.value for checkbox in app.screen.query(Checkbox))
            assert app.spans == []

            await pilot.click("#mask-1")
            await pilot.click("#mask-2")
            await pilot.click("#anonymize")
            await pilot.pause()
            assert not isinstance(app.screen, ColumnSelectionScreen)
            await pilot.click("#export")
            assert (tmp_path / "in_anonymised.csv").read_bytes() == (
                b"ID;ID;Notes\r\n90051512340;90051512340;[PESEL]\r\n"
            )
            assert source.read_bytes() == text.encode()

    asyncio.run(exercise())


def test_csv_preview_keeps_arrow_navigation_for_table_and_keyboard_checkboxes(
    tmp_path: Path,
) -> None:
    text = "ID;Notes\n90051512340;one\n90051512340;two\n"
    app = AnonymizationDiffApp(text, [], source_path=tmp_path / "in.csv", detector=piitier.detect)

    async def exercise() -> None:
        async with app.run_test(size=(100, 25)) as pilot:
            table = app.screen.query_one(DataTable)
            table.focus()
            await pilot.press("down")
            assert table.cursor_coordinate.row == 1
            checkbox = app.screen.query_one("#mask-1", Checkbox)
            checkbox.focus()
            await pilot.press("space")
            assert not checkbox.value

    asyncio.run(exercise())


def test_csv_export_default_name_preserves_bytes_and_refuses_overwrite(tmp_path: Path) -> None:
    text = "ID;Notes\r\n90051512340;90051512340\r\n"
    source = tmp_path / "in.csv"
    source.write_bytes(text.encode())
    app = AnonymizationDiffApp(text, [], source_path=source, detector=piitier.detect)

    async def exercise() -> None:
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.click("#mask-1")
            await pilot.click("#anonymize")
            await pilot.pause()
            assert app.query_one("#export-filename", Input).value == "in_anonymised.csv"
            assert await pilot.click("#export")
            output = tmp_path / "in_anonymised.csv"
            assert output.read_bytes() == b"ID;Notes\r\n90051512340;[PESEL]\r\n"
            assert source.read_bytes() == text.encode()

            output.write_bytes(b"EXISTING")
            await pilot.pause(0.25)
            assert await pilot.click("#export")
            await pilot.pause()
            assert output.read_bytes() == b"EXISTING"
            assert "istnieje" in str(app.query_one("#export-status", Static).render())

    asyncio.run(exercise())


def test_csv_export_renamed_file_rejects_source_and_path_escape(tmp_path: Path) -> None:
    text = "ID;Notes\n90051512340;90051512340\n"
    source = tmp_path / "in.csv"
    source.write_text(text, encoding="utf-8")
    app = AnonymizationDiffApp(text, [], source_path=source, detector=piitier.detect)

    async def exercise() -> None:
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.click("#anonymize")
            await pilot.pause()
            filename = app.query_one("#export-filename", Input)
            filename.value = "../outside.csv"
            assert await pilot.click("#export")
            assert not (tmp_path.parent / "outside.csv").exists()
            filename.value = "in.csv"
            await pilot.pause(0.25)
            assert await pilot.click("#export")
            assert source.read_text(encoding="utf-8") == text

            filename.value = "renamed.csv"
            await pilot.pause(0.25)
            assert await pilot.click("#export")
            assert (tmp_path / "renamed.csv").read_bytes() == (b"ID;Notes\n[PESEL];[PESEL]\n")
            assert source.read_text(encoding="utf-8") == text

    asyncio.run(exercise())


def test_csv_ragged_third_column_can_be_left_unmasked(tmp_path: Path) -> None:
    text = "ID;Notes\n90051512340;90051512340;90051512340\n"
    app = AnonymizationDiffApp(text, [], source_path=tmp_path / "in.csv", detector=piitier.detect)

    async def exercise() -> None:
        async with app.run_test(size=(110, 28)) as pilot:
            table = app.screen.query_one(DataTable)
            assert table.get_row_at(0)[2] == "90051512340"
            await pilot.click("#mask-3")
            await pilot.click("#anonymize")
            await pilot.pause()
            assert build_diff(text, app.spans, 0)[1].plain == (
                "ID;Notes\n[PESEL];[PESEL];90051512340\n"
            )

    asyncio.run(exercise())


def test_export_filename_input_keeps_arrow_keys(tmp_path: Path) -> None:
    text = "ID;Notes\n90051512340;90051512340\n"
    app = AnonymizationDiffApp(text, [], source_path=tmp_path / "in.csv", detector=piitier.detect)

    async def exercise() -> None:
        async with app.run_test(size=(110, 28)) as pilot:
            await pilot.click("#anonymize")
            await pilot.pause()
            filename = app.query_one("#export-filename", Input)
            filename.focus()
            await pilot.pause()
            filename.cursor_position = len(filename.value)
            assert filename.cursor_position == len(filename.value)
            await pilot.press("left")
            assert filename.cursor_position == len(filename.value) - 1

    asyncio.run(exercise())


@pytest.mark.parametrize(
    ("original", "text", "expected"),
    [
        (
            "Łódź;ID\r\nmiasto;90051512340\r\n".encode("cp1250"),
            "Łódź;ID\r\nmiasto;90051512340\r\n",
            "Łódź;ID\r\nmiasto;[PESEL]\r\n".encode("cp1250"),
        ),
        (
            b"\xef\xbb\xbfID;Notes\r\n90051512340;90051512340\r\n",
            "ID;Notes\r\n90051512340;90051512340\r\n",
            b"\xef\xbb\xbfID;Notes\r\n90051512340;[PESEL]\r\n",
        ),
    ],
)
def test_csv_export_retains_source_encoding(
    tmp_path: Path, original: bytes, text: str, expected: bytes
) -> None:
    source = tmp_path / "in.csv"
    source.write_bytes(original)
    app = AnonymizationDiffApp(text, [], source_path=source, detector=piitier.detect)

    async def exercise() -> None:
        async with app.run_test(size=(110, 28)) as pilot:
            await pilot.click("#mask-1")
            await pilot.click("#anonymize")
            await pilot.pause()
            await pilot.click("#export")
            assert (tmp_path / "in_anonymised.csv").read_bytes() == expected
            assert source.read_bytes() == original

    asyncio.run(exercise())


@pytest.mark.parametrize("action", ["enter", "unlock", "escape", "cancel", "ctrl+c"])
@pytest.mark.parametrize("empty", [False, True])
def test_uc186_uc187_uc188_password_widget_states(tmp_path: Path, action: str, empty: bool) -> None:
    import secrets

    from piitier.tui import PasswordPromptApp

    secret = "" if empty else " " + secrets.token_hex(12) + " "
    app = PasswordPromptApp(tmp_path / "[red]literal.pdf", 2, True)

    async def exercise() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            field = app.query_one("#password-input", Input)
            field.value = secret
            await pilot.pause()
            assert "[red]literal.pdf" in str(app.query_one("#filename", Static).render())
            assert "2/3" in str(app.query_one("#status", Static).render())
            assert field.password
            if secret:
                assert secret not in app.export_screenshot()
            if action in {"unlock", "cancel"}:
                assert await pilot.click("#" + action)
            else:
                await pilot.press(action)
            assert app.return_value == (secret if action in {"unlock", "enter"} else None)
            assert field.value == ""
            assert app.interrupted == (action == "ctrl+c")

    asyncio.run(exercise())


@pytest.mark.parametrize("answers", ["correct", "exhaust", "cancel", "interrupt"])
def test_uc186_uc187_uc188_comparison_authentication_flow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    answers: str,
) -> None:
    import secrets

    from test_loaders_pdf import password_pdf

    from piitier import tui

    secret = secrets.token_hex(12)
    pdf = password_pdf(tmp_path, secret)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    prompts = []
    model_inputs = []
    panes = []

    def prompt_run(app):
        prompts.append((app.attempt, app.incorrect))

        async def exercise():
            async with app.run_test() as pilot:
                field = app.query_one("#password-input", Input)
                field.value = secret if answers == "correct" and app.attempt == 2 else "wrong"
                await pilot.press(
                    "escape"
                    if answers == "cancel"
                    else "ctrl+c"
                    if answers == "interrupt"
                    else "enter"
                )
                assert field.value == ""

        asyncio.run(exercise())
        return app.return_value

    class LocalAnonymizer:
        def __init__(self, **kwargs):
            assert answers == "correct"

        def detect(self, text):
            model_inputs.append(text)
            return piitier.detect(text)

        def assign(self, text, spans):
            return {}

    def comparison_run(app):
        async def exercise():
            async with app.run_test(size=(100, 25)) as pilot:
                before = "\n".join(line.text for line in app.query_one("#before", RichLog).lines)
                after = "\n".join(line.text for line in app.query_one("#after", RichLog).lines)
                panes.append((before, after))
                await pilot.press("down", "up", "q")

        asyncio.run(exercise())

    monkeypatch.setattr(tui.PasswordPromptApp, "run", prompt_run)
    monkeypatch.setattr(tui, "Anonymizer", LocalAnonymizer)
    monkeypatch.setattr(tui.AnonymizationDiffApp, "run", comparison_run)
    assert (
        tui.compare_file(pdf, "local", 0.0, "cpu")
        == {
            "correct": 0,
            "exhaust": 2,
            "cancel": 2,
            "interrupt": 130,
        }[answers]
    )
    if answers == "correct":
        assert prompts == [(1, False), (2, True)]
        assert model_inputs == ["  PESEL: 90051512340  \n\nEnd."]
        assert panes == [("  PESEL: 90051512340  \n\nEnd.", "  PESEL: [PESEL]  \n\nEnd.")]
    else:
        assert model_inputs == panes == []
        assert prompts == (
            [(1, False), (2, True), (3, True)] if answers == "exhaust" else [(1, False)]
        )


@pytest.mark.parametrize("stdin_tty,stdout_tty", [(False, True), (True, False), (False, False)])
def test_uc188_nonterminal_and_parser_errors_are_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stdin_tty: bool,
    stdout_tty: bool,
) -> None:
    import secrets

    from test_loaders_pdf import password_pdf

    from piitier import tui

    secret = secrets.token_hex(12)
    pdf = password_pdf(tmp_path, secret)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: stdin_tty)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: stdout_tty)

    def forbidden(*args, **kwargs):
        pytest.fail("must not open prompt/model before authentication")

    monkeypatch.setattr(tui.PasswordPromptApp, "run", forbidden)
    monkeypatch.setattr(tui, "Anonymizer", forbidden)
    assert tui.compare_file(pdf, "unused", 0.0, "cpu") == 2
    pdf.write_bytes(b"PRIVATE-PARSER-90051512340")
    assert tui.compare_file(pdf, "unused", 0.0, "cpu") == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert secret not in captured.err and "90051512340" not in captured.err
    assert set(tmp_path.iterdir()) == {pdf}


def test_uc189_comparison_interrupt_and_csv_export(tmp_path: Path) -> None:
    text = "ID;Notes\r\n90051512340;90051512340\r\n"
    source = tmp_path / "in.csv"
    source.write_bytes(text.encode())
    app = AnonymizationDiffApp(text, [], source_path=source, detector=piitier.detect)

    async def exercise() -> None:
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.click("#mask-1")
            await pilot.click("#anonymize")
            await pilot.pause()
            after = app.query_one("#after", RichLog)
            assert "\n".join(line.text for line in after.lines) == "ID;Notes\n90051512340;[PESEL]\n"
            await pilot.press("down", "up")
            await pilot.click("#export")
            assert (
                tmp_path / "in_anonymised.csv"
            ).read_bytes() == b"ID;Notes\r\n90051512340;[PESEL]\r\n"
            assert source.read_bytes() == text.encode()
            await pilot.press("ctrl+c")
            assert app.interrupted

    asyncio.run(exercise())


def test_json_comparison_shows_exact_source_and_masked_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_jsonmask import JsonNamePredictor

    from piitier import tui

    source = tmp_path / "test.json"
    text = (
        '{\n  "Zoja Testowa": ["\\u005aoja Testowa", "Mira Fikcyjna"],\n'
        '  "alias": "Zoja Testowa", "number": 90051512340\n}\n'
    )
    expected = (
        '{\n  "Zoja Testowa": ["[OSOBA_1]", "[OSOBA_2]"],\n'
        '  "alias": "[OSOBA_1]", "number": 90051512340\n}\n'
    )
    source.write_text(text, encoding="utf-8")
    monkeypatch.setattr(
        tui, "Anonymizer", lambda **kwargs: piitier.Anonymizer(predictor=JsonNamePredictor())
    )
    panes = []

    def run_comparison(app):
        async def exercise():
            async with app.run_test(size=(110, 30)) as pilot:
                before = "\n".join(line.text for line in app.query_one("#before", RichLog).lines)
                after = "\n".join(line.text for line in app.query_one("#after", RichLog).lines)
                panes.append((before, after))
                await pilot.press("down", "down")
                assert app.active == 2
                await pilot.press("up")
                assert app.active == 1
                await pilot.press("q")

        asyncio.run(exercise())

    monkeypatch.setattr(tui.AnonymizationDiffApp, "run", run_comparison)
    assert tui.compare_file(source, "offline-test-model", 0.0, "cpu") == 0
    assert panes == [(text, expected)]
    assert source.read_text(encoding="utf-8") == text


@pytest.mark.parametrize(
    "payload",
    [b'{"private":"90051512340",}', b'{"private":"90051512340\xff"}'],
)
def test_json_comparison_rejects_invalid_input_before_model_or_display(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    payload: bytes,
) -> None:
    from piitier import tui

    def forbidden_model(**kwargs):
        raise AssertionError("invalid input must fail before model loading")

    monkeypatch.setattr(tui, "Anonymizer", forbidden_model)
    source = tmp_path / "bad.json"
    source.write_bytes(payload)
    assert tui.compare_file(source, "must-not-load", 0.0, "cpu") == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "private" not in captured.err and "90051512340" not in captured.err
    assert {path.name for path in tmp_path.iterdir()} == {"bad.json"}


def _write_workbook(path: Path) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Raport"
    sheet.append(["ID", "Notatka"])
    sheet.append(["90051512340", 90051512340])
    workbook.create_sheet("Druga").append(["90051512340", "x"])
    workbook.save(path)


def test_uc199_xlsx_columns_selected_in_tui_and_exported(tmp_path: Path) -> None:
    source = tmp_path / "raport.xlsx"
    _write_workbook(source)
    original = source.read_bytes()
    rendered = render_workbook(source)
    app = AnonymizationDiffApp(
        rendered.text, [], source_path=source, detector=piitier.detect, rendered=rendered
    )

    async def exercise() -> None:
        async with app.run_test(size=(110, 30)) as pilot:
            assert isinstance(app.screen, ColumnSelectionScreen)
            labels = [str(checkbox.label) for checkbox in app.screen.query(Checkbox)]
            assert labels == ["1. ID", "2. Notatka"]
            table = app.screen.query_one("#table-preview", DataTable)
            assert table.get_row_at(0) == ["90051512340", "90051512340"]

            await pilot.click("#mask-1")
            await pilot.click("#anonymize")
            await pilot.pause()
            assert build_diff(app.text, app.spans, 0)[1].plain == (
                "# Raport\nID | Notatka\n90051512340 | [PESEL]\n\n# Druga\n90051512340 | x\n"
            )
            assert app.query_one("#export-filename", Input).value == "raport_anonymised.xlsx"
            await pilot.click("#export")
            await pilot.pause()
            assert "Zapisano" in str(app.query_one("#export-status", Static).render())

    asyncio.run(exercise())
    exported = openpyxl.load_workbook(tmp_path / "raport_anonymised.xlsx")
    assert [list(ws.iter_rows(values_only=True)) for ws in exported.worksheets] == [
        [("ID", "Notatka"), ("90051512340", "[PESEL]")],
        [("90051512340", "x")],
    ]
    assert source.read_bytes() == original


def test_uc200_xlsx_export_refuses_existing_file(tmp_path: Path) -> None:
    source = tmp_path / "raport.xlsx"
    _write_workbook(source)
    rendered = render_workbook(source)
    app = AnonymizationDiffApp(
        rendered.text, [], source_path=source, detector=piitier.detect, rendered=rendered
    )
    output = tmp_path / "raport_anonymised.xlsx"

    async def exercise() -> None:
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.click("#anonymize")
            await pilot.pause()
            await pilot.click("#export")
            await pilot.pause()
            first = output.read_bytes()
            await pilot.pause(0.25)
            await pilot.click("#export")
            await pilot.pause()
            assert str(app.query_one("#export-status", Static).render()) == "Plik już istnieje"
            assert output.read_bytes() == first

    asyncio.run(exercise())


@pytest.mark.parametrize("converted", [0, 1, 2])
def test_uc217_xlsx_export_shows_converted_formula_count(tmp_path: Path, converted: int) -> None:
    source = tmp_path / "formulas.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["First", "Second", "Safe"])
    sheet.append(['="90051512340"'] * converted + ["=1+2"] * (3 - converted))
    workbook.save(source)
    workbook.close()
    original = source.read_bytes()
    rendered = render_workbook(source)
    app = AnonymizationDiffApp(
        rendered.text, [], source_path=source, detector=piitier.detect, rendered=rendered
    )

    async def exercise() -> None:
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.click("#anonymize")
            await pilot.pause()
            await pilot.click("#export")
            await pilot.pause()
            assert str(app.query_one("#export-status", Static).render()) == (
                f"Zapisano plik XLSX · formuły zamienione na tekst: {converted}"
            )

    asyncio.run(exercise())
    masked = openpyxl.load_workbook(tmp_path / "formulas_anonymised.xlsx")
    assert [masked.active.cell(2, col).value for col in range(1, 4)] == (
        ['="[PESEL]"'] * converted + ["=1+2"] * (3 - converted)
    )
    assert [masked.active.cell(2, col).data_type for col in range(1, 4)] == (
        ["s"] * converted + ["f"] * (3 - converted)
    )
    masked.close()
    assert source.read_bytes() == original
