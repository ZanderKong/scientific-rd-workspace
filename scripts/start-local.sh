#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker Desktop is required for the PostgreSQL-only workspace runtime." >&2
  exit 1
fi
if ! command -v uv >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "uv and npm are required." >&2
  exit 1
fi

cd "$REPO_ROOT"
docker compose up -d postgres
(cd api && uv sync && uv run alembic upgrade head && uv run python -m app.seed && uv run fastapi dev app/main.py --host 127.0.0.1 --port 8000) &
api_pid=$!
(cd web && npm run dev -- --hostname 127.0.0.1 --port 3000) &
web_pid=$!

cleanup() {
  kill "$web_pid" "$api_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
echo "Scientific R&D Workspace: http://127.0.0.1:3000/dashboard/overview"
wait -n "$api_pid" "$web_pid"
