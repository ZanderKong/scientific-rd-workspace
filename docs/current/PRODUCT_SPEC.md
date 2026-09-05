# Product Specification v0.3

Scientific R&D Workspace is a project-scoped research workbench with one canonical graph model shared by Web, REST and MCP.

## User-facing domain

The product has seven kinds: `research_object`, `process_definition`, `data`, `experiment`, `project`, `view` and `claim`. Material, Equipment and Sample are tag groupings over Research Objects. This lets one object participate in multiple roles without copying identity.

Process Definitions describe reusable procedures. Process Executions record actual runs, pin a definition version, capture binding values and support multiple object/data inputs and outputs. Sample Record is a convenient aggregate projection over those executions.

Experiment is a reference context only. It groups references to objects/data/views/claims but does not own or produce them. Data has multiple representations and explicit subject/derived-from lineage. Views reference Data; Claims capture a human/analysis/AI statement with evidence and revisions.

## Core workflows

1. Create or select a Project.
2. Search or create a tagged Research Object.
3. Select a Process Definition version and compose a Sample Record backed by Process Executions.
4. Capture Data and add raw/table/image/description/structured representations.
5. Let subject and derived-from shortcuts update from execution bindings.
6. Reference reusable records from an Experiment, configure a View, or write an evidence-backed Claim.
7. Use ChangeSets for external-agent proposal-first writes and ETag/idempotency for safe retries.

## Product boundaries

PostgreSQL is mandatory. Local storage is the default asset backend; S3-compatible routing is optional. The cutover preserves parser limits, source hashes, revisions, ChangeSets, idempotency, optimistic concurrency and MCP authentication policy.

This plan does not redesign the visual system, add a queue, introduce a second database, or restore the legacy ownership/comparison/payload runtime. Final visual refinement is deferred.
