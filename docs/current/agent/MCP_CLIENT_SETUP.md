# MCP Client Setup

Scientific R&D Workspace exposes its canonical domain services to external MCP clients. Local clients can use stdio; service deployments can use Streamable HTTP. Write operations default to ChangeSet proposal mode and require review before authoritative mutation.

## Prerequisites

The MCP server uses the same PostgreSQL database, object schemas and domain services as the REST API.

From `api`:

```bash
uv sync --frozen
uv run alembic upgrade head
```

Set the required PostgreSQL connection and storage environment variables before starting the server.

## Local stdio

Start:

```bash
uv run python -m app.agent.mcp_server --transport stdio
```

Configure the MCP client to launch that command with working directory `api`.

The server must keep protocol output on stdout clean; operational logs belong on stderr.

## Streamable HTTP

Start the server with the repository-supported Streamable HTTP transport and deployment configuration.

Non-loopback deployments must use the documented authentication/proxy protection. Do not expose an unauthenticated write-capable MCP endpoint.

## Recommended client flow

1. call `workspace_capabilities`;
2. read Project Context;
3. search before creating a tagged Research Object or other reusable record;
4. read the target domain record and its current hash before proposing a mutation;
5. use domain-level tools instead of low-level graph writes;
6. submit changes through proposal-first ChangeSets;
7. review and apply through the trusted Workspace review flow;
8. re-read and re-propose when a ChangeSet becomes stale.

The Workspace does not provide an embedded assistant fallback. External clients remain responsible for model selection, reasoning and conversational UX.
