# Sample Recording API Contract

Plan 08 exposes the same aggregate API to the GUI and to external agents. The API is PostgreSQL-backed and semantic validation is authoritative; an agent must not recreate one record by looping over object and relation writes.

## Read

```text
GET /api/v1/samples/{sample_id}/record
```

The response contains the final `sample`, ordered `steps`, each step's `process` and resource relations, direct `data` outputs, `editable`, and `edit_blockers`. A record is editable only when the graph can be represented as one linear `precedes` chain ending in the Sample's single producing Process. Branched, cyclic, or externally dependent structures remain readable and return `editable: false`; never flatten them by inference.

## Create and edit

```text
POST /api/v1/sample-records
PUT  /api/v1/samples/{sample_id}/record
```

Both are aggregate desired-state transactions. A successful request may create/update the Sample, multiple Processes, inline Material/Equipment resources, usage schemas, `uses` relations, `precedes` ordering, the final `produces` relation, and revision snapshots. Any validation failure rolls back the whole transaction. Do not use SQLite as a substitute for PostgreSQL.

`POST` requires `project_scope_id`, a final Sample draft, and at least one ordered Process step. A resource draft either references `target_object_id` or supplies an inline `create_target`; it may also include `usage_values` and `usage_schema_additions`. Existing Material/Equipment identity is never changed by a usage value. A Sample resource is allowed only as a `precursor`.

`PUT` sends the complete desired state of the editable chain. Existing Process IDs may be retained, new steps omit `process_id`, and omitted existing steps are archived when removal is safe. An externally referenced Process is not hard-deleted; unsafe removal returns HTTP 409.

## Semantic rules

- Canonical object kinds are `material`, `sample`, `equipment`, `process`, `data`, `experiment`, and `project`.
- Canonical relations are `contains`, `includes`, `uses`, `produces`, `precedes`, and `related_to`. `includes` is reserved for non-owning Experiment → Sample membership; it is not part of Sample Record composition.
- `Experiment contains Process/Sample/Data` is exclusive ownership. It is not multi-Experiment membership.
- `precursor`, `subject`, `reference`, and `control` are roles on Process → Sample `uses`; only `precursor` drives lineage and only `subject` drives current Data.
- Sample and Data have at most one producer. Process `precedes` and precursor lineage are cycle-protected.
- Do not use `related_to` to simulate membership or provenance.

## Usage values and parameters

Resource identity fields remain in `object.properties_jsonb` and the concrete resource's optional `usage_schema_jsonb`. Actual values for one Process use belong in the relation envelope:

```json
{
  "usage_values": {
    "quantity": { "value": 10, "unit": "g" },
    "rpm": { "value": 700, "unit": "rpm" }
  }
}
```

Process-own conditions belong in `process.properties_jsonb.parameters`. Units are metadata and are never silently converted. Legacy top-level `quantity` relation metadata is readable in the record projection, but new writes should use `usage_values`.

## Clone behavior

To implement “create from this Sample”, read the record, remove the Sample code/ID, Process IDs, and relation IDs in the new draft, retain existing resource object IDs and copied values, then call `POST /sample-records`. Data, attachments, revisions, and source mutation are not copied.
