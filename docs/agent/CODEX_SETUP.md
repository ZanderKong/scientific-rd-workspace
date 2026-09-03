# Codex Setup

For a local Codex task, run the API and web app from the repository checkout. PostgreSQL is required; set `DATABASE_URL` to a PostgreSQL connection before migrations or seed.

```bash
cd api
uv sync --frozen
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd web
npm ci
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 npm run dev
```

For MCP stdio, point the client at `uv run python -m app.agent.mcp_server --transport stdio` with working directory `api`. The MCP server uses the same PostgreSQL and object schemas as REST.
