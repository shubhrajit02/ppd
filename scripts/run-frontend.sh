#!/usr/bin/env bash
# Starts the web app on http://127.0.0.1:3000. Installs dependencies on first run.
set -euo pipefail
cd "$(dirname "$0")/../frontend"
[ -d node_modules ] || npm ci
exec npm run dev
