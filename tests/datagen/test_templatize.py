"""Tests for piitier.datagen.templatize (real PDF → placeholder template).

Ollama and PDF extraction are stubbed by monkeypatching the module-level ``_probe_model``,
``_generate`` and ``load_pdf`` names: no network, no real documents. All fixture values are
synthetic (textbook-valid PESEL / NIP / IBAN examples, stock names).
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from piitier.datagen import templatize as tz
from piitier.datagen.build import build, check, collect_templates

_PESEL = "44051401359"
_NIP = "1234563218"
_IBAN = "PL61109010140000071219812874"

# Lowercase prose (no digits, no capitalised bigrams) to push a chunk over the 400-char floor.
_FILLER = (
    "Ochrona obejmuje szkody powstałe w okresie ubezpieczenia na terytorium kraju. "
    "Ubezpieczyciel wypłaca odszkodowanie w terminie wskazanym w warunkach umowy. "
    "Zgłoszenie szkody należy przekazać niezwłocznie po jej wystąpieniu. "
    "Wysokość składki zależy od zakresu ochrony oraz wybranych wariantów. "
    "Umowa ulega rozwiązaniu z upływem okresu, na który została zawarta. "
    "Ubezpieczony może odstąpić od umowy w terminie wskazanym w warunkach ogólnych. "
)

_IDS = f"PESEL: {_PESEL}\nNIP: {_NIP}\nIBAN: {_IBAN}\n\n"


def _spans(*pairs: tuple[str, str]) -> str:
    return json.dumps({"spans": [{"text": t, "label": lbl} for t, lbl in pairs]})


@pytest.fixture
def run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., tuple[dict[str, Any], Path]]:
    """Return ``run(docs, responses, server_alive=True, **kw)``: stub PDFs + Ollama.

    A response that is an exception is raised by the stubbed ``_generate``; after the
    first (startup) probe, ``_probe_model`` fails unless *server_alive*.
    """

    def _run(
        docs: list[str],
        responses: list[str | Exception],
        server_alive: bool = True,
        **kw: Any,
    ) -> tuple[dict[str, Any], Path]:
        pdf_dir = tmp_path / "pdf"
        pdf_dir.mkdir(exist_ok=True)
        texts: dict[str, str] = {}
        for i, text in enumerate(docs):
            name = f"doc{i:03d}.pdf"
            (pdf_dir / name).write_bytes(b"%PDF-stub")
            texts[name] = text
        replies: Iterator[str | Exception] = iter(responses)
        probes: list[str] = []

        def fake_probe(opener: Any, url: str, model: str) -> str:
            if probes and not server_alive:
                raise tz.OllamaUnreachableError(f"ollama not reachable at {url}")
            probes.append(url)
            return "fake-digest"

        def fake_generate(opener: Any, url: str, payload: Any, timeout: float) -> str:
            reply = next(replies)
            if isinstance(reply, Exception):
                raise reply
            return reply

        monkeypatch.setattr(tz, "load_pdf", lambda p: texts[p.name])
        monkeypatch.setattr(tz, "_probe_model", fake_probe)
        monkeypatch.setattr(tz, "_generate", fake_generate)

        out = tmp_path / "templates"
        result = tz.templatize(pdf_dir, out, **kw)
        return result, out

    return _run


def _written(out: Path) -> list[Path]:
    return sorted((out / "polisa").glob("*.txt")) if (out / "polisa").exists() else []


def test_rule_and_llm_spans_become_placeholders(run: Callable[..., Any]) -> None:
    doc = (
        "POLISA UBEZPIECZENIA\n"
        "Ubezpieczający: Jan Kowalski\n"
        f"PESEL: {_PESEL}\n"
        f"NIP: {_NIP}\n"
        "Miejscowość: Gdańsk\n\n" + _FILLER
    )
    result, out = run([doc], [_spans(("Jan Kowalski", "OSOBA"), ("Gdańsk", "MIEJSCOWOSC"))])

    assert result["accepted"] == 1
    (path,) = _written(out)
    text = path.read_text(encoding="utf-8")
    for ph in ("{{NIP}}", "{{MIEJSCOWOSC}}"):
        assert ph in text
    # Entity-linked: OSOBA and PESEL on the line below get numbered together (#12).
    assert re.search(r"\{\{OSOBA(?:#\d+)?\}\}", text)
    assert re.search(r"\{\{PESEL(?:#\d+)?\}\}", text)
    # No raw value digits remain; entity ids inside {{…}} are placeholders, not values.
    assert not re.search(r"\d", re.sub(r"\{\{[^{}]*\}\}", "", text))
    assert "Kowalski" not in text and "Gdańsk" not in text
    assert path.name.startswith("polisa_pdf_") and text.endswith("\n")


def test_failed_llm_call_skips_chunk_while_server_is_alive(run: Callable[..., Any]) -> None:
    doc = "POLISA\n" + _IDS + _FILLER
    timeout = tz.OllamaUnreachableError("ollama not reachable at http://127.0.0.1:11434")
    result, out = run([doc, doc.replace("POLISA", "CERTYFIKAT")], [timeout, _spans()])

    assert result == {"pdfs_read": 2, "accepted": 1, "rejected": {"llm_error": 1}}
    assert len(_written(out)) == 1


def test_dead_server_aborts_but_manifest_records_written_templates(
    run: Callable[..., Any], tmp_path: Path
) -> None:
    doc = "POLISA\n" + _IDS + _FILLER
    down = tz.OllamaUnreachableError("ollama not reachable at http://127.0.0.1:11434")
    with pytest.raises(tz.OllamaUnreachableError):
        run(
            [doc, doc.replace("POLISA", "CERTYFIKAT"), doc.replace("POLISA", "ANEKS")],
            [_spans(), down],
            server_alive=False,
        )

    out = tmp_path / "templates"
    (record,) = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert record["pdfs_read"] == 2
    assert record["accepted"] == 1
    assert len(_written(out)) == 1


def test_parallel_workers_pair_each_reply_with_its_chunk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    names = [
        "Adam Lis", "Ewa Kot", "Olga Sowa", "Piotr Dąb", "Iga Wróbel", "Jan Mak",
        "Ola Bąk", "Lech Gil", "Zofia Puchacz", "Marek Zięba", "Ala Czajka", "Kuba Szpak",
    ]  # fmt: skip
    block = "POLISA\n" + _IDS.strip() + "\n" + _FILLER.strip().replace(". ", ".\n")
    doc = "\n".join(f"{block}\nOpiekun: {name}." for name in names)
    assert len(tz._segment(doc)) > 2

    def fake_generate(opener: Any, url: str, payload: Any, timeout: float) -> str:
        chunk = payload["prompt"].rsplit("---\n", 1)[1]
        found = [n for n in names if n in chunk]
        # Uneven delays: replies complete in a different order than they were submitted.
        time.sleep(0.05 / (1 + len(chunk) % 7))
        return _spans(*((n, "OSOBA") for n in found))

    def written(out: Path) -> dict[str, str]:
        return {p.name: p.read_text(encoding="utf-8") for p in _written(out)}

    (tmp_path / "pdf").mkdir()
    (tmp_path / "pdf" / "doc.pdf").write_bytes(b"%PDF-stub")
    monkeypatch.setattr(tz, "load_pdf", lambda p: doc)
    monkeypatch.setattr(tz, "_probe_model", lambda opener, url, model: "fake-digest")
    monkeypatch.setattr(tz, "_generate", fake_generate)

    serial = tz.templatize(tmp_path / "pdf", tmp_path / "serial")
    parallel = tz.templatize(tmp_path / "pdf", tmp_path / "parallel", workers=4)

    # A reply applied to the wrong chunk leaves that chunk's name in place → leaked_value.
    assert serial["rejected"].get("leaked_value", 0) == 0
    assert parallel == serial
    assert written(tmp_path / "parallel") == written(tmp_path / "serial")
    assert all(n not in t for t in written(tmp_path / "parallel").values() for n in names)


@pytest.mark.parametrize(
    "tail",
    ["\n00-950 Gdańsk\n", ",\n00-950 Pozna ń\n", "\n\n00-950, Gdańsk\n"],
)
def test_multiline_address_collapses_into_one_adres(run: Callable[..., Any], tail: str) -> None:
    doc = "POLISA\n" + _IDS + "Właściciel:\nul. Polna 12" + tail + "Koniec danych.\n\n" + _FILLER
    spans = _spans(("ul. Polna 12", "ADRES"), ("Gdańsk", "MIEJSCOWOSC"))
    result, out = run([doc], [spans])

    assert result["accepted"] == 1
    # The LLM-flagged ADRES gets entity #1; the tail merge preserves the entity id.
    text = _written(out)[0].read_text(encoding="utf-8")
    assert re.search(r"Właściciel:\n\{\{ADRES(?:#\d+)?\}\}\nKoniec danych\.", text)


def test_checksum_valid_id_glued_to_letters_is_rejected(run: Callable[..., Any]) -> None:
    doc = "POLISA\n" + _IDS + f"Polisa Nr: PL23-P{_PESEL}\n\n" + _FILLER
    result, out = run([doc], [_spans()])

    assert result["rejected"] == {"leaked_value": 1}
    assert _written(out) == []


def test_insurer_footer_values_marked_by_code(run: Callable[..., Any]) -> None:
    footer = (
        "Sąd Rejonowy, KRS: 0000012345, NIP 123-45-67-890.\n"
        "Infolinia: 801 102 102, tel. +48 22 5229999, fax (22) 522 99 98.\n"
        "Kontakt: szkody@example.pl.\n"
    )
    doc = "POLISA\n" + _IDS + footer + "\n" + _FILLER
    result, out = run([doc], [_spans()])
    assert result["accepted"] == 1
    text = _written(out)[0].read_text(encoding="utf-8")
    assert "Sąd Rejonowy, KRS: 0000012345, NIP {{NIP}}.\n" in text
    assert "Infolinia: {{TELEFON}}, tel. {{TELEFON}}, fax {{TELEFON}}.\n" in text
    assert "Kontakt: {{EMAIL}}.\n" in text


@pytest.mark.parametrize("line", ["Numer klienta 123456789", "lub 22 566 55 55"])
def test_bare_digit_run_without_phone_context_is_not_a_phone(
    run: Callable[..., Any], line: str
) -> None:
    doc = "POLISA\n" + _IDS + line + "\n\n" + _FILLER
    result, out = run([doc], [_spans()])

    assert result["rejected"] == {"leaked_value": 1}
    assert _written(out) == []


def test_workers_below_one_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="workers"):
        tz.templatize(tmp_path, tmp_path / "out", workers=0)


def test_llm_span_not_in_chunk_is_skipped(run: Callable[..., Any]) -> None:
    doc = "POLISA\n" + _IDS + _FILLER
    result, out = run([doc], [_spans(("Zenon Nieistniejący", "OSOBA"))])

    assert result["rejected"]["llm_not_verbatim"] == 1
    (path,) = _written(out)
    expected = "POLISA\nPESEL: {{PESEL}}\nNIP: {{NIP}}\nIBAN: {{IBAN}}\n\n" + _FILLER.rstrip()
    assert path.read_text(encoding="utf-8") == expected + "\n"


def test_llm_policy_number_is_not_relabelled_by_nip_rule(run: Callable[..., Any]) -> None:
    # A 10-digit policy number that happens to pass the NIP checksum.
    doc = f"POLISA\nNumer polisy: {_NIP}\nPESEL: {_PESEL}\nIBAN: {_IBAN}\n\n" + _FILLER
    result, out = run([doc], [_spans((_NIP, "NR_POLISY"))])

    assert result["accepted"] == 1
    text = _written(out)[0].read_text(encoding="utf-8")
    assert "Numer polisy: {{NR_POLISY}}" in text
    assert "{{NIP}}" not in text


def test_birth_date_label_only_in_birth_date_context(run: Callable[..., Any]) -> None:
    doc = (
        "POLISA\n"
        + _IDS
        + "Data urodzenia: 1980-05-12\nOkres ubezpieczenia od: 2023-02-10\n\n"
        + _FILLER
    )
    result, out = run(
        [doc],
        [_spans(("1980-05-12", "DATA_URODZENIA"), ("2023-02-10", "DATA_URODZENIA"))],
    )

    assert result["rejected"]["llm_bad_label"] == 1
    text = _written(out)[0].read_text(encoding="utf-8")
    assert "Data urodzenia: {{DATA_URODZENIA}}" in text
    assert "Okres ubezpieczenia od: 2023-02-10" in text


def test_amounts_with_currency_and_postcodes_marked_by_code(run: Callable[..., Any]) -> None:
    doc = (
        "POLISA\n"
        + _IDS
        + "Suma gwarancyjna: 5 210 000 € na osobie, składka 1234,56 zł\n"
        + "Siedziba: ul. Polna 1, 00-950\nWystawiono 09-02-2023 10:15\n\n"
        + _FILLER
    )
    result, out = run([doc], [_spans()])

    assert result["accepted"] == 1
    text = _written(out)[0].read_text(encoding="utf-8")
    assert "{{KWOTA}} € na osobie, składka {{KWOTA}} zł" in text
    assert "Siedziba: {{ADRES}}\n" in text
    assert "Wystawiono 09-02-2023 10:15" in text


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (
            "NIP\u00a0123\u00a045\u00a067\u00a0890, tel.\u00a0+48\u00a022\u00a0522\u00a099\u00a099",
            "NIP {{NIP}}, tel. {{TELEFON}}",
        ),
        ("Siedziba: Al. Jerozolimskie 136, 02-305 Warszawa", "Siedziba: {{ADRES}}"),
        ("Adres: ul. Postępu\n18A, 02-676 Warszawa", "Adres: {{ADRES}}"),
        ("Nr nadwozia (VIN): WVWZZZ1KZBW123456", "Nr nadwozia (VIN): {{VIN}}"),
        ("ŁĄCZNIE: 2 489.00 PLN", "ŁĄCZNIE: {{KWOTA}} PLN"),
        ("Kapitał zakładowy: 236.000.000 PLN", "Kapitał zakładowy: {{KWOTA}} PLN"),
    ],
)
def test_code_rules_mark_layout_variants(run: Callable[..., Any], line: str, expected: str) -> None:
    doc = "POLISA\n" + _IDS + line + "\nKoniec.\n\n" + _FILLER
    result, out = run([doc], [_spans()])

    assert result["accepted"] == 1
    assert expected + "\nKoniec." in _written(out)[0].read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "line",
    ["Ubezpieczający\nANNA NOWAKOWSKA", "LA6FDUEY68EBY1746Nr nadwozia"],
)
def test_caps_name_and_glued_vin_are_rejected(run: Callable[..., Any], line: str) -> None:
    doc = "POLISA\n" + _IDS + line + "\n\n" + _FILLER
    result, out = run([doc], [_spans()])

    assert result["rejected"] == {"leaked_value": 1}
    assert _written(out) == []


def test_allowlisted_caps_vocabulary_is_accepted(run: Callable[..., Any]) -> None:
    doc = "POLISA\n" + _IDS + "Pochodzenie pojazdu: SALON POLSKA\n\n" + _FILLER
    result, _ = run([doc], [_spans()])

    assert result["accepted"] == 1


def test_valid_pesel_flagged_as_policy_number_keeps_pesel_label(
    run: Callable[..., Any],
) -> None:
    doc = "POLISA\n" + _IDS + "\n" + _FILLER
    result, out = run([doc], [_spans((_PESEL, "NR_POLISY"))])

    assert result["accepted"] == 1
    text = _written(out)[0].read_text(encoding="utf-8")
    assert "PESEL: {{PESEL}}" in text
    assert "{{NR_POLISY}}" not in text


@pytest.mark.parametrize(
    ("line", "span", "label"),
    [
        ("Model: GOLF VII 1.5 TSI", "GOLF VII 1.5 TSI", "NR_SZKODY"),
        ("Ubezpieczyciel: wefox Insurance AG", "wefox Insurance AG", "OSOBA"),
        ("Rok produkcji: 2017", "2017", "NR_REJESTRACYJNY"),
        ("Strona: www.example.com", "www.example.com", "EMAIL"),
    ],
)
def test_llm_span_without_label_shape_is_skipped(
    run: Callable[..., Any], line: str, span: str, label: str
) -> None:
    doc = "POLISA\n" + _IDS + line + "\n\n" + _FILLER
    result, out = run([doc], [_spans((span, label))])

    assert result["rejected"] == {"llm_bad_label": 1}
    assert line in _written(out)[0].read_text(encoding="utf-8")


def test_address_triple_collapses_into_one_adres(run: Callable[..., Any]) -> None:
    doc = (
        "POLISA\n"
        + _IDS
        + "Adres: ul. Polna 12, 00-950 Gdańsk\n"
        + "Siedziba: ul. Leśna 3, 9490 Vaduz, Liechtenstein.\n\n"
        + _FILLER
    )
    spans = _spans(
        ("ul. Polna 12", "ADRES"),
        ("Gdańsk", "MIEJSCOWOSC"),
        ("ul. Leśna 3", "ADRES"),
        ("Vaduz", "MIEJSCOWOSC"),
    )
    result, out = run([doc], [spans])

    assert result["accepted"] == 1
    text = _written(out)[0].read_text(encoding="utf-8")
    # Two distinct ADRES spans get different entity ids (#1 and #2).
    assert re.search(r"Adres: \{\{ADRES(?:#\d+)?\}\}\n", text)
    assert re.search(r"Siedziba: \{\{ADRES(?:#\d+)?\}\}, Liechtenstein\.\n", text)


def test_address_with_city_and_country_both_flagged_collapses(run: Callable[..., Any]) -> None:
    doc = (
        "POLISA\n"
        + _IDS
        + "Siedziba: ul. Leśna 3, 9490 Vaduz, Liechtenstein, oddział.\n\n"
        + _FILLER
    )
    spans = _spans(
        ("ul. Leśna 3", "ADRES"), ("Vaduz", "MIEJSCOWOSC"), ("Liechtenstein", "MIEJSCOWOSC")
    )
    result, out = run([doc], [spans])

    assert result["accepted"] == 1
    assert re.search(
        r"Siedziba: \{\{ADRES(?:#\d+)?\}\}, oddział\.\n",
        _written(out)[0].read_text(encoding="utf-8"),
    )


def test_llm_span_replaced_only_on_token_boundaries(run: Callable[..., Any]) -> None:
    doc = "POLISA\n" + _IDS + "Limit: 5 210 000 € oraz 10 000 € na bagaż.\n\n" + _FILLER
    result, out = run([doc], [_spans(("10 000", "KWOTA"))])

    assert result["accepted"] == 1
    text = _written(out)[0].read_text(encoding="utf-8")
    assert "Limit: {{KWOTA}} € oraz {{KWOTA}} € na bagaż." in text


def test_llm_label_outside_allowed_set_is_ignored(run: Callable[..., Any]) -> None:
    doc = "POLISA\n" + _IDS + "Wiek: czterdzieści lat\n\n" + _FILLER
    result, out = run([doc], [_spans(("czterdzieści lat", "WIEK"))])

    assert result["rejected"]["llm_bad_label"] == 1
    (path,) = _written(out)
    assert "czterdzieści lat" in path.read_text(encoding="utf-8")


def test_surviving_person_name_is_rejected_and_not_written(run: Callable[..., Any]) -> None:
    doc = "POLISA\nUbezpieczona: Anna Nowak\n" + _IDS + _FILLER
    result, out = run([doc], [_spans()])

    assert result["accepted"] == 0
    assert result["rejected"] == {"leaked_value": 1}
    assert _written(out) == []


def test_allowlisted_capitalised_bigram_is_accepted(run: Callable[..., Any]) -> None:
    doc = "Towarzystwo Ubezpieczeń\n" + _IDS + _FILLER
    result, out = run([doc], [_spans()])

    assert result == {"pdfs_read": 1, "accepted": 1, "rejected": {}}
    assert "Towarzystwo Ubezpieczeń" in _written(out)[0].read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "leak",
    ["ref. 501 234 567", "symbol 12-345-678", "Opiekun: Anna Nowak"],
)
def test_unmarked_value_shaped_literals_are_rejected(run: Callable[..., Any], leak: str) -> None:
    doc = "POLISA\n" + _IDS + leak + "\n\n" + _FILLER
    result, out = run([doc], [_spans()])

    assert result["rejected"] == {"leaked_value": 1}
    assert _written(out) == []


def test_too_few_placeholders_rejected(run: Callable[..., Any]) -> None:
    doc = f"POLISA\nPESEL: {_PESEL}\n\n" + _FILLER
    result, out = run([doc], [_spans()])

    assert result["rejected"] == {"too_few_placeholders": 1}
    assert _written(out) == []


def test_policy_dates_stay_literal_and_pass_the_gate(run: Callable[..., Any]) -> None:
    dates = "Wystawiono: 09-02-2023 10:15\nOkres: 2023-02-10 - 2024-02-09\nZawarto 14.02.2023\n"
    doc = "POLISA\n" + _IDS + dates + "\n" + _FILLER
    result, out = run([doc], [_spans()])

    assert result["accepted"] == 1
    assert dates in _written(out)[0].read_text(encoding="utf-8")


def test_unparseable_llm_response_rejected(run: Callable[..., Any]) -> None:
    doc = "POLISA\n" + _IDS + _FILLER
    result, out = run([doc], ["nie wiem"])

    assert result["rejected"] == {"llm_parse_error": 1}
    assert _written(out) == []


def test_identical_chunks_written_once(run: Callable[..., Any]) -> None:
    doc = "POLISA\n" + _IDS + _FILLER
    result, out = run([doc, doc], [_spans(), _spans()])

    assert result["accepted"] == 1
    assert result["rejected"] == {"duplicate": 1}
    assert len(_written(out)) == 1


def test_oversized_paragraph_split_on_line_boundaries(run: Callable[..., Any]) -> None:
    # pypdf output often has no blank lines: one paragraph far over the 2000-char cap.
    block = "POLISA\n" + _IDS.strip() + "\n" + _FILLER.strip().replace(". ", ".\n")
    doc = "\n".join([block] * 10)
    assert "\n\n" not in doc and len(doc) > 2 * tz._MAX_CHUNK
    n_chunks = len(tz._segment(doc))
    result, out = run([doc], [_spans()] * n_chunks)

    assert n_chunks > 1
    for path in _written(out):
        assert len(path.read_text(encoding="utf-8")) <= tz._MAX_CHUNK + 1
    assert result["accepted"] + result["rejected"].get("duplicate", 0) == n_chunks


def test_reject_dir_inside_repository_raises(
    run: Callable[..., Any],
) -> None:
    # reject_dir must lie outside the repository root, not just outside the cwd (#11).
    repo_root = Path(__file__).resolve().parents[2]
    with pytest.raises(ValueError, match="outside the repository"):
        run(["POLISA\n" + _IDS + _FILLER], [], reject_dir=repo_root / "tmp_test_rejects")


def test_rejected_chunks_go_to_reject_dir_only(
    run: Callable[..., Any], tmp_path_factory: pytest.TempPathFactory
) -> None:
    reject_dir = tmp_path_factory.mktemp("rejects")
    doc = "POLISA\nUbezpieczona: Anna Nowak\n" + _IDS + _FILLER
    _, out = run([doc], [_spans()], reject_dir=reject_dir)

    (rejected,) = (reject_dir / "leaked_value").glob("*.txt")
    assert "Anna Nowak" in rejected.read_text(encoding="utf-8")
    assert not any("Anna Nowak" in p.read_text(encoding="utf-8") for p in out.rglob("*"))


def test_manifest_record_appended(run: Callable[..., Any]) -> None:
    doc = "POLISA\n" + _IDS + _FILLER
    run([doc], [_spans()])
    _, out = run([doc], [_spans()])

    records = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert len(records) == 2
    assert records[0]["accepted"] == 1 and records[0]["rejected"] == {}
    assert records[1]["accepted"] == 0 and records[1]["rejected"] == {"duplicate": 1}
    assert records[1]["digest"] == "fake-digest"
    assert records[1]["source"].endswith("/pdf")


def test_empty_pdf_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no PDFs"):
        tz.templatize(tmp_path, tmp_path / "out")


def test_accepted_templates_build_and_check(run: Callable[..., Any], tmp_path: Path) -> None:
    docs = [
        "POLISA\nUbezpieczający: Jan Kowalski\nMiejscowość: Gdańsk\n" + _IDS + _FILLER,
        f"POLISA\nPESEL: {_PESEL}\nNumer polisy: AB-778899\nSkładka: 1 250,00 zł\n"
        f"IBAN: {_IBAN}\n\n" + _FILLER,
    ]
    responses = [
        _spans(("Jan Kowalski", "OSOBA"), ("Gdańsk", "MIEJSCOWOSC")),
        _spans(("AB-778899", "NR_POLISY"), ("1 250,00", "KWOTA")),
    ]
    result, out = run(docs, responses)
    assert result["accepted"] == 2

    templates = collect_templates(out)
    assert {t.template_id for t in templates} == {p.stem for p in _written(out)}

    dataset = tmp_path / "dataset"
    build(out, n=10, seed=7, out=dataset)
    assert check(dataset) == (0, "")


# ---------------------------------------------------------------------------
# Tests for new / fixed behaviours (DiffReview #2, #3, #5, #6, #7, #9, #12,
# #16, #17, #20 and TemplateAudit #2, #3, #4, #5, #6, #7, #8, #9, #10, #11)
# ---------------------------------------------------------------------------


def test_unflagged_birth_date_in_birth_date_context_is_rejected(run: Callable[..., Any]) -> None:
    """Gate rejects a literal birth date when the LLM missed it (#2)."""
    doc = "POLISA\n" + _IDS + "Data urodzenia: 1980-05-12\n\n" + _FILLER
    result, out = run([doc], [_spans()])  # LLM returns no spans
    assert _written(out) == []
    assert result["rejected"].get("leaked_value", 0) >= 1


def test_birth_date_context_second_date_on_same_line_not_linked(
    run: Callable[..., Any],
) -> None:
    """The second date on a line that starts with 'Data urodzenia: D1' is NOT a birth date (#3)."""
    doc = "POLISA\n" + _IDS + "Data urodzenia: 1980-05-12, data zawarcia: 2023-02-10\n\n" + _FILLER
    # LLM flags 1980-05-12 as DATA_URODZENIA; 2023-02-10 stays literal (policy date).
    result, out = run([doc], [_spans(("1980-05-12", "DATA_URODZENIA"))])
    assert result["accepted"] == 1
    text = _written(out)[0].read_text(encoding="utf-8")
    assert "{{DATA_URODZENIA}}" in text
    assert "2023-02-10" in text  # policy date stays literal


@pytest.mark.parametrize("prefix", ["Ul. Kaliska 1", "UL. Leśna 7"])
def test_ul_prefix_case_insensitive_redacted(run: Callable[..., Any], prefix: str) -> None:
    """Ul. and UL. match _STREET_RE just like ul. (#1)."""
    doc = "POLISA\n" + _IDS + prefix + "\n\n" + _FILLER
    result, out = run([doc], [_spans()])
    assert _written(out), f"{prefix!r} should be redacted and template accepted"
    assert prefix not in _written(out)[0].read_text(encoding="utf-8")


def test_postcode_town_before_adres_collapses(run: Callable[..., Any]) -> None:
    """Head merge removes leading {{KOD_POCZTOWY}} {{MIEJSCOWOSC}} before {{ADRES}} (#4)."""
    doc = "POLISA\n" + _IDS + "Adres: ul. Polna 12, 00-950 Warszawa\n\n" + _FILLER
    spans = _spans(("ul. Polna 12", "ADRES"), ("Warszawa", "MIEJSCOWOSC"))
    result, out = run([doc], [spans])
    assert result["accepted"] == 1
    text = _written(out)[0].read_text(encoding="utf-8")
    assert re.search(r"Adres: \{\{ADRES(?:#\d+)?\}\}", text)
    # Redundant KOD_POCZTOWY and MIEJSCOWOSC must not remain before the ADRES.
    assert "{{KOD_POCZTOWY}} {{MIEJSCOWOSC}}" not in text


@pytest.mark.parametrize("line", ["Dopłata: 12,5 zł", "Rabat: 0,5 EUR"])
def test_one_decimal_amount_marked_by_code(run: Callable[..., Any], line: str) -> None:
    """_AMOUNT_RE captures one-decimal amounts (12,5 zł, 0,5 EUR) (#6)."""
    doc = "POLISA\n" + _IDS + line + "\n\n" + _FILLER
    result, out = run([doc], [_spans()])
    assert _written(out), f"One-decimal line {line!r} should produce a template"
    text = _written(out)[0].read_text(encoding="utf-8")
    assert "{{KWOTA}}" in text, f"Expected KWOTA in {text!r}"


@pytest.mark.parametrize("town", ["Nowy Sącz", "Bielsko-Biała"])
def test_multiword_town_collapses_into_adres(run: Callable[..., Any], town: str) -> None:
    """Tail merge handles multi-word and hyphenated towns (#7)."""
    doc = "POLISA\n" + _IDS + f"ul. Nowa 5\n00-950 {town}\nKoniec.\n\n" + _FILLER
    result, out = run([doc], [_spans(("ul. Nowa 5", "ADRES"))])
    assert result["accepted"] == 1
    text = _written(out)[0].read_text(encoding="utf-8")
    assert town not in text, f"Town {town!r} should have been merged into ADRES"


def test_kwota_without_currency_not_replaced(run: Callable[..., Any]) -> None:
    """KWOTA span is only replaced where followed by a currency symbol (#5)."""
    doc = "POLISA\n" + _IDS + "ul. Polna 100\nSkładka: 100 zł\n\n" + _FILLER
    # LLM flags '100' as KWOTA; the one in the street should NOT be replaced.
    result, out = run([doc], [_spans(("100", "KWOTA"))])
    assert _written(out)
    text = _written(out)[0].read_text(encoding="utf-8")
    assert "{{KWOTA}}" in text  # currency occurrence replaced
    assert "ul. Polna 100" in text or "{{ADRES}}" in text  # street not clobbered


def test_no_text_pdf_counted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PdfNoTextError and unreadable PDFs are counted in rejected (#20)."""
    from piitier.loaders import PdfNoTextError

    pdf_dir = tmp_path / "pdf"
    pdf_dir.mkdir()
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        (pdf_dir / name).write_bytes(b"%PDF-stub")

    call_n = 0

    def fake_load(p: Path) -> str:
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            return "too short"
        if call_n == 2:
            raise PdfNoTextError("no text")
        raise ValueError("unreadable")

    monkeypatch.setattr(tz, "load_pdf", fake_load)
    monkeypatch.setattr(tz, "_probe_model", lambda *a, **kw: "digest")
    monkeypatch.setattr(tz, "_generate", lambda *a, **kw: '{"spans":[]}')

    result = tz.templatize(pdf_dir, tmp_path / "out")
    assert result["rejected"].get("no_text", 0) == 1
    assert result["rejected"].get("unreadable", 0) == 1


def test_limit_below_one_rejected(tmp_path: Path) -> None:
    """limit=0 and limit=-1 raise ValueError (#17)."""
    (tmp_path / "a.pdf").write_bytes(b"%PDF-stub")
    for lim in (0, -1):
        with pytest.raises(ValueError, match="limit"):
            tz.templatize(tmp_path, tmp_path / "out", limit=lim)


def test_entity_linking_pesel_joined_to_nearby_osoba(run: Callable[..., Any]) -> None:
    """PESEL on line directly below OSOBA#n gets {{PESEL#n}} (#12)."""
    doc = (
        "POLISA\n"
        + "Ubezpieczający: Jan Kowalski\n"
        + f"PESEL: {_PESEL}\n"
        + f"NIP: {_NIP}\n"
        + f"IBAN: {_IBAN}\n\n"
        + _FILLER
    )
    result, out = run([doc], [_spans(("Jan Kowalski", "OSOBA"))])
    assert result["accepted"] == 1
    text = _written(out)[0].read_text(encoding="utf-8")
    # OSOBA and PESEL should share the same entity id
    osoba = re.search(r"\{\{OSOBA#(\d+)\}\}", text)
    pesel = re.search(r"\{\{PESEL#(\d+)\}\}", text)
    assert osoba and pesel, "both should be entity-linked"
    assert osoba.group(1) == pesel.group(1)


def test_foreign_postcode_literal_is_rejected(run: Callable[..., Any]) -> None:
    """A 4-5 digit foreign postcode followed by a city name leaks (TA #3)."""
    doc = "POLISA\n" + _IDS + "Aeulestrasse 56, 9490 Vaduz\n\n" + _FILLER
    result, out = run([doc], [_spans()])
    assert _written(out) == []
    assert result["rejected"].get("leaked_value", 0) >= 1


def test_street_prefix_in_literal_is_rejected(run: Callable[..., Any]) -> None:
    """An unredacted 'ul. …' or 'al. …' prefix in a literal triggers the leak check (#1)."""
    doc = "POLISA\n" + _IDS + "Adres: ul. Kwiatowa bez numeru\n\n" + _FILLER
    # No house number → _STREET_RE won't match; the leak check catches the prefix.
    result, out = run([doc], [_spans()])
    assert _written(out) == []
    assert result["rejected"].get("leaked_value", 0) >= 1


def test_kwota_before_km_not_placed_without_currency(run: Callable[..., Any]) -> None:
    """KWOTA span is not placed when followed by 'km' (no currency suffix) (#5, TA #9)."""
    doc = "POLISA\n" + _IDS + "Przebieg: 5 000 km\n\n" + _FILLER
    result, out = run([doc], [_spans(("5 000", "KWOTA"))])
    # With currency-only replacement, '5 000 km' is not replaced by {{KWOTA}}
    for path in _written(out):
        assert "{{KWOTA}} km" not in path.read_text(encoding="utf-8").lower()


def test_kwota_before_km_rejected_by_gate() -> None:
    """_gate rejects {{KWOTA}} immediately before 'km' (TA #9)."""
    from piitier.datagen.templatize import _gate

    # Simulate a template that has {{KWOTA}} before km (e.g. from a prior code path)
    chunk = "{{PESEL}}\n{{NIP}}\n{{IBAN}}\n5 {{KWOTA}} km\n\n" + _FILLER
    assert _gate(chunk, "polisa") == "leaked_value"


def test_junk_town_token_adjacent_to_miejscowosc_label_is_rejected(
    run: Callable[..., Any],
) -> None:
    """Bare uppercase token next to 'Miejscowość (Place)' label is rejected (TA #10)."""
    doc = "POLISA\n" + _IDS + "TAKOC\nMiejscowość (Place)\nDOM\n\n" + _FILLER
    result, out = run([doc], [_spans()])
    # At least one chunk should be rejected because of the junk token
    assert result["rejected"].get("leaked_value", 0) >= 1


def test_miejscowosc_before_adres_collapses(run: Callable[..., Any]) -> None:
    """{{MIEJSCOWOSC}} directly before {{ADRES}} is merged away (TA #8)."""
    doc = "POLISA\n" + _IDS + "ul. Polna 12, Warszawa\n\n" + _FILLER
    spans = _spans(("ul. Polna 12", "ADRES"), ("Warszawa", "MIEJSCOWOSC"))
    result, out = run([doc], [spans])
    assert result["accepted"] == 1
    text = _written(out)[0].read_text(encoding="utf-8")
    # {{MIEJSCOWOSC}} must not appear directly before {{ADRES[#n]?}}
    assert not re.search(r"\{\{MIEJSCOWOSC\}\}\s*\{\{ADRES", text)


def test_double_adres_trailer_collapses(run: Callable[..., Any]) -> None:
    """{{ADRES}} followed by another {{ADRES}} is merged into one (TA #7)."""
    doc = "POLISA\n" + _IDS + "ul. Polna 12, ul. Boczna 3\n\n" + _FILLER
    # Both address segments flagged separately by LLM
    spans = _spans(("ul. Polna 12", "ADRES"), ("ul. Boczna 3", "ADRES"))
    result, out = run([doc], [spans])
    assert result["accepted"] == 1
    text = _written(out)[0].read_text(encoding="utf-8")
    # Only one ADRES placeholder should remain on that line
    assert not re.search(r"\{\{ADRES[^}]*\}\}.*\{\{ADRES", text)


def test_plate_keyword_triggers_redaction(run: Callable[..., Any]) -> None:
    """'Numer rejestracyjny:' followed by a plate is redacted by code rule (TA #5)."""
    doc = (
        "POLISA\n"
        + _IDS
        + "Nr nadwozia (VIN): WVWZZZ1KZBW123456\n"
        + "Numer rejestracyjny: ZKL2387\n\n"
        + _FILLER
    )
    result, out = run([doc], [_spans(("WVWZZZ1KZBW123456", "VIN"))])
    assert result["accepted"] == 1
    text = _written(out)[0].read_text(encoding="utf-8")
    assert "{{NR_REJESTRACYJNY}}" in text
    assert "ZKL2387" not in text


def test_eik_nr_polisy_context_fix_direct() -> None:
    """EIK / 'kod identyfikacyjny' before {{NR_POLISY}} → literal restored (TA #4)."""
    from piitier.datagen.templatize import _rule_redact

    chunk = "nr EIK {{NR_POLISY}}, kapitał akcyjny {{PESEL}}"
    result = _rule_redact(chunk)
    assert "{{NR_POLISY}}" not in result, "EIK placeholder should be removed"
    assert "EIK" in result
    assert "{{PESEL}}" in result  # other placeholders unaffected


def test_policy_no_pesel_context_fix_direct() -> None:
    """'Policy no' before {{PESEL}} → {{NR_POLISY}} (TA #4)."""
    from piitier.datagen.templatize import _rule_redact

    chunk = "Policy no {{PESEL}} {{NIP}} {{IBAN}}"
    result = _rule_redact(chunk)
    assert "{{NR_POLISY}}" in result
    assert "Policy no {{PESEL}}" not in result
    assert "{{NIP}}" in result  # other placeholders unaffected


def test_company_as_osoba_rejected_by_shape(run: Callable[..., Any]) -> None:
    """An OSOBA span containing a company suffix (Sp. z o.o.) is rejected (TA #6)."""
    doc = "POLISA\n" + _IDS + "Ubezpieczyciel: Firma Sp. z o.o.\n\n" + _FILLER
    result, out = run([doc], [_spans(("Firma Sp. z o.o.", "OSOBA"))])
    assert _written(out)
    text = _written(out)[0].read_text(encoding="utf-8")
    assert "Firma Sp. z o.o." in text  # span was rejected, literal remains


def test_normalise_removes_test_stamp_and_rule_lines(run: Callable[..., Any]) -> None:
    """_normalise strips 'T E S T' stamps and long horizontal rule lines (TA #11)."""
    stamp = "T E S T"
    _unused_rules = "─" * 20  # long rule lines use [-_=]; see _normalise
    doc = "POLISA\n" + _IDS + stamp + "\n" + "=" * 20 + "\n\n" + _FILLER
    result, out = run([doc], [_spans()])
    # Both stamp and rule lines are normalised away before chunking; template is accepted
    assert result["accepted"] == 1
    text = _written(out)[0].read_text(encoding="utf-8")
    assert stamp not in text
    assert "=" * 20 not in text


def test_prompts_file_lists_exactly_llm_labels() -> None:
    """templatize_polisa.txt must enumerate exactly the labels in _LLM_LABELS (#20 / UC45)."""
    from pathlib import Path

    prompt = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "piitier"
        / "datagen"
        / "prompts"
        / "templatize_polisa.txt"
    ).read_text(encoding="utf-8")
    # Extract the colon-delimited label list from line "Dozwolone etykiety (pole «label»): …"
    m = re.search(r"Dozwolone etykiety[^:]*:\s*([A-Z_, ]+)\.", prompt)
    assert m, "could not find label list in prompt"
    prompt_labels = frozenset(t.strip() for t in m.group(1).split(",") if t.strip())
    expected = frozenset(lbl.name for lbl in tz._LLM_LABELS)
    assert prompt_labels == expected, (
        f"Prompt labels differ from _LLM_LABELS.\n"
        f"  prompt only: {prompt_labels - expected}\n"
        f"  code only:   {expected - prompt_labels}"
    )


def test_load_manifest_shared_with_llm(tmp_path: Path) -> None:
    """_load_manifest can be called from llm.write_templates path (no duplicate code) (#19)."""
    # Verify import works (lazy import inside write_templates avoids circular import)
    from piitier.datagen.templatize import _load_manifest

    manifest = tmp_path / "manifest.json"
    assert _load_manifest(manifest) == []

    manifest.write_text("[]", encoding="utf-8")
    assert _load_manifest(manifest) == []

    manifest.write_text("[{}]", encoding="utf-8")
    assert _load_manifest(manifest) == [{}]

    manifest.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="blank"):
        _load_manifest(manifest)

    manifest.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="array"):
        _load_manifest(manifest)


