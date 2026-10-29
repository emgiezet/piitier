"""Batch outputs, failure isolation and non-destructive filesystem boundaries."""

import secrets
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_loaders_pdf import password_pdf

import piitier
from piitier.batch import mask_batch
from piitier.labels import Label
from piitier.spans import Span


def pdf_at(root: Path, name: str, secret: str, *, image: bool = False) -> None:
    password_pdf(root, secret, image=image).rename(root / name)


def test_uc181_mixed_exact_outputs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source, target = tmp_path / "in", tmp_path / "out"
    source.mkdir()
    secret = secrets.token_hex(12)
    pdf_at(source, "a.PDF", secret)
    (source / "b.csv").write_bytes(b"ID\r\n90051512340\r\n")
    (source / "c.md").write_text("# PESEL: 90051512340")
    (source / "ignored.bin").write_bytes(b"ignored")
    (source / "subdir").mkdir()
    mapping = source / "map.csv"
    mapping.write_text(f"filename,password\na.PDF,{secret}\n")
    (source / "alias.csv").symlink_to(mapping)
    assert mask_batch(source, target, mapping) == 0
    assert {p.name: p.read_bytes() for p in target.iterdir()} == {
        "a.txt": b"  PESEL: [PESEL]  \n\nEnd.",
        "b.csv": b"ID\r\n[PESEL]\r\n",
        "c.md": b"# PESEL: [PESEL]",
    }
    assert capsys.readouterr() == ("", "batch: 3 masked, 0 failed\n")


def test_uc181_model_reuse_and_local_numbering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "in"
    source.mkdir()
    (source / "a.txt").write_text("Anna 90051512340")
    (source / "b.txt").write_text("Ewa 90051512340")
    real = piitier.Anonymizer
    constructions = []

    class Predictor:
        def predict(self, text):
            return [Span(0, text.index(" "), Label.OSOBA, "model", 1.0, "valid")]

    def construct(**kwargs):
        constructions.append(kwargs)
        return real(predictor=Predictor())

    monkeypatch.setattr(piitier, "Anonymizer", construct)
    target = tmp_path / "out"
    assert mask_batch(source, target, model="local", revision="rev", threshold=0.2) == 0
    assert (target / "a.txt").read_text() == "[OSOBA_1] [PESEL]"
    assert (target / "b.txt").read_text() == "[OSOBA_1] [PESEL]"
    assert constructions == [{"model": "local", "revision": "rev", "threshold": 0.2}]


