"""JSON value masking preserves serialized structure and decoded offset boundaries."""

import json
import re
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

import piitier
from piitier.cli import mask_file
from piitier.coref import Coreferencer
from piitier.labels import Label
from piitier.spans import Span


class JsonNamePredictor:
    """Offline NER seam; production fusion, coreference and rendering stay real."""

    def predict(self, text: str) -> list[Span]:
        return [
            Span(match.start(), match.end(), Label.OSOBA, "model", 1.0, "valid")
            for match in re.finditer(r"Zoja Testowa|Mira Fikcyjna", text)
        ]


def test_json_cli_preserves_structure_and_masks_only_string_values(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    output = tmp_path / "output.json"
    text = (
        '{\r\n  "90051512340": ["PESEL: \\u00390051512340", '
        '{"value": 42}], "flag": true, "empty": null\r\n}\r\n'
    )
    source.write_bytes(text.encode())
    assert mask_file(source, output) == 0
    assert output.read_bytes() == (
        b'{\r\n  "90051512340": ["PESEL: [PESEL]", '
        b'{"value": 42}], "flag": true, "empty": null\r\n}\r\n'
    )
    assert source.read_bytes() == text.encode()


def test_json_numeric_pii_is_rejected_with_safe_error() -> None:
    from piitier.jsonmask import NumericPiiError, mask_json

    with pytest.raises(NumericPiiError) as error:
        mask_json('{"value": 90051512340}', detector=piitier.detect)
    assert "90051512340" not in str(error.value)
    # Skip selection does not bypass numeric safety.
    with pytest.raises(NumericPiiError):
        mask_json('{"value": 90051512340}', detector=piitier.detect, skip_fields=[".value"])
    with pytest.raises(NumericPiiError):
        mask_json('{"value": 90051512340}', detector=piitier.detect, skip_fields=["."])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (r'"PESEL: \u00390051512340"', '"PESEL: [PESEL]"'),
        (
            r'{"a":"90051512340","a":"\u0039\u0030\u0030\u0035\u0031\u0035\u0031\u0032\u0033\u0034\u0030"}',
            '{"a":"[PESEL]","a":"[PESEL]"}',
        ),
        (
            r'["\ud83e\uddea PESEL: 90051512340\nnext", "\"90051512340\""]',
            r'["\ud83e\uddea PESEL: [PESEL]\nnext", "\"[PESEL]\""]',
        ),
        (
            r'{"a\"b:c": ["900515", "12340"], "numeric": 42, "n": -0.012300e+999}',
            r'{"a\"b:c": ["900515", "12340"], "numeric": 42, "n": -0.012300e+999}',
        ),
        (' \r\n[true, false, null, {}, [], ""]\t', ' \r\n[true, false, null, {}, [], ""]\t'),
        ('\ufeff{"a":"90051512340"}\r\n', '\ufeff{"a":"[PESEL]"}\r\n'),
        ("9" * 5000, "9" * 5000),
    ],
)
def test_json_scalar_boundaries_and_serialized_fidelity(text: str, expected: str) -> None:
    from piitier.jsonmask import mask_json

    assert mask_json(text, detector=piitier.detect) == expected


@given(
    prefix=st.text(alphabet='Zażółć 🧪\\/"\n\t\b', max_size=25),
    suffix=st.text(alphabet='Zażółć 🧪\\/"\n\t\b', max_size=25),
    ascii_escapes=st.booleans(),
    escaped_identifier=st.booleans(),
)
def test_json_replacements_change_no_surrounding_serialized_characters(
    prefix: str, suffix: str, ascii_escapes: bool, escaped_identifier: bool
) -> None:
    from piitier.jsonmask import mask_json

    left = json.dumps(prefix + " PESEL: ", ensure_ascii=ascii_escapes)[1:-1]
    right = json.dumps(" " + suffix, ensure_ascii=ascii_escapes)[1:-1]
    identifier = (
        r"\u0039\u0030\u0030\u0035\u0031\u0035\u0031\u0032\u0033\u0034\u0030"
        if escaped_identifier
        else "90051512340"
    )
    text = '{\r\n  "key": "' + left + identifier + right + '"\r\n}'
    expected = '{\r\n  "key": "' + left + "[PESEL]" + right + '"\r\n}'
    result = mask_json(text, detector=piitier.detect)
    assert result == expected
    assert json.loads(result) == {"key": prefix + " PESEL: [PESEL] " + suffix}


