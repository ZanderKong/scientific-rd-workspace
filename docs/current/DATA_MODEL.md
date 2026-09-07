# Canonical Data Model v1.5

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
| `subject` | Data → Research Object subject projection with manual, acquisition-document or producer source |
| `derived_from` | Data → Data lineage derived only from explicit input Data |
| `related_to` | weak, non-provenance association |

Generic relation writes reject `subject` and `derived_from`; aggregate commands maintain their typed source rows and revision pins. Scope, self-edge, duplicate, cycle and target-kind rules are enforced in one semantic service.

## Process model

`process_definition` is the reusable process identity. `process_definition_versions` stores versioned descriptions, execution fields and UI schema; a state row points to the current version.

`process_executions` are independent event records. Each execution pins exactly one definition version and may have many:

- object bindings: input/context/output, role, field-definition snapshot and values; bindings retain identity with an `is_active` lifecycle flag so unbind/restore does not delete rows still referenced by historical occurrences;
- data bindings: input/output and values;
- `precedes` execution edges and append-only execution revisions.

An execution may produce multiple Research Objects and Data records. Binding field snapshots preserve historical values after a definition or object schema changes.

The Sample Record API owns a `ScientificDocumentV1` and stable `DocumentOccurrence` rows. Scientific Sample/Data identities carry an explicit authoring marker even when the document is empty. Process occurrences uniquely own authored Executions; object occurrences may own stable bindings to a process occurrence. Typed occurrence values form the query projection while the Execution/binding/document remains authoritative. Aggregate create and update preserve IDs, pin revisions and write the revision manifest atomically.

## Experiment

Experiment is a context record with typed `references` grouped by role/order/note. It has no ownership, provenance or cascade relationship to Process, Sample, Data or Research Object records. An object/data record can be reused by multiple experiments or by none.

## Data and representations

`data` has one `data_records` row and zero or more `data_representations`:

```text
raw_file · table · image · description · structured
```

Representations are immutable and content-addressed. A Data record may set one `origin_representation_id`; representations can reference a source representation for derivation without copying the Data identity. Table rows, scalar values and other typed payloads are representation subrecords.

Data can be assembled as a recoverable draft with stable identity and idempotent attachment IDs. Finalize atomically publishes the Data record, representations and subject sources. Raw files remain valid when enhanced parsing fails.

`Asset` stores storage backend, bucket/key, filename, MIME, byte count and SHA-256. Local storage is the default; optional S3-compatible storage is selected by policy. Presigned URLs are generated on demand and never persisted.

`DataImport` retains source Asset, parser/version, source checksum, mapping, warnings/errors and committed representation ID. CSV/XLSX parser limits, finite numeric validation, source row numbers and unit non-conversion remain enforced.

## Views, Claims and revision protection

A View revision pins explicit Data revision IDs, Representation IDs and an optional Artifact Asset ID/hash. Metadata-only changes keep the existing pin; source or Artifact changes append a ViewRevision. A Claim separately stores author provenance, one typed primary source revision and a finite context snapshot. `ClaimContextReference` and revision manifest indexes protect and reverse-query pinned sources.

## Governance and migration

ChangeSets, idempotency records, ETag/If-Match and revisions remain active. Alembic `0001`–`0012` are immutable history. Additive migrations `0013`–`0019` establish Scientific Records, typed occurrence projections, Data drafts, View manifests, Claim provenance and typed historical revision references; `0020_authoring_binding` adds explicit record ownership and durable binding validity; `0021_typed_revision_refs` adds typed source/target revision foreign keys and protection indexes. PostgreSQL is the only supported database.
