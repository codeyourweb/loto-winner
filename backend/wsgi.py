"""WSGI entry point for a production deployment.

The Flask development server is **not** a production server. This module exposes
a WSGI application compatible with:

* ``waitress-serve`` (recommended on Windows/Linux, pure Python) ::

      waitress-serve --listen=0.0.0.0:8000 wsgi:app

* ``gunicorn`` (Linux/macOS) ::

      gunicorn --workers 4 --bind 0.0.0.0:8000 wsgi:app

It loads the production configuration (secure cookies, HSTS, CORS allowlist,
rate limiting) read from the environment variables.
"""

from __future__ import annotations

import os

from app import create_app
from app.config import ProductionConfig


def _validate_production_env() -> list[str]:
    """Returns the list of missing critical environment variables."""
    problems: list[str] = []

    if not os.environ.get("LOTO_SECRET_KEY"):
        problems.append(
            "LOTO_SECRET_KEY est absent : définissez une clé aléatoire "
            "(ex. `python -c \"import secrets; print(secrets.token_hex(32))\"`)."
        )

    if not os.environ.get("LOTO_CORS_ORIGINS"):
        problems.append(
            "LOTO_CORS_ORIGINS est absent : indiquez les origines autorisées, "
            "séparées par des virgules (ex. https://loto.example)."
        )

    return problems


app = create_app(ProductionConfig)

if __name__ == "__main__":
    missing = _validate_production_env()
    if missing:
        raise SystemExit(
            "Configuration de production incomplète :\n  - " + "\n  - ".join(missing)
        )

    # Development fallback: do not use in production.
    app.run(
        host=os.environ.get("LOTO_HOST", "0.0.0.0"),
        port=int(os.environ.get("LOTO_PORT", "8000")),
        debug=False,
    )
