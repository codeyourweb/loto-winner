"""SQLite access: schema, Flask connection and import of **real** draws.

Data comes from the official FDJ archives (see ``fdj_importer``). Each draw keeps
the real per-rank reports, which makes it possible to compute exact winnings
rather than averages.

Synchronisation:
* at startup, the history is completed if new draws have been published;
* a single network synchronisation per day;
* offline, a synthetic history can be generated (fallback) so the application
  stays usable, clearly identified through ``source``.
"""

from __future__ import annotations

import datetime as dt
import logging
import sqlite3
from pathlib import Path
from typing import TypedDict

from flask import current_app, g

from .fdj_importer import DrawRecord, fetch_all_draws, load_from_path
from .simulated_data import generate_simulated_draws

logger = logging.getLogger("loto.db")

# Switch date to the current LOTO formula (5/49 + 1 lucky number/10).
FORMULA_START = dt.date(2008, 10, 6)

SCHEMA = """
CREATE TABLE IF NOT EXISTS draws (
    draw_date   TEXT    PRIMARY KEY,
    n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
    n4 INTEGER NOT NULL, n5 INTEGER NOT NULL,
    chance      INTEGER NOT NULL,
    r1_winners  INTEGER NOT NULL DEFAULT 0,
    r1_report   REAL    NOT NULL DEFAULT 0,
    source      TEXT    NOT NULL DEFAULT 'fdj'
);

CREATE INDEX IF NOT EXISTS idx_draws_date ON draws (draw_date);

CREATE TABLE IF NOT EXISTS rank_reports (
    draw_date TEXT    NOT NULL,
    rank      INTEGER NOT NULL,
    winners   INTEGER NOT NULL DEFAULT 0,
    report    REAL    NOT NULL DEFAULT 0,
    PRIMARY KEY (draw_date, rank),
    FOREIGN KEY (draw_date) REFERENCES draws (draw_date) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS simulations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at     TEXT    NOT NULL,
    numbers        TEXT    NOT NULL,
    chance         INTEGER NOT NULL,
    total_spent    REAL    NOT NULL,
    total_won      REAL    NOT NULL,
    net            REAL    NOT NULL,
    best_rank      INTEGER,
    jackpot_hits   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sync_state (
    id                INTEGER PRIMARY KEY CHECK (id = 1),
    last_sync_at      TEXT,
    last_draw_date    TEXT,
    source            TEXT,
    total_draws       INTEGER NOT NULL DEFAULT 0
);
"""

INSERT_DRAW_SQL = """
INSERT INTO draws (
    draw_date, n1, n2, n3, n4, n5, chance, r1_winners, r1_report, source
) VALUES (
    :draw_date, :n1, :n2, :n3, :n4, :n5, :chance, :r1_winners, :r1_report, :source
)
ON CONFLICT(draw_date) DO UPDATE SET
    n1 = excluded.n1, n2 = excluded.n2, n3 = excluded.n3,
    n4 = excluded.n4, n5 = excluded.n5, chance = excluded.chance,
    r1_winners = excluded.r1_winners, r1_report = excluded.r1_report,
    source = excluded.source
"""

INSERT_RANK_SQL = """
INSERT INTO rank_reports (draw_date, rank, winners, report)
VALUES (:draw_date, :rank, :winners, :report)
ON CONFLICT(draw_date, rank) DO UPDATE SET
    winners = excluded.winners, report = excluded.report
"""


class SyncReport(TypedDict):
    """Result of a history synchronisation."""

    total_before: int
    inserted: int
    total_after: int
    latest_date: str | None
    source: str
    warnings: list[str]


def get_db() -> sqlite3.Connection:
    """Returns the SQLite connection attached to the current request."""
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE_PATH"],
            timeout=5.0,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exception: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _count(connection: sqlite3.Connection) -> int:
    return int(connection.execute("SELECT COUNT(*) FROM draws").fetchone()[0])


def _read_state(connection: sqlite3.Connection) -> dict:
    row = connection.execute("SELECT * FROM sync_state WHERE id = 1").fetchone()
    return dict(row) if row else {}


def _write_state(
    connection: sqlite3.Connection, *, source: str, total: int, latest: str | None
) -> None:
    connection.execute(
        """
        INSERT INTO sync_state (id, last_sync_at, last_draw_date, source, total_draws)
        VALUES (1, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            last_sync_at = excluded.last_sync_at,
            last_draw_date = excluded.last_draw_date,
            source = excluded.source,
            total_draws = excluded.total_draws
        """,
        (dt.datetime.now(dt.timezone.utc).isoformat(), latest, source, total),
    )
    connection.commit()


