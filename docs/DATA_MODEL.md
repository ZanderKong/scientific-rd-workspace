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

`ObjectType` identifies a type; `ObjectTypeVersion` stores the JSON Schema/UI schema. Published schema fields are immutable. New schema means a new version row; existing objects keep their exact `type_version_id`.

## Objects

`research_objects` contains:

- `kind`, `code`, `title`, `status`
- nullable `project_scope_id` (projects are scopes; materials/equipment may be global or scoped)
- `type_version_id`
- `properties_jsonb` for typed structured fields
- `content_document` for rich/block content, kept separate from properties
- timestamps

JSONB GIN, kind/scope indexes and `pg_trgm` code/title indexes support typed search without introducing a second search store.

## Relations

`object_relations(source_object_id, target_object_id, relation_type, role, properties_jsonb)` contains only:

- `contains`: Experiment → Process/Sample/Data
- `uses`: Process → Material/Sample/Equipment/Data
- `produces`: Process → Sample/Data
- `precedes`: Process → Process
- `related_to`: weak cross-object association

Foreign keys cascade when an object is removed. A PostgreSQL unique index with `NULLS NOT DISTINCT` prevents duplicate semantic edges, including two null-role edges. Quantity metadata, when supplied, is `{ "quantity": { "value": number, "unit": string } }`.

## Revisions and files

`object_revisions` is append-only from the service contract. Each row stores a monotonically allocated revision number, a JSONB snapshot of the object/direct relations/attachment metadata/payload summary, and a SHA-256 of canonical JSON.

`attachments` is object-centric. The database stores filename, content type, byte count, storage key and SHA-256; file bytes are in the configured storage adapter. An attachment referenced by `DataImport` or `DataPayload` cannot be deleted.

## Data import and payload

`data_imports` records source format, parser key/version, source checksum, selected sheet, headers, preview metadata, explicit mapping, warnings/errors and completion status. Only CSV/XLSX is accepted, with bounded size/rows/columns and finite numeric validation.

`data_payloads` currently supports `xy_series`; `data_points` preserves source row number, ordinal, X and Y values. Import commits never interpolate, reorder, or silently convert units. Payload summaries and canonical point hashes support reproducibility.

## Migration boundary

`api/alembic/versions/0001_v0_2_research_object_graph.py` is a fresh baseline. It enables `pg_trgm`, creates all tables/constraints/indexes, and seeds the seven counter rows. No previous SQLite or phase-specific migration is part of the active history.
