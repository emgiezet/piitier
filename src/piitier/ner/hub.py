"""Checkpoint resolution — local path or Hugging Face Hub snapshot.

Seam for tests
--------------
The module-level name ``_snapshot_download`` is the injection point.  Tests can
monkeypatch ``piitier.ner.hub._snapshot_download`` to any callable that accepts
``repo_id`` and ``revision`` keyword arguments and returns a path-like string,
preventing any real network access::

    monkeypatch.setattr(piitier.ner.hub, "_snapshot_download", fake_fn)

When ``_snapshot_download`` is ``None`` the real function is lazily imported
from ``huggingface_hub`` on the first hub-resolution call; setting it to a
non-``None`` value before that call suppresses the import entirely.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

# Injection point — monkeypatch this in tests to avoid network calls.
_snapshot_download: Callable[..., str] | None = None

_HUB_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9._-]+")


def _load_snapshot_download() -> Callable[..., str]:
    """Return a snapshot_download callable, importing it lazily if needed.

    Reads the module-level ``_snapshot_download`` so that tests which set it
    before the first call bypass the real import entirely.

    Raises
    ------
    ValueError
        When ``huggingface_hub`` is not installed.
    """
    global _snapshot_download
    fn = _snapshot_download
    if fn is None:
        try:
            from huggingface_hub import snapshot_download  # deferred; heavy dep

            _snapshot_download = snapshot_download
            fn = snapshot_download
        except ImportError as exc:
            raise ValueError(
                "Hugging Face Hub support needs the 'ner' extra: pip install 'piitier[ner]'"
            ) from exc
    return fn


def resolve_checkpoint(model: str | Path, revision: str | None = None) -> Path:
    """Resolve *model* to a local checkpoint directory.

    Resolution order:

    1. ``Path(model).is_dir()`` → return it immediately (local always wins,
       even if the string also matches the ``owner/name`` Hub pattern).
    2. Matches ``owner/name`` → download via Hugging Face Hub
       (``huggingface_hub.snapshot_download``); see the seam note above.
    3. Anything else → ``ValueError``.

    Parameters
    ----------
    model:
        A filesystem path (string or :class:`~pathlib.Path`) or a Hugging Face
        Hub repo id of the form ``"owner/name"``.
    revision:
        Branch, tag, or commit hash forwarded to ``snapshot_download``.
        Ignored for local paths.

    Returns
    -------
    Path
        An existing local directory containing the checkpoint.

    Raises
    ------
    ValueError
        If the model cannot be resolved:

        - ``huggingface_hub`` is not installed → message mentions
          ``piitier[ner]``.
        - The hub download fails → message starts with
          ``"could not download <model>: "``.
        - Neither a local directory nor a valid ``owner/name`` id → message
          starts with ``"model checkpoint not found: "``.
    """
    local = Path(model)
    if local.is_dir():
        return local

    model_str = str(model)
    if _HUB_RE.fullmatch(model_str):
        fn = _load_snapshot_download()  # raises ValueError on ImportError
        try:
            downloaded = fn(repo_id=model_str, revision=revision)
        except Exception as exc:
            raise ValueError(f"could not download {model}: {exc}") from exc
        return Path(downloaded)

    raise ValueError(f"model checkpoint not found: {model}")
