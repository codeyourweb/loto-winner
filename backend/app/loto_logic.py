"""Rules of the French LOTO: ranks, validation and winnings computation.

LOTO has **9 winning ranks**. Rank 1 is the jackpot (5 numbers + lucky number).
Rank 9 groups "1 number + lucky number" and "0 number + lucky number", both
refunded at €2.20.

Winnings are not averages: they come from the **real payout reports** published
by the FDJ for each draw.
"""

from __future__ import annotations

from .config import (
    CHANCE_MAX,
    MAX_RANK,
    PICK_COUNT,
    RANK_GAINS_FALLBACK,
    RANK_LABELS,
    TOTAL_NUMBERS,
)

# Maximum number of items accepted in the list supplied by the client.
MAX_INPUT_LENGTH = 64


def _is_plain_int(value) -> bool:
    """True only for a "plain" integer (neither boolean nor float)."""
    return isinstance(value, int) and not isinstance(value, bool)


class ValidationError(ValueError):
    """Client-side input error (returned as HTTP 400)."""


def validate_selection(numbers, chance, *, allow_incomplete: bool = False) -> tuple[list[int], int]:
    """Validates and normalises a played combination.

    Rejects any malformed input (unexpected types, booleans, floats, oversized
    lists…) so as to avoid 500 errors as well as resource abuse
    (OWASP A03:2021 — Injection).
    """
    if not isinstance(numbers, (list, tuple)):
        raise ValidationError("`numbers` doit être une liste de numéros.")

    if len(numbers) > MAX_INPUT_LENGTH:
        raise ValidationError("Trop de numéros fournis.")

    if any(not _is_plain_int(n) for n in numbers):
        raise ValidationError("Les numéros doivent être des entiers.")

    cleaned = sorted(set(numbers))

    if len(cleaned) != len(numbers):
        raise ValidationError("Les numéros doivent être distincts.")

    if not allow_incomplete and len(cleaned) != PICK_COUNT:
        raise ValidationError(f"Vous devez cocher exactement {PICK_COUNT} numéros.")

    if any(n < 1 or n > TOTAL_NUMBERS for n in cleaned):
        raise ValidationError(f"Les numéros doivent être compris entre 1 et {TOTAL_NUMBERS}.")

    if not _is_plain_int(chance):
        raise ValidationError("Le numéro chance doit être un entier.")

    if chance < 1 or chance > CHANCE_MAX:
        raise ValidationError(f"Le numéro chance doit être compris entre 1 et {CHANCE_MAX}.")

    return cleaned, chance


def rank_for(matches: int, chance_hit: bool) -> int | None:
    """Determines the winning rank, or ``None`` if the grid loses.

    Official LOTO ranks:
    ``1`` 5 n° + lucky · ``2`` 5 n° · ``3`` 4 n° + lucky · ``4`` 4 n° ·
    ``5`` 3 n° + lucky · ``6`` 3 n° · ``7`` 2 n° + lucky · ``8`` 2 n° ·
    ``9`` 1 n° + lucky ("0 n° + lucky" is refunded at the same amount).
    """
    if matches == 5:
        return 1 if chance_hit else 2
    if matches == 4:
        return 3 if chance_hit else 4
    if matches == 3:
        return 5 if chance_hit else 6
    if matches == 2:
        return 7 if chance_hit else 8
    if chance_hit:
        return 9
    return None


def gain_for_rank(
    rank: int | None,
    jackpot: float,
    *,
    reports: dict[int, float] | None = None,
    winners: dict[int, int] | None = None,
) -> float:
    """Returns the **real** win associated with a rank.

    The amount comes from the official report published for the draw in question.
    The FDJ publishes a report even without a winner (guaranteed amount, or a
    rolled-over jackpot): a present report is therefore always authoritative,
    including when ``winners == 0``.

    The ``RANK_GAINS_FALLBACK`` fallback is only a safety net for incomplete
    data. Inside the replayed window (9-rank formula, from 2017 onwards), every
    rank has an official report and it never triggers.
    """
    if rank is None:
        return 0.0

    reports = reports or {}
    winners = winners or {}

    report = reports.get(rank)
    if report:
        return float(report)

    # Report missing AND no winner: no amount was actually paid out.
    if winners.get(rank) == 0:
        return 0.0

    if rank == 1:
        return float(jackpot) if jackpot else 0.0

    return float(RANK_GAINS_FALLBACK.get(rank, 0.0))


def evaluate(
    numbers: list[int],
    chance: int,
    drawn: list[int],
    drawn_chance: int,
    *,
    jackpot: float = 0.0,
    reports: dict[int, float] | None = None,
    winners: dict[int, int] | None = None,
) -> tuple[int, int | None, float]:
    """Evaluates a grid against a draw. Returns ``(matches, rank, gain)``."""
    matches = len(set(numbers) & set(drawn))
    chance_hit = chance == drawn_chance
    rank = rank_for(matches, chance_hit)
    gain = gain_for_rank(rank, jackpot, reports=reports, winners=winners)
    return matches, rank, gain


def rank_rules() -> list[dict]:
    """Description of the ranks, used by the front end for display."""
    return [
        {
            "rank": rank,
            "label": RANK_LABELS[rank],
            "gain": None if rank == 1 else RANK_GAINS_FALLBACK[rank],
            "is_jackpot": rank == 1,
        }
        for rank in sorted(RANK_LABELS)
    ]


__all__ = [
    "MAX_RANK",
    "ValidationError",
    "evaluate",
    "gain_for_rank",
    "rank_for",
    "rank_rules",
    "validate_selection",
]
