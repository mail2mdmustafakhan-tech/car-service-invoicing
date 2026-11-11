#!/usr/bin/env bash
# Start the application on macOS or Linux without Docker.
#
#     ./run.sh
#
# The first run creates a local Python environment and installs the four
# dependencies; later runs skip straight to starting the server.

set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
HOST="${CARSERVICE_HOST:-127.0.0.1}"
PORT="${CARSERVICE_PORT:-8000}"

if [ ! -d .venv ]; then
    echo "First run: setting up Python environment..."
    "$PYTHON" -m venv .venv
    ./.venv/bin/pip install --quiet --upgrade pip
    ./.venv/bin/pip install --quiet -r requirements.txt
    echo "Done."
fi

echo
echo "  Car Service Invoicing"
echo "  Open this address in your browser:  http://${HOST}:${PORT}"
echo "  Press Ctrl+C to stop."
echo

exec ./.venv/bin/python -m uvicorn app.main:app --host "$HOST" --port "$PORT"
