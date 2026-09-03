# Scientific Workspace Agent Platform Handoff

The Plan 09 implementation is on branch `plan-09-scientific-workspace-agent-platform`.

Implemented boundary: canonical Experiment/Project/Data/Execution services, typed REST records, PostgreSQL migrations 0004–0006, record hashes/ETags, persistent idempotency, machine-readable errors, official MCP stdio/Streamable HTTP adapter, bounded resources/tools, and proposal-first ChangeSets.

Validation completed locally: Ruff and mapper checks, Alembic offline SQL generation, OpenAPI generation, frontend lint/format/typecheck, and 19 frontend tests. Live PostgreSQL migration/API tests and browser acceptance require a PostgreSQL 17-capable CI runner or equivalent environment; this host has no Docker/PostgreSQL executable.

Before merge: run the full PostgreSQL CI matrix, exercise MCP with the official client over stdio and Streamable HTTP, run the browser smoke flow for Project → Experiment → Sample → Data → Execution, inspect the generated artifact, then merge only after the feature branch is green.
