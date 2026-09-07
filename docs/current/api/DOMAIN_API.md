# Scientific Workspace Domain API v1.5

Base URL: `/api/v1`. The server is authoritative for scope, relation semantics, hashes and revisions.

## Research Objects

```text
GET/PATCH/DELETE /objects/{id}
GET       /objects/{id}/relations
POST      /objects
GET       /objects
POST      /relations
GET/POST  /objects/{id}/revisions
```

`POST /objects` accepts the seven canonical kinds. A physical resource uses `kind=research_object` and `tags`. Generic relation writes accept only `references` and `related_to`; aggregate commands manage `subject` and `derived_from`.

Deleting an Experiment removes only that Experiment and its owned `references` rows. Referenced Research Objects, Data and Process Definitions remain independent canonical records and may still be used by other Experiments.

## Process

```text
GET/POST /process-definitions
GET      /process-definitions/{id}
POST     /process-definitions/{id}/versions
POST     /process-executions
GET/PUT  /process-executions/{id}
GET      /process-executions/{id}/revisions/{revision_number}
GET      /objects/{id}/process-executions
```

An execution pins a definition version and accepts multiple object/data bindings. Binding snapshots preserve historical field definitions and values.

## Product projections

```text
GET/PUT  /samples/{id}/record
GET      /samples/{id}/record/revisions/{revision_number}
POST     /sample-records
POST     /sample-records/batch
POST     /experiment-records
GET/PUT  /experiments/{id}/record
PATCH    /experiments/{id}/metadata
POST     /experiments/{id}/references
DELETE   /experiments/{id}/references/{relation_id}
PUT      /experiments/{id}/reference-order
POST     /record-tables/query
```

Sample writes use `ScientificDocumentV1` plus stable typed occurrences; the `steps` input format is removed. The table query performs full-scope filtering and sorting before pagination and returns ordered occurrence values. Experiment output remains grouped typed references and never ownership/provenance.

## Data and assets

```text
POST     /data-records
POST     /data-drafts
GET/PUT  /data-drafts/{id}
POST     /data-drafts/{id}/attachments
DELETE   /data-drafts/{id}/attachments/{client_attachment_id}
POST     /data-drafts/{id}/finalize
GET/PUT  /data/{id}/record
GET      /data/{id}/record/revisions/{revision_number}
POST     /data/{id}/representations
GET      /data/{id}/representations
GET      /data/{id}/representations/{representation_id}
POST     /data/{id}/imports/preview
POST     /data/{id}/imports/{import_id}/commit
POST     /objects/{id}/assets
GET      /assets/{id}/download
```

Representations are `raw_file`, `table`, `image`, `description` or `structured`. Legacy `/payloads`, `/data-payloads` and typed payload endpoints are removed.
Data record reads and writes use the same `ScientificDocumentV1` plus occurrence contract. Occurrence field projections preserve empty slots so a table can distinguish an unreferenced field from a referenced but unfilled occurrence.

## View and Claim

```text
POST/GET/PUT /views/{id}
GET          /views/{id}/revisions
GET          /views/{id}/revisions/{revision_number}
POST/GET/PUT /claims/{id}
GET          /claims/{id}/revisions/{revision_number}
```

View writes require explicit Data revision and Representation IDs and may pin an Artifact Asset hash. Claim writes require author provenance and a typed Experiment/Data/View primary-source revision; context is captured at creation or by explicit refresh. Evidence can be added or removed through the same conditional Claim update. `GET /claims/by-reference/{object_id}` returns reverse references.

## ChangeSets

External-agent writes use `POST /change-sets/propose`, review, then apply. Create proposals do not carry a target id; apply records the created aggregate identity. Update proposals require `target_id` and `base_record_sha256`, and the applied result returns the new aggregate hash.

## Safety contract

Aggregate writes return `record_sha256` and a quoted `ETag` where applicable. Send `If-Match` for conditional updates. Create-like writes accept `Idempotency-Key`; a different payload under the same key returns `idempotency_conflict`. External-agent writes go through proposal-first ChangeSets.
