"""Synthetic data only: the two-pane view never logs document contents."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

from rich.text import Text
from textual.widgets import RichLog, Static

from piitier.labels import Label
from piitier.spans import Span
from piitier.tui import AnonymizationDiffApp, build_diff


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
    assert "model not found" in result.stderr
    assert "PRIVATE TEST TEXT" not in result.stderr + result.stdout