def test_json_surrogate_pair_replacement_and_decoded_document_numbering() -> None:
    from piitier.jsonmask import detect_json, mask_json

    def find(text: str) -> list[Span]:
        return [Span(0, len(text), Label.ADRES, "model", 1.0, "valid")]

    text = r'["\ud83e\uddea", "🧪", "elsewhere", "\u0065lsewhere"]'
    coref = Coreferencer()
    spans, numbering = detect_json(text, detector=find, numbering_fn=coref.assign)
    assert [text[s.start : s.end] for s in spans] == [
        r"\ud83e\uddea",
        "🧪",
        "elsewhere",
        r"\u0065lsewhere",
    ]
    assert numbering is not None
    assert [numbering[(s.start, s.end)] for s in spans] == [1, 1, 2, 2]
    assert mask_json(text, detector=find, numbering_fn=coref.assign) == (
        '["[ADRES_1]", "[ADRES_1]", "[ADRES_2]", "[ADRES_2]"]'
    )


@pytest.mark.parametrize(
    "text",
    [
        "",
        '{"private": "90051512340",}',
        '{"private": "90051512340"} trailing',
        '{"private": "90051512340"}\n{}',
        '{"private": "\\x39"}',
        '{"private": "raw\nnewline"}',
        '{"private": 01}',
        '{"private": NaN}',
        '{"private": Infinity}',
        '{"private": -Infinity}',
        '{"private": /* comment */ null}',
        "\ufeff\ufeff{}",
        pytest.param("[" * 2000 + "]" * 1999, id="deep-unclosed-array"),
    ],
)
def test_json_rejects_invalid_documents_without_content_diagnostics(text: str) -> None:
    from piitier.jsonmask import mask_json

    with pytest.raises(ValueError) as error:
        mask_json(text, detector=piitier.detect)
    assert "90051512340" not in str(error.value)
    assert "private" not in str(error.value)


@pytest.mark.parametrize(
    "payload",
    [
        b'{"private":"90051512340",}',
        b'{"private":"90051512340\x81"}',
        b'{"private":"90051512340\x00"}',
    ],
)
def test_json_loader_rejects_bad_encoding_and_syntax_privately(
    tmp_path: Path, payload: bytes
) -> None:
    from piitier.loaders import load_with_password

    source = tmp_path / "data.JSON"
    source.write_bytes(payload)
    with pytest.raises(ValueError) as error:
        load_with_password(source)
    assert "90051512340" not in str(error.value)
    assert "private" not in str(error.value)
    assert source.read_bytes() == payload


def test_json_loader_supports_cp1250_roundtrip(tmp_path: Path) -> None:
    from piitier.loaders import load_with_password

    source = tmp_path / "data.JSON"
    payload = '{"private":"Łódź 90051512340"}'.encode("cp1250")
    source.write_bytes(payload)
    assert load_with_password(source).encode("cp1250") == payload


def test_json_loader_retains_utf8_bom_and_line_endings(tmp_path: Path) -> None:
    from piitier.loaders import load_with_password

    text = '\ufeff{\r\n  "city": "Łódź", "n": 90051512340\r\n}\r\n'
    source = tmp_path / "data.JSON"
    source.write_bytes(text.encode("utf-8"))
    assert load_with_password(source) == text


@pytest.mark.parametrize("escaped", [False, True])
@pytest.mark.parametrize("entrypoint", ["mask", "batch"])
def test_json_overlapping_rules_preserve_surrounding_structure(
    tmp_path: Path, escaped: bool, entrypoint: str
) -> None:
    from piitier.batch import mask_batch

    source_dir = tmp_path / "inputs"
    source_dir.mkdir()
    source = source_dir / "overlap.json"
    identifier = r"\u0030" * 14 if escaped else "0" * 14
    source.write_text('["' + identifier + '",true]')
    if entrypoint == "mask":
        output = tmp_path / "masked.json"
        assert mask_file(source, output) == 0
    else:
        target = tmp_path / "outputs"
        assert mask_batch(source_dir, target) == 0
        output = target / "overlap.json"
    result = output.read_text()
    assert json.loads(result)[1] is True
    # Both valid rule labels have equal taxonomy precedence; either must replace once.
    assert result in {'["[REGON]",true]', '["[NR_KARTY]",true]'}


def test_json_overlapping_spans_cover_all_detected_characters_once() -> None:
    from piitier.jsonmask import mask_json

    def find(text: str) -> list[Span]:
        return [
            Span(0, 4, Label.PESEL, "rule", 1.0, "valid"),
            Span(2, 6, Label.EMAIL, "rule", 1.0, "valid"),
        ]

    assert mask_json(r'{"v": "A\u0042CDEF tail"}', detector=find) == (
        '{"v": "[PESEL][EMAIL] tail"}'
    )
