"""Technical tests: FDJ import, robustness, API contract and data consistency."""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from app.config import FIXTURE_DRAW_FILE
from app.db import FORMULA_START, init_db
from app.fdj_importer import (
    DrawRecord,
    parse_archive,
    _parse_date,
    _parse_reports,
    _to_float,
)
from app.loto_logic import rank_for
from app.simulated_data import generate_simulated_draws


# ---------------------------------------------------------------------------
# Parsing of the official FDJ data
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("29/09/2025", date(2025, 9, 29)),
        ("20250929", date(2025, 9, 29)),
        ("06/10/2008", date(2008, 10, 6)),
    ],
)
def test_parse_date_accepts_fdj_formats(raw, expected):
    assert _parse_date(raw) == expected


def test_parse_date_rejects_garbage():
    assert _parse_date("n/a") is None
    assert _parse_date("") is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("23000000,00", 23_000_000.0),
        ("1 234,50", 1234.50),
        ("2,20", 2.20),
        ("0", 0.0),
        ("", 0.0),
    ],
)
def test_to_float_handles_french_amounts(raw, expected):
    assert _to_float(raw) == pytest.approx(expected)


def test_parse_reports_extracts_rang1_and_rangs_2_to_9():
    header = [
        "date_de_tirage", "nombre_de_gagnant_au_rang1", "rapport",
    ]
    index = {name: position for position, name in enumerate(header)}
    row = [
        "29/09/2025", "1", "23000000,00",
        "5", "39760,40", "57", "851,20", "460", "380,40",
        "2048", "51,00", "19499", "19,30", "29193", "10,00",
        "266617", "4,30", "384300", "2,20", "C 3359 3727",
    ]

    r1_report, rank_reports = _parse_reports(row, index)

    assert r1_report == pytest.approx(23_000_000.0)
    assert set(rank_reports) == set(range(2, 10))
    assert rank_reports[2] == (5, pytest.approx(39760.40))
    assert rank_reports[9] == (384300, pytest.approx(2.20))


def test_parse_reports_stops_at_winner_codes():
    """The winning LOTO codes must not be interpreted as amounts."""
    header = ["nombre_de_gagnant_au_rang1", "rapport"]
    index = {name: position for position, name in enumerate(header)}
    row = ["0", "0", "1", "100,00", "C 1234 5678"]
    r1_report, rank_reports = _parse_reports(row, index)
    # The first amount after rank 1 is the rank-1 report itself (0).
    assert r1_report == 0.0
    # Rank 2 (1 winner, €100) precedes the winning code that stops the parsing.
    assert rank_reports[2] == (1, pytest.approx(100.0))


def test_parse_archive_rejects_non_zip():
    with pytest.raises(Exception):
        parse_archive(b"not a zip", source_label="test")


def test_draw_record_as_row_and_rank_rows():
    record = DrawRecord(
        draw_date=date(2025, 9, 29),
        numbers=[5, 17, 27, 32, 44],
        chance=4,
        r1_winners=1,
        r1_report=23_000_000.0,
        rank_reports={2: (0, 39760.40), 9: (384300, 2.20)},
    )

    row = record.as_row()
    assert row["draw_date"] == "2025-09-29"
    assert (row["n1"], row["n5"]) == (5, 44)
    assert row["chance"] == 4
    assert row["r1_winners"] == 1

    ranks = record.rank_rows()
    assert [item["rank"] for item in ranks] == [2, 9]


# ---------------------------------------------------------------------------
# Synthetic history (fallback)
# ---------------------------------------------------------------------------


def test_simulated_history_is_deterministic():
    assert generate_simulated_draws(end=date(2020, 1, 1)) == generate_simulated_draws(
        end=date(2020, 1, 1)
    )


def test_simulated_history_respects_loto_rules():
    rows = generate_simulated_draws(end=date(2010, 1, 1))
    assert len(rows) > 100
    for row in rows:
        numbers = [row[f"n{i}"] for i in range(1, 6)]
        assert len(set(numbers)) == 5
        assert all(1 <= n <= 49 for n in numbers)
        assert 1 <= row["chance"] <= 10
        assert row["source"] == "simulated"


def test_simulated_history_starts_at_formula_change():
    rows = generate_simulated_draws(end=date(2008, 11, 1))
    assert rows[0]["draw_date"] >= FORMULA_START.isoformat()


# ---------------------------------------------------------------------------
# Payout scale and ranks (9 official ranks)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "matches,chance,expected",
    [
        (5, True, 1),
        (5, False, 2),
        (4, True, 3),
        (4, False, 4),
        (3, True, 5),
        (3, False, 6),
        (2, True, 7),
        (2, False, 8),
        (1, True, 9),   # refunded at the same rank as 1 no. + lucky number
        (1, False, None),
        (0, False, None),
        (0, False, None),
    ],
)
def test_rank_for(matches, chance, expected):
    assert rank_for(matches, chance) == expected


def test_no_tenth_rank_exists():
    """LOTO has only 9 ranks: no rank beyond that."""
    assert rank_for(0, False) is None


# ---------------------------------------------------------------------------
# Import en base
# ---------------------------------------------------------------------------


def test_init_db_without_network_uses_simulated_fallback(tmp_path):
    """Without network or local file, the simulated fallback takes over."""
    report = init_db(tmp_path / "offline.db", allow_network=False)
    assert report["source"] == "simulated"
    assert report["total_after"] > 0


