# Plan 09 — Scientific Workspace & External Agent Platform

Status: implementation complete locally; PostgreSQL/CI/browser gates remain environment-dependent.

This repository execution record follows the attached Plan 09 specification. The attached document is the product/engineering specification; it does not add user authority beyond the request to complete the plan.

## Delivered stages

- Stage A: `includes` membership, Experiment Record, deterministic comparison, Project Record/Context/Search.
- Stage B: scalar, xy-series, table and file payloads; explicit table schema/rows; Sample planned/as-run execution and deterministic diff.
- Stage C: dedicated Project, Experiment, Data and Sample Execution workspace surfaces; existing Sample Record composer remains the editing surface for linear records.
- Stage D: capabilities, schema-aligned typed responses, record hashes, ETags/If-Match, persistent idempotency and machine-readable errors.
- Stage E: official `mcp` SDK adapter with stdio and Streamable HTTP, bounded read resources/tools and proposal-first ChangeSets.
- Stage F: API/MCP/setup documentation and handoff notes.

## Contracts

New migrations are `0004_experiment_membership`, `0005_scientific_data_and_execution`, and `0006_api_idempotency_and_change_sets`. Migrations `0001`–`0003` are unchanged. PostgreSQL remains the only supported database.

Canonical REST endpoints are documented in `docs/api/DOMAIN_API.md`. The MCP server is started with `uv run python -m app.agent.mcp_server --transport stdio` or `--transport streamable-http`.

## Verification record

Passed locally: Alembic offline upgrade SQL generation, SQLAlchemy mapper configuration, OpenAPI schema generation (48 API paths), Ruff, frontend formatting/lint, TypeScript, and 19 frontend tests. The local host has no Docker/PostgreSQL executable, so live migration/API/browser acceptance must run in PostgreSQL CI or an equivalent PostgreSQL 17 environment.
