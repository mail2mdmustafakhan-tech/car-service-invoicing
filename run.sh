#!/usr/bin/env bash
# ===========================================================================
#  Car Service Invoicing -- start the application on macOS or Linux
# ===========================================================================
#
#      ./run.sh
#
#  The first run creates a private Python environment inside this folder and
#  installs four packages into it; that takes a minute. Later runs skip
#  straight to starting the server.
#
#  Nothing is installed system-wide, and deleting the .venv folder undoes it.
# ===========================================================================

set -euo pipefail
cd "$(dirname "$0")"

HOST="${CARSERVICE_HOST:-127.0.0.1}"
PORT="${CARSERVICE_PORT:-8000}"

# --- Find a working Python -------------------------------------------------
PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 &&
           "$candidate" -c 'import sys; assert sys.version_info >= (3, 10)' >/dev/null 2>&1; then
            PYTHON="$candidate"
            break
        fi
    done
fi

if [ -z "$PYTHON" ]; then
    cat <<'MSG'

  Python 3.10 or newer was not found.

    macOS:         brew install python
    Debian/Ubuntu: sudo apt install python3 python3-venv
    or download:   https://www.python.org/downloads/

MSG
    exit 1
fi

# --- Set up the environment on first run -----------------------------------
if [ ! -x .venv/bin/python ]; then
    echo
    echo "  First run: setting up Python environment. This takes a minute..."
    echo
    "$PYTHON" -m venv .venv
    ./.venv/bin/python -m pip install --quiet --upgrade pip
    ./.venv/bin/python -m pip install --quiet -r requirements.txt
    echo "  Setup complete."
fi

# --- Start -----------------------------------------------------------------
cat <<MSG

  ================================================
    Car Service Invoicing is starting

    Open this address in your browser:
      http://${HOST}:${PORT}

    Press Ctrl+C to stop.
  ================================================

MSG

exec ./.venv/bin/python -m uvicorn app.main:app --host "$HOST" --port "$PORT"
