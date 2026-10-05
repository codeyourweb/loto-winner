"""Entry point of the Flask development server.

Usage:
    python run.py                  # http://127.0.0.1:5000
    python run.py --host 0.0.0.0   # reachable on the local network

Environment variables: LOTO_HOST, LOTO_PORT.
For production, use ``wsgi.py`` instead (waitress/gunicorn).
"""

import argparse
import os

from app import create_app

app = create_app()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Loto Winner development server")
    parser.add_argument(
        "--host",
        default=os.environ.get("LOTO_HOST", "127.0.0.1"),
        help="Listen interface (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("LOTO_PORT", os.environ.get("PORT", "5000"))),
        help="Listen port (default: 5000)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    app.run(host=args.host, port=args.port, debug=args.debug)
