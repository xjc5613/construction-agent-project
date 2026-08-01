#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"
NODE_BIN="${ROOT_DIR}/.tools/node/bin"
cd "${ROOT_DIR}"

usage() {
  cat <<'EOF'
Usage: ./scripts/workbench.sh <command>

Commands:
  setup    Install Python and frontend dependencies.
  backend  Start the FastAPI server on http://127.0.0.1:8000.
  frontend Start the Vite server on http://127.0.0.1:5173.
  start    Start backend and frontend together.
  build    Build the production frontend bundle.
  check    Verify API and frontend production build.
EOF
}

ensure_node() {
  if [[ ! -x "${NODE_BIN}/node" ]]; then
    "${ROOT_DIR}/scripts/bootstrap_node.sh"
  fi
  export PATH="${NODE_BIN}:${PATH}"
}

ensure_port_free() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port ${port} is already in use. Stop the existing service before starting the workbench." >&2
    exit 1
  fi
}

case "${1:-}" in
  setup)
    ensure_node
    python3 -m pip install -r "${ROOT_DIR}/requirements.txt"
    npm --prefix "${FRONTEND_DIR}" ci
    python3 "${ROOT_DIR}/scripts/migrate_resources.py" --apply
    python3 "${ROOT_DIR}/scripts/seed_library.py" --include-legacy-project
    ;;
  backend)
    ensure_port_free 8000
    exec python3 -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload
    ;;
  frontend)
    ensure_node
    ensure_port_free 5173
    exec npm --prefix "${FRONTEND_DIR}" run dev -- --host 127.0.0.1 --strictPort
    ;;
  start)
    ensure_node
    ensure_port_free 8000
    ensure_port_free 5173
    python3 -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 &
    BACKEND_PID=$!
    npm --prefix "${FRONTEND_DIR}" run dev -- --host 127.0.0.1 --strictPort &
    FRONTEND_PID=$!
    cleanup() {
      kill "${BACKEND_PID}" "${FRONTEND_PID}" 2>/dev/null || true
    }
    trap cleanup EXIT INT TERM
    wait "${BACKEND_PID}" "${FRONTEND_PID}"
    ;;
  build)
    ensure_node
    exec npm --prefix "${FRONTEND_DIR}" run build
    ;;
  check)
    ensure_node
    python3 -m pytest tests/ -q
    npm --prefix "${FRONTEND_DIR}" run build
    ;;
  *)
    usage
    exit 1
    ;;
esac