def test_uc182_all_failed_input_kinds_continue(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source, target = tmp_path / "in", tmp_path / "out"
    source.mkdir()
    secret = secrets.token_hex(12)
    pdf_at(source, "a-missing.pdf", secret)
    pdf_at(source, "b-wrong.pdf", secret)
    pdf_at(source, "c-scan.pdf", secret, image=True)
    (source / "d-corrupt.pdf").write_bytes(b"PRIVATE-PARSER-90051512340")
    (source / "e.txt").write_text("PESEL: 90051512340")
    mapping = source / "map.csv"
    mapping.write_text(f"filename,password\nb-wrong.pdf,wrong\nc-scan.pdf,{secret}\n")
    assert mask_batch(source, target, mapping) == 4
    assert {p.name: p.read_text() for p in target.iterdir()} == {"e.txt": "PESEL: [PESEL]"}
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.endswith("batch: 1 masked, 4 failed\n")
    assert secret not in captured.err and "90051512340" not in captured.err


@pytest.mark.parametrize("outcome", ["rescue", "eof", "interrupt"])
def test_uc183_prompt_outcomes(tmp_path: Path, outcome: str) -> None:
    source, target = tmp_path / "in", tmp_path / "out"
    source.mkdir()
    (source / "a.txt").write_text("PESEL: 90051512340")
    secret = secrets.token_hex(12)
    pdf_at(source, "b.pdf", secret)
    (source / "c.txt").write_text("PESEL: 90051512340")

    def prompt(path, attempt, incorrect):
        if outcome == "interrupt":
            raise KeyboardInterrupt
        if outcome == "eof":
            return None
        return "wrong" if attempt == 1 else secret

    assert (
        mask_batch(source, target, prompt=prompt)
        == {"rescue": 0, "eof": 4, "interrupt": 130}[outcome]
    )
    assert (target / "a.txt").read_text() == "PESEL: [PESEL]"
    assert (target / "c.txt").exists() == (outcome != "interrupt")
    if outcome == "rescue":
        assert (target / "b.txt").read_text() == "  PESEL: [PESEL]  \n\nEnd."
    else:
        assert not (target / "b.txt").exists()


def test_uc184_collisions_and_symlinks(tmp_path: Path) -> None:
    source, target = tmp_path / "in", tmp_path / "out"
    source.mkdir()
    target.mkdir()
    pdf_at(source, "same.pdf", "")
    (source / "same.txt").write_text("later")
    (source / "existing.txt").write_text("source")
    (source / "dangling.txt").write_text("source")
    preserved = tmp_path / "preserved"
    preserved.write_text("keep")
    (target / "existing.txt").symlink_to(preserved)
    (target / "dangling.txt").symlink_to(tmp_path / "absent")
    assert mask_batch(source, target) == 4
    assert (target / "same.txt").read_text() == "  PESEL: [PESEL]  \n\nEnd."
    assert preserved.read_text() == "keep"
    assert (target / "dangling.txt").is_symlink() and not (tmp_path / "absent").exists()
    assert (source / "same.txt").read_text() == "later"


@pytest.mark.parametrize(
    "case", ["input", "output", "nested", "alias", "map", "threshold", "model", "empty"]
)
def test_uc180_uc185_configuration_is_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    source, target = tmp_path / "in", tmp_path / "out"
    source.mkdir()
    if case != "empty":
        (source / "a.txt").write_text("PESEL: 90051512340")
    kwargs = {}
    if case == "input":
        source = tmp_path / "missing"
    if case == "output":
        target.write_text("keep")
    if case == "nested":
        target = source / "nested"
    if case == "alias":
        target.symlink_to(source, target_is_directory=True)
    if case == "map":
        mapping = source / "map.csv"
        mapping.write_text("filename,password\na.pdf,p\na.pdf,q\n")
        kwargs["passwords_file"] = mapping
    if case == "threshold":
        kwargs.update(model="unused", threshold=float("nan"))
    if case in {"model", "empty"}:
        kwargs["model"] = "unused"

    def construct(**kwargs):
        if case == "model":
            raise ValueError("private model error")
        pytest.fail("must not construct model before valid nonempty selection")

    monkeypatch.setattr(piitier, "Anonymizer", construct)
    assert mask_batch(source, target, **kwargs) == (0 if case == "empty" else 2)
    if case == "alias":
        assert (target / "a.txt").read_text() == "PESEL: 90051512340"
        assert target.is_symlink()
    else:
        assert not (target / "a.txt").exists()


@pytest.mark.parametrize("failure", ["write", "interrupt", "race", "inference"])
def test_uc185_write_cleanup_and_continuation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    source, target = tmp_path / "in", tmp_path / "out"
    source.mkdir()
    for name in ["a.txt", "b.txt"]:
        (source / name).write_text("PESEL: 90051512340")
    original_open, original_mask = Path.open, piitier.mask

    @contextmanager
    def open_output(path, *args, **kwargs):
        if path == target / "a.txt" and args and args[0] == "x":
            if failure == "race":
                with original_open(path, "w") as handle:
                    handle.write("other writer")
                raise FileExistsError
            with original_open(path, *args, **kwargs) as handle:

                def write(text):
                    handle.write(text[:3])
                    if failure == "interrupt":
                        raise KeyboardInterrupt
                    raise OSError("private disk error")

                yield SimpleNamespace(fileno=handle.fileno, write=write)
        else:
            with original_open(path, *args, **kwargs) as handle:
                yield handle

    if failure != "inference":
        monkeypatch.setattr(Path, "open", open_output)
    else:
        calls = []

        def mask(text):
            calls.append(text)
            if len(calls) == 1:
                raise ValueError("private document text")
            return original_mask(text)

        monkeypatch.setattr(piitier, "mask", mask)
    assert mask_batch(source, target) == (130 if failure == "interrupt" else 4)
    if failure == "race":
        assert (target / "a.txt").read_text() == "other writer"
    else:
        assert not (target / "a.txt").exists()
    if failure == "interrupt":
        assert not (target / "b.txt").exists()
    else:
        assert (target / "b.txt").read_text() == "PESEL: [PESEL]"


def test_uc183_interrupt_during_output_ownership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os
    import signal

    source, target = tmp_path / "in", tmp_path / "out"
    source.mkdir()
    (source / "a.txt").write_text("PESEL: 90051512340")
    original = os.fstat

    def interrupt(fd):
        os.kill(os.getpid(), signal.SIGINT)
        return original(fd)

    monkeypatch.setattr(os, "fstat", interrupt)
    assert mask_batch(source, target) == 130
    assert not (target / "a.txt").exists()
