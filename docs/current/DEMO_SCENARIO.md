# v0.3 Demo Scenario

The repeat-safe seed is synthetic/anonymised and demonstrates a tagged Research Object graph.

1. Start PostgreSQL and run `uv run alembic upgrade head` followed by `uv run python -m app.seed`.
2. Open `/dashboard/samples` and select a Sample-tagged Research Object.
3. Inspect its Process Execution steps, pinned definition versions and bound objects/data.
4. Open a Data record and show multiple representations plus subject/derived-from shortcuts.
5. Open an Experiment and show that it references records without owning provenance.
6. Read the same records through MCP to verify adapter/service parity.

The seed is not production scientific evidence. User-created/imported records are never marked as demo data.
