# Scientific Workspace Domain API

Base URL: `/api/v1`. The API is object-centric, PostgreSQL-backed, and server-authoritative for project scope and relation semantics.

## Aggregate records

| Domain | Read | Write |
| --- | --- | --- |
| Project | `GET /projects/{id}/record`, `/context`, `/search` | `POST /project-records`, `PUT /projects/{id}/record` |
| Sample | `GET /samples/{id}/record` | `POST /sample-records`, `PUT /samples/{id}/record` |
| Experiment | `GET /experiments/{id}/record`, `/comparison` | `POST /experiment-records`, `PUT /experiments/{id}/record` |
| Data | `GET /data/{id}/record` | `POST /data-records` |
| Execution | `GET /samples/{id}/execution` | `/execution/start`, `PUT /execution`, `/complete`, `/cancel` |

Experiment membership is represented by `includes` relations. It is non-owning and does not replace legacy `contains` ownership or change Sample project scope.

## Typed Data payloads

Create typed payloads with `POST /data/{id}/payloads/scalar`, `/table`, or `/file`. Table requests must provide explicit `columns` and `rows`; values are validated against column types. File payloads reference an existing attachment and preserve its checksum. Existing XY import endpoints remain available and retain source row numbers and source checksums.

## Stable response rules

Aggregate responses include `record_sha256` and write responses also emit the same value as a quoted `ETag`. Send that ETag as `If-Match` for conditional updates. Create-like writes accept `Idempotency-Key`; the same key and request hash replay the stored response, while a different request returns `idempotency_conflict`.

Use `GET /capabilities` to discover contract version, object/relation/payload kinds and write policy.
