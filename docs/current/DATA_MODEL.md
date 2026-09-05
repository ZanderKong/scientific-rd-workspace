# Canonical Data Model v0.3

## Kinds and identity

`research_objects` is the shared identity table. Its allowed kinds are:

```text
research_object · process_definition · data · experiment · project · view · claim
```

Material, Equipment and Sample are `research_object` rows distinguished by `tags_jsonb`; no physical table or API kind exists for them. Each row has a stable UUID/code, status, optional project scope, optional ObjectType version, tags, properties, process-field definitions, content document and timestamps.

`ObjectRevision` stores immutable JSON snapshots and SHA-256 hashes. `ObjectTypeVersion` is immutable; a new schema is a new version and existing records retain their pinned version.

## Relations

The only public relation types are:

| relation | meaning |
| --- | --- |
| `references` | non-owning research context, primarily Experiment references |
| `subject` | Data → Research Object subject shortcut, system-managed |
| `derived_from` | Data → Data lineage shortcut, system-managed |
| `related_to` | weak, non-provenance association |

Generic relation writes reject `subject` and `derived_from`; those are synchronized from Process Execution Data bindings. Scope, self-edge, duplicate, cycle and target-kind rules are enforced in one semantic service.

## Process model

`process_definition` is the reusable process identity. `process_definition_versions` stores versioned descriptions, execution fields and UI schema; a state row points to the current version.

`process_executions` are independent event records. Each execution pins exactly one definition version and may have many:

- object bindings: input/context/output, role, field-definition snapshot and values;
- data bindings: input/output and values;
- `precedes` execution edges and append-only execution revisions.

An execution may produce multiple Research Objects and Data records. Binding field snapshots preserve historical values after a definition or object schema changes.

The Sample Record API is a projection: a Sample is a tagged Research Object, and its steps are Process Executions. It never persists a legacy Process object or one-to-one SampleExecution. Aggregate create and update are transactional: retained `execution_id` values keep their identity, new steps inherit the Sample's project scope, and the returned projection is reloaded after binding replacement so it reflects the committed values.

## Experiment

Experiment is a context record with typed `references` grouped by role/order/note. It has no ownership, provenance or cascade relationship to Process, Sample, Data or Research Object records. An object/data record can be reused by multiple experiments or by none.

## Data and representations

`data` has one `data_records` row and zero or more `data_representations`:

```text
raw_file · table · image · description · structured
```

Representations are immutable and content-addressed. A Data record may set one `origin_representation_id`; representations can reference a source representation for derivation without copying the Data identity. Table rows, scalar values and other typed payloads are representation subrecords.

`subject` and `derived_from` shortcuts are maintained from execution bindings. A Data page can therefore show all representations, subjects and upstream Data without reconstructing old Process/Experiment ownership.

`Asset` stores storage backend, bucket/key, filename, MIME, byte count and SHA-256. Local storage is the default; optional S3-compatible storage is selected by policy. Presigned URLs are generated on demand and never persisted.

`DataImport` retains source Asset, parser/version, source checksum, mapping, warnings/errors and committed representation ID. CSV/XLSX parser limits, finite numeric validation, source row numbers and unit non-conversion remain enforced.

## Governance and migration

ChangeSets, idempotency records, ETag/If-Match and revisions remain active. Alembic `0001`–`0006` are immutable v0.2 history; `0007` adds canonical tables/transition columns, `0008` copies old records, `0009` removes legacy storage, `0010` finalizes strict checks/indexes, `0011` persists ProcessExecution View revision pins, and `0012` aligns explicit migration metadata with runtime indexes/constraints. PostgreSQL is the only supported database. The named synthetic `GoldenCl2WorkflowFactory` is repeat-safe and verifies a complete Cl₂ sensor workflow without introducing a second runtime model.