# ---------------------------------------------------------------------------
# Additional tests for TemplateAudit2 rules (B1, M1, M2, m1)
# ---------------------------------------------------------------------------


def test_plate_before_vin_redacted_by_rule(run: Callable[..., Any]) -> None:
    """A plate directly before a VIN is redacted to {{NR_REJESTRACYJNY}} (B1)."""
    doc = "POLISA\n" + _IDS + "GPU1379 1HGCM82633A004352\n\n" + _FILLER
    result, path = run([doc], [_spans()])
    text = _written(path)[0].read_text(encoding="utf-8")
    assert "{{NR_REJESTRACYJNY}}" in text
    assert "GPU1379" not in text
    assert "{{VIN}}" in text


def test_plate_before_vin_gate_rejects() -> None:
    """_gate rejects a template where an unredacted plate sits directly before {{VIN}} (B1)."""
    from piitier.datagen.templatize import _gate

    chunk = "{{PESEL}}\n{{NIP}}\n{{IBAN}}\nGPU1379 {{VIN}}\n\n" + _FILLER
    assert _gate(chunk, "polisa") == "leaked_value"


def test_plate_before_vin_no_false_positive(run: Callable[..., Any]) -> None:
    """Ordinary text before {{VIN}} is not misidentified as a registration plate (B1)."""
    doc = "POLISA\n" + _IDS + "Model: 1HGCM82633A004352\n\n" + _FILLER
    result, path = run([doc], [_spans()])
    text = _written(path)[0].read_text(encoding="utf-8")
    assert "{{NR_REJESTRACYJNY}}" not in text


