"""Import of the **real** LOTO draw history from the FDJ.

La Française des Jeux officially publishes its complete archives in CSV format
(ZIP-compressed), on an **anonymous** endpoint (no authentication):

    https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/<id>

These archives cover draws since 1976. This module focuses on the "new formula"
of LOTO (from October 2008): 5 balls out of 49 and 1 lucky number out of 10.

File format (``;`` separator, UTF-8 with BOM):

    annee_numero_de_tirage;jour_de_tirage;date_de_tirage;date_de_forclusion;
    boule_1;boule_2;boule_3;boule_4;boule_5;numero_chance;
    combinaison_gagnante_en_ordre_croissant;nombre_de_gagnant_au_rang1;rapport

The ``rapport`` column then contains, in sequence, ``nombre_de_gagnant;rapport``
pairs for **ranks 2 to 9**. Since each draw has its own report, the winnings
computed by the simulator are the **real winnings**, not averages.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import logging
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("loto.import")

DOC_BASE = (
    "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/"
)

# Identifiers of the archives published by the FDJ ("draw history" page).
# Only the periods relevant to the current formula (2008+) are used.
ARCHIVES: list[tuple[str, str]] = [
    ("2008-2017", DOC_BASE + "1a2b3c4d-9876-4562-b3fc-2c963f66afm6"),
    ("2017-2019", DOC_BASE + "1a2b3c4d-9876-4562-b3fc-2c963f66afn6"),
    ("2019-2019b", DOC_BASE + "1a2b3c4d-9876-4562-b3fc-2c963f66afo6"),
    ("2019-2026", DOC_BASE + "1a2b3c4d-9876-4562-b3fc-2c963f66afp6"),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.fdj.fr/jeux-de-tirage/loto/historique",
    "Accept": "application/zip, application/octet-stream, */*",
}

REQUEST_TIMEOUT = 60

# Number of winning ranks in LOTO ("0 number + lucky" wins nothing).
MAX_RANK = 9


@dataclass(slots=True)
class DrawRecord:
    """A normalised real draw."""

    draw_date: dt.date
    numbers: list[int]
    chance: int
    r1_winners: int
    r1_report: float
    rank_reports: dict[int, tuple[int, float]]  # rank -> (winners, report)

    def as_row(self) -> dict:
        """Converts the record into a row ready for the database."""
        numbers = self.numbers
        return {
            "draw_date": self.draw_date.isoformat(),
            "n1": numbers[0],
            "n2": numbers[1],
            "n3": numbers[2],
            "n4": numbers[3],
            "n5": numbers[4],
            "chance": self.chance,
            "jackpot": int(round(self.r1_report)),
            "r1_winners": self.r1_winners,
            "r1_report": self.r1_report,
        }

    def rank_rows(self) -> list[dict]:
        """Per-rank report rows associated with the draw."""
        return [
            {
                "draw_date": self.draw_date.isoformat(),
                "rank": rank,
                "winners": winners,
                "report": report,
            }
            for rank, (winners, report) in sorted(self.rank_reports.items())
        ]


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


class ImportError_(RuntimeError):
    """Error while importing the official data."""


def download_archive(url: str) -> bytes:
    """Downloads an official ZIP archive."""
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return response.read()
    except (urllib.error.URLError, OSError) as exc:  # pragma: no cover - network
        raise ImportError_(f"Téléchargement impossible ({url}) : {exc}") from exc


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _parse_date(raw: str) -> dt.date | None:
    """Accepts ``DD/MM/YYYY`` and ``YYYYMMDD``."""
    raw = raw.strip()
    for fmt in ("%d/%m/%Y", "%Y%m%d"):
        try:
            return dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _to_float(raw: str) -> float:
    """Converts a French amount ("1 234,50") into a float."""
    cleaned = raw.strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _to_int(raw: str) -> int:
    try:
        return int(raw.strip())
    except ValueError:
        return 0


def parse_archive(content: bytes, *, source_label: str = "") -> list[DrawRecord]:
    """Parses a ZIP archive and returns the real draws it contains."""
    records: list[DrawRecord] = []

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        csv_names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise ImportError_(f"Aucun CSV dans l'archive {source_label or '?'}")

        for name in csv_names:
            text = archive.read(name).decode("utf-8-sig", "replace")
            records.extend(_parse_csv(text, source_label=f"{source_label}:{name}"))

    return records


def _parse_csv(text: str, *, source_label: str = "") -> list[DrawRecord]:
    """Parses a FDJ CSV (one row per draw)."""
    reader = csv.reader(io.StringIO(text), delimiter=";")
    try:
        header = next(reader)
    except StopIteration:
        return []

    # Locate columns by name (the format has varied across periods).
    index = {name.strip(): position for position, name in enumerate(header)}

    def column(row: list[str], key: str) -> str:
        position = index.get(key)
        if position is None or position >= len(row):
            return ""
        return row[position]

    required = {
        "date_de_tirage",
        "boule_1",
        "boule_2",
        "boule_3",
        "boule_4",
        "boule_5",
        "numero_chance",
    }
    missing = required - set(index)
    if missing:
        logger.warning("Missing columns in %s: %s", source_label, sorted(missing))
        return []

    records: list[DrawRecord] = []
    for row in reader:
        if not row or not any(cell.strip() for cell in row):
            continue

        draw_date = _parse_date(column(row, "date_de_tirage"))
        if draw_date is None:
            continue

        try:
            numbers = sorted(
                int(column(row, f"boule_{position}"))
                for position in range(1, 6)
            )
            chance = int(column(row, "numero_chance"))
        except ValueError:
            continue

        if len(set(numbers)) != 5 or not all(1 <= n <= 49 for n in numbers):
            continue
        if not 1 <= chance <= 10:
            continue

        r1_winners = _to_int(column(row, "nombre_de_gagnant_au_rang1"))
        r1_report, rank_reports = _parse_reports(row, index)

        records.append(
            DrawRecord(
                draw_date=draw_date,
                numbers=numbers,
                chance=chance,
                r1_winners=r1_winners,
                r1_report=r1_report,
                rank_reports=rank_reports,
            )
        )

    return records


def _parse_reports(
    row: list[str], index: dict[str, int]
) -> tuple[float, dict[int, tuple[int, float]]]:
    """Extracts the rank-1 report and the (winners, report) pairs for ranks 2 to 9.

    The pairs immediately follow the ``nombre_de_gagnant_au_rang1`` column.
    We work on the raw strings so as not to lose the integer / decimal
    distinction (winner counts are integers).
    """
    start = index.get("nombre_de_gagnant_au_rang1")
    if start is None:
        return 0.0, {}

    cells: list[str] = []
    for cell in row[start + 1 :]:
        cell = cell.strip()
        if not cell:
            break
        # Stop once we leave the amounts (winning LOTO codes, "eur"…).
        if any(char.isalpha() for char in cell):
            break
        cells.append(cell)

    if not cells:
        return 0.0, {}

    r1_report = _to_float(cells[0])
    rank_reports: dict[int, tuple[int, float]] = {}

    rank = 2
    position = 1
    while rank <= MAX_RANK and position + 1 < len(cells):
        winners = _to_int(cells[position])
        report = _to_float(cells[position + 1])
        rank_reports[rank] = (winners, report)
        rank += 1
        position += 2

    return r1_report, rank_reports


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def fetch_all_draws(
    *, on_progress=None
) -> tuple[list[DrawRecord], list[str]]:
    """Downloads all archives and returns the real draws (2008+).

    Returns ``(draws, warnings)``. Failing archives are reported without
    interrupting the import of the others.
    """
    all_records: dict[dt.date, DrawRecord] = {}
    warnings: list[str] = []

    for label, url in ARCHIVES:
        try:
            content = download_archive(url)
            records = parse_archive(content, source_label=label)
        except (ImportError_, zipfile.BadZipFile, OSError) as exc:
            message = f"Archive « {label} » ignorée : {exc}"
            logger.warning(message)
            warnings.append(message)
            continue

        for record in records:
            all_records[record.draw_date] = record

        if on_progress:
            on_progress(label, len(records))

    ordered = [all_records[date] for date in sorted(all_records)]
    return ordered, warnings


def load_from_path(path: str | Path) -> list[DrawRecord]:
    """Loads draws from a local file (``.csv`` or ``.zip``).

    Used for offline environments and tests: makes it possible to inject an
    extract of the official format without network access.
    """
    source = Path(path)
    if not source.exists():
        raise ImportError_(f"Fichier source introuvable : {source}")

    content = source.read_bytes()
    if source.suffix.lower() == ".zip":
        return parse_archive(content, source_label=source.name)

    text = content.decode("utf-8-sig", "replace")
    return _parse_csv(text, source_label=source.name)
