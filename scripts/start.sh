#!/usr/bin/env bash
# ---------------------------------------------------------------------------
#  Loto Winner - Linux / macOS launcher
#
#  Prepares the environment (Python venv + npm dependencies) then starts the
#  Flask API and the Vite server in parallel. Ctrl+C stops both cleanly.
#
#  Usage:
#     ./scripts/start.sh
#     BACKEND_PORT=5001 FRONTEND_PORT=5174 ./scripts/start.sh
#     ./scripts/start.sh --skip-install --no-browser
# ---------------------------------------------------------------------------
set -euo pipefail

# --- Colors (disabled when the output is not a terminal) --------------------
if [ -t 1 ]; then
    C_RESET="\033[0m"; C_CYAN="\033[36m"; C_GREEN="\033[32m"; C_YELLOW="\033[33m"; C_RED="\033[31m"
else
    C_RESET=""; C_CYAN=""; C_GREEN=""; C_YELLOW=""; C_RED=""
fi

step()  { printf "\n${C_CYAN}==> %s${C_RESET}\n" "$1"; }
ok()    { printf "    ${C_GREEN}OK${C_RESET}  %s\n" "$1"; }
warn()  { printf "    ${C_YELLOW}!!${C_RESET}  %s\n" "$1"; }
fail()  { printf "${C_RED}%s${C_RESET}\n" "$1" >&2; exit 1; }

# --- Options ----------------------------------------------------------------
BACKEND_PORT="${BACKEND_PORT:-5000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
SKIP_INSTALL=0
NO_BROWSER=0

while [ $# -gt 0 ]; do
    case "$1" in
        --backend-port)  BACKEND_PORT="$2"; shift 2 ;;
        --frontend-port) FRONTEND_PORT="$2"; shift 2 ;;
        --skip-install)  SKIP_INSTALL=1; shift ;;
        --no-browser)    NO_BROWSER=1; shift ;;
        -h|--help)
            sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) fail "Option inconnue : $1" ;;
    esac
done

# --- Paths ------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

# --- 1. Prerequisites --------------------------------------------------------
step "Verification des prerequis"
command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1 \
    || fail "Python introuvable. Installez Python 3.11+."
command -v npm >/dev/null 2>&1 \
    || fail "npm introuvable. Installez Node.js 20+ (https://nodejs.org/)."

PYTHON_CMD="python3"
command -v python3 >/dev/null 2>&1 || PYTHON_CMD="python"

[ -d "$BACKEND_DIR" ]  || fail "Dossier backend introuvable : $BACKEND_DIR"
[ -d "$FRONTEND_DIR" ] || fail "Dossier frontend introuvable : $FRONTEND_DIR"
ok "python et npm sont disponibles"

# --- 2. Dependencies --------------------------------------------------------
if [ "$SKIP_INSTALL" -eq 0 ]; then
    step "Preparation de l'environnement Python"
    if [ ! -x "$VENV_PYTHON" ]; then
        echo "    Creation du virtualenv..."
        "$PYTHON_CMD" -m venv "$VENV_DIR"
        ok "Virtualenv cree dans backend/.venv"
    else
        ok "Virtualenv existant reutilise"
    fi

    "$VENV_PYTHON" -m pip install --upgrade pip --quiet
    "$VENV_PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt" --quiet
    ok "Dependances Python installees"

    step "Preparation des dependances Node"
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        ( cd "$FRONTEND_DIR" && npm install --silent )
    fi
    ok "Dependances npm installees"
else
    warn "Installation ignoree (--skip-install)"
    [ -x "$VENV_PYTHON" ] || fail "Virtualenv absent : relancez sans --skip-install"
fi

# --- 3. Clean shutdown ------------------------------------------------------
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    step "Arret des serveurs"
    for pid in "$FRONTEND_PID" "$BACKEND_PID"; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            # Also kills the process group (vite / Flask reloader).
            kill -TERM "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    wait 2>/dev/null || true
    ok "Serveurs arretes"
}
trap cleanup EXIT INT TERM

# --- 4. Starting ------------------------------------------------------------
step "Demarrage de l'API Flask sur le port $BACKEND_PORT"
(
    cd "$BACKEND_DIR"
    LOTO_PORT="$BACKEND_PORT" setsid "$VENV_PYTHON" run.py --port "$BACKEND_PORT" \
        >"$ROOT_DIR/.backend.log" 2>&1 &
    echo $! > "$ROOT_DIR/.backend.pid"
) &
sleep 1
BACKEND_PID="$(cat "$ROOT_DIR/.backend.pid" 2>/dev/null || echo "")"
ok "Backend demarre (PID $BACKEND_PID)"

step "Demarrage du frontend Vite sur le port $FRONTEND_PORT"
(
    cd "$FRONTEND_DIR"
    LOTO_BACKEND_PORT="$BACKEND_PORT" setsid npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort \
        >"$ROOT_DIR/.frontend.log" 2>&1 &
    echo $! > "$ROOT_DIR/.frontend.pid"
) &
sleep 1
FRONTEND_PID="$(cat "$ROOT_DIR/.frontend.pid" 2>/dev/null || echo "")"
ok "Frontend demarre (PID $FRONTEND_PID)"

# --- 5. Waiting for availability --------------------------------------------
step "Attente de la disponibilite des serveurs"

wait_endpoint() {
    url="$1"; timeout="${2:-45}"; elapsed=0
    while [ "$elapsed" -lt "$timeout" ]; do
        if command -v curl >/dev/null 2>&1; then
            curl -fsS -o /dev/null --max-time 2 "$url" 2>/dev/null && return 0
        else
            "$VENV_PYTHON" - "$url" <<'PY' 2>/dev/null && return 0
import sys, urllib.request
urllib.request.urlopen(sys.argv[1], timeout=2)
PY
        fi
        sleep 0.7
        elapsed=$((elapsed + 1))
    done
    return 1
}

if wait_endpoint "http://127.0.0.1:$BACKEND_PORT/api/health"; then
    ok "API prete : http://127.0.0.1:$BACKEND_PORT/api/health"
else
    warn "L'API n'a pas repondu (voir .backend.log)"
fi

if wait_endpoint "http://127.0.0.1:$FRONTEND_PORT/"; then
    ok "Interface prete : http://127.0.0.1:$FRONTEND_PORT"
    if [ "$NO_BROWSER" -eq 0 ]; then
        if command -v xdg-open >/dev/null 2>&1; then
            xdg-open "http://127.0.0.1:$FRONTEND_PORT" >/dev/null 2>&1 || true
        elif command -v open >/dev/null 2>&1; then
            open "http://127.0.0.1:$FRONTEND_PORT" >/dev/null 2>&1 || true
        fi
    fi
else
    warn "Le frontend n'a pas repondu (voir .frontend.log)"
fi

printf "\n${C_GREEN}  Loto Winner est en cours d'execution.${C_RESET}\n"
printf "  Interface : http://127.0.0.1:%s\n" "$FRONTEND_PORT"
printf "  API       : http://127.0.0.1:%s\n" "$BACKEND_PORT"
printf "${C_YELLOW}  Appuyez sur Ctrl+C pour tout arreter.${C_RESET}\n\n"

# --- 6. Monitoring -----------------------------------------------------------
while true; do
    sleep 1
    if [ -n "$BACKEND_PID" ] && ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        warn "Le backend s'est arrete : extinction."
        break
    fi
    if [ -n "$FRONTEND_PID" ] && ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        warn "Le frontend s'est arrete : extinction."
        break
    fi
done