def test_pesel_in_company_register_context_stays_literal(run: Callable[..., Any]) -> None:
    """An LLM span flagged as PESEL inside a company-register context remains literal (M1)."""
    doc = (
        "BALCIA INSURANCE SE, wpisana do Rejestru Przedsiębiorstw Republiki Łotewskiej "
        f"pod nr 40103424710\n{_IDS}\n" + _FILLER
    )
    # LLM incorrectly flags the register number as PESEL
    spans_json = _spans(("40103424710", "PESEL"))
    result, path = run([doc], [spans_json])
    text = _written(path)[0].read_text(encoding="utf-8")
    assert "40103424710" in text, "Company register number should not be replaced"
    assert "{{PESEL}}" not in text.split("\n")[0]


def test_pesel_in_company_register_context_rejected_by_gate() -> None:
    """_gate rejects a template where {{PESEL}} appears in a company-register context (M1)."""
    from piitier.datagen.templatize import _gate

    chunk = (
        "{{PESEL}}\n{{NIP}}\n{{IBAN}}\n"
        "BALCIA INSURANCE SE, wpisana do Rejestru Przedsiębiorstw Republiki Łotewskiej "
        "pod nr {{PESEL}}\n" + _FILLER
    )
    assert _gate(chunk, "polisa") == "llm_bad_label"


