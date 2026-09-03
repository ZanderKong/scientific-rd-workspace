# Claude Code Setup

Use the same repository-local MCP command as Codex. From the `api` directory:

```bash
uv sync --frozen
uv run python -m app.agent.mcp_server --transport stdio
```

Configure the client to launch that command with `DATABASE_URL` and any required storage settings in its environment. Start with `workspace_capabilities`, then read Project Context and domain records before proposing ChangeSets. Use REST review/apply endpoints for human approval. Do not provide SQLite or an embedded assistant as a fallback.
