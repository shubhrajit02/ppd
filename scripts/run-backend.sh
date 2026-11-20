#!/usr/bin/env bash
# Starts the API on http://127.0.0.1:8000. Creates .venv and installs on first run. Loads .env if present.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/aicr-api ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -c backend/requirements-dev.lock -e "backend[web,dev]"
fi
if [ -f .env ]; then set -a; . ./.env; set +a; fi
exec .venv/bin/aicr-api
