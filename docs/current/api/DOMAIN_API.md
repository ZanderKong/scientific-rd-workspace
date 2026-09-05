# Scientific Workspace Domain API v0.3

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

`POST /objects` accepts only the v0.3 kinds. A physical resource uses `kind=research_object` and `tags`. Generic relation writes accept only `references` and `related_to`; `subject` and `derived_from` are system-managed.

Deleting an Experiment removes only that Experiment and its owned `references` rows. Referenced Research Objects, Data and Process Definitions remain independent canonical records and may still be used by other Experiments.

## Process

```text
GET/POST /process-definitions
GET      /process-definitions/{id}
POST     /process-definitions/{id}/versions
POST     /process-executions
GET/PUT  /process-executions/{id}
GET      /objects/{id}/process-executions
```

An execution pins a definition version and accepts multiple object/data bindings. Binding snapshots preserve historical field definitions and values.

## Product projections

```text
GET/PUT  /samples/{id}/record
POST     /sample-records
POST     /experiment-records
GET/PUT  /experiments/{id}/record
```

Sample output is an execution projection. Experiment output is grouped typed references and never ownership/provenance.

## Data and assets

```text
POST     /data-records
GET/PUT  /data/{id}/record
POST     /data/{id}/representations
GET      /data/{id}/representations
GET      /data/{id}/representations/{representation_id}
POST     /data/{id}/imports/preview
POST     /data/{id}/imports/{import_id}/commit
POST     /objects/{id}/assets
GET      /assets/{id}/download
```

Representations are `raw_file`, `table`, `image`, `description` or `structured`. Legacy `/payloads`, `/data-payloads` and typed payload endpoints are removed.

## View and Claim

```text
POST/GET/PUT /views/{id}
GET          /views/{id}/revisions
POST/GET/PUT /claims/{id}
```

View config references Data without copying values. An Execution that consumes a View must persist both the View id and the exact View revision id. Claims expose statement/source/confidence/evidence and append-only revisions; Claim evidence is scope-checked and claim-to-claim cycles are rejected.

## ChangeSets

External-agent writes use `POST /change-sets/propose`, review, then apply. Create proposals do not carry a target id; apply records the created aggregate identity. Update proposals require `target_id` and `base_record_sha256`, and the applied result returns the new aggregate hash.

## Safety contract

Aggregate writes return `record_sha256` and a quoted `ETag` where applicable. Send `If-Match` for conditional updates. Create-like writes accept `Idempotency-Key`; a different payload under the same key returns `idempotency_conflict`. External-agent writes go through proposal-first ChangeSets.
