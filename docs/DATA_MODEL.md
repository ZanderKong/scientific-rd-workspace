# Canonical Data Model — v0.2

## Identity and types

All domain records use a UUID primary key and a unique human-readable code. Codes are allocated by PostgreSQL counter rows under `SELECT ... FOR UPDATE`:

| kind | prefix |
| --- | --- |
| project | PRJ |
| experiment | EXP |
| sample | SMP |
| process | PRC |
| data | DAT |
| material | MAT |
| equipment | EQP |

`ObjectType` identifies a type and has one `is_default` row per canonical kind. `ObjectTypeVersion` stores the JSON Schema/UI schema. Published schema fields are immutable. New schema means a new version row; existing objects keep their exact `type_version_id`. When a type is omitted, the service selects the default ObjectType's highest active version.

## Objects

`research_objects` contains:

- `kind`, `code`, `title`, `status`
- nullable `project_scope_id` (projects are scopes; materials/equipment may be global or scoped)
- `type_version_id`
- `properties_jsonb` for typed structured fields
- `usage_schema_jsonb` for per-object Material/Equipment usage-field definitions; all other kinds return `{}`
- `content_document` for rich/block content, kept separate from properties
- timestamps

JSONB GIN, kind/scope indexes and `pg_trgm` code/title indexes support typed search without introducing a second search store.

## Relations

`object_relations(source_object_id, target_object_id, relation_type, role, properties_jsonb)` contains only:

- `contains`: Experiment → Process/Sample/Data; it is the single ownership edge and does not claim ownership of upstream inputs consumed by a process.
- `uses`: Process → Material/Sample/Equipment/Data; Process → Sample requires a non-empty role. Canonical roles are `precursor`, `subject`, `reference`, `control`; aliases normalize to those values and unknown roles are preserved after trimming.
- `produces`: Process → Sample/Data
- `precedes`: Process → Process
- `includes`: Experiment → Sample non-owning membership. Its role is always null; order and optional note live in `properties_jsonb`.
- `related_to`: weak cross-object association; never canonical provenance

Foreign keys cascade when an object is removed. A PostgreSQL unique index with `NULLS NOT DISTINCT` prevents duplicate semantic edges, including two null-role edges. Quantity metadata, when supplied, is `{ "quantity": { "value": number, "unit": string } }`.

Partial unique indexes enforce one incoming `contains` owner and one incoming `produces` producer. Relation writes also reject precursor lineage cycles, Process `precedes` cycles, invalid scope crossings and ownership conflicts. Scope changes revalidate all existing edges.

Material and Equipment usage definitions are stored on the concrete resource object as `usage_schema_jsonb.fields[]`. Supported field types are `number`, `text`, `boolean` and `select`; defaults are suggestions, not evidence, and units are metadata with no implicit conversion. A Sample Record's actual use values are stored on the Process → resource `uses` relation under `properties_jsonb.usage_values`, for example `{ "usage_values": { "quantity": { "value": 10, "unit": "g" } } }`. Legacy top-level `quantity` remains readable through the Sample Record projection.

`GET /api/v1/samples/{id}/record` reconstructs a linear chain backwards from the Sample's single producing Process through `precedes`. A branched or externally dependent graph is viewable but returns `editable: false` with blockers; it is never silently flattened. `POST /api/v1/sample-records` and `PUT /api/v1/samples/{id}/record` are aggregate desired-state transactions. Removing a safe composer-owned Process archives it after disconnecting it from the active chain; it is not hard-deleted.

## Revisions and files

`object_revisions` is append-only from the service contract. Each row stores a monotonically allocated revision number, a JSONB snapshot of the object/direct relations/attachment metadata/payload summary, and a SHA-256 of canonical JSON.

`attachments` is object-centric. The database stores filename, content type, byte count, storage key and SHA-256; file bytes are in the configured storage adapter. An attachment referenced by `DataImport` or `DataPayload` cannot be deleted.

## Data import and payload

`data_imports` records source format, parser key/version, source checksum, selected sheet, headers, preview metadata, explicit mapping, warnings/errors and completion status. Only CSV/XLSX is accepted, with bounded size/rows/columns and finite numeric validation.

`data_payloads` supports `scalar`, `xy_series`, `table`, and `file`. Scalar values are finite and carry an explicit unit. Tables store explicit typed columns and ordered JSONB rows with optional source row numbers. XY payloads use `data_points` to preserve source row number, ordinal, X and Y values. File payloads reference an object attachment and preserve its checksum. Import commits never interpolate, reorder, or silently convert units. Payload summaries and canonical hashes support reproducibility.

`sample_executions` is one-to-one with Sample. Starting an execution stores the current Sample Record as `plan_snapshot_jsonb` plus its hash; observations and deviation notes are appended/updated in the execution, while the current Sample Record remains the as-run side. The service returns a deterministic diff without mutating the plan snapshot.

`api_idempotency_records` persists request-hash and response replay data. `change_sets` persists proposal, preview, review, apply status, source client metadata and optional base record hash; applied object revisions link back to the ChangeSet.

## Migration boundary

`api/alembic/versions/0001_v0_2_research_object_graph.py` is a fresh baseline. `0002_v0_2_semantic_stabilization` adds semantic ownership/producer indexes. `0003_sample_recording_workflow` adds `research_objects.usage_schema_jsonb`; 0001 and 0002 are immutable. No previous SQLite or phase-specific migration is part of the active history.

Plan 09 adds the `0004_experiment_membership`, `0005_data_execution`, and `0006_agent_changes` revisions (with descriptive migration filenames). PostgreSQL remains the only supported database.
