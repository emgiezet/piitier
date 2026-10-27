"""Tabular-document → placeholder-template harvester (``templatize-tables`` command).

Reads insurer-report XLSX and CSV files and produces placeholder-only templates
for the ``raport_towarzystwa`` document type.
Public entry point: :func:`templatize_tables`.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

import openpyxl
import openpyxl.utils.exceptions

import piitier
from piitier.datagen.templatize import (
    _gate,
    _leaks,
    _load_manifest,
)
from piitier.labels import Label

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_CHARS: int = 2000
_MIN_ROWS: int = 2
_MAX_ROWS: int = 8
_HEADER_SCAN_ROWS: int = 15
_MIN_HEADER_CELLS: int = 3

# Labels that join the *person group* when given an explicit entity id (#n).
_PERSON_GROUP: frozenset[Label] = frozenset(
    {Label.OSOBA, Label.IMIE, Label.NAZWISKO, Label.DATA_URODZENIA, Label.PESEL}
)
# Labels that join the *address group* when given an explicit entity id (#n).
_ADDRESS_GROUP: frozenset[Label] = frozenset({Label.ADRES, Label.KOD_POCZTOWY, Label.MIEJSCOWOSC})
# Strong checksum labels accepted for unmapped-cell detection.
_STRONG_LABELS: frozenset[Label] = frozenset(
    {Label.PESEL, Label.IBAN, Label.NR_DOWODU, Label.NR_KARTY}
)
# Cell values treated as absent/empty even in a mapped column.
_ABSENT: frozenset[str] = frozenset({"", "-", "0"})

# ---------------------------------------------------------------------------
# Column mapping table
# ---------------------------------------------------------------------------


def _c(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


# Ordered list of (compiled regex, Label, role).
# role ∈ {'client', 'staff', 'other'}.
# Patterns match _norm_header() output: stripped, whitespace-collapsed,
# casefolded, <br> removed.
_COL_MAP: list[tuple[re.Pattern[str], Label, str]] = [
    # ── Client full-name (OSOBA, role=client) ──────────────────────────────
    (_c(r"ubezpieczaj[aą]cy\s*[-–]\s*nazwa"), Label.OSOBA, "client"),
    (_c(r"ubezpieczaj[aą]cy\s+customer"), Label.OSOBA, "client"),
    (_c(r"^ubezpieczaj[aą]cy$"), Label.OSOBA, "client"),
    (_c(r"^ubezpieczajacy$"), Label.OSOBA, "client"),
    (_c(r"^ubezpieczony$"), Label.OSOBA, "client"),
    (_c(r"^klient$"), Label.OSOBA, "client"),
    (_c(r"^imię\s+i\s+nazwisko\s+ubezpieczaj[aą]cego$"), Label.OSOBA, "client"),
    (_c(r"^imię\s*/\s*nazwisko\s+lub\s+nazwa\s+ubezpieczaj[aą]cego$"), Label.OSOBA, "client"),
    (_c(r"imię\s+i\s+nazwisko\s+klienta"), Label.OSOBA, "client"),
    (_c(r"imię\s+i\s+nazwisko\s+ubezpieczon\w+"), Label.OSOBA, "client"),
    (_c(r"nazwisko\s+i\s+imie\s+klienta"), Label.OSOBA, "client"),
    (_c(r"^nabywcaimienazwisko$"), Label.OSOBA, "client"),
    (_c(r"^właściciel(?:\s+polisy|\s+obiektu)?$"), Label.OSOBA, "client"),
    (_c(r"d[łl]u[żz]nik\s*[-–]\s*nazwa"), Label.OSOBA, "client"),
    (_c(r"^nazwa\s+klienta$"), Label.OSOBA, "client"),
    # ── Client first-name / last-name split ─────────────────────────────────
    (_c(r"^klient_imie$|^imi[eę]$"), Label.IMIE, "client"),
    (_c(r"^imię\s+właściciela\s+polisy$"), Label.IMIE, "client"),
    (_c(r"^klient_nazwisko$|^nazwisko(?:\(nazwa\))?$"), Label.NAZWISKO, "client"),
    (_c(r"^nazwisko\s+właściciela\s+polisy$"), Label.NAZWISKO, "client"),
    # ── Client PESEL ────────────────────────────────────────────────────────
    (_c(r"^pesel(?:\s*/\s*regon)?$"), Label.PESEL, "client"),
    (_c(r"^pesel\s+właściciela\s+polisy$"), Label.PESEL, "client"),
    # ── Non-person IDs (role=other, no entity numbering) ────────────────────
    (_c(r"^nip$"), Label.NIP, "other"),
    (_c(r"^regon$"), Label.REGON, "other"),
    # ── Staff full-name (OSOBA, role=staff) ─────────────────────────────────
    (_c(r"imię\s+i\s+nazwisko\s+owca(?:\s*/\s*ofwca)?$"), Label.OSOBA, "staff"),
    (_c(r"imię\s+i\s+nazwisko\s+agenta\s+dystrybutora"), Label.OSOBA, "staff"),
    (_c(r"imię\s+i\s+nazwisko\s+(?:agenta?|sprzedawcy)"), Label.OSOBA, "staff"),
    (_c(r"^agent\s+dystrybutor$"), Label.OSOBA, "staff"),
    (_c(r"^(?:nazwa\s+)?ofwca(?:\s+\(nazwa\))?$"), Label.OSOBA, "staff"),
    (_c(r"^owca_name$|^owca$"), Label.OSOBA, "staff"),
    (_c(r"^agent[\s_]+name$|^agent\s*\(nazwa\)$|^nazwa\s+agenta$"), Label.OSOBA, "staff"),
    (_c(r"^nazwa\s+sprzedawcy$"), Label.OSOBA, "staff"),
    (_c(r"^sprzedawcaimienazwisko$"), Label.OSOBA, "staff"),
    (_c(r"^inkasent(?:imienazwisko)?$"), Label.OSOBA, "staff"),
    (_c(r"^pracownik\d*$"), Label.OSOBA, "staff"),
    (_c(r"^u[żz]ytkownik$|^user[\s_]+name$"), Label.OSOBA, "staff"),
    (_c(r"^po[śs]rednik$|^posrednik$|^nazwa\s+po[śs]rednika$"), Label.OSOBA, "staff"),
    (_c(r"^imie_nazwisko$"), Label.OSOBA, "staff"),
    (_c(r"wystawiaj[aą]cy"), Label.OSOBA, "staff"),
    (_c(r"^imię\s*\+\s*nazwisko\s+\(agent\s+user\)$"), Label.OSOBA, "staff"),
    # ── Staff first-name / last-name split ──────────────────────────────────
    (_c(r"^(?:imię|imie)\s+ofwca$"), Label.IMIE, "staff"),
    (_c(r"^(?:imię|imie)\s+agenta$"), Label.IMIE, "staff"),
    (_c(r"^nazwisko\s+ofwca$"), Label.NAZWISKO, "staff"),
    (_c(r"^nazwisko\s+agenta$"), Label.NAZWISKO, "staff"),
    # ── Staff PESEL ─────────────────────────────────────────────────────────
    (_c(r"^pesel\s+(?:pracownika|ofwca)$"), Label.PESEL, "staff"),
    # ── Staff NIP (other, no entity) ────────────────────────────────────────
    (_c(r"^nip_agenta$"), Label.NIP, "other"),
    # ── Policy / contract numbers ────────────────────────────────────────────
    (
        _c(r"^(?:nr\.?\s+)?polisy?$|^numer\s+polisy?$|^nr_polisy$|^polisa$|^policy_nr$"),
        Label.NR_POLISY,
        "other",
    ),
    (_c(r"^seria\s+i\s+numer\s+polisy$"), Label.NR_POLISY, "other"),
    (
        _c(r"^numer\s+polisy\s+wznawianej$|^polisa\s+(?:bazowa|wznawiana)$"),
        Label.NR_POLISY,
        "other",
    ),
    (_c(r"^nr\s+polisy\s+poprzedniej$"), Label.NR_POLISY, "other"),
    (_c(r"nr\s*\.?\s*polisy\s+\d+\s+policy\s+no"), Label.NR_POLISY, "other"),
    (_c(r"^nr\s+umowy$|^numer\s+umowy$"), Label.NR_UMOWY, "other"),
    # ── IBAN / bank account ──────────────────────────────────────────────────
    (_c(r"^konto\s+klienta$|^nr_rachunku$"), Label.IBAN, "other"),
    # ── Vehicle ─────────────────────────────────────────────────────────────
    (_c(r"^vin$"), Label.VIN, "other"),
    (
        _c(r"^(?:numer|numery|nr)[\s_.]*rej(?:estracyjn\w*|\.)?$"),
        Label.NR_REJESTRACYJNY,
        "other",
    ),
    # ── Client address ───────────────────────────────────────────────────────
    (_c(r"^ulica$|^nieruchomosc$|^lokal$"), Label.ADRES, "client"),
    (_c(r"^kod_p$|^kod\s+pocztowy$"), Label.KOD_POCZTOWY, "client"),
    (_c(r"^miasto$|^poczta$|^miejscowosc$"), Label.MIEJSCOWOSC, "client"),
    # ── Money / amounts ──────────────────────────────────────────────────────
    (_c(r"^kwota"), Label.KWOTA, "other"),
    (_c(r"kwota$"), Label.KWOTA, "other"),
    (_c(r"^inkaso"), Label.KWOTA, "other"),
    (_c(r"inkaso$"), Label.KWOTA, "other"),
    (_c(r"^sk[lł]adka"), Label.KWOTA, "other"),
    (_c(r"sk[lł]adka$"), Label.KWOTA, "other"),
    (_c(r"^odszkodowani"), Label.KWOTA, "other"),
    (_c(r"odszkodowani[ae]$"), Label.KWOTA, "other"),
    (_c(r"^do\s+wyp[lł]aty$"), Label.KWOTA, "other"),
    (_c(r"^podstawa$"), Label.KWOTA, "other"),
    (_c(r"^podst(?:awa)?\s+nal"), Label.KWOTA, "other"),
    (_c(r"^prow(?:\s+\[pln\])?$"), Label.KWOTA, "other"),
    (_c(r"^gwp"), Label.KWOTA, "other"),
    (_c(r"^przypis"), Label.KWOTA, "other"),
    (_c(r"^potr[aą]cen"), Label.KWOTA, "other"),
    (_c(r"^balans$|^saldo$"), Label.KWOTA, "other"),
    (_c(r"^kwota_oplacona\d*$|^yearly\s+premium$"), Label.KWOTA, "other"),
    (_c(r".*\[pln\]$"), Label.KWOTA, "other"),
]

# Columns dropped by header: logins and agent/user/intermediary identifiers. They have no
# taxonomy label, yet identify a person (logins embed first names, ``ZURGRZ0001`` is built
# from a surname), so their values must never reach a template. Note numbers go too.
_DROP_COL_RE = _c(
    r"login|\buid\b|^id\b|[\s_]id$|^agent$|^nr\s+agenta$|^agent\s*\(numer\)$"
    r"|numer\s+członkowski|^nr\s+owca$|^nr\s+ma$|^(?:kod|id)\s+po[śs]rednika$|^nr\s+noty$"
    r"|^d[łl]u[żz]nik\s*[-–]\s*numer$"
)
# A header cell that is a number belongs to a summary block, not a column header.
_NUMERIC_RE = re.compile(r"[\d\s.,%+-]+")


def _norm_header(h: str) -> str:
    """Strip, collapse whitespace, casefold, remove ``<br>`` tags."""
    h = re.sub(r"<br\s*/?>", " ", h, flags=re.IGNORECASE)
    h = re.sub(r"\s+", " ", h.strip())
    return h.casefold()


def _map_header(h: str) -> tuple[Label, str] | None:
    """Return ``(label, role)`` for *h*, or ``None`` when no mapping exists."""
    norm = _norm_header(h)
    if not norm:
        return None
    for pattern, label, role in _COL_MAP:
        if pattern.search(norm):
            return label, role
    return None


# ---------------------------------------------------------------------------
# Header-row detection
# ---------------------------------------------------------------------------


def _detect_header_row(rows: list[list[Any]]) -> int | None:
    """Return the index of the header row within the first *_HEADER_SCAN_ROWS* rows.

    A header row is the first row where:

    * ≥ ``_MIN_HEADER_CELLS`` non-empty cells
    * more than half of non-empty cells are string values
    * at least one cell maps to a PII label
    """
    for i, row in enumerate(rows[:_HEADER_SCAN_ROWS]):
        non_empty = [c for c in row if c is not None and str(c).strip()]
        if len(non_empty) < _MIN_HEADER_CELLS:
            continue
        str_cells = [c for c in non_empty if isinstance(c, str)]
        if len(str_cells) <= len(non_empty) // 2:
            continue
        if any(_NUMERIC_RE.fullmatch(str(c).strip()) for c in non_empty):
            continue
        if any(_map_header(str(c)) is not None for c in str_cells):
            return i
    return None


# ---------------------------------------------------------------------------
# Cell formatting
# ---------------------------------------------------------------------------


def _fmt_cell(v: Any) -> str:
    """Format a spreadsheet cell value as a string.

    * ``None`` → ``""``
    * ``bool`` → ``"True"`` / ``"False"``
    * ``int`` → digits without ``.0``
    * ``float`` → short ``%g`` form, integer when exact
    * ``datetime.datetime`` → ``"YYYY-MM-DD HH:MM:SS"`` / ``"YYYY-MM-DD"``
    * ``datetime.date`` → ``"YYYY-MM-DD"``
    * everything else → ``str(v).strip()``
    """
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, datetime.datetime):
        if v.hour or v.minute or v.second:
            return v.strftime("%Y-%m-%d %H:%M:%S")
        return v.strftime("%Y-%m-%d")
    if isinstance(v, datetime.date):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return f"{v:g}"
    return str(v).strip()


# ---------------------------------------------------------------------------
# Unmapped-cell checksum detection
# ---------------------------------------------------------------------------


def _checksum_label_cell(text: str) -> str | None:
    """Return label name if *text* is a single checksum-valid strong PII value."""
    stripped = text.strip()
    for span in piitier.detect(stripped):
        if (
            span.label in _STRONG_LABELS
            and span.status == "valid"
            and span.start == 0
            and span.end == len(stripped)
        ):
            return span.label.name
    return None


# ---------------------------------------------------------------------------
# Column analysis (per sheet)
# ---------------------------------------------------------------------------


def _analyse_columns(
    headers: list[str],
    data_rows: list[list[Any]],
) -> tuple[dict[int, tuple[Label, str]], set[int]]:
    """Return ``(col_lookup, drop_cols)`` for the sheet.

    *col_lookup* maps column index → ``(Label, role)`` for PII columns.
    *drop_cols* is the set of column indices that must be dropped because their
    unmapped cell values trip the leak check (long non-taxonomy numeric IDs etc.).
    """
    col_lookup: dict[int, tuple[Label, str]] = {}
    for i, h in enumerate(headers):
        result = _map_header(h)
        if result is not None:
            col_lookup[i] = result

    mapped_idxs = set(col_lookup)
    drop_cols: set[int] = set()

    for col_idx, h in enumerate(headers):
        if col_idx in mapped_idxs:
            continue
        norm = _norm_header(h)
        if not norm or _NUMERIC_RE.fullmatch(norm) or _DROP_COL_RE.search(norm):
            drop_cols.add(col_idx)
            continue
        for row in data_rows[:50]:
            v = row[col_idx] if col_idx < len(row) else None
            if v is None:
                continue
            cell_str = _fmt_cell(v)
            if cell_str in _ABSENT:
                continue
            if _leaks(cell_str):
                drop_cols.add(col_idx)
                break

    return col_lookup, drop_cols


# ---------------------------------------------------------------------------
# Window rendering
# ---------------------------------------------------------------------------


def _render_window(
    headers: list[str],
    col_lookup: dict[int, tuple[Label, str]],
    drop_cols: set[int],
    raw_rows: list[list[Any]],
    sep: str,
) -> str:
    """Render *raw_rows* into a template string.

    Each call gets a fresh entity counter starting at 1.  Within a row, all
    person-group (or address-group) labels of the same role share one entity id.
    The counter increments globally across rows in the window.
    """
    active_header_parts = [h for i, h in enumerate(headers) if i not in drop_cols]
    header_line = sep.join(active_header_parts)

    entity_seq: list[int] = [0]
    rendered_rows: list[str] = []

    for row_vals in raw_rows:
        row_entity: dict[str, int] = {}
        cells: list[str] = []

        for col_idx in range(len(headers)):
            if col_idx in drop_cols:
                continue
            raw = row_vals[col_idx] if col_idx < len(row_vals) else None
            cell_str = _fmt_cell(raw)
            mapping = col_lookup.get(col_idx)

            if mapping is None:
                if cell_str and cell_str not in _ABSENT:
                    lbl_name = _checksum_label_cell(cell_str)
                    cells.append(f"{{{{{lbl_name}}}}}" if lbl_name else cell_str)
                else:
                    cells.append(cell_str)
            else:
                label, role = mapping
                if not cell_str or cell_str in _ABSENT:
                    cells.append(cell_str)
                elif label in _PERSON_GROUP or label in _ADDRESS_GROUP:
                    if role not in row_entity:
                        entity_seq[0] += 1
                        row_entity[role] = entity_seq[0]
                    n = row_entity[role]
                    cells.append(f"{{{{{label.name}#{n}}}}}")
                else:
                    cells.append(f"{{{{{label.name}}}}}")

        rendered_rows.append(sep.join(cells))

    return header_line + "\n" + "\n".join(rendered_rows) + "\n"


# ---------------------------------------------------------------------------
# Window selection
# ---------------------------------------------------------------------------


def _build_window(
    headers: list[str],
    col_lookup: dict[int, tuple[Label, str]],
    drop_cols: set[int],
    data_rows: list[list[Any]],
    start: int,
    sep: str,
) -> str | None:
    """Build one template window starting at row *start*.

    Rows are added until adding the next would exceed _MAX_CHARS or _MAX_ROWS
    rows are reached.  Returns ``None`` when fewer than _MIN_ROWS fit.
    """
    active_headers = [h for i, h in enumerate(headers) if i not in drop_cols]
    header_line = sep.join(active_headers)
    base_len = len(header_line) + 1  # +1 for trailing newline

    chosen: list[list[Any]] = []
    total = base_len

    for i in range(start, min(start + _MAX_ROWS, len(data_rows))):
        row_vals = data_rows[i]
        cells_preview = [
            _fmt_cell(row_vals[ci] if ci < len(row_vals) else None)
            for ci in range(len(headers))
            if ci not in drop_cols
        ]
        # A sparse row is a blank line or a summary/footer block: the table ends there.
        if sum(1 for c in cells_preview if c) < _MIN_HEADER_CELLS:
            break
        row_len = len(sep.join(cells_preview)) + 1  # +1 for newline

        if total + row_len > _MAX_CHARS and len(chosen) >= _MIN_ROWS:
            break
        chosen.append(row_vals)
        total += row_len
        if total > _MAX_CHARS:
            break

    if len(chosen) < _MIN_ROWS:
        return None

    return _render_window(headers, col_lookup, drop_cols, chosen, sep)


# ---------------------------------------------------------------------------
# File readers
# ---------------------------------------------------------------------------


def _read_xlsx(path: Path) -> list[tuple[str, list[list[Any]]]]:
    """Return ``[(sheet_name, rows)]`` for every worksheet in *path*."""
    sheets: list[tuple[str, list[list[Any]]]] = []
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception:  # broad catch: openpyxl can raise many error types on corrupt files
        return sheets
    try:
        for ws in wb.worksheets:
            rows: list[list[Any]] = [list(row) for row in ws.iter_rows(values_only=True)]
            sheets.append((ws.title, rows))
    finally:
        wb.close()
    return sheets


def _sniff_delimiter(text: str) -> str:
    """Detect CSV delimiter from *text* sample."""
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        return dialect.delimiter
    except csv.Error:
        first = sample.split("\n", 1)[0]
        counts = {d: first.count(d) for d in (";", ",", "\t")}
        return max(counts, key=lambda k: counts[k]) if counts else ";"


def _read_csv(path: Path) -> list[tuple[str, list[list[Any]], str]]:
    """Return ``[(sheet_name, rows, delimiter)]`` for the CSV *path*.

    Encoding tried in order: ``utf-8-sig``, ``cp1250``.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return []

    text: str | None = None
    for enc in ("utf-8-sig", "cp1250"):
        try:
            text = raw.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if text is None:
        return []

    delim = _sniff_delimiter(text)
    rows: list[list[Any]] = [list(row) for row in csv.reader(io.StringIO(text), delimiter=delim)]
    return [(path.stem, rows, delim)]


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _is_inside(path: Path, parent: Path) -> bool:
    """Return ``True`` when *path* is equal to or under *parent*."""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def templatize_tables(
    src_dir: Path,
    out: Path,
    *,
    doc_type: str = "raport_towarzystwa",
    max_per_file: int = 3,
    reject_dir: Path | None = None,
) -> dict[str, Any]:
    """Convert tabular insurer reports into placeholder-only templates.

    Reads every ``*.xlsx`` (all worksheets) and ``*.csv`` under *src_dir*.
    Skips ``~$`` lock files and all other file extensions.

    Parameters
    ----------
    src_dir:
        Directory containing ``*.xlsx`` and ``*.csv`` source files.
    out:
        Root output directory.  Accepted templates are written to
        ``out/<doc_type>/<doc_type>_<sha256[:12]>.txt``.
    doc_type:
        Document-type label used for gating and the manifest.
    max_per_file:
        Maximum templates extracted per worksheet (windows: first / middle / last).
    reject_dir:
        Optional directory for rejected snippets (for inspection).
        Must resolve **outside** ``Path.cwd()``.

    Returns
    -------
    dict with keys ``"files_read"``, ``"accepted"``, ``"rejected"``
    (only non-zero reasons included in ``"rejected"``).

    Raises
    ------
    ValueError
        If *reject_dir* resolves inside the current working directory.
    """
    if reject_dir is not None:
        if _is_inside(reject_dir.resolve(), Path.cwd().resolve()):
            raise ValueError("reject_dir must be outside the repository")

    out_doc_dir = out / doc_type
    manifest_path = out / "manifest.json"

    # Pre-collect sha256 hashes of all existing templates for deduplication.
    known_hashes: set[str] = set()
    for existing in out.rglob("*.txt"):
        try:
            known_hashes.add(hashlib.sha256(existing.read_bytes()).hexdigest())
        except OSError:
            pass

    files_read: int = 0
    accepted: int = 0
    rejected_counts: dict[str, int] = {}

    def _inc_reject(reason: str) -> None:
        rejected_counts[reason] = rejected_counts.get(reason, 0) + 1

    def _accept_template(text: str) -> bool:
        nonlocal accepted
        h = _sha256_text(text)
        if h in known_hashes:
            _inc_reject("duplicate")
            return False
        known_hashes.add(h)
        reason = _gate(text, doc_type)
        if reason is not None:
            _inc_reject(reason)
            if reject_dir is not None:
                dest = reject_dir / reason / f"{h[:12]}.txt"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text, encoding="utf-8")
            return False
        out_doc_dir.mkdir(parents=True, exist_ok=True)
        (out_doc_dir / f"{doc_type}_{h[:12]}.txt").write_text(text, encoding="utf-8")
        accepted += 1
        return True

    def _process_sheet(all_rows: list[list[Any]], sep: str) -> None:
        if not all_rows:
            return
        hdr_idx = _detect_header_row(all_rows)
        if hdr_idx is None:
            _inc_reject("no_header")
            return

        headers = [str(c) if c is not None else "" for c in all_rows[hdr_idx]]
        data_rows = all_rows[hdr_idx + 1 :]

        if len(data_rows) < _MIN_ROWS:
            _inc_reject("no_header")
            return

        col_lookup, drop_cols = _analyse_columns(headers, data_rows)

        n = len(data_rows)
        last_start = max(0, n - _MAX_ROWS)
        mid_start = max(0, last_start // 2)
        candidates = [0, mid_start, last_start]

        seen_in_run: set[str] = set()
        wins = 0

        for start in candidates[:max_per_file]:
            if wins >= max_per_file:
                break
            text = _build_window(headers, col_lookup, drop_cols, data_rows, start, sep)
            if text is None:
                continue
            wh = _sha256_text(text)
            if wh in seen_in_run:
                continue
            seen_in_run.add(wh)
            if _accept_template(text):
                wins += 1

    # ── Iterate over source files (recursively) ──────────────────────────────
    all_src: list[Path] = sorted(
        p for p in src_dir.rglob("*") if p.is_file() and p.suffix.lower() in (".xlsx", ".csv")
    )
    for src_path in all_src:
        if src_path.name.startswith("~$"):
            continue
        suffix = src_path.suffix.lower()

        if suffix == ".xlsx":
            files_read += 1
            for _name, rows in _read_xlsx(src_path):
                _process_sheet(rows, "\t")

        elif suffix == ".csv":
            files_read += 1
            for _name, rows, delim in _read_csv(src_path):
                _process_sheet(rows, delim)

    # ── Append manifest record ───────────────────────────────────────────────
    records = _load_manifest(manifest_path)
    records.append(
        {
            "source": "/".join(src_dir.parts[-2:]),
            "doc_type": doc_type,
            "files_read": files_read,
            "accepted": accepted,
            "rejected": {k: v for k, v in rejected_counts.items() if v > 0},
            "generator": "tabular",
        }
    )
    out.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "files_read": files_read,
        "accepted": accepted,
        "rejected": {k: v for k, v in rejected_counts.items() if v > 0},
    }
