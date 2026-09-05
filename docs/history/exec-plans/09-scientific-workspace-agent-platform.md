# Plan 09 — Scientific Workspace & External Agent Platform

## Final status

**Status:** COMPLETE — MERGED TO `main`

- Final `main`: `af969e92b18908e09a3546d5ce2beeeefed28258`
- Final CI: GitHub Actions run `33784023847` — **SUCCESS**
- PostgreSQL 17 migration/parity/API gates: PASS
- Frontend lint/typecheck/tests/build: PASS
- MCP protocol checks: PASS
- Plan 08 and Plan 09 browser acceptance: PASS

**PLAN 09 PASS — SCIENTIFIC WORKSPACE & EXTERNAL AGENT PLATFORM READY**

## Delivered stages

- Stage A: `includes` membership, Experiment Record, deterministic comparison, Project Record/Context/Search.
- Stage B: scalar, xy-series, table and file payloads; explicit table schema/rows; Sample planned/as-run execution and deterministic diff.
- Stage C: dedicated Project, Experiment, Data and Sample Execution workspace surfaces; existing Sample Record composer remains the editing surface for linear records.
- Stage D: capabilities, schema-aligned typed responses, record hashes, ETags/If-Match, persistent idempotency and machine-readable errors.
- Stage E: official `mcp` SDK adapter with stdio and Streamable HTTP, bounded read resources/tools and proposal-first ChangeSets.
- Stage F: API/MCP/setup documentation and handoff notes.

## Contracts

New revisions are `0004_experiment_membership`, `0005_data_execution`, and `0006_agent_changes` (the latter two live in descriptive migration filenames). Migrations `0001`–`0003` are unchanged. PostgreSQL remains the only supported database.

Canonical REST endpoints are documented in `docs/current/api/DOMAIN_API.md`. The MCP server is started with `uv run python -m app.agent.mcp_server --transport stdio` or `--transport streamable-http`.

## Verification record

Passed locally: Alembic offline upgrade SQL generation, SQLAlchemy mapper configuration, OpenAPI schema generation (48 API paths), Ruff, frontend formatting/lint, TypeScript, and 19 frontend tests. The local host has no Docker/PostgreSQL executable, so live migration/API/browser acceptance must run in PostgreSQL CI or an equivalent PostgreSQL 17 environment.
