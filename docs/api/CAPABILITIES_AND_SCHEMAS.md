# Capabilities and Schemas

`GET /api/v1/capabilities` is the compact discovery endpoint. It returns:

- `api_contract_version`;
- the seven object kinds;
- relation types, including non-owning `includes`;
- `scalar`, `xy_series`, `table`, and `file` payload kinds;
- feature flags for records, comparison, execution, ChangeSets, idempotency and optimistic concurrency;
- the external-agent write policy (`proposal`).

Object type and version discovery remains available through `GET /object-types` and `GET /object-types/{id}`. The MCP `object_schema` tool exposes the same JSON Schema and UI schema without creating a second schema registry.

Table schema is explicit: each column has a stable `key`, display `label`, `value_type`, and optional `unit`; rows carry an ordinal, optional source row number, and typed values. No implicit unit conversion or interpolation occurs in comparison.
