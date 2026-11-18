"""PII-33: overlapping detections must never consume surrounding original text."""

from __future__ import annotations

import asyncio
import re
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

import piitier
from piitier.batch import mask_batch
from piitier.labels import Label
from piitier.render import mask as render_mask
from piitier.spans import Span
from piitier.tui import AnonymizationDiffApp


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Nr 30569309025904 KONIEC.", "Nr [NR_KARTY] KONIEC."),
        ("100;30569309025904;200", "100;[NR_KARTY];200"),
    ],
)
def test_uc250_public_mask_preserves_collision_suffix(text: str, expected: str) -> None:
    assert piitier.mask(text) == expected


def test_uc251_cli_preserves_collision_suffix(tmp_path: Path) -> None:
    source = tmp_path / "a.txt"
    source.write_text("Nr 30569309025904 KONIEC.", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "piitier.cli", "mask", str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == "Nr [NR_KARTY] KONIEC."
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("skip_columns", "expected"),
    [
        (None, "Left;Number;Right\r\n100;[NR_KARTY];200\r\n"),
        (["Left"], "Left;Number;Right\r\n100;[NR_KARTY];200\r\n"),
        (["Number"], "Left;Number;Right\r\n100;30569309025904;200\r\n"),
    ],
)
def test_uc252_csv_preserves_collision_cells(skip_columns: list[str] | None, expected: str) -> None:
    text = "Left;Number;Right\r\n100;30569309025904;200\r\n"
    assert piitier.mask_csv(text, skip_columns=skip_columns, delimiter=";") == expected


@given(
    runs=st.tuples(
        *(st.text("0123456789", min_size=length, max_size=length) for length in range(8, 27))
    )
)
@example(runs=tuple("30569309025904" if n == 14 else "0" * n for n in range(8, 27)))
@settings(max_examples=100, deadline=None)
def test_uc253_random_digit_runs_preserve_outside_bytes(runs: tuple[str, ...]) -> None:
    text = "\r\n".join(f"Żółć 🦊 ⟨{run}⟩ KONIEC." for run in runs)
    spans = piitier.detect(text)
    outside: list[str] = []
    cursor = 0
    for span in sorted(spans, key=lambda item: item.start):
        if span.start > cursor:
            outside.append(text[cursor : span.start])
        cursor = max(cursor, span.end)
    outside.append(text[cursor:])

    # Generated text contains no square brackets: removing placeholders leaves
    # precisely the original characters outside the union, even for overlaps.
    rendered_outside = re.sub(r"\[[^\[\]]+\]", "", piitier.mask(text))
    assert rendered_outside.encode("utf-8") == "".join(outside).encode("utf-8")


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(
    ("regon_status", "card_status", "expected"),
    [
        ("suspect", "valid", "Nr [NR_KARTY] KONIEC."),
        ("valid", "suspect", "Nr [REGON] KONIEC."),
    ],
)
def test_uc254_identical_ranges_use_fusion_priority(
    reverse: bool, regon_status: str, card_status: str, expected: str
) -> None:
    spans = [
        Span(3, 17, Label.REGON, "rule", 1.0, regon_status),
        Span(3, 17, Label.NR_KARTY, "rule", 1.0, card_status),
    ]
    if reverse:
        spans.reverse()
    assert render_mask("Nr 30569309025904 KONIEC.", spans) == expected


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(
    ("regon_range", "card_range", "expected"),
    [
        ((1, 8), (5, 11), "⟨[REGON][NR_KARTY]⟩ KONIEC."),
        ((1, 11), (4, 8), "⟨[REGON][NR_KARTY][REGON]⟩ KONIEC."),
        ((1, 5), (5, 11), "⟨[REGON][NR_KARTY]⟩ KONIEC."),
        ((1, 4), (7, 11), "⟨[REGON]def[NR_KARTY]⟩ KONIEC."),
    ],
    ids=["partial", "nested", "adjacent", "disjoint"],
)
def test_uc255_overlap_shapes_preserve_union_and_surroundings(
    reverse: bool,
    regon_range: tuple[int, int],
    card_range: tuple[int, int],
    expected: str,
) -> None:
    spans = [
        Span(*regon_range, Label.REGON, "rule", 1.0, "suspect"),
        Span(*card_range, Label.NR_KARTY, "rule", 1.0, "valid"),
    ]
    if reverse:
        spans.reverse()
    assert render_mask("⟨abcdefghij⟩ KONIEC.", spans) == expected


def test_uc256_batch_preserves_collision_suffixes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source, target = tmp_path / "in", tmp_path / "out"
    source.mkdir()
    (source / "a.txt").write_text("Nr 30569309025904 KONIEC.", encoding="utf-8")
    (source / "b.csv").write_bytes(b"100;30569309025904;200\r\n")
    assert mask_batch(source, target) == 0
    assert {path.name: path.read_bytes() for path in target.iterdir()} == {
        "a.txt": b"Nr [NR_KARTY] KONIEC.",
        "b.csv": b"100;[NR_KARTY];200\r\n",
    }
    assert capsys.readouterr() == ("", "batch: 2 masked, 0 failed\n")


def test_uc257_rules_only_tui_export_preserves_collision_suffix(tmp_path: Path) -> None:
    text = "Left;Number;Right\r\n100;30569309025904;200\r\n"
    source = tmp_path / "in.csv"
    source.write_bytes(text.encode("utf-8"))
    app = AnonymizationDiffApp(text, [], csv_path=source, detector=piitier.detect)

    async def exercise() -> None:
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.click("#anonymize")
            await pilot.pause()
            await pilot.click("#export")
            assert (tmp_path / "in_anonymised.csv").read_bytes() == (
                b"Left;Number;Right\r\n100;[NR_KARTY];200\r\n"
            )
            assert source.read_bytes() == text.encode("utf-8")

    asyncio.run(exercise())


@pytest.mark.parametrize(
    ("numbering", "expected"),
    [
        (
            {(1, 11): 7, (13, 16): 5},
            "⟨[OSOBA_n][NR_KARTY][OSOBA_n]⟩ [OSOBA_5].",
        ),
        (
            {(1, 11): 7, (1, 4): 9, (13, 16): 5},
            "⟨[OSOBA_9][NR_KARTY][OSOBA_n]⟩ [OSOBA_5].",
        ),
    ],
)
def test_uc258_numbered_fragments_use_exact_range_or_template(
    numbering: dict[tuple[int, int], int], expected: str
) -> None:
    spans = [
        Span(1, 11, Label.OSOBA, "model:ner", 1.0, "valid"),
        Span(4, 8, Label.NR_KARTY, "rule", 1.0, "valid"),
        Span(13, 16, Label.OSOBA, "model:ner", 1.0, "valid"),
    ]
    assert render_mask("⟨abcdefghij⟩ XYZ.", spans, numbering) == expected