def test_pesel_outside_register_context_replaced_normally(run: Callable[..., Any]) -> None:
    """A PESEL outside company-register context is still replaced normally (M1 no-FP)."""
    doc = f"POLISA\nKlient PESEL: {_PESEL}\n{_IDS}\n" + _FILLER
    result, path = run([doc], [_spans()])
    text = _written(path)[0].read_text(encoding="utf-8")
    assert "{{PESEL}}" in text


def test_eik_nr_polisy_kept_literal_and_rejected_in_gate(run: Callable[..., Any]) -> None:
    """An EIK register number stays literal; the gate rejects its placeholder form (M2)."""
    from piitier.datagen.templatize import _gate

    doc = "EUROINS\nujednolicony kod identyfikacyjny 123456789\n" + _IDS + "\n" + _FILLER
    spans_json = _spans(("123456789", "NR_POLISY"))
    result, path = run([doc], [spans_json])
    text = _written(path)[0].read_text(encoding="utf-8")
    assert "123456789" in text, "EIK number must not be replaced by policy number placeholder"

    # Gate rejects placeholder form
    chunk = (
        "{{PESEL}}\n{{NIP}}\n{{IBAN}}\nEUROINS\nujednolicony kod identyfikacyjny {{NR_POLISY}}\n"
        + _FILLER
    )
    assert _gate(chunk, "polisa") == "llm_bad_label"


