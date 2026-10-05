"""Endpoints of the Loto Winner API (real FDJ data)."""

from __future__ import annotations

import datetime as dt

from flask import Blueprint, Response, current_app, jsonify, request

from .config import CHANCE_MAX, GRID_PRICE, MAX_RANK, PICK_COUNT, TOTAL_NUMBERS
from .db import get_db, init_db
from .extensions import limiter
from .loto_logic import ValidationError, rank_rules
from .pdf_report import build_simulation_pdf
from .security import parse_int_arg
from .simulation_service import recent_simulations, run_simulation, save_simulation

api = Blueprint("api", __name__, url_prefix="/api")


@api.errorhandler(ValidationError)
def handle_validation_error(error: ValidationError):
    """Every invalid input returns an explicit 400, never a 500."""
    return jsonify(error=str(error)), 400


def _sync_info() -> dict:
    return dict(current_app.extensions.get("draws_sync_report", {}))


@api.get("/health")
def health():
    row = get_db().execute(
        "SELECT COUNT(*) AS c, MAX(draw_date) AS latest FROM draws"
    ).fetchone()
    sources = [
        {"source": r["source"], "count": r["c"]}
        for r in get_db()
        .execute("SELECT source, COUNT(*) AS c FROM draws GROUP BY source")
        .fetchall()
    ]
    return jsonify(
        status="ok",
        draws=row["c"],
        latest_draw=row["latest"],
        sources=sources,
        data_source=_sync_info().get("source"),
        draws_added_at_startup=_sync_info().get("inserted", 0),
    )


@api.get("/data-source")
def data_source():
    """Provenance and freshness of the data (real or fallback)."""
    db = get_db()
    counts = {
        r["source"]: r["c"]
        for r in db.execute(
            "SELECT source, COUNT(*) AS c FROM draws GROUP BY source"
        ).fetchall()
    }
    row = db.execute(
        "SELECT MIN(draw_date) AS first, MAX(draw_date) AS last FROM draws"
    ).fetchone()
    state = db.execute("SELECT * FROM sync_state WHERE id = 1").fetchone()

    return jsonify(
        is_real_data=counts.get("fdj", 0) > 0 and counts.get("simulated", 0) == 0,
        counts=counts,
        first_draw=row["first"],
        last_draw=row["last"],
        last_sync_at=state["last_sync_at"] if state else None,
        official_source="https://www.fdj.fr/jeux-de-tirage/loto/historique",
    )


@api.post("/admin/sync")
@limiter.limit(lambda: current_app.config.get("RATELIMIT_ADMIN", "5 per minute"))
def admin_sync():
    """Forces a re-synchronisation with the official FDJ archives."""
    db = get_db()
    # Resets the timestamp to allow a new import.
    db.execute("UPDATE sync_state SET last_sync_at = NULL WHERE id = 1")
    db.commit()

    report = init_db(current_app.config["DATABASE_PATH"], allow_network=True)
    current_app.extensions["draws_sync_report"] = dict(report)
    return jsonify(
        inserted=report["inserted"],
        total=report["total_after"],
        latest_draw=report["latest_date"],
        source=report["source"],
        warnings=report["warnings"],
    )


@api.get("/config")
def get_config():
    """Game rules and indicative payout scale."""
    rules = _sync_info()
    return jsonify(
        total_numbers=TOTAL_NUMBERS,
        pick_count=PICK_COUNT,
        chance_max=CHANCE_MAX,
        grid_price=GRID_PRICE,
        max_rank=MAX_RANK,
        ranks=rank_rules(),
        data_source=rules.get("source"),
        draws_available=rules.get("total_after", 0),
    )


