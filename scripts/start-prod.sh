#!/usr/bin/env bash
# ---------------------------------------------------------------------------
#  Loto Winner - production mode launch (API only).
#
#  Starts the Flask API with a production WSGI server:
#    - waitress  (Windows / Linux, pure Python) — recommended when not root;
#    - gunicorn  (Linux / macOS).
#
#  REQUIRED environment variables before going live:
#     LOTO_SECRET_KEY     random secret key (>= 32 bytes)
#     LOTO_CORS_ORIGINS   allowed origins, comma-separated
#  Optional:
#     LOTO_HOST, LOTO_PORT, RATELIMIT_STORAGE_URI (e.g. redis://localhost:6379)
#
#  Usage:
#     ./scripts/start-prod.sh
#     SERVER=gunicorn WORKERS=4 PORT=8000 ./scripts/start-prod.sh
# ---------------------------------------------------------------------------
set -euo pipefail

if [ -t 1 ]; then
    C_RESET="\033[0m"; C_CYAN="\033[36m"; C_RED="\033[31m"; C_YELLOW="\033[33m"
else
    C_RESET=""; C_CYAN=""; C_RED=""; C_YELLOW=""
fi

step() { printf "\n${C_CYAN}==> %s${C_RESET}\n" "$1"; }
fail() { printf "${C_RED}%s${C_RESET}\n" "$1" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$ROOT_DIR/backend"
VENV_PYTHON="$BACKEND_DIR/.venv/bin/python"

SERVER="${SERVER:-auto}"
WORKERS="${WORKERS:-4}"
HOST="${LOTO_HOST:-0.0.0.0}"
PORT="${LOTO_PORT:-8000}"

# --- Production guards ------------------------------------------------------
step "Verification de la configuration de production"

[ -n "${LOTO_SECRET_KEY:-}" ] || fail "LOTO_SECRET_KEY est requis. Ex.: export LOTO_SECRET_KEY=\$(python -c 'import secrets;print(secrets.token_hex(32))')"
[ -n "${LOTO_CORS_ORIGINS:-}" ] || fail "LOTO_CORS_ORIGINS est requis. Ex.: export LOTO_CORS_ORIGINS=https://loto.example"

if [ "${#LOTO_SECRET_KEY}" -lt 32 ]; then
    fail "LOTO_SECRET_KEY doit faire au moins 32 caracteres."
fi

printf "    ${C_YELLOW}Pensez a placer un reverse proxy TLS (nginx/Caddy) devant l'API.${C_RESET}\n"

[ -x "$VENV_PYTHON" ] || fail "Virtualenv introuvable : lancez ./scripts/start.sh une fois, ou creez backend/.venv"

cd "$BACKEND_DIR"

# --- WSGI server selection --------------------------------------------------
if [ "$SERVER" = "auto" ]; then
    if "$VENV_PYTHON" -c "import gunicorn" >/dev/null 2>&1; then
        SERVER="gunicorn"
    elif "$VENV_PYTHON" -c "import waitress" >/dev/null 2>&1; then
        SERVER="waitress"
    else
        fail "Aucun serveur WSGI installe. Installez-en un :\n  pip install waitress   (Windows/Linux)\n  pip install gunicorn   (Linux/macOS)"
    fi
fi

step "Demarrage via $SERVER sur $HOST:$PORT"

case "$SERVER" in
    gunicorn)
        exec "$VENV_PYTHON" -m gunicorn \
            --workers "$WORKERS" \
            --bind "$HOST:$PORT" \
            --access-logfile "-" \
            --error-logfile "-" \
            wsgi:app
        ;;
    waitress)
        exec "$VENV_PYTHON" -m waitress \
            --host="$HOST" \
            --port="$PORT" \
            --threads="${THREADS:-8}" \
            wsgi:app
        ;;
    *)
        fail "Serveur inconnu : $SERVER (valeurs acceptees : auto, gunicorn, waitress)"
        ;;
esac
