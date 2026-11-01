"""Issue #21 acceptance at the public API and subprocess CLI boundaries."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import piitier


def run_mask(source: Path, output: Path, *flags: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "piitier.cli", "mask", str(source), "-o", str(output), *flags],
        capture_output=True,
    )


def test_uc174_issue21_cli_preserves_selected_raw_json(tmp_path: Path) -> None:
    source = tmp_path / "in.json"
    output = tmp_path / "out.json"
    original = (
        b'\xef\xbb\xbf{\r\n "klient": {"pesel":"\\u00390051512340", '
        b'"notatka":"90051512340"}\r\n}\r\n'
    )
    source.write_bytes(original)
    result = run_mask(source, output, "--skip-fields", ".klient.pesel")
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == b""
    assert output.read_bytes() == original.replace(
        b'"notatka":"90051512340"', b'"notatka":"[PESEL]"'
    )
    assert source.read_bytes() == original
    assert json.loads(output.read_bytes())["klient"]["pesel"] == "90051512340"


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        (
            ".osoby[].email",
            '{"osoby":[{"email":"a@example.test","id":"[PESEL]"},{"email":"b@example.test"}]}',
        ),
        (
            ".osoby[0].email",
            '{"osoby":[{"email":"a@example.test","id":"[PESEL]"},{"email":"[EMAIL]"}]}',
        ),
    ],
)
def test_uc175_issue21_public_api_wildcard_and_index(selector: str, expected: str) -> None:
    text = '{"osoby":[{"email":"a@example.test","id":"90051512340"},{"email":"b@example.test"}]}'
    import re

    from piitier.labels import Label
    from piitier.spans import Span

    def detector(value: str) -> list[Span]:
        return piitier.detect(value) + [
            Span(match.start(), match.end(), Label.EMAIL, "model", 1.0, "valid")
            for match in re.finditer(r"[ab]@example\.test", value)
        ]

    assert piitier.mask_json(text, skip_fields=[selector], detector=detector) == expected


def test_uc175_issue21_quoted_comma_key_is_one_selector(tmp_path: Path) -> None:
    source, output = tmp_path / "in.json", tmp_path / "out.json"
    text = '{"dane osobowe":{"a,b":"90051512340","a":"90051512340"},"v":"90051512340"}'
    source.write_text(text)
    result = run_mask(
        source, output, "--skip-fields", '."dane osobowe"."a,b"', "--skip-fields", ".v"
    )
    assert result.returncode == 0, result.stderr
    assert output.read_text() == text.replace('"a":"90051512340"', '"a":"[PESEL]"')
    assert result.stderr == b""


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp1250"])
def test_uc174_issue21_cli_retains_source_encoding(tmp_path: Path, encoding: str) -> None:
    source, output = tmp_path / "in.json", tmp_path / "out.json"
    text = '{\r\n "city":"Łódź", "v":"90051512340"\r\n}\r\n'
    original = text.encode(encoding)
    source.write_bytes(original)
    result = run_mask(source, output)
    assert result.returncode == 0, result.stderr
    assert output.read_bytes() == text.replace("90051512340", "[PESEL]").encode(encoding)
    assert source.read_bytes() == original


@pytest.mark.parametrize("skip", [[], [".v"], ["."]])
def test_uc179_issue21_numeric_pii_is_never_skippable(skip: list[str]) -> None:
    with pytest.raises(ValueError) as error:
        piitier.mask_json('{"v":90051512340}', skip_fields=skip)
    assert "90051512340" not in str(error.value)


@pytest.mark.parametrize("existing", [False, True])
def test_uc179_issue21_cli_numeric_failure_preserves_output(tmp_path: Path, existing: bool) -> None:
    source, output = tmp_path / "in.json", tmp_path / "out.json"
    source.write_text('{"v":90051512340}')
    if existing:
        output.write_bytes(b"preserve existing bytes\r\n")
    result = run_mask(source, output, "--skip-fields", ".v")
    assert result.returncode == 2
    assert result.stdout == b""
    assert b"90051512340" not in result.stderr and b"Traceback" not in result.stderr
    assert (
        output.read_bytes() == b"preserve existing bytes\r\n" if existing else not output.exists()
    )


@pytest.mark.parametrize("selector", [".v | .x", ".[] | select(.)", ".v,.x", ".v[1:2]", ".v[-1]"])
def test_uc180_issue21_cli_rejects_unsupported_paths(tmp_path: Path, selector: str) -> None:
    source, output = tmp_path / "in.json", tmp_path / "out.json"
    source.write_text('{"v":"90051512340"}')
    result = run_mask(source, output, "--skip-fields", selector)
    assert result.returncode == 2
    assert result.stdout == b"" and not output.exists()
    assert b"90051512340" not in result.stderr and b"Traceback" not in result.stderr


def test_uc180_issue21_unmatched_path_warns_and_continues(tmp_path: Path) -> None:
    source, output = tmp_path / "in.json", tmp_path / "out.json"
    source.write_text('{"v":"90051512340"}')
    result = run_mask(source, output, "--skip-fields", ".missing")
    assert result.returncode == 0
    assert output.read_text() == '{"v":"[PESEL]"}'
    assert b"warning" in result.stderr.lower() and b"90051512340" not in result.stderr


@pytest.mark.parametrize(
    "suffix,payload", [(".json", b'{"private":"90051512340",}'), (".txt", b"90051512340")]
)
def test_uc181_issue21_invalid_input_is_safe(tmp_path: Path, suffix: str, payload: bytes) -> None:
    source, output = tmp_path / ("in" + suffix), tmp_path / "out.json"
    source.write_bytes(payload)
    result = run_mask(source, output, "--skip-fields", ".v")
    assert result.returncode == 2
    assert result.stdout == b"" and not output.exists()
    assert b"90051512340" not in result.stderr and b"private" not in result.stderr
    assert b"Traceback" not in result.stderr


def test_uc175_issue21_model_numbering_resets_and_skips_raw_alias() -> None:
    from test_jsonmask import JsonNamePredictor

    anonymizer = piitier.Anonymizer(predictor=JsonNamePredictor())
    text = '{"keep":"\\u005aoja Testowa","values":["Mira Fikcyjna","Zoja Testowa","Mira Fikcyjna"]}'
    expected = '{"keep":"\\u005aoja Testowa","values":["[OSOBA_1]","[OSOBA_2]","[OSOBA_1]"]}'
    assert anonymizer.mask_json(text, skip_fields=[".keep"]) == expected
    assert anonymizer.mask_json('["Zoja Testowa"]') == '["[OSOBA_1]"]'


def test_uc180_issue21_public_api_warns_for_unmatched_selector() -> None:
    with pytest.warns(UserWarning) as warnings:
        result = piitier.mask_json('{"v":"90051512340"}', skip_fields=[".missing"])
    assert result == '{"v":"[PESEL]"}'
    assert all("90051512340" not in str(item.message) for item in warnings)


def test_uc179_issue21_batch_numeric_pii_isolated(tmp_path: Path) -> None:
    source = tmp_path / "inputs"
    source.mkdir()
    (source / "bad.json").write_text('{"v":90051512340}')
    (source / "good.json").write_text('{"v":"90051512340","n":42}')
    output = tmp_path / "outputs"
    result = subprocess.run(
        [sys.executable, "-m", "piitier.cli", "mask-batch", str(source), "-o", str(output)],
        capture_output=True,
    )
    assert result.returncode == 4 and result.stdout == b""
    assert not (output / "bad.json").exists()
    assert (output / "good.json").read_text() == '{"v":"[PESEL]","n":42}'
    assert result.stderr.endswith(b"batch: 1 masked, 1 failed\n")
    assert b"90051512340" not in result.stderr and b"Traceback" not in result.stderr


@pytest.mark.parametrize("selector", ['.v"x"', ".v[0]x", "..v", '."bad\\q"'])
def test_uc180_issue21_malformed_paths_are_typed_errors(selector: str) -> None:
    from piitier.jsonmask import JsonSelectorError

    with pytest.raises(JsonSelectorError):
        piitier.mask_json('{"v":["90051512340"]}', skip_fields=[selector])


def test_uc175_issue21_canonical_paths_select_nested_values() -> None:
    from piitier.jsonmask import json_selectors, parse_json_values

    text = '{"osoby":[{"email":"90051512340"}],"dane osobowe":{"a,b":"90051512340"}}'
    selectors = json_selectors(parse_json_values(text))
    assert ".osoby[].email" in selectors
    assert '."dane osobowe"."a,b"' in selectors
    assert piitier.mask_json(text, skip_fields=[".osoby[].email"]) == (
        '{"osoby":[{"email":"90051512340"}],"dane osobowe":{"a,b":"[PESEL]"}}'
    )


def test_uc176_issue21_container_ranges_exclude_keys() -> None:
    from piitier.jsonmask import parse_json_values, plan_json_skips

    text = '{"group":{"key":"90051512340","flag":true},"other":"90051512340"}'
    plan = plan_json_skips(parse_json_values(text), [".group"])
    assert [text[start:end] for start, end in plan.protected_ranges] == ['"90051512340"', "true"]


@pytest.mark.parametrize(
    "text,selectors,expected",
    [
        (
            '{"a":"90051512340","a":"\\u00390051512340","b":"90051512340"}',
            [".a"],
            '{"a":"90051512340","a":"\\u00390051512340","b":"[PESEL]"}',
        ),
        ('"\\u00390051512340"', ["."], '"\\u00390051512340"'),
        ('["90051512340","90051512340"]', [".[0]"], '["90051512340","[PESEL]"]'),
        ('["90051512340","90051512340"]', [".[]"], '["90051512340","90051512340"]'),
    ],
)
def test_uc175_issue21_duplicate_and_root_paths(
    text: str, selectors: list[str], expected: str
) -> None:
    assert piitier.mask_json(text, skip_fields=selectors) == expected


def test_uc179_issue21_skipped_container_cannot_hide_numeric_pii() -> None:
    with pytest.raises(ValueError):
        piitier.mask_json('{"group":[{"v":90051512340}]}', skip_fields=[".group"])


def test_uc180_issue21_unknown_and_matched_paths_apply_together() -> None:
    notifications = []
    result = piitier.mask_json(
        '{"keep":"90051512340","mask":"90051512340"}',
        skip_fields=[".missing", ".keep"],
        on_unknown_field=notifications.append,
    )
    assert result == '{"keep":"90051512340","mask":"[PESEL]"}'
    assert notifications == [".missing"]


def test_uc174_issue21_batch_preserves_cp1250(tmp_path: Path) -> None:
    from piitier.batch import mask_batch

    source, output = tmp_path / "input", tmp_path / "output"
    source.mkdir()
    original = '{\r\n"city":"Łódź","id":"90051512340"\r\n}\r\n'.encode("cp1250")
    (source / "in.json").write_bytes(original)
    assert mask_batch(source, output) == 0
    assert (output / "in.json").read_bytes() == (
        '{\r\n"city":"Łódź","id":"[PESEL]"\r\n}\r\n'.encode("cp1250")
    )
    assert (source / "in.json").read_bytes() == original
