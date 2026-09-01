#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
API_DIR="$REPO_ROOT/api"
WEB_DIR="$REPO_ROOT/web"
DATA_DIR="$REPO_ROOT/data/local"
DB_PATH="$DATA_DIR/scientific_rd.db"

mkdir -p "$DATA_DIR" "$REPO_ROOT/data/uploads"

# SQLite is an explicit local-only fallback when PostgreSQL/Docker is absent.
# The normal app defaults and Docker Compose path continue to use PostgreSQL.
export DATABASE_URL="sqlite+pysqlite:///$DB_PATH"
export STORAGE_ROOT="$REPO_ROOT/data/uploads"
export CORS_ORIGINS='["http://localhost:3000","http://127.0.0.1:3000"]'
export NEXT_PUBLIC_API_URL="http://127.0.0.1:8000/api/v1"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but was not found in PATH." >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required but was not found in PATH." >&2
  exit 1
fi

echo "Preparing local SQLite database at $DB_PATH"
(cd "$API_DIR" && uv sync && uv run python -m app.local_bootstrap)

api_pid=""
web_pid=""
cleanup() {
  trap - EXIT INT TERM
  if [[ -n "$web_pid" ]] && kill -0 "$web_pid" 2>/dev/null; then
    kill "$web_pid" 2>/dev/null || true
  fi
  if [[ -n "$api_pid" ]] && kill -0 "$api_pid" 2>/dev/null; then
    kill "$api_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting API: http://127.0.0.1:8000"
(cd "$API_DIR" && uv run fastapi dev app/main.py --host 127.0.0.1 --port 8000) &
api_pid=$!

if [[ ! -d "$WEB_DIR/node_modules" ]]; then
  echo "Installing web dependencies"
  (cd "$WEB_DIR" && npm install)
fi

echo "Starting web: http://127.0.0.1:3000/dashboard/overview"
(cd "$WEB_DIR" && npm run dev -- --hostname 127.0.0.1 --port 3000) &
web_pid=$!

echo "Local deployment is running. Press Ctrl-C to stop both services."
while kill -0 "$api_pid" 2>/dev/null && kill -0 "$web_pid" 2>/dev/null; do
  sleep 1
done

if ! kill -0 "$api_pid" 2>/dev/null; then
  echo "API process exited; stopping web process." >&2
else
  echo "Web process exited; stopping API process." >&2
fi
