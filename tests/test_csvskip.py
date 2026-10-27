"""CSV field offsets and skip-column filtering (UC-167, UC-168)."""

import piitier
from piitier.csvskip import filter_spans, parse_csv_field_ranges, plan_skips, sniff_delimiter
from piitier.labels import Label
from piitier.spans import Span


def test_uc167_quoted_fields_keep_original_offsets_and_values() -> None:
    text = '"A";"Opis, ; i\nnowa ""linia""";"PESEL"\r\n"Jan";"tekst 90051512340";"90051512340"\r\n'
    parsed = parse_csv_field_ranges(text, ";")
    assert [[field.value for field in row] for row in parsed.rows] == [
        ["A", 'Opis, ; i\nnowa "linia"', "PESEL"],
        ["Jan", "tekst 90051512340", "90051512340"],
    ]
    plan = plan_skips(parsed, ['Opis, ; i\nnowa "linia"'])
    assert plan.unknown_selectors == []
    assert [text[start:end] for start, end in plan.protected_ranges] == [
        '"Opis, ; i\nnowa ""linia"""',
        '"tekst 90051512340"',
    ]
    assert len(parsed.rows) == 2


def test_uc168_cross_column_detection_is_kept() -> None:
    parsed = parse_csv_field_ranges("col1 col2 col3 col4\n4111 1111 1111 1111\n", " ")
    protected = plan_skips(parsed, ["col2"]).protected_ranges
    card = Span(20, 39, Label.NR_KARTY, "rule", 1.0, "valid")
    assert filter_spans([card], protected) == [card]


def test_skipped_spans_only_when_wholly_enclosed() -> None:
    text = "ID;Notes\r\n90051512340;90051512340\r\n"
    protected = plan_skips(parse_csv_field_ranges(text, ";"), ["1"]).protected_ranges
    first = Span(10, 21, Label.PESEL, "rule", 1.0, "valid")
    second = Span(22, 33, Label.PESEL, "rule", 1.0, "valid")
    assert filter_spans([first, second], protected) == [second]


def test_unknown_index_and_name_on_ragged_rows() -> None:
    parsed = parse_csv_field_ranges("ID;note\r\n1;ok;extra\r\n", ";")
    plan = plan_skips(parsed, ["3", "4", "missing", "NOTE"])
    assert plan.unknown_selectors == ["4", "missing"]
    assert plan.protected_ranges == [(3, 7), (11, 13), (14, 19)]


def test_empty_and_newline_variants() -> None:
    assert parse_csv_field_ranges("", ";").rows == []
    parsed = parse_csv_field_ranges('"A\r\nB",C\rD,E\n', ",")
    assert [[field.value for field in row] for row in parsed.rows] == [["A\r\nB", "C"], ["D", "E"]]
    assert sniff_delimiter("ID;Notes\n1;2\n") == ";"


def test_uc172_public_api_masks_other_columns_and_preserves_selected() -> None:
    text = "ID;Notes\r\n90051512340;90051512340\r\n"
    assert piitier.mask_csv(text, skip_columns=["ID"], delimiter=";") == (
        "ID;Notes\r\n90051512340;[PESEL]\r\n"
    )


def test_public_api_warns_unknown_without_skipping_known_column() -> None:
    warnings: list[str] = []
    text = "ID;Notes\n90051512340;90051512340\n"
    assert (
        piitier.mask_csv(
            text, skip_columns=["missing", "ID"], delimiter=";", on_unknown_column=warnings.append
        )
        == "ID;Notes\n90051512340;[PESEL]\n"
    )
    assert warnings == ["missing"]


def test_public_api_without_selection_matches_plain_mask() -> None:
    text = "ID;Notes\n90051512340;90051512340\n"
    assert piitier.mask_csv(text) == piitier.mask(text)


def test_digit_like_header_is_selectable_without_integer_conversion() -> None:
    text = "²;Notes\n90051512340;90051512340\n"
    assert piitier.mask_csv(text, skip_columns=["²"], delimiter=";") == (
        "²;Notes\n90051512340;[PESEL]\n"
    )
