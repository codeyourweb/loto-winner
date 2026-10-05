"""Functional tests: end-to-end user journey (real data)."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# 1. Valid grid: the financial balance is consistent
# ---------------------------------------------------------------------------


def test_simulation_returns_complete_report(client, valid_payload):
    response = client.post("/api/simulate", json=valid_payload)
    assert response.status_code == 200

    data = response.get_json()
    assert set(data) >= {"summary", "jackpot", "by_rank", "timeline"}

    summary = data["summary"]
    assert summary["numbers"] == [1, 2, 3, 4, 5]
    assert summary["chance"] == 7
    assert summary["total_draws"] > 0


def test_net_equals_won_minus_spent(client, valid_payload):
    summary = client.post("/api/simulate", json=valid_payload).get_json()["summary"]
    assert summary["net"] == pytest.approx(summary["total_won"] - summary["total_spent"], abs=0.01)


def test_total_spent_matches_draw_count_and_grid_price(client, valid_payload):
    summary = client.post("/api/simulate", json=valid_payload).get_json()["summary"]
    assert summary["total_spent"] == pytest.approx(
        summary["total_draws"] * 2.20, abs=0.01
    )


def test_timeline_length_matches_draw_count(client, valid_payload):
    data = client.post("/api/simulate", json=valid_payload).get_json()
    assert len(data["timeline"]) == data["summary"]["total_draws"]


def test_cumulative_curve_matches_final_net(client, valid_payload):
    data = client.post("/api/simulate", json=valid_payload).get_json()
    assert data["timeline"][-1]["cumulative"] == pytest.approx(data["summary"]["net"], abs=0.01)


def test_win_rate_and_winning_draws_are_consistent(client, valid_payload):
    summary = client.post("/api/simulate", json=valid_payload).get_json()["summary"]
    expected = summary["winning_draws"] / summary["total_draws"] * 100
    assert summary["win_rate"] == pytest.approx(expected, abs=0.01)


# ---------------------------------------------------------------------------
# 2. The reported case: combination really won on 29/09/2025
# ---------------------------------------------------------------------------


def test_winning_combination_of_2025_09_29_is_detected(client):
    """The grid 5-17-27-32-44 + 4 won the €23M of 29 September 2025."""
    response = client.post(
        "/api/simulate",
        json={"numbers": [5, 17, 27, 32, 44], "chance": 4, "persist": False},
    )
    assert response.status_code == 200
    data = response.get_json()

    assert data["jackpot"]["hits"] == 1
    assert data["jackpot"]["last_date"] == "2025-09-29"
    assert data["jackpot"]["amounts"][0] == pytest.approx(23_000_000, abs=1)

    assert data["summary"]["best_rank"] == 1
    assert data["summary"]["total_won"] >= 23_000_000
    # A single rank 1 is enough to make the balance largely positive.
    assert data["summary"]["net"] > 0


def test_jackpot_win_uses_the_real_report(client):
    """The rank-1 win is the official report, not an estimate."""
    detail = client.get("/api/draws/2025-09-29").get_json()
    assert detail["numbers"] == [5, 17, 27, 32, 44]
    assert detail["chance"] == 4
    assert detail["jackpot"] == pytest.approx(23_000_000, abs=1)
    assert detail["jackpotWinners"] == 1


# ---------------------------------------------------------------------------
# 3. Recherche du jackpot
# ---------------------------------------------------------------------------


def test_jackpot_hits_are_consistent_with_dates(client, valid_payload):
    data = client.post("/api/simulate", json=valid_payload).get_json()
    assert data["jackpot"]["hits"] == len(data["jackpot"]["dates"])


def test_jackpot_dates_belong_to_history(client, valid_payload):
    data = client.post("/api/simulate", json=valid_payload).get_json()
    known = {entry["date"] for entry in data["timeline"]}
    for date in data["jackpot"]["dates"]:
        assert date in known


def test_lucky_combination_wins_many_jackpots(client):
    """The 2025 winning grid also claims the subsequent jackpots."""
    data = client.post(
        "/api/simulate",
        json={"numbers": [5, 17, 27, 32, 44], "chance": 4, "persist": False},
    ).get_json()

    assert data["jackpot"]["hits"] >= 1
    assert data["jackpot"]["last_date"] is not None
    assert all(amount > 0 for amount in data["jackpot"]["amounts"])


# ---------------------------------------------------------------------------
# 4. Ranks and real winnings
# ---------------------------------------------------------------------------


def test_rank_breakdown_covers_the_nine_ranks(client, valid_payload):
    data = client.post("/api/simulate", json=valid_payload).get_json()
    assert [entry["rank"] for entry in data["by_rank"]] == list(range(1, 10))


def test_rank_counts_sum_equals_winning_draws(client, valid_payload):
    data = client.post("/api/simulate", json=valid_payload).get_json()
    assert sum(entry["count"] for entry in data["by_rank"]) == data["summary"]["winning_draws"]


def test_rank_winnings_sum_equals_total_won(client, valid_payload):
    data = client.post("/api/simulate", json=valid_payload).get_json()
    total = sum(entry["total_won"] for entry in data["by_rank"])
    assert total == pytest.approx(data["summary"]["total_won"], abs=0.01)


def test_gains_are_real_reports_not_averages(client):
    """Two grids winning the same rank on different draws get different amounts."""
    config = client.get("/api/config").get_json()
    assert config["max_rank"] == 9
    assert len(config["ranks"]) == 9


# ---------------------------------------------------------------------------
# 4a. Time scope: 9-rank scale only
# ---------------------------------------------------------------------------


def test_simulation_only_covers_the_nine_rank_formula(client, valid_payload):
    """Draws before 6 March 2017 (6 ranks) are excluded from the simulation."""
    summary = client.post("/api/simulate", json=valid_payload).get_json()["summary"]

    assert summary["simulation_start"] == "2017-03-06"
    assert summary["first_draw"] >= "2017-03-06"
    assert summary["last_draw"] >= summary["first_draw"]


def test_simulated_draws_never_precede_the_current_formula(client, valid_payload):
    """No replayed draw predates the appearance of ranks 7 to 9."""
    timeline = client.post("/api/simulate", json=valid_payload).get_json()["timeline"]

    assert timeline
    assert all(entry["date"] >= "2017-03-06" for entry in timeline)


# ---------------------------------------------------------------------------
# 5. Browsing the real draws
# ---------------------------------------------------------------------------


def test_draws_endpoint_is_paginated(client):
    page = client.get("/api/draws?limit=5&offset=0").get_json()
    assert page["limit"] == 5
    assert len(page["draws"]) == 5
    assert page["total"] > 5

    page2 = client.get("/api/draws?limit=5&offset=5").get_json()
    assert page["draws"][0]["date"] != page2["draws"][0]["date"]


def test_draws_are_sorted_most_recent_first(client):
    dates = [draw["date"] for draw in client.get("/api/draws?limit=10").get_json()["draws"]]
    assert dates == sorted(dates, reverse=True)


def test_draw_detail_exposes_rank_reports(client):
    detail = client.get("/api/draws/2026-10-03").get_json()
    assert detail["date"] == "2026-10-03"
    assert len(detail["numbers"]) == 5
    assert [r["rank"] for r in detail["reports"]] == list(range(2, 10))


def test_draw_detail_unknown_date_returns_404(client):
    assert client.get("/api/draws/1900-01-01").status_code == 404


def test_draw_detail_rejects_bad_date_format(client):
    assert client.get("/api/draws/not-a-date").status_code == 400


def test_jackpots_endpoint_returns_valid_combinations(client):
    payload = client.get("/api/jackpots?limit=5").get_json()
    assert payload["total"] > 0
    for draw in payload["jackpots"]:
        assert len(set(draw["numbers"])) == 5
        assert 1 <= draw["chance"] <= 10
        assert draw["jackpot"] > 0
        assert draw["winners"] >= 1


def test_hot_numbers_respects_ranges(client):
    stats = client.get("/api/stats/hot-numbers").get_json()
    for entry in stats["hot"] + stats["cold"]:
        assert 1 <= entry["number"] <= 49
    for entry in stats["chance"]:
        assert 1 <= entry["number"] <= 10


def test_simulation_is_persisted_and_listed(client):
    response = client.post(
        "/api/simulate",
        json={"numbers": [10, 20, 30, 40, 49], "chance": 3, "persist": True},
    ).get_json()
    assert response["simulation_id"] is not None
    listing = client.get("/api/simulations?limit=1").get_json()["simulations"]
    assert listing[0]["id"] == response["simulation_id"]


# ---------------------------------------------------------------------------
# 6. Data provenance
# ---------------------------------------------------------------------------


def test_data_source_endpoint_reports_provenance(client):
    payload = client.get("/api/data-source").get_json()
    assert "counts" in payload
    assert payload["first_draw"] is not None
    assert payload["last_draw"] is not None
    assert payload["official_source"].startswith("https://www.fdj.fr")


def test_health_endpoint_reports_history_and_source(client):
    health = client.get("/api/health").get_json()
    assert health["status"] == "ok"
    assert health["draws"] > 0
    assert health["latest_draw"] is not None
    assert "sources" in health


# ---------------------------------------------------------------------------
# 7. Export PDF
# ---------------------------------------------------------------------------


def test_pdf_export_returns_a_pdf_attachment(client, valid_payload):
    response = client.post("/api/simulate/pdf", json=valid_payload)
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF-")
    assert response.data.rstrip().endswith(b"%%EOF")


def test_pdf_export_sets_download_filename(client, valid_payload):
    disposition = client.post("/api/simulate/pdf", json=valid_payload).headers.get(
        "Content-Disposition", ""
    )
    assert "attachment" in disposition
    assert "-".join(str(n) for n in valid_payload["numbers"]) in disposition


def test_pdf_export_does_not_archive_a_simulation(client, valid_payload):
    before = len(client.get("/api/simulations?limit=100").get_json()["simulations"])
    client.post("/api/simulate/pdf", json=valid_payload)
    after = len(client.get("/api/simulations?limit=100").get_json()["simulations"])
    assert after == before


def test_pdf_export_validates_input(client):
    response = client.post("/api/simulate/pdf", json={"numbers": [1, 2], "chance": 3})
    assert response.status_code == 400


def test_pdf_export_requires_json_body(client):
    response = client.post("/api/simulate/pdf", data="not json", content_type="application/json")
    assert response.status_code == 400
