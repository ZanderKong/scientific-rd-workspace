# MCP Resources and Transports

Static resource: `workspace://capabilities`.

Templates:

- `project://{project_id}/context`
- `project://{project_id}/schemas`
- `sample://{sample_id}/record`
- `sample://{sample_id}/execution`
- `sample://{sample_id}/lineage`
- `experiment://{experiment_id}/record`
- `experiment://{experiment_id}/comparison`
- `data://{data_id}/record`

Run stdio for local clients:

```bash
cd api
uv run python -m app.agent.mcp_server --transport stdio
```

Run Streamable HTTP on loopback:

```bash
MCP_BEARER_TOKEN='set-a-local-token' \
  uv run python -m app.agent.mcp_server --transport streamable-http --host 127.0.0.1 --port 8001
```

The HTTP endpoint is `/mcp`. Non-loopback HTTP refuses to start without `MCP_BEARER_TOKEN`; configure a TLS/authenticated reverse proxy for shared environments.
