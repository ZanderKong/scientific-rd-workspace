# MCP Resources and Transports v0.3

Static resource: `workspace://capabilities`.

Templates:

- `project://{project_id}/context`
- `project://{project_id}/schemas`
- `sample://{sample_id}/record`
- `sample://{sample_id}/lineage`
- `experiment://{experiment_id}/record`
- `data://{data_id}/record`
- `view://{view_id}/record`
- `claim://{claim_id}/record`

Run local stdio:

```bash
cd api
uv run python -m app.agent.mcp_server --transport stdio
```

Run loopback Streamable HTTP:

```bash
MCP_BEARER_TOKEN='set-a-local-token' \
  uv run python -m app.agent.mcp_server --transport streamable-http --host 127.0.0.1 --port 8001
```

Non-loopback HTTP requires `MCP_BEARER_TOKEN` and an external TLS/auth proxy.
