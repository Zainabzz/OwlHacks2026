#!/bin/sh
set -eu
BACKEND_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname -- "$BACKEND_DIR")
if [ ! -x "$BACKEND_DIR/.venv/bin/python" ]; then
  echo "Backend environment missing. Run:"
  echo "python3 -m venv backend/.venv"
  echo "backend/.venv/bin/python -m pip install -r backend/requirements.txt"
  exit 1
fi
cd "$PROJECT_DIR"
exec "$BACKEND_DIR/.venv/bin/python" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 "$@"
