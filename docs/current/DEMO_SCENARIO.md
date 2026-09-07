# v1.5 Demo Scenario

The repeat-safe seed is synthetic/anonymised and demonstrates a tagged Research Object graph.

1. Start PostgreSQL and run `uv run alembic upgrade head` followed by `uv run python -m app.seed`.
2. Open `/dashboard/samples` and select a Sample-tagged Research Object.
3. Compose a Sample with inline Process/Object refs, edit PropertySlots, save and reopen its fixed revision.
4. Finalize a recoverable Data draft with raw and description representations and explicit subject source.
5. Use the dynamic Sample table and picker to create an Experiment without transferring ownership.
6. Create a View pinned to the Data revision/Representations, attach an Artifact, then create a Claim from the View revision.
7. Read the same records through MCP to verify adapter/service parity.

The seed is not production scientific evidence. User-created/imported records are never marked as demo data.
