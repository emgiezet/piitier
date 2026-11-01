"""Nonrecursive batch anonymisation with exclusive, document-local text outputs."""

from __future__ import annotations

import os
import signal
import sys
import threading
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import FrameType

import piitier
from piitier.jsonmask import mask_json
from piitier.loaders import PasswordPrompt, decode_json_bytes, get_loader, load_with_password
from piitier.passwords import parse_passwords_csv


@contextmanager
def _defer_interrupt() -> Iterator[None]:
    """Record Ctrl-C until exclusive creation has a cleanup identity."""
    if threading.current_thread() is not threading.main_thread():
        # Python delivers process signals only to the main thread.
        yield
        return
    interrupted = False

    def defer(signum: int, frame: FrameType | None) -> None:
        nonlocal interrupted
        interrupted = True

    previous = signal.signal(signal.SIGINT, defer)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)
        if interrupted:
            raise KeyboardInterrupt


def _write_output(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Remove only the file this attempt created if writing or closing fails."""
    identity = None
    try:
        with ExitStack() as files:
            with _defer_interrupt():
                output = files.enter_context(path.open("x", encoding=encoding, newline=""))
                stat = os.fstat(output.fileno())
                identity = (stat.st_dev, stat.st_ino)
            output.write(text)
    except BaseException:
        if identity is not None:
            try:
                stat = path.stat(follow_symlinks=False)
                if identity == (stat.st_dev, stat.st_ino):
                    path.unlink()
            except FileNotFoundError:
                pass
        raise


def mask_batch(
    input_dir: Path,
    output_dir: Path,
    passwords_file: Path | None = None,
    model: str | None = None,
    threshold: float = 0.0,
    revision: str | None = None,
    *,
    prompt: PasswordPrompt | None = None,
) -> int:
    """Mask each supported file, preserving completed outputs after individual failures."""
    try:
        if not input_dir.is_dir():
            print(f"invalid input directory: {input_dir}", file=sys.stderr)
            return 2
        if model is not None and not (0.0 <= threshold <= 1.0):
            print("invalid threshold (expected a number in [0, 1])", file=sys.stderr)
            return 2
        source = input_dir.resolve()
        target = output_dir.resolve()
        if target == source or target.is_relative_to(source):
            print("output directory cannot be equal to or beneath input directory", file=sys.stderr)
            return 2
        if output_dir.exists() and not output_dir.is_dir():
            print(f"invalid output directory: {output_dir}", file=sys.stderr)
            return 2
        passwords = parse_passwords_csv(passwords_file) if passwords_file is not None else {}
        map_path = passwords_file.resolve() if passwords_file is not None else None
        files = [
            path
            for path in sorted(input_dir.iterdir(), key=lambda item: item.name)
            if path.is_file()
            and get_loader(path) is not None
            and (map_path is None or path.resolve() != map_path)
        ]
        output_dir.mkdir(parents=True, exist_ok=True)
    except ValueError as error:
        print(str(error), file=sys.stderr)  # Only our sanitised map diagnostics.
        return 2
    except OSError:
        print("cannot access batch paths", file=sys.stderr)
        return 2

    if not files:
        print("batch: 0 masked, 0 failed", file=sys.stderr)
        return 0
    try:
        anonymizer = (
            piitier.Anonymizer(model=model, threshold=threshold, revision=revision)
            if model is not None
            else None
        )
    except KeyboardInterrupt:
        return 130
    except Exception:
        print("could not initialise model", file=sys.stderr)
        return 2

    masked = failed = 0
    for path in files:
        suffix = path.suffix.lower()
        is_pdf = suffix == ".pdf"
        destination = output_dir / (path.with_suffix(".txt").name if is_pdf else path.name)
        try:
            encoding = "utf-8"
            if suffix == ".json":
                text, encoding = decode_json_bytes(path.read_bytes())
            else:
                text = load_with_password(
                    path,
                    password=passwords.get(path.name) if is_pdf else None,
                    prompt=prompt,
                )
            if suffix == ".json":
                if anonymizer is not None:
                    result = mask_json(
                        text, detector=anonymizer.detect, numbering_fn=anonymizer.assign
                    )
                else:
                    result = mask_json(text, detector=piitier.detect)
            else:
                result = anonymizer.mask(text) if anonymizer is not None else piitier.mask(text)
            _write_output(destination, result, encoding=encoding)
        except KeyboardInterrupt:
            return 130
        except Exception:
            # Parser, inference and filesystem exceptions may contain input bytes.
            print(f"failed: {path}", file=sys.stderr)
            failed += 1
        else:
            masked += 1
    print(f"batch: {masked} masked, {failed} failed", file=sys.stderr)
    return 4 if failed else 0
