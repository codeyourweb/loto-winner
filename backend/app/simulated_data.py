"""**Synthetic** fallback history.

Used only when importing the real FDJ data is impossible (no network, service
unavailable) and the database is empty. The draws produced here are clearly
tagged ``source = 'simulated'`` so they are never mistaken for official results.

The generator is deterministic (fixed seed): the same sequence is produced on
every run.
"""

from __future__ import annotations

import datetime as dt
import random

from .config import CHANCE_MAX, PICK_COUNT, TOTAL_NUMBERS

DRAW_WEEKDAYS = (0, 2, 5)  # Monday, Wednesday, Saturday
START_DATE = dt.date(2008, 10, 6)
DEFAULT_SEED = 20261005

# Probability that at least one player wins the jackpot.
JACKPOT_WIN_PROBABILITY = 0.14
DEFAULT_JACKPOT = 2_000_000

# Average fallback reports per rank (used offline only).
FALLBACK_REPORTS = {
    2: 20_000.0,
    3: 1_000.0,
    4: 400.0,
    5: 50.0,
    6: 20.0,
    7: 10.0,
    8: 5.0,
    9: 2.20,
}


def _iter_dates(start: dt.date, end: dt.date):
    current = start
    while current <= end:
        if current.weekday() in DRAW_WEEKDAYS:
            yield current
        current += dt.timedelta(days=1)


def generate_simulated_draws(
    seed: int = DEFAULT_SEED, *, end: dt.date | None = None
) -> list[dict]:
    """Returns a list of synthetic draws ready for the database."""
    end = end or dt.date.today()
    rng = random.Random(seed)
    rows: list[dict] = []
    jackpot = float(DEFAULT_JACKPOT)

    for date in _iter_dates(START_DATE, end):
        numbers = sorted(rng.sample(range(1, TOTAL_NUMBERS + 1), PICK_COUNT))
        chance = rng.randint(1, CHANCE_MAX)
        current_jackpot = jackpot
        won = rng.random() < JACKPOT_WIN_PROBABILITY

        if won:
            jackpot = float(DEFAULT_JACKPOT)
        else:
            jackpot += rng.randint(200_000, 1_600_000)

        rows.append(
            {
                "draw_date": date.isoformat(),
                "n1": numbers[0],
                "n2": numbers[1],
                "n3": numbers[2],
                "n4": numbers[3],
                "n5": numbers[4],
                "chance": chance,
                "r1_winners": 1 if won else 0,
                "r1_report": current_jackpot if won else 0.0,
                "source": "simulated",
            }
        )

    return rows
