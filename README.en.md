# Scientific R&D Workspace

[简体中文](README.md) | **English**

Make AI-assisted research easier. Scientific R&D Workspace connects research objects, experimental procedures, data, and conclusions as structured records—a shared workspace for researchers and AI.

Connect an external AI client such as Codex through MCP. AI helps organize information, query records, and propose changes; the workspace provides structured storage, relationships, and revision tracking, with a UI for researchers to inspect and review them.

> This is a development version. The v1.5 workflow refactor is still undergoing acceptance testing. Full concurrency, real Chinese IME, and scale performance gates remain open. See [current status](docs/handoff/CURRENT_STATE.md).

## Workflow

- **Objects and templates**: maintain materials, equipment, samples, and process definitions with reusable fields and template versions.
- **Sample and Data**: reference objects and processes in a document, enter actual values, and organize representations, original attachments, and acquisition sources.
- **Experiment**: reference existing records to provide research context and tabular views.
- **View and Claim**: register analysis artifacts and statements with their sources and pinned revisions.

The application does not embed a language model or analysis runtime. External tools perform reasoning and analysis; the workspace organizes evidence, records results, and preserves connections.

## Installation

Requires **Git, Node.js 22, Python 3.11–3.13, uv, and Docker Compose**. These instructions are for a fresh local installation. Back up an existing database and review [current status](docs/handoff/CURRENT_STATE.md) before upgrading.

```bash
git clone https://github.com/ZanderKong/scientific-rd-workspace.git
cd scientific-rd-workspace
docker compose up -d --wait postgres

cd api
cp .env.example .env
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, start the frontend from the repository directory:

```bash
cd web
npm ci
npm run dev
```

Open the [workspace](http://localhost:3000/dashboard). API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs). Demo data is optional: run `uv run python -m app.seed` from `api` if you want example records.

Configuration:

- `api/.env`: database connection, upload limits, and storage paths; see the [example](api/.env.example). PostgreSQL uses port `5432` by default. To use an existing PostgreSQL instance, set `DATABASE_URL` and skip the Compose database.
- `web/.env.local`: optionally set `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`, which is also the default.
- PostgreSQL stores structured records; attachments default to `data/uploads/`. Back up both the database and attachment directory.

Defaults are intended for local development. Multi-user access control is not implemented; public deployment requires additional access controls.

## Using AI through MCP

After installation, connect Codex or another MCP client directly to the workspace. MCP and the Web API share the same database and domain services.

### Codex: local stdio (recommended)

Run this from the repository root to register the MCP server with Codex. The client starts the MCP process as needed; PostgreSQL must remain available:

```bash
codex mcp add scientific-workspace -- uv --directory "$PWD/api" run --frozen python -m app.agent.mcp_server --transport stdio
```

Other clients can use the same launch command with the repository's `api` directory as the working directory. Ensure MCP and the API use the same database and attachment storage settings.

### Streamable HTTP

For a separately running MCP service, execute from `api`:

```bash
uv run python -m app.agent.mcp_server --transport streamable-http --host 127.0.0.1 --port 8001
```

Connect to `http://127.0.0.1:8001/mcp`. For Codex:

```bash
codex mcp add scientific-workspace --url http://127.0.0.1:8001/mcp
```

Choose either transport. Binding to a non-loopback address requires `MCP_BEARER_TOKEN`. See [MCP setup](docs/current/agent/MCP_CLIENT_SETUP.md) for details.

### Suggested workflow

1. Create a project and prepare research objects and process templates in the workspace.
2. Ask AI to read capabilities, project context, and existing records before creating anything.
3. Ask AI to structure experimental notes, link samples and data, and propose a ChangeSet.
4. Review and apply changes in the workspace. After analysis, record the sources of resulting data, artifacts, and statements.

Example prompt:

> Use the scientific-workspace MCP to read capabilities and project context, then find existing samples and process templates. Organize my experimental notes into records. Preserve original values and units, and do not invent missing information. Propose a ChangeSet for my review before making changes.

Available operations are defined by the server's capabilities and MCP tools. See [Agent Interface](docs/current/agent/AGENT_INTERFACE.md).

## Design principles

- **Structure alongside narrative**: retain research prose while giving objects, processes, and fields explicit identities for queries and reuse.
- **Facts with provenance**: distinguish templates from actual executions, data from representations, and artifacts from claims; express their basis through revision references.
- **Shared rules for people and AI**: Web, REST, and MCP reuse domain services. External AI proposes changes for a trusted review flow to apply.
- **Clear tool boundaries**: PostgreSQL manages structured data and file storage preserves original attachments. The workspace does not introduce another model or analysis engine.

Stack: Next.js / React / TypeScript / BlockNote; FastAPI / SQLAlchemy / Alembic / PostgreSQL 17; MCP stdio and Streamable HTTP.

## Documentation

[Architecture](ARCHITECTURE.md) · [Product specification](docs/current/PRODUCT_SPEC.md) · [Data model](docs/current/DATA_MODEL.md) · [REST API](docs/current/api/DOMAIN_API.md) · [Status and acceptance](docs/handoff/CURRENT_STATE.md) · [Documentation index](docs/README.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)
