"""Tests for piitier.datagen.tabular (commission-settlement template harvester)."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

import openpyxl
import pytest

from piitier.datagen.build import build, check
from piitier.datagen.tabular import (
    _analyse_columns,
    _build_window,
    _detect_header_row,
    _fmt_cell,
    _map_header,
    _render_window,
    templatize_tables,
)
from piitier.labels import Label

# ---------------------------------------------------------------------------
# Textbook-valid PII values (fictional, for test fixtures only)
# ---------------------------------------------------------------------------

_VALID_PESEL = "44051401359"  # textbook-valid PESEL (male, born 1944-05-14)
_VALID_NIP = "1234563218"  # checksum-valid NIP


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_xlsx(path: Path, headers: list[str], rows: list[list[Any]]) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    wb.save(path)


def _write_csv(path: Path, headers: list[str], rows: list[list[Any]], delim: str = ";") -> None:
    import csv

    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=delim)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)


def _accepted_templates(out: Path, doc_type: str = "zestawienie_prowizyjne") -> list[str]:
    """Return sorted list of accepted template file contents."""
    return sorted(p.read_text(encoding="utf-8") for p in (out / doc_type).glob("*.txt"))


# ---------------------------------------------------------------------------
# Unit tests – helpers
# ---------------------------------------------------------------------------


def test_fmt_cell_none() -> None:
    assert _fmt_cell(None) == ""


def test_fmt_cell_int() -> None:
    assert _fmt_cell(42) == "42"
    assert _fmt_cell(0) == "0"


def test_fmt_cell_float_integer() -> None:
    assert _fmt_cell(3.0) == "3"


def test_fmt_cell_float_decimal() -> None:
    result = _fmt_cell(1.5)
    assert "." in result
    assert "e" not in result.lower()


def test_fmt_cell_bool_before_int() -> None:
    assert _fmt_cell(True) == "True"
    assert _fmt_cell(False) == "False"


def test_fmt_cell_datetime_with_time() -> None:
    v = datetime.datetime(2025, 9, 1, 14, 30, 0)
    assert _fmt_cell(v) == "2025-09-01 14:30:00"


def test_fmt_cell_datetime_date_only() -> None:
    v = datetime.datetime(2025, 9, 1, 0, 0, 0)
    assert _fmt_cell(v) == "2025-09-01"


def test_map_header_osoba_client() -> None:
    assert _map_header("Klient") == (Label.OSOBA, "client")
    assert _map_header("UBEZPIECZAJACY") == (Label.OSOBA, "client")
    assert _map_header("Ubezpieczający") == (Label.OSOBA, "client")
    assert _map_header("Właściciel polisy") == (Label.OSOBA, "client")


def test_map_header_pesel() -> None:
    assert _map_header("PESEL") == (Label.PESEL, "client")
    assert _map_header("PESEL/REGON") == (Label.PESEL, "client")


def test_map_header_policy_number() -> None:
    assert _map_header("Nr polisy") == (Label.NR_POLISY, "other")
    assert _map_header("POLISA") == (Label.NR_POLISY, "other")
    assert _map_header("Numer polisy") == (Label.NR_POLISY, "other")
    assert _map_header("POLICY_NR") == (Label.NR_POLISY, "other")


def test_map_header_staff() -> None:
    assert _map_header("Imię i nazwisko agenta dystrybutora") == (Label.OSOBA, "staff")
    assert _map_header("OWCA") == (Label.OSOBA, "staff")
    assert _map_header("Użytkownik") == (Label.OSOBA, "staff")


def test_map_header_amount() -> None:
    assert _map_header("Prowizja") == (Label.KWOTA, "other")
    assert _map_header("Inkaso") == (Label.KWOTA, "other")
    assert _map_header("Składka") == (Label.KWOTA, "other")
    assert _map_header("Do wypłaty") == (Label.KWOTA, "other")
    assert _map_header("PODST NAL [PLN]") == (Label.KWOTA, "other")
    assert _map_header("STAWKA PROW [%]") == (Label.KWOTA, "other")


def test_map_header_unmapped() -> None:
    assert _map_header("Ryzyko") is None
    assert _map_header("Produkt") is None
    assert _map_header("Status") is None
    assert _map_header("") is None


# ---------------------------------------------------------------------------
# UC: Header detection with preamble
# ---------------------------------------------------------------------------


def test_uc_header_detection_with_preamble(tmp_path: Path) -> None:
    """Header detection skips preamble lines (CSV summary rows before the real header)."""
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out"

    # Write CSV with 3 preamble lines before the real header
    import csv

    csv_path = src / "test.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Szczegóły zestawienia prowizyjnego nr B/001/2025"])
        w.writerow(["Podstawa naliczenia prowizji łącznie: 5000,00 zł"])
        w.writerow([])
        w.writerow(["Nr polisy", "Klient", "PESEL", "Prowizja"])
        w.writerow(["POL-001", "Jan Testowy", _VALID_PESEL, "500"])
        w.writerow(["POL-002", "Anna Testowa", "56120303455", "300"])

    result = templatize_tables(src, out, reject_dir=Path("/tmp"))
    assert result["files_read"] == 1
    # At least one template accepted with preamble correctly skipped
    templates = _accepted_templates(out)
    assert len(templates) >= 1
    # Template must contain OSOBA#1 and PESEL#1 placeholders
    assert "{{OSOBA#1}}" in templates[0] or "{{PESEL#1}}" in templates[0]
    # Template must NOT contain the preamble text
    for t in templates:
        assert "Szczegóły zestawienia" not in t


# ---------------------------------------------------------------------------
# UC: Entity consistency – full-name + PESEL share entity id
# ---------------------------------------------------------------------------


def test_uc_fullname_pesel_share_entity(tmp_path: Path) -> None:
    """OSOBA and PESEL in the same row share the same entity id (#n)."""
    headers = ["Nr polisy", "Klient", "PESEL", "Prowizja"]
    rows = [
        ["POL-001", "Jan Testowy", _VALID_PESEL, "500"],
        ["POL-002", "Anna Testowa", "56120303455", "300"],
    ]
    col_lookup, drop_cols = _analyse_columns(headers, rows)

    text = _render_window(headers, col_lookup, drop_cols, rows, "\t")
    lines = text.strip().split("\n")
    # Row 1: client → entity #1
    assert "{{OSOBA#1}}" in lines[1]
    assert "{{PESEL#1}}" in lines[1]
    # Row 2: client → entity #2 (fresh per row, incrementing globally)
    assert "{{OSOBA#2}}" in lines[2]
    assert "{{PESEL#2}}" in lines[2]


# ---------------------------------------------------------------------------
# UC: IMIE/NAZWISKO split columns share the row's entity id
# ---------------------------------------------------------------------------


def test_uc_split_name_share_entity(tmp_path: Path) -> None:
    """IMIE and NAZWISKO columns for the same role share one entity id per row."""
    headers = ["Nr polisy", "KLIENT_IMIE", "KLIENT_NAZWISKO", "Prowizja"]
    rows = [
        ["POL-001", "Jan", "Testowy", "500"],
        ["POL-002", "Anna", "Testowa", "300"],
    ]
    col_lookup, drop_cols = _analyse_columns(headers, rows)
    text = _render_window(headers, col_lookup, drop_cols, rows, "\t")
    lines = text.strip().split("\n")

    # Both IMIE and NAZWISKO in row 1 must use entity #1
    assert "{{IMIE#1}}" in lines[1]
    assert "{{NAZWISKO#1}}" in lines[1]
    # Row 2 uses entity #2
    assert "{{IMIE#2}}" in lines[2]
    assert "{{NAZWISKO#2}}" in lines[2]


# ---------------------------------------------------------------------------
# UC: Staff entity is different from client entity in the same row
# ---------------------------------------------------------------------------


def test_uc_client_and_staff_distinct_entities(tmp_path: Path) -> None:
    """Client OSOBA and staff OSOBA in the same row use different entity ids."""
    headers = ["Nr polisy", "Klient", "Agent dystrybutor", "Prowizja"]
    rows = [
        ["POL-001", "Jan Testowy", "Ewa Agentowa", "500"],
        ["POL-002", "Anna Testowa", "Piotr Agentowy", "300"],
    ]
    col_lookup, drop_cols = _analyse_columns(headers, rows)
    text = _render_window(headers, col_lookup, drop_cols, rows, "\t")
    lines = text.strip().split("\n")

    # Row 1: client=#1, staff=#2
    assert "{{OSOBA#1}}" in lines[1]
    assert "{{OSOBA#2}}" in lines[1]
    # They must be different (two occurrences of different numbers)
    assert lines[1].count("{{OSOBA#1}}") == 1
    assert lines[1].count("{{OSOBA#2}}") == 1


# ---------------------------------------------------------------------------
# UC: Amount column → KWOTA placeholder
# ---------------------------------------------------------------------------


def test_uc_amount_column_maps_to_kwota(tmp_path: Path) -> None:
    """Money columns like 'Prowizja' and 'Składka' map to {{KWOTA}}."""
    headers = ["Nr polisy", "Klient", "Składka", "Prowizja"]
    rows = [
        ["POL-001", "Jan Testowy", "500", "50"],
        ["POL-002", "Anna Testowa", "300", "30"],
    ]
    col_lookup, drop_cols = _analyse_columns(headers, rows)
    text = _render_window(headers, col_lookup, drop_cols, rows, "\t")

    assert "{{KWOTA}}" in text
    # Original values must not appear
    assert "500" not in text
    assert "50\t" not in text


# ---------------------------------------------------------------------------
# UC: Long-id unmapped column is dropped entirely
# ---------------------------------------------------------------------------


def test_uc_long_id_column_dropped(tmp_path: Path) -> None:
    """Unmapped columns with 7+ digit values are dropped (whole column inc. header)."""
    headers = ["Nr polisy", "Klient", "Id wplaty", "Prowizja"]
    rows = [
        ["POL-001", "Jan Testowy", "12345678901", "500"],
        ["POL-002", "Anna Testowa", "98765432109", "300"],
    ]
    col_lookup, drop_cols = _analyse_columns(headers, rows)

    # "Id wplaty" column (index 2) must be dropped
    assert 2 in drop_cols
    text = _render_window(headers, col_lookup, drop_cols, rows, "\t")
    assert "Id wplaty" not in text
    assert "12345678901" not in text


# ---------------------------------------------------------------------------
# UC: Checksum-valid PESEL in unmapped column labelled PESEL
# ---------------------------------------------------------------------------


def test_uc_unmapped_pesel_detected(tmp_path: Path) -> None:
    """A checksum-valid PESEL in an unmapped column is replaced with {{PESEL}}."""
    headers = ["Nr polisy", "Prowizja", "Identyfikator"]
    rows = [
        ["POL-001", "500", _VALID_PESEL],
        ["POL-002", "300", _VALID_PESEL],
    ]
    col_lookup, drop_cols = _analyse_columns(headers, rows)
    # "Identyfikator" is unmapped; its values are valid PESELs → must trip _leaks()
    # and be detected as PESEL or dropped.
    # Either the column is dropped or cells are replaced with {{PESEL}}
    text = _render_window(headers, col_lookup, drop_cols, rows, "\t")
    if 2 not in drop_cols:
        # If not dropped, must have been replaced
        assert _VALID_PESEL not in text
        assert "{{PESEL}}" in text


# ---------------------------------------------------------------------------
# UC: Unmapped column holding bigram names → template rejected (leaked_value)
# ---------------------------------------------------------------------------


def test_uc_leaked_name_causes_rejection(tmp_path: Path) -> None:
    """Unmapped column with capitalised name pairs trips the gate."""
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out"
    reject_dir = Path("/tmp/tabular_test_rejects")

    headers = ["Nr polisy", "Prowizja", "Komentarz"]
    rows = [
        ["POL-001", "500", "Jan Kowalski"],
        ["POL-002", "300", "Anna Nowak"],
    ]
    _write_xlsx(src / "test.xlsx", headers, rows)

    templatize_tables(src, out, reject_dir=reject_dir)
    # "Jan Kowalski" etc. are bigrams → template should be rejected
    # (though drop detection might catch it first)
    templates = _accepted_templates(out)
    for t in templates:
        assert "Jan Kowalski" not in t
        assert "Anna Nowak" not in t


# ---------------------------------------------------------------------------
# UC: Deduplication by sha256
# ---------------------------------------------------------------------------


def test_uc_deduplication(tmp_path: Path) -> None:
    """Identical template content is not written twice."""
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out"

    # Write a file with just 2 rows so all 3 windows are identical
    headers = ["Nr polisy", "Klient", "PESEL", "Prowizja"]
    rows = [
        ["POL-001", "Jan Testowy", _VALID_PESEL, "500"],
        ["POL-002", "Anna Testowa", "56120303455", "300"],
    ]
    _write_xlsx(src / "test.xlsx", headers, rows)

    templatize_tables(src, out, reject_dir=Path("/tmp"))
    templates = list((out / "zestawienie_prowizyjne").glob("*.txt"))
    # Even if 3 windows are attempted, only unique ones are written
    # Filenames include sha256; no duplicates
    names = {t.name for t in templates}
    assert len(names) == len(templates)

    # Second run should deduplicate against existing files
    result2 = templatize_tables(src, out, reject_dir=Path("/tmp"))
    assert result2["accepted"] == 0 or result2["rejected"].get("duplicate", 0) > 0


# ---------------------------------------------------------------------------
# UC: reject_dir inside cwd → ValueError
# ---------------------------------------------------------------------------


def test_uc_reject_dir_inside_cwd_raises(tmp_path: Path) -> None:
    """reject_dir inside cwd raises ValueError."""
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out"

    # Monkeypatch Path.cwd to return tmp_path
    import unittest.mock as mock

    with mock.patch("piitier.datagen.tabular.Path.cwd", return_value=tmp_path):
        with pytest.raises(ValueError, match="outside the repository"):
            templatize_tables(src, out, reject_dir=tmp_path / "rejects")


# ---------------------------------------------------------------------------
# UC: detect_header_row
# ---------------------------------------------------------------------------


def test_detect_header_row_first_row() -> None:
    rows: list[list[Any]] = [
        ["Nr polisy", "Klient", "PESEL", "Prowizja"],
        ["POL-001", "Jan Testowy", "44051401359", "500"],
    ]
    assert _detect_header_row(rows) == 0


def test_detect_header_row_with_preamble() -> None:
    rows: list[list[Any]] = [
        ["Zestawienie prowizyjne nr B/001/2025"],
        [None],
        ["Nr polisy", "Klient", "PESEL", "Prowizja"],
        ["POL-001", "Jan Testowy", "44051401359", "500"],
    ]
    assert _detect_header_row(rows) == 2


def test_detect_header_row_no_pii_column() -> None:
    rows: list[list[Any]] = [
        ["Ryzyko", "Produkt", "Status", "Data"],
        ["OC", "Komunikacja", "Aktywna", "2025-01-01"],
    ]
    assert _detect_header_row(rows) is None


# ---------------------------------------------------------------------------
# UC: Every accepted template builds via build() + check() == (0, "")
# ---------------------------------------------------------------------------


def test_uc_accepted_templates_build_and_check(tmp_path: Path) -> None:
    """Every accepted template must render successfully and pass the offset check."""
    src = tmp_path / "src"
    src.mkdir()
    tmpl_out = tmp_path / "templates"
    build_out = tmp_path / "build"

    # Write an XLSX with valid data
    headers = ["Nr polisy", "Klient", "PESEL", "Agent", "Prowizja"]
    rows = [
        ["POL-001", "Jan Testowy", _VALID_PESEL, "Ewa Agentowa", "500"],
        ["POL-002", "Anna Testowa", "56120303455", "Piotr Agentowy", "300"],
        ["POL-003", "Tomasz Testowy", "80010112345", "Ewa Agentowa", "400"],
    ]
    _write_xlsx(src / "komisja.xlsx", headers, rows)

    result = templatize_tables(src, tmpl_out, reject_dir=tmp_path / "rejects")
    assert result["accepted"] > 0, f"No templates accepted: {result['rejected']}"

    build(tmpl_out, n=5, seed=42, out=build_out)
    code, msg = check(build_out)
    assert code == 0, f"check() failed: {msg}"


# ---------------------------------------------------------------------------
# UC: CSV delimiter handling
# ---------------------------------------------------------------------------


def test_uc_csv_semicolon_delimiter(tmp_path: Path) -> None:
    """CSV files with ; delimiter are read correctly."""
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out"

    _write_csv(
        src / "test.csv",
        ["Nr polisy", "Klient", "PESEL", "Prowizja"],
        [
            ["POL-001", "Jan Testowy", _VALID_PESEL, "500"],
            ["POL-002", "Anna Testowa", "56120303455", "300"],
        ],
        delim=";",
    )
    result = templatize_tables(src, out, reject_dir=Path("/tmp"))
    assert result["files_read"] == 1


# ---------------------------------------------------------------------------
# UC: Manifest is written correctly
# ---------------------------------------------------------------------------


def test_uc_manifest_written(tmp_path: Path) -> None:
    """templatize_tables appends one record to manifest.json."""
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out"

    _write_xlsx(
        src / "test.xlsx",
        ["Nr polisy", "Klient", "PESEL", "Prowizja"],
        [
            ["POL-001", "Jan Testowy", _VALID_PESEL, "500"],
            ["POL-002", "Anna Testowa", "56120303455", "300"],
        ],
    )

    templatize_tables(src, out, reject_dir=Path("/tmp"))

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert isinstance(manifest, list)
    assert len(manifest) >= 1
    rec = manifest[-1]
    assert rec["doc_type"] == "zestawienie_prowizyjne"
    assert rec["generator"] == "tabular"
    assert "files_read" in rec
    assert "accepted" in rec


# ---------------------------------------------------------------------------
# UC: Files read counter (xlsx only, no csv in this test)
# ---------------------------------------------------------------------------


def test_uc_files_read_counts_correctly(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out"

    for i in range(3):
        _write_xlsx(
            src / f"file{i}.xlsx",
            ["Nr polisy", "Klient", "PESEL", "Prowizja"],
            [
                [f"POL-{i}01", "Jan Testowy", _VALID_PESEL, "500"],
                [f"POL-{i}02", "Anna Testowa", "56120303455", "300"],
            ],
        )

    result = templatize_tables(src, out, reject_dir=Path("/tmp"))
    assert result["files_read"] == 3


# ---------------------------------------------------------------------------
# UC: Lock files (~$) are skipped
# ---------------------------------------------------------------------------


def test_uc_lock_files_skipped(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out"

    # Create a lock file – should be silently skipped
    (src / "~$komisja.xlsx").write_bytes(b"lock")
    _write_xlsx(
        src / "komisja.xlsx",
        ["Nr polisy", "Klient", "PESEL", "Prowizja"],
        [
            ["POL-001", "Jan Testowy", _VALID_PESEL, "500"],
            ["POL-002", "Anna Testowa", "56120303455", "300"],
        ],
    )

    result = templatize_tables(src, out, reject_dir=Path("/tmp"))
    # Only the non-lock file is counted
    assert result["files_read"] == 1


# ---------------------------------------------------------------------------
# UC: Empty/dash/zero cells in mapped columns stay literal
# ---------------------------------------------------------------------------


def test_uc_absent_cells_stay_literal(tmp_path: Path) -> None:
    headers = ["Nr polisy", "Klient", "PESEL", "Prowizja"]
    rows = [
        ["POL-001", "Jan Testowy", "-", "500"],
        ["POL-002", None, "56120303455", "0"],
    ]
    col_lookup, drop_cols = _analyse_columns(headers, rows)
    text = _render_window(headers, col_lookup, drop_cols, rows, "\t")
    lines = text.strip().split("\n")

    # "-" stays as "-" (PESEL col, row 1 is absent)
    assert "-" in lines[1]
    # None formats to ""
    assert lines[2].count("\t") >= 3  # still tab-separated


# ---------------------------------------------------------------------------
# UC: NIP / REGON stay anonymous (no entity)
# ---------------------------------------------------------------------------


def test_uc_nip_regon_anonymous(tmp_path: Path) -> None:
    headers = ["Nr polisy", "Klient", "NIP", "REGON", "Prowizja"]
    rows = [
        ["POL-001", "Jan Testowy", "1234563218", "123456789", "500"],
        ["POL-002", "Anna Testowa", "9876543219", "987654321", "300"],
    ]
    col_lookup, drop_cols = _analyse_columns(headers, rows)
    text = _render_window(headers, col_lookup, drop_cols, rows, "\t")

    assert "{{NIP}}" in text
    assert "{{REGON}}" in text
    # No entity suffix on NIP or REGON
    assert "{{NIP#" not in text
    assert "{{REGON#" not in text


# ---------------------------------------------------------------------------
# UC: person identifiers without a taxonomy label never reach a template
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("header", "value"),
    [
        ("Login", "jan55"),
        ("LOGIN OFWCA", "anna1"),
        ("UID agenta", "AG-1234"),
        ("ID<br>UŻYTKOWNIKA", "AG-1234"),
        ("Agent obslugujacy id", "TESJAN0001"),
        ("AGENT_ID", "AG-1234"),
        ("Nr agenta", "AG-1234"),
        ("Numer członkowski", "AG-1234"),
        ("Nr OWCA", "10/213/123"),
        ("Dłużnik - Numer", "AG-1234"),
        ("", "TEST Jan"),
        ("88.98", "LOGIN OWCA"),
    ],
)
def test_identifier_columns_dropped(header: str, value: str) -> None:
    headers = ["Nr polisy", "Klient", header, "Prowizja"]
    rows = [["POL-001", "Jan Testowy", value, "500"], ["POL-002", "Anna Testowa", value, "300"]]
    col_lookup, drop_cols = _analyse_columns(headers, rows)
    text = _render_window(headers, col_lookup, drop_cols, rows, "\t")
    assert drop_cols == {2}
    assert value not in text


@pytest.mark.parametrize(
    ("header", "label"),
    [
        ("Numer rejestracyjny", Label.NR_REJESTRACYJNY),
        ("NR_REJ", Label.NR_REJESTRACYJNY),
        ("Nr rej.", Label.NR_REJESTRACYJNY),
        ("IMIĘ", Label.IMIE),
        ("Imie", Label.IMIE),
    ],
)
def test_map_header_spelling_variants(header: str, label: Label) -> None:
    mapped = _map_header(header)
    assert mapped is not None and mapped[0] is label


def test_header_row_with_numeric_cell_is_skipped() -> None:
    rows: list[list[Any]] = [
        ["Prowizja naliczona", "88.98", "Klient"],
        ["Nr polisy", "Klient", "Prowizja"],
    ]
    assert _detect_header_row(rows) == 1


def test_window_ends_at_sparse_summary_row() -> None:
    headers = ["Nr polisy", "Klient", "Prowizja"]
    rows: list[list[Any]] = [
        ["POL-001", "Jan Testowy", "500"],
        ["POL-002", "Anna Testowa", "300"],
        [None, None, None],
        ["Podsumowanie:", None, "800"],
    ]
    col_lookup, drop_cols = _analyse_columns(headers, rows)
    text = _build_window(headers, col_lookup, drop_cols, rows, 0, "\t")
    assert text is not None
    assert text.count("\n") == 3  # header + two data rows
    assert "Podsumowanie" not in text
    assert _build_window(headers, col_lookup, drop_cols, rows, 2, "\t") is None