@api.get("/draws")
def get_draws():
    """Paginated list of real draws (most recent first)."""
    limit = parse_int_arg(
        request.args.get("limit"), name="limit", default=50, minimum=1, maximum=500
    )
    offset = parse_int_arg(
        request.args.get("offset"), name="offset", default=0, minimum=0, maximum=1_000_000
    )

    db = get_db()
    total = db.execute("SELECT COUNT(*) AS c FROM draws").fetchone()["c"]
    rows = db.execute(
        """
        SELECT draw_date, n1, n2, n3, n4, n5, chance, r1_winners, r1_report, source
        FROM draws ORDER BY draw_date DESC LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()

    draws = [
        {
            "date": row["draw_date"],
            "numbers": [row["n1"], row["n2"], row["n3"], row["n4"], row["n5"]],
            "chance": row["chance"],
            "jackpot": row["r1_report"],
            "jackpotWinners": row["r1_winners"],
            "source": row["source"],
        }
        for row in rows
    ]
    return jsonify(total=total, limit=limit, offset=offset, draws=draws)


@api.get("/draws/<draw_date>")
def get_draw(draw_date: str):
    """Detail of a draw: numbers and real per-rank reports."""
    try:
        dt.date.fromisoformat(draw_date)
    except ValueError:
        raise ValidationError("Date attendue au format AAAA-MM-JJ.") from None

    db = get_db()
    row = db.execute("SELECT * FROM draws WHERE draw_date = ?", (draw_date,)).fetchone()
    if row is None:
        return jsonify(error="Tirage introuvable."), 404

    reports = [
        {
            "rank": item["rank"],
            "winners": item["winners"],
            "report": item["report"],
        }
        for item in db.execute(
            "SELECT rank, winners, report FROM rank_reports WHERE draw_date = ? ORDER BY rank",
            (draw_date,),
        ).fetchall()
    ]

    return jsonify(
        date=row["draw_date"],
        numbers=[row["n1"], row["n2"], row["n3"], row["n4"], row["n5"]],
        chance=row["chance"],
        jackpot=row["r1_report"],
        jackpotWinners=row["r1_winners"],
        source=row["source"],
        reports=reports,
    )


@api.get("/jackpots")
def get_jackpots():
    """Draws where the jackpot (rank 1) was won."""
    limit = parse_int_arg(
        request.args.get("limit"), name="limit", default=25, minimum=1, maximum=200
    )
    db = get_db()
    total = db.execute(
        "SELECT COUNT(*) AS c FROM draws WHERE r1_winners > 0"
    ).fetchone()["c"]
    rows = db.execute(
        """
        SELECT draw_date, n1, n2, n3, n4, n5, chance, r1_winners, r1_report
        FROM draws WHERE r1_winners > 0
        ORDER BY draw_date DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()

    return jsonify(
        total=total,
        jackpots=[
            {
                "date": row["draw_date"],
                "numbers": [row["n1"], row["n2"], row["n3"], row["n4"], row["n5"]],
                "chance": row["chance"],
                "jackpot": row["r1_report"],
                "winners": row["r1_winners"],
            }
            for row in rows
        ],
    )


@api.post("/simulate")
@limiter.limit(lambda: current_app.config.get("RATELIMIT_SIMULATE", "30 per minute"))
def simulate():
    """Replays a combination over the entire real history."""
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify(error="Corps JSON attendu."), 400
    if not isinstance(payload, dict):
        return jsonify(error="Corps JSON invalide (objet attendu)."), 400

    result = run_simulation(payload.get("numbers"), payload.get("chance"))

    if payload.get("persist", True) is not False:
        try:
            result["simulation_id"] = save_simulation(result)
        except Exception:  # noqa: BLE001 - archiving must not break the response
            result["simulation_id"] = None

    return jsonify(result)


@api.post("/simulate/pdf")
@limiter.limit(lambda: current_app.config.get("RATELIMIT_PDF", "20 per minute"))
def simulate_pdf():
    """Generates the PDF report of a simulation (same inputs as /simulate)."""
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify(error="Corps JSON attendu."), 400
    if not isinstance(payload, dict):
        return jsonify(error="Corps JSON invalide (objet attendu)."), 400

    result = run_simulation(payload.get("numbers"), payload.get("chance"))
    pdf_bytes = build_simulation_pdf(result)

    numbers = "-".join(str(n) for n in result["summary"]["numbers"])
    filename = f"loto-winner_{numbers}_chance-{result['summary']['chance']}.pdf"

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
            "Cache-Control": "no-store",
        },
    )


@api.get("/simulations")
def list_simulations():
    limit = parse_int_arg(
        request.args.get("limit"), name="limit", default=10, minimum=1, maximum=100
    )
    return jsonify(simulations=recent_simulations(limit))


@api.get("/stats/hot-numbers")
def hot_numbers():
    """Most and least frequent numbers of the real history."""
    db = get_db()
    counts = {n: 0 for n in range(1, TOTAL_NUMBERS + 1)}
    chance_counts = {n: 0 for n in range(1, CHANCE_MAX + 1)}

    rows = db.execute("SELECT n1, n2, n3, n4, n5, chance FROM draws").fetchall()
    for row in rows:
        for key in ("n1", "n2", "n3", "n4", "n5"):
            counts[row[key]] += 1
        chance_counts[row["chance"]] += 1

    ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    rarest = sorted(counts.items(), key=lambda item: item[1])

    return jsonify(
        total_draws=len(rows),
        hot=[{"number": n, "count": c} for n, c in ordered[:10]],
        cold=[{"number": n, "count": c} for n, c in rarest[:10]],
        chance=[{"number": n, "count": c} for n, c in sorted(chance_counts.items())],
    )
