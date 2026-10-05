"""Central configuration of the Loto Winner application.

Sensitive or environment-dependent values are read from environment variables
(OWASP A05:2021 — Security Misconfiguration) instead of being hard-coded.
"""

import datetime as dt
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Official FDJ extract used by the test suite (no network access).
FIXTURE_DRAW_FILE = BASE_DIR / "tests" / "fixtures" / "fdj_sample.csv"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASE_PATH = Path(os.environ.get("LOTO_DB_PATH", BASE_DIR / "loto.db"))

# ---------------------------------------------------------------------------
# LOTO game rules (La Française des Jeux)
# ---------------------------------------------------------------------------
TOTAL_NUMBERS = 49          # numbers from 1 to 49
PICK_COUNT = 5              # 5 numbers to pick
CHANCE_MAX = 10             # lucky number from 1 to 10

GRID_PRICE = 2.20           # price of a single grid (€)

# LOTO has 9 winning ranks. Rank 9 groups "1 number + lucky number" and
# "0 number + lucky number", both refunded at €2.20.
MAX_RANK = 9

# Label of each rank, as displayed by the FDJ.
RANK_LABELS = {
    1: "5 numéros + n° chance (cagnotte)",
    2: "5 numéros",
    3: "4 numéros + n° chance",
    4: "4 numéros",
    5: "3 numéros + n° chance",
    6: "3 numéros",
    7: "2 numéros + n° chance",
    8: "2 numéros",
    9: "1 numéro + n° chance (remboursé)",
}

# "Floor" amounts used only when a draw's real report is missing while winners
# do exist (data anomaly).
RANK_GAINS_FALLBACK = {
    2: 20_000.0,
    3: 1_000.0,
    4: 400.0,
    5: 50.0,
    6: 20.0,
    7: 10.0,
    8: 5.0,
    9: 2.20,
}

RANK_GAINS = RANK_GAINS_FALLBACK  # internal compatibility alias

# First draw of the **current** LOTO formula, with 9 winning ranks. Before that
# date the game had only 6 ranks: ranks 7 to 9 did not exist and the FDJ
# therefore publishes no report for them. Including them in the simulation
# would skew the winnings ("floor" values), so they are excluded.
SIMULATION_START = dt.date(2017, 3, 6)


def _csv_env(name: str, default: str) -> list[str]:
    """Reads a comma-separated list from an environment variable."""
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class Config:
    """Development configuration (safe but permissive values)."""

    ENV = os.environ.get("FLASK_ENV", "development")
    DEBUG = False
    TESTING = False

    # Session key: in production, LOTO_SECRET_KEY must be provided.
    SECRET_KEY = os.environ.get("LOTO_SECRET_KEY")

    DATABASE_PATH = str(DATABASE_PATH)
    SIMULATION_START = SIMULATION_START.isoformat()
    JSON_SORT_KEYS = False

    # --- Input limits (OWASP A04:2021 Insecure Design) -----------------------
    MAX_CONTENT_LENGTH = 64 * 1024          # 64 KiB: rejects large bodies

    # --- CORS (OWASP A05:2021) ------------------------------------------------
    # Origin allowlist. Never "*" in production.
    CORS_ORIGINS = _csv_env(
        "LOTO_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )

    # --- Rate limiting (OWASP A04 / API4:2023) -------------------------------
    RATELIMIT_ENABLED = os.environ.get("LOTO_RATELIMIT", "1") != "0"
    RATELIMIT_DEFAULT = "300 per minute"
    RATELIMIT_SIMULATE = "30 per minute"
    RATELIMIT_PDF = "20 per minute"
    RATELIMIT_ADMIN = "5 per minute"
    RATELIMIT_HEADERS_ENABLED = True

    # --- Import of real data (FDJ) -------------------------------------------
    # If the import fails and the database is empty, should a simulated history
    # be generated so the application stays usable offline?
    ALLOW_SIMULATED_FALLBACK = os.environ.get("LOTO_ALLOW_FALLBACK", "1") != "0"

    # --- Cookies / sessions (OWASP A07:2021) ---------------------------------
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # enabled in ProductionConfig

    # HSTS only when the server really sits behind TLS.
    SECURITY_HSTS = False

    # --- Miscellaneous -------------------------------------------------------
    PROPAGATE_EXCEPTIONS = False

    GRID_PRICE = GRID_PRICE
    MAX_RANK = MAX_RANK
    RANK_GAINS = RANK_GAINS
    RANK_GAINS_FALLBACK = RANK_GAINS_FALLBACK
    RANK_LABELS = RANK_LABELS
    TOTAL_NUMBERS = TOTAL_NUMBERS
    PICK_COUNT = PICK_COUNT
    CHANCE_MAX = CHANCE_MAX


class ProductionConfig(Config):
    """Production configuration: hardened, no weak default value."""

    ENV = "production"
    DEBUG = False
    TESTING = False

    SESSION_COOKIE_SECURE = True
    SECURITY_HSTS = True

    # In production, the key MUST be provided through the environment.
    SECRET_KEY = os.environ.get("LOTO_SECRET_KEY")

    # The origin list MUST be provided explicitly.
    CORS_ORIGINS = _csv_env("LOTO_CORS_ORIGINS", "")


class TestConfig(Config):
    """Configuration used by the test suite."""

    TESTING = True
    DEBUG = False
    SECRET_KEY = "test-secret-key"
    CORS_ORIGINS = ["http://testserver"]
    RATELIMIT_ENABLED = False

    # Tests use a **real** extract of the official FDJ format: never any network
    # download during the test suite.
    ALLOW_SIMULATED_FALLBACK = False
    ALLOW_NETWORK_IMPORT = False
    LOCAL_DRAW_FILE = str(FIXTURE_DRAW_FILE)
