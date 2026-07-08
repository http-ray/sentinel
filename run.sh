#!/usr/bin/env bash
# Sentinel launcher (macOS/Linux). Creates the venv on first run, then runs the
# requested command.
#
#   ./run.sh              # run the offline incident simulation (default)
#   ./run.sh sim 1        # run a specific sample alert by index
#   ./run.sh test         # run the test suite
#   ./run.sh server       # start the API server (http://localhost:8000/docs)
#   ./run.sh setup        # create the venv and install deps only
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
VENV_PY="$ROOT/.venv/bin/python"

ensure_venv() {
    if [ ! -x "$VENV_PY" ]; then
        echo "First run: creating virtual environment in .venv ..."
        python3 -m venv "$ROOT/.venv"
        echo "Installing Sentinel and dependencies ..."
        "$VENV_PY" -m pip install --upgrade pip --quiet
        "$VENV_PY" -m pip install -e ".[dev]" --quiet
        echo "Environment ready."
    fi
}

cmd="${1:-sim}"
case "$cmd" in
    help)
        echo "Sentinel launcher"
        echo "  ./run.sh            Run the offline incident simulation (default)"
        echo "  ./run.sh sim 1      Run a specific sample alert by index"
        echo "  ./run.sh test       Run the pytest suite"
        echo "  ./run.sh server     Start the API server on http://localhost:8000"
        echo "  ./run.sh setup      Create the venv and install deps only"
        ;;
    setup)  ensure_venv ;;
    test)   ensure_venv; "$VENV_PY" -m pytest ;;
    server)
        ensure_venv
        echo "Starting server -> http://localhost:8000/docs (Ctrl+C to stop)"
        "$VENV_PY" -m uvicorn sentinel.api.main:app --reload
        ;;
    sim)
        ensure_venv
        "$VENV_PY" "$ROOT/scripts/simulate.py" --alert "${2:-0}"
        ;;
    *)
        echo "Unknown command: $cmd (try: ./run.sh help)" >&2
        exit 1
        ;;
esac
