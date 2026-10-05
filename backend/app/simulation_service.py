"""Simulation engine: replays a grid over the **real** history of draws.

Unlike an "average" simulation, each win comes from the **official report** of
the draw in question (``rank_reports`` column), which yields exact amounts —
including the jackpot actually at stake.

Only draws of the **current formula** (9 ranks, from 6 March 2017) are replayed:
earlier draws followed a 6-rank scale for which the FDJ publishes no report at
ranks 7 to 9. Including them would produce estimated winnings instead of the
real reports.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .config import GRID_PRICE, MAX_RANK, RANK_LABELS, SIMULATION_START
from .db import get_db
from .loto_logic import evaluate, validate_selection

FETCH_DRAWS_SQL = """
SELECT draw_date, n1, n2, n3, n4, n5, chance, r1_winners, r1_report, source
FROM draws
WHERE draw_date >= ?
ORDER BY draw_date ASC
"""

FETCH_RANKS_SQL = """
SELECT draw_date, rank, winners, report FROM rank_reports
WHERE draw_date >= ?
"""


def _load_history(
    start: str,
) -> tuple[list[dict], dict[str, dict[int, tuple[int, float]]]]:
    """Loads the draws of the current formula and their per-rank reports."""
    rows = get_db().execute(FETCH_DRAWS_SQL, (start,)).fetchall()
    draws = [dict(row) for row in rows]

    reports: dict[str, dict[int, tuple[int, float]]] = {}
    for row in get_db().execute(FETCH_RANKS_SQL, (start,)).fetchall():
        reports.setdefault(row["draw_date"], {})[row["rank"]] = (
            row["winners"],
            row["report"],
        )

    return draws, reports


def run_simulation(numbers, chance) -> dict:
    """Replays the combination on every real draw and aggregates the results."""
    cleaned, chance_value = validate_selection(numbers, chance)

    start = SIMULATION_START.isoformat()
    draws, all_reports = _load_history(start)
    if not draws:
        return {
            "summary": {
                "total_draws": 0,
                "numbers": cleaned,
                "chance": chance_value,
                "simulation_start": start,
            },
            "timeline": [],
            "by_rank": [],
            "jackpot": {"hits": 0, "dates": [], "amounts": []},
        }

    total_spent = 0.0
    total_won = 0.0
    cumulative = 0.0
    timeline: list[dict] = []
    rank_counts: dict[int, int] = {rank: 0 for rank in range(1, MAX_RANK + 1)}
    rank_winnings: dict[int, float] = {rank: 0.0 for rank in range(1, MAX_RANK + 1)}

    jackpot_dates: list[str] = []
    jackpot_amounts: list[float] = []
    best_rank: int | None = None
    best_rank_date: str | None = None
    best_rank_numbers: list[int] | None = None
    biggest_win = 0.0

    drought = 0
    longest_drought = 0

    for draw in draws:
        drawn = [draw["n1"], draw["n2"], draw["n3"], draw["n4"], draw["n5"]]
        date = draw["draw_date"]
        day_reports = all_reports.get(date, {})
        winners = {rank: pair[0] for rank, pair in day_reports.items()}
        reports = {rank: pair[1] for rank, pair in day_reports.items()}

        matches, rank, gain = evaluate(
            cleaned,
            chance_value,
            drawn,
            draw["chance"],
            jackpot=draw["r1_report"],
            reports=reports,
            winners=winners,
        )

        total_spent += GRID_PRICE
        total_won += gain
        cumulative = total_won - total_spent

        if rank is not None:
            rank_counts[rank] += 1
            rank_winnings[rank] += gain

        is_jackpot = rank == 1
        if is_jackpot:
            jackpot_dates.append(date)
            jackpot_amounts.append(gain)

        if rank is not None and (best_rank is None or rank < best_rank):
            best_rank = rank
            best_rank_date = date
            best_rank_numbers = drawn

        biggest_win = max(biggest_win, gain)

        if is_jackpot:
            drought = 0
        else:
            drought += 1
            longest_drought = max(longest_drought, drought)

        timeline.append(
            {
                "date": date,
                "matches": matches,
                "chance": draw["chance"],
                "rank": rank,
                "gain": round(gain, 2),
                "cumulative": round(cumulative, 2),
                "isJackpot": is_jackpot,
            }
        )

    total_draws = len(draws)
    by_rank = [
        {
            "rank": rank,
            "label": RANK_LABELS[rank],
            "count": rank_counts[rank],
            "total_won": round(rank_winnings[rank], 2),
        }
        for rank in range(1, MAX_RANK + 1)
    ]

    net = total_won - total_spent
    winning_draws = sum(rank_counts.values())
    source = draws[0].get("source", "fdj")

    summary = {
        "numbers": cleaned,
        "chance": chance_value,
        "stake_per_draw": round(GRID_PRICE, 2),
        "total_draws": total_draws,
        "total_spent": round(total_spent, 2),
        "total_won": round(total_won, 2),
        "net": round(net, 2),
        "roi": round((net / total_spent) * 100, 2) if total_spent else 0.0,
        "winning_draws": winning_draws,
        "win_rate": round(winning_draws / total_draws * 100, 2) if total_draws else 0.0,
        "biggest_win": round(biggest_win, 2),
        "best_rank": best_rank,
        "best_rank_label": RANK_LABELS.get(best_rank) if best_rank else None,
        "best_rank_date": best_rank_date,
        "best_rank_numbers": best_rank_numbers,
        "first_draw": draws[0]["draw_date"],
        "last_draw": draws[-1]["draw_date"],
        "simulation_start": start,
        "data_source": source,
    }

    jackpot = {
        "hits": len(jackpot_dates),
        "dates": jackpot_dates,
        "amounts": [round(amount, 2) for amount in jackpot_amounts],
        "last_date": jackpot_dates[-1] if jackpot_dates else None,
        "first_date": jackpot_dates[0] if jackpot_dates else None,
        "longest_drought_draws": longest_drought,
        "current_drought_draws": drought,
    }

    return {
        "summary": summary,
        "jackpot": jackpot,
        "by_rank": by_rank,
        "timeline": timeline,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def save_simulation(result: dict) -> int:
    """Archives a simulation in the database and returns its identifier."""
    summary = result["summary"]
    cursor = get_db().execute(
        """
        INSERT INTO simulations (
            created_at, numbers, chance, total_spent, total_won, net,
            best_rank, jackpot_hits
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            ",".join(str(n) for n in summary["numbers"]),
            summary["chance"],
            summary["total_spent"],
            summary["total_won"],
            summary["net"],
            summary.get("best_rank"),
            result["jackpot"]["hits"],
        ),
    )
    get_db().commit()
    return int(cursor.lastrowid)


def recent_simulations(limit: int = 10) -> list[dict]:
    rows = get_db().execute(
        "SELECT * FROM simulations ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(row) for row in rows]