def test_init_db_prefers_local_real_data(tmp_path):
    """An official local file takes precedence over the simulated fallback."""
    report = init_db(
        tmp_path / "local.db",
        allow_network=False,
        local_source=FIXTURE_DRAW_FILE,
        allow_fallback=False,
    )
    assert report["source"] == "fdj"
    assert report["total_after"] == 10


def test_sync_is_idempotent_offline(tmp_path):
    db_path = tmp_path / "idem.db"
    first = init_db(db_path, allow_network=False, local_source=FIXTURE_DRAW_FILE)
    second = init_db(db_path, allow_network=False, local_source=FIXTURE_DRAW_FILE)
    assert second["inserted"] == 0
    assert second["total_after"] == first["total_after"]


def test_draws_table_has_unique_dates(tmp_path):
    db_path = tmp_path / "unique.db"
    init_db(db_path, allow_network=False, local_source=FIXTURE_DRAW_FILE)
    connection = sqlite3.connect(db_path)
    total = connection.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
    distinct = connection.execute("SELECT COUNT(DISTINCT draw_date) FROM draws").fetchone()[0]
    connection.close()
    assert total == distinct


# ---------------------------------------------------------------------------
# Contrat JSON de l'API
# ---------------------------------------------------------------------------


def test_json_content_type_on_all_endpoints(client):
    for path in (
        "/",
        "/api/health",
        "/api/config",
        "/api/data-source",
        "/api/draws",
        "/api/jackpots",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert response.is_json


def test_simulation_response_has_stable_schema(client, valid_payload):
    summary = client.post("/api/simulate", json=valid_payload).get_json()["summary"]
    required = {
        "numbers",
        "chance",
        "net",
        "roi",
        "total_spent",
        "total_won",
        "total_draws",
        "stake_per_draw",
        "biggest_win",
        "win_rate",
        "first_draw",
        "last_draw",
        "simulation_start",
        "data_source",
    }
    assert required <= set(summary)


def test_numbers_in_response_are_sorted(client):
    summary = client.post(
        "/api/simulate",
        json={"numbers": [40, 3, 25, 7, 11], "chance": 4, "persist": False},
    ).get_json()["summary"]
    assert summary["numbers"] == sorted(summary["numbers"])


# ---------------------------------------------------------------------------
# Winnings: never an estimate, always a published report
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "numbers,chance",
    [
        ([2, 10, 16, 18, 42], 3),   # rang 3 (4 n° + chance)
        ([2, 10, 16, 18, 36], 3),   # rang 1 (5 n° + chance)
        ([3, 6, 15, 29, 43], 4),    # rang 1
        ([1, 2, 3, 4, 5], 7),       # rank 9 (refunded)
    ],
)
def test_every_gain_matches_an_official_report(client, numbers, chance):
    """Every replayed win is an FDJ report of the draw, never an estimated value.

    For each winning draw, the amount must match the published report of the
    rank in question (rank 1: jackpot at stake). The "floor" fallback must never
    be used inside the replayed window.
    """
    result = client.post(
        "/api/simulate", json={"numbers": numbers, "chance": chance, "persist": False}
    ).get_json()

    wins = [entry for entry in result["timeline"] if entry["rank"]]
    assert wins, "the grid must win at least one draw on the fixture"

    for entry in wins:
        detail = client.get(f"/api/draws/{entry['date']}").get_json()
        reports = {r["rank"]: r["report"] for r in detail["reports"]}

        if entry["rank"] == 1:
            # The jackpot at stake that evening: it is the real rank-1 win,
            # whether or not players claimed it (rolled-over amount).
            assert detail["jackpot"] > 0
            assert entry["gain"] == pytest.approx(detail["jackpot"], abs=0.01)
        else:
            assert entry["rank"] in reports
            assert reports[entry["rank"]] > 0
            assert entry["gain"] == pytest.approx(reports[entry["rank"]], abs=0.01)


def test_rank_reports_are_complete_in_the_simulated_window(client):
    """Inside the replayed window, all 8 winning ranks have an official report."""
    draws = client.get("/api/draws?limit=500").get_json()["draws"]
    assert draws

    for draw in draws:
        detail = client.get(f"/api/draws/{draw['date']}").get_json()
        assert [r["rank"] for r in detail["reports"]] == list(range(2, 10))
        for report in detail["reports"]:
            assert report["report"] > 0


def test_roi_formula_matches_definition(client, valid_payload):
    summary = client.post("/api/simulate", json=valid_payload).get_json()["summary"]
    assert summary["roi"] == pytest.approx(
        summary["net"] / summary["total_spent"] * 100, abs=0.02
    )


def test_timeline_entries_are_serializable_primitives(client, valid_payload):
    timeline = client.post("/api/simulate", json=valid_payload).get_json()["timeline"]
    allowed = (str, int, float, bool, type(None))
    for entry in timeline[:50]:
        for value in entry.values():
            assert isinstance(value, allowed)


def test_unknown_route_returns_json_404(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.is_json


def test_wrong_method_returns_405(client):
    assert client.get("/api/simulate").status_code == 405


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


def test_simulation_completes_under_time_budget(client, valid_payload):
    import time

    start = time.perf_counter()
    response = client.post("/api/simulate", json=valid_payload)
    elapsed = time.perf_counter() - start
    assert response.status_code == 200
    assert elapsed < 3.0


def test_pdf_document_structure(client, valid_payload):
    data = client.post("/api/simulate/pdf", json=valid_payload).data
    assert data.startswith(b"%PDF-")
    assert data.rstrip().endswith(b"%%EOF")
    assert len(data) > 3_000