def _import_records(connection: sqlite3.Connection, records: list[DrawRecord]) -> int:
    """Inserts (or updates) real draws and their per-rank reports."""
    payload = []
    ranks = []
    for record in records:
        row = record.as_row()
        row["source"] = "fdj"
        payload.append(row)
        ranks.extend(record.rank_rows())

    connection.executemany(INSERT_DRAW_SQL, payload)
    if ranks:
        connection.executemany(INSERT_RANK_SQL, ranks)
    connection.commit()
    return len(payload)


def _import_simulated(connection: sqlite3.Connection) -> int:
    """Fallback: generates a synthetic history when the network is unavailable."""
    rows = generate_simulated_draws()
    connection.executemany(INSERT_DRAW_SQL, rows)
    connection.commit()
    return len(rows)


def sync_draws(
    connection: sqlite3.Connection,
    *,
    allow_network: bool = True,
    local_source: str | Path | None = None,
    allow_fallback: bool = True,
) -> SyncReport:
    """Imports/completes the history of real draws.

    Order of precedence:
    1. the official FDJ archives (if the network is allowed);
    2. a local ``fdj_history.csv``/``.zip`` file (offline environments);
    3. a synthetic fallback history (last resort).
    """
    total_before = _count(connection)
    state = _read_state(connection)
    warnings: list[str] = []

    already_synced_today = (
        total_before > 0
        and bool(state.get("last_sync_at"))
        and state["last_sync_at"][:10] == dt.date.today().isoformat()
    )
    if already_synced_today:
        return SyncReport(
            total_before=total_before,
            inserted=0,
            total_after=total_before,
            latest_date=state.get("last_draw_date"),
            source=state.get("source") or "fdj",
            warnings=[],
        )

    source = state.get("source") or "fdj"
    imported = False

    # 1) Official archives online.
    if allow_network:
        try:
            records, warnings = fetch_all_draws()
            records = [record for record in records if record.draw_date >= FORMULA_START]
            if records:
                _import_records(connection, records)
                source = "fdj"
                imported = True
            elif total_before == 0:
                raise RuntimeError("aucun tirage retourné par la FDJ")
        except Exception as exc:  # noqa: BLE001 - try the next sources
            logger.warning("Import FDJ en ligne indisponible : %s", exc)
            warnings.append(f"Import FDJ en ligne indisponible : {exc}")

    # 2) Local file supplied by the operator (same official format).
    if not imported and local_source and Path(local_source).exists():
        try:
            records = load_from_path(local_source)
            records = [record for record in records if record.draw_date >= FORMULA_START]
            if records:
                _import_records(connection, records)
                source = "fdj"
                imported = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Fichier local illisible : %s", exc)
            warnings.append(f"Fichier local illisible : {exc}")

    # 3) Synthetic fallback.
    if not imported and total_before == 0:
        if not allow_fallback:
            raise RuntimeError(
                "Aucune source de tirages disponible et le repli simulé est désactivé."
            )
        _import_simulated(connection)
        source = "simulated"

    total_after = _count(connection)
    latest = connection.execute("SELECT MAX(draw_date) AS d FROM draws").fetchone()[0]
    _write_state(connection, source=source, total=total_after, latest=latest)

    return SyncReport(
        total_before=total_before,
        inserted=max(0, total_after - total_before),
        total_after=total_after,
        latest_date=latest,
        source=source,
        warnings=warnings,
    )


def init_db(
    db_path: str | Path | None = None,
    *,
    allow_network: bool = True,
    local_source: str | Path | None = None,
    allow_fallback: bool = True,
) -> SyncReport:
    """Creates the schema, then synchronises the history."""
    path = Path(db_path) if db_path else Path(current_app.config["DATABASE_PATH"])
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        connection.executescript(SCHEMA)
        connection.commit()
        return sync_draws(
            connection,
            allow_network=allow_network,
            local_source=local_source,
            allow_fallback=allow_fallback,
        )
    finally:
        connection.close()


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    report = init_db(
        app.config["DATABASE_PATH"],
        allow_network=bool(app.config.get("ALLOW_NETWORK_IMPORT", True)),
        local_source=app.config.get("LOCAL_DRAW_FILE"),
        allow_fallback=bool(app.config.get("ALLOW_SIMULATED_FALLBACK", True)),
    )
    app.extensions["draws_sync_report"] = dict(report)

    if report["source"] == "simulated":
        logger.warning(
            "SIMULATED history loaded (fallback): %s draws. "
            "Check the network connection to import the real FDJ data.",
            report["total_after"],
        )
    else:
        logger.info(
            "Real FDJ history: %s draws, latest draw %s",
            report["total_after"],
            report["latest_date"],
        )
