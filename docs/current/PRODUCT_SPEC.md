# Product Specification v1.5

Scientific R&D Workspace is a project-scoped research workbench with one canonical graph model shared by Web, REST and MCP.

## User-facing domain

The product has seven kinds: `research_object`, `process_definition`, `data`, `experiment`, `project`, `view` and `claim`. Material, Equipment and Sample are tag groupings over Research Objects. This lets one object participate in multiple roles without copying identity.

Process Definitions describe reusable procedures. Scientific Composer records narrative, Process/Object refs and PropertySlots in one continuous document. Saved Process occurrences own actual Executions and stable object bindings with fixed identities and revision snapshots.

Experiment is a reference context only. Data supports recoverable drafts, multiple representations and explicit subject/derived-from sources. Views pin Data revisions, Representations and Artifact hashes. Claims separate author provenance from a typed primary source and finite context snapshot.

## Core workflows

1. Create or select a Project.
2. Search or create a tagged Research Object.
3. Compose a Sample as continuous text with inline Process/Object refs and values.
4. Capture Data through a recoverable draft and finalize raw/table/image/description/structured representations.
5. Query Samples/Data by typed occurrence fields and select Samples for an Experiment.
6. Create a fixed-version View and a Claim whose source and context remain readable after current records change.
7. Use ChangeSets for external-agent proposal-first writes and ETag/idempotency for safe retries.

## Product boundaries

PostgreSQL is mandatory. Local storage is the default asset backend; S3-compatible routing is optional. The cutover preserves parser limits, source hashes, revisions, ChangeSets, idempotency, optimistic concurrency and MCP authentication policy.

The product does not add collaborative editing, offline auto-merge, a queue, a second database, unit conversion or an embedded analysis/AI runtime.