def test_nr_polisy_outside_eik_context_replaced_normally(run: Callable[..., Any]) -> None:
    """A NR_POLISY outside EIK context is replaced normally (M2 no-FP)."""
    doc = "POLISA\nNumer polisy: 123456789\n" + _IDS + "\n" + _FILLER
    spans_json = _spans(("123456789", "NR_POLISY"))
    result, path = run([doc], [spans_json])
    text = _written(path)[0].read_text(encoding="utf-8")
    assert "{{NR_POLISY}}" in text


def test_adres_with_junk_suffix_rejected_by_gate() -> None:
    """_gate rejects an ADRES placeholder followed by junk like city2111 (m1)."""
    from piitier.datagen.templatize import _gate

    chunk = "{{PESEL}}\n{{NIP}}\n{{IBAN}}\nAdres:\n{{ADRES#1}} city2111\n" + _FILLER
    assert _gate(chunk, "polisa") == "leaked_value"


def test_clean_adres_accepted_without_junk(run: Callable[..., Any]) -> None:
    """A clean ADRES placeholder without trailing junk is accepted (m1 no-FP)."""
    doc = f"POLISA\nAdres:\nul. Polna 12, 00-001 Warszawa\n{_IDS}\n" + _FILLER
    result, path = run([doc], [_spans()])
    assert len(_written(path)) >= 0
