# Execution Plan 02 — Scientific Workflow

**Status:** IN PROGRESS — Phase 2 implementation started with explicit authorization

**Baseline:** Phase 1 PASS at commit `9bb494d`

**Release target:** `phase-2-scientific-workflow`

**Goal:** Extend the working ELN core into a traceable scientific-data workflow:

`Raw Attachment → Import → Measurement → Plot → Compare → Literature → Evidence`

**Do not implement:** AI analysis, Finding, Evidence Gate decisions, human review workflow, LangGraph, Langfuse, MCP, embeddings, pgvector, universal instrument parsing, or any other Phase 3 capability.

---

# 0. Planning Outcome

This plan is derived from the repository at `9bb494d`, not from the Phase 2 scope in isolation. Phase 1 is a stable baseline: all additions must preserve the existing project, experiment, exact template-version, attachment, clone, and revision contracts.

The principal Phase 2 decisions are:

1. `Measurement` is a first-class, immutable scientific entity owned by an Experiment.
2. Every imported Measurement has one explicit provenance chain: `Attachment → MeasurementImport → Measurement`.
3. P0 supports one deliberately narrow data shape: a finite numeric x/y series from a rectangular CSV or XLSX table.
4. One import creates one Measurement by mapping one x column and one y column. Importing another y column creates another import from the same raw Attachment.
5. The raw Attachment is retained as the authoritative source. Parsed points are immutable derived data.
6. No value or unit is silently converted. Compare overlays require an exact compatibility signature.
7. Compare is a computed view, not a persisted `Comparison` entity.
8. Literature P0 is local/manual canonical metadata. Zotero is not a Phase 2 P0 dependency.
9. Zotero may be added later as a read-only `LiteratureProvider`; provider payloads must map into the canonical Literature model.
10. Evidence is human-authored in Phase 2, immutable except for explicit withdrawal, and points to exactly one version-stable source.
11. New revisions use an additive snapshot schema v2. Existing Phase 1 snapshot rows are never rewritten.
12. Recharts 3.8.0 and the existing shadcn chart wrapper are reused. No second chart library is added.
13. CSV uses Python's standard library. XLSX uses `openpyxl` in read-only mode with `defusedxml`; pandas, NumPy, xlrd, and client-side spreadsheet parsers are not required.

## 0.1 Zotero decision

Zotero integration remains optional and outside Phase 2 P0.

Reasons:

- manual Literature records satisfy the Phase 2 exit path without credentials or external availability;
- private Zotero libraries require an API key/OAuth, while the local API depends on a configured desktop process;
- making either dependency P0 would make CI and the core demo nondeterministic;
- the canonical model includes `provider`, `external_id`, `provider_version`, and `raw_provider_json`, so a later provider is additive rather than a data-model rewrite.

If separately authorized after P0, implement only a read-only provider boundary:

```text
LiteratureProvider.search(query, cursor) -> ProviderPage
LiteratureProvider.get_item(external_id) -> ProviderLiterature
LiteratureImportService.map(provider_item) -> LiteratureCreate
```

Do not create a fake provider or empty plugin framework during P0. Do not expose Zotero JSON as the product's domain model. Credentials remain server-side.

## 0.2 Dependency verification notes

- The repository already locks Recharts 3.8.0 and contains `web/src/components/ui/chart.tsx`; use its line/scatter primitives and responsive container.
- `openpyxl` supports read-only/lazy workbook loading and `data_only`; the implementation must close every workbook explicitly.
- The openpyxl project warns that XML expansion protections require `defusedxml`; include it with the XLSX reader.
- Zotero Web API v3 remains the recommended API, but private-library reads require credentials. This reinforces the optional-provider decision.

Reference documentation:

- https://openpyxl.readthedocs.io/en/stable/optimized.html
- https://openpyxl.readthedocs.io/en/stable/api/openpyxl.reader.excel.html
- https://pypi.org/project/openpyxl/
- https://recharts.github.io/en-US/api/ScatterChart/
- https://www.zotero.org/support/dev/web_api/v3/
- https://www.zotero.org/support/dev/web_api/v3/basics

---

# 1. Definition of Done

Phase 2 is complete only when all of the following pass against PostgreSQL 17:

1. Upgrade from a populated Phase 1 schema at Alembic revision `0002_immutable_template_versions` succeeds without changing Phase 1 rows.
2. Blank-database upgrade to the new head succeeds and `alembic check` reports no differences.
3. Phase 1 API, UI, clone, attachment, exact-template-version, and revision tests remain green.
4. A user can upload a supported CSV or XLSX file as a normal Attachment.
5. The import wizard previews headers and the first 20 data rows before committing anything derived.
6. For XLSX, the wizard shows available worksheets and the selected worksheet.
7. A user can map exactly one x column and one y column, assign labels and explicit units, select a supported measurement type and line/scatter presentation, and validate the mapping.
8. A successful commit atomically creates one Measurement and all MeasurementPoints, and completes one MeasurementImport.
9. A failed validation creates no Measurement or points, preserves the raw Attachment, and returns actionable file/row/column errors.
10. The completed chain is queryable in both directions: Attachment → Imports and Measurement → Import → Attachment.
11. An Attachment used by a completed Measurement cannot be deleted; the API returns a diagnostic `409 attachment_in_use`.
12. Measurement metadata, summary statistics, provenance, table preview, and line/scatter plot render in the Experiment Data tab.
13. Measurement and point rows are immutable through the Phase 2 API.
14. A user can select 2–5 Experiments from one Project and open Compare.
15. Compare shows template-aware structured-property differences with missing, null, scalar, quantity, array, and schema-version cases distinguished.
16. Compare shows Measurement KPI rows and overlays only compatible series without interpolation, resampling, or unit conversion.
17. A user can create and edit local/manual Literature records and link them to Experiments.
18. A user can create human-authored Evidence with a claim, stance, locator, and exactly one Literature, Measurement, or ExperimentRevision source.
19. Evidence source identity and citation/source snapshots remain stable if current Experiment or Literature metadata later changes.
20. Evidence can be explicitly withdrawn but not edited in place or hard-deleted.
21. Newly created Experiment revisions use snapshot schema v2 and include current Measurement, Literature-link, and Evidence references; Phase 1 snapshots still render.
22. Seed is idempotent and produces three synthetic imported measurement series plus local Literature/Evidence suitable for the Phase 2 demo.
23. Refresh and full PostgreSQL/API/Web restart preserve imported data, Compare inputs, Literature links, Evidence, and provenance.
24. Backend format/lint/tests, frontend lint/typecheck/tests/format/build, and browser console/runtime validation pass.
25. GitHub Actions verifies the same PostgreSQL 17 and frontend gates.
26. A factual `docs/handoff/PHASE_2_HANDOFF.md` is produced only after the complete audit.

If any P0 item above is missing, the verdict is `PHASE 2 NOT READY`.

---

# 2. Stable Phase 1 Contracts

The executor must treat these as non-negotiable unless this plan explicitly adds to them:

- Existing table identities and columns remain intact.
- Experiment IDs remain stable.
- Each Experiment remains permanently bound to its exact immutable `template_id` and `template_version`.
- `structured_data` remains schema-driven JSON and is never moved into Measurement or rich text.
- `note_document` remains separate BlockNote JSON.
- `parent_experiment_id` remains the clone lineage edge.
- Existing ExperimentRevision rows remain immutable.
- Existing revision JSON continues to use `snapshot_json.experiment` and `snapshot_json.attachments`.
- Attachment bytes remain outside PostgreSQL and are accessed through `StorageAdapter`.
- Web continues to call FastAPI over the typed REST client and never accesses PostgreSQL directly.
- Existing routes retain their request/response meanings.
- SQLite remains a development fallback, but PostgreSQL 17 is authoritative for acceptance.

No Phase 2 migration may rewrite Phase 1 `experiments`, `experiment_templates`, or `experiment_revisions` data.

---

# 3. Canonical Phase 2 Data Model

Use additive Alembic migrations. Use the existing portable `JSON` with PostgreSQL `JSONB` variant and SQLAlchemy `Uuid` conventions.

## 3.1 MeasurementImport

Table: `measurement_imports`

```text
MeasurementImport
- id: UUID PK
- experiment_id: UUID FK experiments.id, indexed, required
- source_attachment_id: UUID FK attachments.id, indexed, required
- status: preview_ready | completed | failed
- source_format: csv | xlsx
- parser_key: string, P0 value `tabular-xy`
- parser_version: integer, P0 value 1
- sheet_name: string nullable (required for completed XLSX imports)
- source_sha256: 64-character checksum copied from Attachment at preview time
- header_json: JSON array of unique column names
- source_metadata_json: JSON object with sheet names, detected dimensions, and preview metadata
- mapping_json: JSON nullable; final accepted or rejected mapping
- warnings_json: JSON array
- errors_json: JSON array
- row_count: integer nullable
- created_at
- completed_at nullable
```

Constraints and lifecycle:

- `status`, `source_format`, positive `parser_version`, and non-negative `row_count` have database checks.
- Attachment and Experiment ownership must match; enforce this in the service and tests.
- A row begins as `preview_ready` or `failed`.
- `preview_ready` may transition once to `completed` or `failed`.
- Completed and failed rows are immutable.
- A `preview_ready` or `failed` row without a Measurement may be explicitly discarded; a completed row cannot.
- Preview sample values are returned by the API but are not duplicated into PostgreSQL. Raw bytes remain authoritative.

## 3.2 Measurement

Table: `measurements`

```text
Measurement
- id: UUID PK
- experiment_id: UUID FK experiments.id, indexed, required
- import_id: UUID FK measurement_imports.id, unique, required
- name: string(240), required
- measurement_type: spectral_response | time_series | other_xy
- schema_key: string, P0 value `xy-series`
- schema_version: integer, P0 value 1
- default_chart_type: line | scatter
- x_label: string(120)
- x_unit: string(64), explicit; use `1` for dimensionless
- y_label: string(120)
- y_unit: string(64), explicit; use `1` for dimensionless
- row_count: integer
- summary_json: {x_min, x_max, y_min, y_max, y_mean}
- points_sha256: checksum of canonical ordered point serialization
- created_at
```

Rules:

- One import creates at most one Measurement.
- `measurement.experiment_id` must equal its import's Experiment.
- Measurement has no PATCH or DELETE endpoint in Phase 2.
- Scientific fields, provenance, summary, and point digest are immutable after commit.
- `measurement_type` is intentionally a small controlled set, not an ontology system.
- Do not add arbitrary JSON measurement schemas or a Measurement template designer in P0.

## 3.3 MeasurementPoint

Table: `measurement_points`

```text
MeasurementPoint
- measurement_id: UUID FK measurements.id
- ordinal: integer, zero-based source order
- source_row_number: integer, one-based spreadsheet/CSV row number
- x_value: double precision finite number
- y_value: double precision finite number
```

Constraints:

- composite primary key `(measurement_id, ordinal)`;
- unique `(measurement_id, source_row_number)`;
- ordinals and row numbers are non-negative/positive;
- values must be finite; validate in Python before insert because portable finite checks differ by dialect;
- point order is the source row order; do not sort, interpolate, average, or deduplicate.

## 3.4 LiteratureRecord

Table: `literature_records`

```text
LiteratureRecord
- id: UUID PK
- project_id: UUID FK projects.id, indexed, required
- item_type: journal_article | conference_paper | book_chapter | report | preprint | other
- title: string(500), required
- authors_json: ordered JSON array of {family, given} or {literal}
- publication_year: integer nullable
- container_title: string(500) nullable
- doi: string(255) nullable, trimmed and normalized for display/search
- url: string(2000) nullable
- abstract: text nullable
- provider: string nullable; reserved for `zotero`
- external_id: string nullable
- provider_version: string nullable
- raw_provider_json: JSON nullable
- created_at
- updated_at
```

Constraints:

- unique `(project_id, provider, external_id)` when provider identity is present;
- manual P0 rows have provider fields null;
- validate author shape, year range, DOI length, and HTTP(S) URL at the API boundary;
- Literature metadata may be corrected through PATCH;
- Evidence stores a citation snapshot so later Literature corrections do not change historical Evidence meaning.

This is a bibliography record, not a reference-manager replacement. Do not add collections, tags, PDFs, annotations, citation-style rendering, sync state, or full-text indexing in P0.

## 3.5 ExperimentLiteratureLink

Table: `experiment_literature_links`

```text
ExperimentLiteratureLink
- id: UUID PK
- experiment_id: UUID FK experiments.id, indexed
- literature_id: UUID FK literature_records.id, indexed
- relationship_type: background | method | comparison | supporting | contradicting
- notes: text nullable
- created_at
```

Constraints:

- unique `(experiment_id, literature_id)`;
- Experiment and Literature must belong to the same Project;
- links may be updated or removed without modifying either source entity.

## 3.6 EvidenceRecord

Table: `evidence_records`

```text
EvidenceRecord
- id: UUID PK
- project_id: UUID FK projects.id, indexed
- context_experiment_id: UUID FK experiments.id nullable, indexed
- claim_text: text, required
- stance: supports | contradicts | context
- source_type: literature | measurement | experiment_revision
- literature_id: UUID FK literature_records.id nullable
- measurement_id: UUID FK measurements.id nullable
- experiment_revision_id: UUID FK experiment_revisions.id nullable
- locator: string(500) nullable
- notes: text nullable
- source_snapshot_json: JSON, required
- status: active | withdrawn
- withdrawal_reason: string(1000) nullable
- created_at
- withdrawn_at nullable
```

Constraints and semantics:

- exactly one of `literature_id`, `measurement_id`, and `experiment_revision_id` is non-null;
- the non-null FK must match `source_type`;
- every source and optional context Experiment must belong to `project_id`;
- Experiment evidence must point to an immutable ExperimentRevision, not mutable live Experiment state;
- Literature evidence snapshots canonical citation fields at creation;
- Measurement evidence snapshots immutable measurement identity, labels, units, summary, point digest, import ID, raw Attachment ID, and raw checksum;
- ExperimentRevision evidence snapshots experiment ID/code, revision number, template ID/version, and revision creation time;
- claim, stance, source, locator, notes, and source snapshot are immutable;
- withdrawal is an explicit state transition with reason and time; no hard delete is exposed.

This shape is intentionally suitable for Phase 3 Findings to reference Evidence IDs later, but Phase 2 does not create Findings, gate decisions, confidence scores, reviews, or evaluation cases.

---

# 4. Narrow Tabular Import Contract

## 4.1 Supported files

P0 supports only:

- `.csv`: comma-delimited, UTF-8 or UTF-8 with BOM, first row is the header;
- `.xlsx`: Office Open XML workbook, one selected visible worksheet, first row is the header.

Explicitly unsupported:

- `.xls`, `.xlsb`, `.xlsm`, TSV, locale-specific decimal commas, password-protected files;
- merged/multi-row headers, pivot tables, charts, hidden scientific metadata, macros;
- multiple tables per worksheet, ragged tables, instrument-vendor binary formats;
- image/PDF OCR, automatic instrument detection, automatic unit conversion;
- more than one x and one y mapping per import.

The wizard must describe this supported shape before upload.

## 4.2 Resource limits

Add backend settings with documented defaults:

```text
MAX_IMPORT_BYTES=10485760       # 10 MiB, below the general 25 MiB attachment cap
MAX_IMPORT_ROWS=10000
MAX_IMPORT_COLUMNS=100
IMPORT_PREVIEW_ROWS=20
MAX_XLSX_EXPANDED_BYTES=52428800
MAX_XLSX_ARCHIVE_ENTRIES=200
```

Enforce limits server-side during preview and again during commit. Do not trust the client preview.

## 4.3 CSV parser rules

- Use `csv` from the Python standard library.
- Decode only `utf-8-sig`; invalid bytes are a diagnostic validation failure.
- Reject NUL bytes and non-text/binary content.
- Use comma delimiter and standard quote handling; do not guess dialects.
- Header cells must be nonblank and unique after trim.
- Preserve original header spelling in provenance; mapping uses exact header values.
- Require a rectangular table.
- Ignore only completely empty trailing rows and report their count as a warning.
- A completely empty internal row is an error, not silently dropped.

## 4.4 XLSX parser rules

- Add `openpyxl>=3.1.5,<4` and `defusedxml>=0.7,<1` through uv and refresh `uv.lock`.
- Check archive entry count and total uncompressed size before openpyxl reads it.
- Load with `read_only=True`, `data_only=True`, and `keep_links=False`; always close in `finally` or a context-owning adapter.
- Return all visible worksheet names and the selected worksheet.
- Default preview to the first visible worksheet, but require the chosen name in the final mapping.
- Do not evaluate formulas. Use the cached value exposed by `data_only=True`; a mapped formula without a cached finite numeric value is a row validation error.
- Reject encrypted, corrupt, macro-enabled, or invalid OOXML packages.
- Apply the same header, rectangularity, row, and column limits as CSV.

## 4.5 Mapping rules

Commit payload:

```json
{
  "measurement_name": "Absorbance spectrum",
  "measurement_type": "spectral_response",
  "default_chart_type": "line",
  "sheet_name": "Sheet1",
  "x": {
    "column": "wavelength_nm",
    "label": "Wavelength",
    "unit": "nm"
  },
  "y": {
    "column": "absorbance_au",
    "label": "Absorbance",
    "unit": "AU"
  }
}
```

Validation:

- x and y columns must exist and be different;
- names, labels, and units are trimmed and nonblank;
- use the literal unit `1` for a dimensionless axis;
- every mapped cell must parse as a finite number; booleans, dates, blanks, NaN, and infinity fail;
- all errors include source row number and column;
- report the total error count and return at most the first 50 detailed errors;
- record every unmapped column name in `mapping_json.ignored_columns` so omission is explicit;
- non-monotonic x and duplicate x values are warnings, not silent corrections;
- the parser never sorts points or coerces units.

## 4.6 Atomic commit

On `commit`:

1. lock the `preview_ready` MeasurementImport row;
2. verify import ownership, status, Attachment row, Attachment checksum, source format, sheet, and headers;
3. parse and validate the full source again;
4. construct canonical ordered points, summary statistics, and point digest;
5. in one database transaction insert Measurement and all points and mark the import completed;
6. return the created Measurement.

If scientific/file validation fails:

- roll back Measurement and all point inserts;
- in a separate transaction mark the import `failed` and persist mapping, warnings, and errors;
- return structured `422` details containing `import_id`;
- keep the Attachment bytes and metadata.

If database/infrastructure commit fails:

- roll back all derived rows;
- leave the import `preview_ready` so the same operation can be safely retried;
- return a server error without deleting or mutating the raw Attachment.

Calling commit on a completed or scientifically failed import returns `409` and never duplicates a Measurement.

---

# 5. Provenance and Immutability

## 5.1 Required provenance chain

Every Measurement detail response must expose:

```text
Measurement
  └── import_id → MeasurementImport
        ├── parser_key + parser_version
        ├── mapping_json
        ├── source_sha256
        └── source_attachment_id → Attachment
              └── storage_key → StorageAdapter bytes
```

The API must never accept a client-supplied checksum, summary, row count, point digest, parser version, or provenance FK as authoritative.

## 5.2 Attachment deletion

- An Attachment referenced by a completed MeasurementImport is authoritative raw data and cannot be deleted.
- Return HTTP `409` with code `attachment_in_use`, a human message, and referencing import/measurement IDs.
- An unused Attachment retains the Phase 1 database-first deletion ordering.
- A non-completed import may be explicitly discarded first; completed imports cannot be discarded.
- Storage cleanup failures retain the Phase 1 diagnostic/orphan semantics.

## 5.3 Measurement immutability

- Do not expose Measurement or MeasurementPoint PATCH/DELETE routes.
- Add service/ORM guards and tests against in-place mutation through application sessions.
- Corrections require a new import and new Measurement, preserving the old chain.
- The UI labels the newer record separately; supersession workflows are deferred unless actual use requires them.

## 5.4 Revision snapshot schema v2

Newly created revision JSON adds fields without removing Phase 1 keys:

```json
{
  "snapshot_schema_version": 2,
  "experiment": { "...existing Phase 1 shape...": true },
  "attachments": [],
  "measurements": [
    {
      "id": "...",
      "name": "Absorbance spectrum",
      "measurement_type": "spectral_response",
      "schema_key": "xy-series",
      "schema_version": 1,
      "x_label": "Wavelength",
      "x_unit": "nm",
      "y_label": "Absorbance",
      "y_unit": "AU",
      "row_count": 301,
      "summary_json": {},
      "points_sha256": "...",
      "import_id": "...",
      "source_attachment_id": "...",
      "source_sha256": "..."
    }
  ],
  "literature_links": [],
  "evidence": []
}
```

Rules:

- Existing rows without `snapshot_schema_version` are interpreted as schema v1.
- Never backfill or rewrite Phase 1 snapshot JSON.
- Keep `snapshot_json.experiment.note_document` and the existing exact template identity unchanged.
- Do not copy Measurement points or Attachment bytes into revision JSON.
- Measurement/Evidence IDs are safe references because those entities are immutable/non-deletable.
- Literature link entries include a citation snapshot so later metadata edits do not rewrite the revision's meaning.
- Revision UI renders new sections read-only only when present.

---

# 6. API Contracts

All routes remain under `/api/v1`. Pydantic request and response types are authoritative and must appear correctly in OpenAPI.

## 6.1 Structured import errors

Extend the frontend client to parse both legacy string `detail` and this import-specific shape:

```json
{
  "detail": {
    "code": "non_numeric_value",
    "message": "3 mapped cells are invalid.",
    "import_id": "uuid-or-null",
    "errors": [
      {"row": 14, "column": "absorbance_au", "message": "Expected a finite number."}
    ],
    "warnings": []
  }
}
```

Do not silently flatten away row/column information in the Web client.

## 6.2 Imports and Measurements

```text
POST   /experiments/{experiment_id}/measurement-imports/preview
GET    /experiments/{experiment_id}/measurement-imports
GET    /measurement-imports/{import_id}
POST   /measurement-imports/{import_id}/commit
DELETE /measurement-imports/{import_id}                  # only non-completed/no Measurement

GET    /experiments/{experiment_id}/measurements
GET    /measurements/{measurement_id}
GET    /measurements/{measurement_id}/points
```

Preview request:

```json
{"source_attachment_id": "uuid", "sheet_name": "optional"}
```

Preview response (`201`): import identity/status, source Attachment summary, available/selected sheets, headers, first 20 rows, detected row/column counts, and warnings.

Measurement list response excludes points but includes summary and provenance IDs. Measurement detail includes import and Attachment metadata. Points response returns ordered `{ordinal, source_row_number, x_value, y_value}` rows; no pagination is required while the hard 10,000-row limit remains.

Status codes:

- `404`: Experiment, Attachment, import, or Measurement not found;
- `409`: cross-Experiment source, source checksum/header change, invalid import state, duplicate commit, or referenced Attachment deletion;
- `413`: import resource limits exceeded;
- `415`: unsupported extension/media/signature;
- `422`: recognized file or mapping is scientifically/structurally invalid.

## 6.3 Compare

Compare remains read-only and non-persistent:

```text
POST /comparisons/experiments
```

Request:

```json
{
  "project_id": "uuid",
  "experiment_ids": ["uuid", "uuid"],
  "measurement_ids": ["optional", "uuid"]
}
```

Validation:

- 2–5 unique Experiments;
- all belong to `project_id`;
- selected Measurements belong to selected Experiments;
- no cross-Project Compare in P0.

Response contains:

- Experiment identity, parent, template ID/version, and status;
- structured-difference rows;
- Measurement summaries and compatibility signatures;
- incompatibility reasons;
- no persisted Comparison ID.

The UI fetches compatible point sets through the Measurement points endpoint. Do not duplicate every point in the comparison metadata response.

## 6.4 Literature and links

```text
GET|POST /projects/{project_id}/literature
GET|PATCH /literature/{literature_id}

GET|POST /experiments/{experiment_id}/literature-links
PATCH|DELETE /experiment-literature-links/{link_id}
```

List Literature supports `q` and optional `publication_year`; keep search simple and server-side. No full-text engine is added.

Link creation rejects cross-Project records with `409` and duplicates with `409`.

## 6.5 Evidence

```text
GET|POST /projects/{project_id}/evidence
GET      /evidence/{evidence_id}
POST     /evidence/{evidence_id}/withdraw
```

Evidence create uses a discriminated source union rather than exposing nullable FK combinations:

```json
{
  "context_experiment_id": "optional-uuid",
  "claim_text": "Starch increases response near 450 nm in this synthetic dataset.",
  "stance": "supports",
  "source": {
    "type": "measurement",
    "measurement_id": "uuid",
    "locator": "430–470 nm"
  },
  "notes": "Human-authored Phase 2 evidence note."
}
```

Alternative source variants are `literature_id` and `{experiment_id, revision_number}`. The service resolves the latter to `experiment_revision_id` and snapshots source metadata server-side.

Evidence list filters may include `context_experiment_id`, `source_type`, and `status`. No claim generation, ranking, confidence, or automated support classification is permitted.

---

# 7. Compare Semantics

## 7.1 Structured-property differences

The backend computes deterministic rows from each Experiment's live `structured_data` and exact template schema.

Algorithm:

1. Load each exact `template_id`; never substitute the active version.
2. Build the union of schema/data JSON Pointer paths.
3. Treat missing as distinct from explicit `null`.
4. Render scalar leaves directly.
5. Recognize a quantity only when the schema describes an object with `value` and `unit`; compare both together without conversion.
6. Treat arrays and other composite objects as canonical JSON values in P0; do not invent domain-specific matching.
7. Preserve schema labels where available; fall back to the JSON Pointer.
8. Mark a row different when presence, type, value, or unit differs.
9. Return all rows and a `differs` flag; UI defaults to different-only and offers show-all.
10. If template versions differ, show both versions and never assume renamed paths are semantically equivalent.

## 7.2 Measurement compatibility

Compatibility signature:

```text
(measurement_type, schema_key, schema_version, x_unit, y_unit)
```

Rules:

- exact trimmed, case-sensitive unit match only;
- x grids do not need to be identical; each series keeps its own points;
- no interpolation, resampling, smoothing, normalization, baseline correction, or unit conversion;
- incompatible series are listed with reasons and are not drawn on the same axes;
- compatible line and scatter series may share a chart; each keeps its chosen marker/line style;
- KPI table shows row count, x min/max, y min/max, and y mean from immutable summaries;
- no statistical significance, regression, area-under-curve, or scientific conclusion is calculated in P0.

---

# 8. UI and Navigation

Reuse the existing dashboard shell, API client, TanStack Query, TanStack Table, shadcn primitives, and Recharts wrapper. New feature code should be split by feature rather than making `experiment-detail.tsx` larger.

## 8.1 Navigation additions

Add only when the corresponding route is functional:

```text
Scientific R&D
├── Overview
├── Projects
├── Experiments
├── Compare
└── Literature
```

Evidence is contextual inside Project/Experiment/Literature surfaces in Phase 2; it does not need a top-level placeholder route.

## 8.2 Experiment Data tab

Add `Data` to Experiment detail without changing Phase 1 tabs.

Data tab states:

- no Measurements: explanation plus `Import measurement` action;
- import in progress: wizard state and cancel/discard action;
- failed import: structured errors and raw Attachment link;
- Measurement list: name, type, axes/units, rows, created time, provenance link;
- selected Measurement: KPI summary, table preview, line/scatter plot, provenance panel.

The provenance panel links:

`Measurement → Import mapping/parser → Raw Attachment download`

## 8.3 Import wizard

Steps:

1. **Raw file** — select an existing CSV/XLSX Attachment or upload through the Phase 1 Attachment endpoint.
2. **Preview** — show format, sheets, selected sheet, headers, first 20 rows, detected dimensions, limits, and warnings.
3. **Map** — choose measurement name/type/chart, x and y columns, labels, and explicit units.
4. **Validate** — submit commit, show warnings/errors without losing mapping state.
5. **Complete** — open the immutable Measurement detail.

Requirements:

- no client-only authoritative parsing;
- preview table horizontally scrolls and clearly identifies ignored columns;
- row/column errors are visible and grouped, not hidden in a toast;
- changing XLSX sheet creates a new preview attempt or discards the prior non-completed attempt;
- browser refresh after completion loads canonical API state;
- no mock API.

## 8.4 Compare route

Route:

```text
/dashboard/compare?project={id}&experiments={id1},{id2}
```

Flow:

- Project selector;
- Experiment selector limited to 2–5 in that Project;
- shareable URL state using existing `nuqs` patterns;
- summary row with code/title/status/template version/parent;
- structured differences table, different-only by default;
- Measurement selector grouped by Experiment;
- KPI table;
- compatible overlay charts and explicit incompatible-series messages;
- loading, empty, validation, and backend-unreachable states.

Project detail should expose a `Compare selected` action, but the dedicated route owns comparison rendering.

## 8.5 Literature routes

Routes:

```text
/dashboard/literature
/dashboard/literature/[literatureId]
```

List columns: title, first author/author summary, year, container, DOI, linked Experiments, updated time.

P0 actions:

- create manual record;
- edit manual metadata;
- search by title/author/DOI text;
- open detail;
- link/unlink from an Experiment with relationship type and notes.

The detail page shows canonical metadata, linked Experiments, and Evidence using this source. Do not add citation-style selection or PDF management.

## 8.6 Evidence UI

Experiment detail gains an `Evidence` section or tab only when functional.

Create form:

- human-authored claim text;
- stance;
- one source selector: linked Literature, current Experiment revision, or Measurement;
- locator;
- notes;
- source preview before save.

Read view:

- claim and stance;
- context Experiment;
- immutable source identity/snapshot;
- link to Literature, Measurement provenance, or revision viewer;
- active/withdrawn status;
- explicit withdraw action with reason.

The UI must say `Human-authored evidence`; it must not imply AI generation or scientific validation.

---

# 9. Failure Behaviour Matrix

| Situation | HTTP/UI behaviour | Persistence guarantee |
| --- | --- | --- |
| General Attachment exceeds 25 MiB | Existing `413` | No metadata; temporary bytes cleaned as in Phase 1. |
| Import source exceeds 10 MiB | `413 import_too_large` | Raw Attachment remains; no derived rows. |
| Unsupported extension/signature | `415 unsupported_import_format` | Raw Attachment remains; no Measurement. |
| Invalid UTF-8/binary CSV | `422 invalid_csv_encoding` | Failed import may be inspected/discarded; no Measurement. |
| XLSX zip expansion/entry limit | `413 unsafe_xlsx_archive` | Raw Attachment remains; no workbook processing or Measurement. |
| Corrupt/encrypted XLSX | `422 invalid_xlsx` | Failed import with diagnostic; no Measurement. |
| Missing/duplicate headers | `422 invalid_header` | Failed import; no Measurement. |
| Wrong Experiment Attachment | `409 attachment_experiment_mismatch` | No import/Measurement. |
| Unknown sheet | `422 sheet_not_found` with available names | No Measurement. |
| Too many rows/columns | `413 import_shape_limit` | Failed import; no Measurement. |
| Missing mapping/unit | `422 invalid_mapping` | Import failed; no Measurement/points. |
| Non-numeric/blank/NaN/infinite mapped value | `422 non_numeric_value` with row/column | Import failed; no Measurement/points. |
| Non-monotonic or duplicate x | Success with visible warning | Source order retained; no correction. |
| Commit called twice | `409 import_already_finalized` | Exactly one Measurement. |
| Source checksum/header changes | `409 source_changed` | No new derived rows. |
| Database commit fails | `500`, retry offered | All derived rows rolled back; import stays retryable; raw source untouched. |
| Delete referenced raw Attachment | `409 attachment_in_use` | Metadata and bytes retained. |
| Compare cross-Project or >5 | `422 invalid_comparison` | No persistence. |
| Compare unit mismatch | Inline incompatibility message | No conversion or partial overlay. |
| Literature duplicate provider identity | `409 duplicate_literature` | Existing record returned/linked as appropriate. |
| Evidence source outside Project | `409 evidence_source_project_mismatch` | No Evidence row. |
| Evidence invalid source combination | `422` through discriminated schema/DB check | No Evidence row. |
| Withdraw Evidence twice | Idempotent `200` if same state or diagnostic `409` | No hard delete or source mutation. |

---

# 10. Migration and Backwards Compatibility

## 10.1 Migration sequence

- `0003_measurements_and_imports`: add `measurement_imports`, `measurements`, and `measurement_points` only.
- `0004_literature_and_evidence`: add `literature_records`, `experiment_literature_links`, and `evidence_records` only.

Do not edit `0001_phase1_foundation` or `0002_immutable_template_versions` after the Phase 1 baseline.

## 10.2 Upgrade checks

CI and local verification must cover both:

1. blank PostgreSQL → Alembic head;
2. populated Phase 1 schema at `0002` → head.

The populated upgrade fixture must include:

- one immutable template version;
- one Project and Experiment with structured data and BlockNote JSON;
- one Attachment row;
- one revision using the Phase 1 snapshot shape.

After upgrade, assert all IDs, JSON, template constraints, Attachment metadata, and revision bytes are unchanged. Then exercise a new Measurement import against that Experiment.

## 10.3 Downgrade policy

Downgrade functions may drop only the Phase 2 tables in reverse dependency order. A downgrade is destructive to Phase 2 data and is a test/development operation, not an application workflow. Never downgrade a user database automatically.

## 10.4 SQLite fallback

- Keep JSON/UUID/check constraints portable where practical.
- Use a portable CASE-based check for exactly one Evidence source rather than PostgreSQL-only `num_nonnulls`.
- Run the development fallback migration and seed in CI or local verification.
- PostgreSQL-specific indexes may be added only if a measured query requires them; do not add speculative GIN indexes in P0.

---

# 11. Milestone Plan

Every milestone ends with a runnable product, a focused commit, verification, and a factual Implementation Note appended to this file. Do not begin the next milestone while a relevant check is failing.

## Milestone 1 — Lock Contracts and Add Measurement Schema

### Objective

Turn the approved plan into durable source-of-truth updates and add only the foundational Measurement/Import schema.

### Tasks

1. Update `AGENTS.md` active target to Phase 2 without deleting the Phase 1 history.
2. Add the approved Phase 2 entities/invariants to `docs/DATA_MODEL.md`.
3. Add import/compare/literature/evidence boundaries to `ARCHITECTURE.md` and Phase 2 UI routes to `docs/UI_SPEC.md`.
4. Add `openpyxl` and `defusedxml` to `api/pyproject.toml` and refresh `uv.lock`; do not add pandas/NumPy/xlrd.
5. Add SQLAlchemy models and relationships for MeasurementImport, Measurement, and MeasurementPoint.
6. Add migration `0003_measurements_and_imports` with explicit names, checks, FKs, unique constraints, and indexes.
7. Add Pydantic enums and read schemas without exposing mutation routes yet.
8. Add blank and populated-Phase-1 PostgreSQL migration verification.

### Acceptance

- Migration is additive and preserves populated Phase 1 data byte-for-byte at the application-field level.
- One Import can own at most one Measurement.
- Models and migration agree on PostgreSQL.
- Phase 1 API/UI behavior is unchanged.
- No import or Measurement UI is exposed yet.

### Verify

```bash
cd api
uv sync --locked
uvx ruff check app tests alembic
uvx ruff format --check app tests alembic
DATABASE_URL=<postgresql17-url> uv run alembic upgrade head
DATABASE_URL=<postgresql17-url> uv run alembic check
TEST_DATABASE_URL=<postgresql17-url> uv run pytest
```

Run the dedicated `0002 populated → head` migration test and the SQLite local bootstrap migration.

## Milestone 2 — Narrow Parser, Preview, and Atomic Import API

### Objective

Implement the highest-risk Phase 2 path on the backend before building UI.

### Tasks

1. Create a focused parser boundary such as `TabularMeasurementParser`; do not build a plugin registry.
2. Implement CSV and XLSX adapters exactly to Section 4 limits.
3. Add archive/encoding/shape/header safety checks and structured import errors.
4. Implement preview service and `POST .../measurement-imports/preview`.
5. Implement commit service with row lock, checksum/header revalidation, finite numeric validation, summaries, point digest, bulk point insert, and atomic status transition.
6. Add import list/detail/discard routes and Measurement list/detail/points routes.
7. Add Measurement/point immutability guards.
8. Add Attachment deletion guard for referenced completed imports while preserving Phase 1 delete ordering for unused files.
9. Add small deterministic CSV/XLSX fixtures, including corrupt and hostile-shape cases.

### Acceptance

- Same logical CSV and XLSX input produce the same canonical point sequence/digest.
- Preview creates no Measurement.
- Commit creates exactly one Measurement and all points atomically.
- Scientific validation failure creates zero derived rows and preserves raw bytes.
- Infrastructure failure rolls back and remains retryable.
- Referenced raw Attachment deletion returns diagnostic 409.
- No universal parser behavior or unit conversion appears.

### Verify

```bash
cd api
uvx ruff check app tests alembic
uvx ruff format --check app tests alembic
TEST_DATABASE_URL=<postgresql17-url> uv run pytest tests/test_measurement_parser.py tests/test_measurement_imports.py tests/test_attachments.py
```

Also inspect generated OpenAPI for all success/error contracts.

## Milestone 3 — Import Wizard and Measurement Visualization

### Objective

Deliver the complete user-facing import and single-Experiment data flow.

### Tasks

1. Add typed Measurement, Import, preview, mapping, point, and structured-error contracts to the Web domain/API layer.
2. Split new Data functionality into feature modules/components; do not further inflate the existing experiment detail component.
3. Add the Experiment `Data` tab and all empty/loading/error states.
4. Build the five-step Import wizard from Section 8.3 using the existing Attachment upload endpoint.
5. Preserve mapping form state on validation errors and render row/column details inline.
6. Add Measurement list/detail, summary cards, points table preview, and provenance panel.
7. Reuse Recharts/shadcn ChartContainer for accessible responsive line/scatter rendering.
8. Add tests for API error decoding, wizard transitions, unit requirements, ignored columns, and chart data shaping.
9. Browser-test CSV and XLSX flows against PostgreSQL.

### Acceptance

- A user completes upload → preview → map → validate → Measurement without terminal/database intervention.
- The raw file is visible/downloadable before and after import.
- Error cases never show a success state or lose actionable details.
- Chart axes show explicit labels and units.
- Refresh loads the same immutable Measurement/provenance.
- Existing Overview/Record/Files/Revisions behavior remains intact.

### Verify

```bash
cd web
npm run lint
npm run typecheck
npm run test
npm run format:check
npm run build
```

Browser checks: supported CSV, multi-sheet XLSX selection, invalid numeric row, unsupported `.xls`, refresh, download raw source, and browser console.

## Milestone 4 — Compare Service and API

### Objective

Implement deterministic structured-data and Measurement compatibility comparison without persistence.

### Tasks

1. Implement schema-aware JSON Pointer flattening and quantity handling from Section 7.1.
2. Load exact historical template rows for every Experiment.
3. Implement Measurement compatibility signatures and reason codes.
4. Implement `POST /comparisons/experiments` with same-Project and cardinality checks.
5. Return stable structured rows, Experiment summaries, Measurement summaries, compatibility groups, and incompatibility reasons.
6. Add tests for same/different template versions, missing vs null, quantities, arrays, ignored schema paths, unit mismatch, differing x grids, and cross-Project rejection.

### Acceptance

- Compare never mutates or persists domain state.
- Different template versions are explicit.
- Unknown semantic equivalence is not invented.
- No unit conversion, interpolation, normalization, or statistical conclusion occurs.
- Response ordering is deterministic for stable UI/tests.

### Verify

```bash
cd api
uvx ruff check app tests
uvx ruff format --check app tests
TEST_DATABASE_URL=<postgresql17-url> uv run pytest tests/test_compare.py
```

## Milestone 5 — Compare UI

### Objective

Make the Phase 2 comparison path understandable and shareable.

### Tasks

1. Add the functional `/dashboard/compare` route and then expose the nav item.
2. Add same-Project selector and 2–5 Experiment multi-select with URL state.
3. Add `Compare selected` from Project detail.
4. Render Experiment identity/template/parent summary.
5. Render structured difference table with different-only default and show-all toggle.
6. Add Measurement selectors, KPI table, compatible overlay charts, and incompatibility messages.
7. Fetch point sets in parallel with TanStack Query; avoid request waterfalls.
8. Add loading/empty/error states and keyboard-accessible selection.
9. Test URL parsing, selection bounds, table rows, compatibility grouping, and chart series shaping.

### Acceptance

- EXP-041/044/045 can be selected and shared through a URL.
- Structured changes and Measurement overlays appear in one coherent page.
- Incompatible units are never plotted together.
- Series retain distinct Experiment labels/colors and raw x grids.
- Page remains usable at 1024 px and stable at 1280 px+.

### Verify

Run the complete frontend suite and a PostgreSQL-backed browser Compare flow, including reload and direct navigation to the query URL.

## Milestone 6 — Literature and Evidence Schema

### Objective

Add canonical local bibliography and Phase-3-compatible Evidence storage without external providers.

### Tasks

1. Add SQLAlchemy models for LiteratureRecord, ExperimentLiteratureLink, and EvidenceRecord.
2. Add migration `0004_literature_and_evidence` with portable source checks and indexes.
3. Add Pydantic canonical author, Literature, link, discriminated Evidence-source, and withdrawal schemas.
4. Add Literature citation snapshot and Evidence source snapshot builders.
5. Add immutable Evidence field guards with allowed withdrawal transition.
6. Extend blank/populated migration tests.
7. Do not add Zotero HTTP clients, secrets, OAuth, provider UI, AI, or Finding tables.

### Acceptance

- Database enforces exactly one Evidence source.
- Cross-Project relationships are rejected by services.
- Literature remains editable while Evidence source snapshots remain unchanged.
- Experiment Evidence resolves an immutable revision.
- Measurement Evidence captures the complete raw-data provenance identity.

### Verify

Run Ruff, migration parity, PostgreSQL model tests, Evidence constraint tests, and all Phase 1/Measurement regressions.

## Milestone 7 — Manual Literature and Experiment Links

### Objective

Deliver local/manual Literature records and Experiment associations as the reliable P0 path.

### Tasks

1. Implement Literature list/create/get/patch services and routes.
2. Implement Experiment Literature link list/create/patch/delete services and routes.
3. Add typed Web feature API/query/mutation modules.
4. Build Literature list, search/filter, create/edit form, and detail routes.
5. Add linked Experiment sections to Literature and Experiment detail.
6. Add loading/empty/error/duplicate/cross-Project states.
7. Add backend/API/frontend/browser tests.

### Acceptance

- Manual Literature works offline with no credentials.
- Ordered author data round-trips without being flattened into one opaque string.
- Experiment links show relation type and notes.
- Duplicate and cross-Project links are diagnostic.
- No UI implies Zotero sync exists.

### Verify

Run backend and frontend suites plus browser create/edit/link/unlink/reload checks against PostgreSQL.

## Milestone 8 — Evidence UI and Revision Snapshot v2

### Objective

Connect human-authored claims to stable scientific sources and include provenance references in new revisions.

### Tasks

1. Implement Evidence list/create/get/withdraw services and routes.
2. Resolve and snapshot Literature, Measurement, or ExperimentRevision sources server-side.
3. Build contextual Evidence create/read/withdraw UI.
4. Clearly label all records as human-authored Phase 2 evidence.
5. Extend revision creation to snapshot schema v2.
6. Extend the revision parser/viewer to support v1 and v2 without changing old rows.
7. Render Measurement, Literature-link, and Evidence sections read-only in v2 revision views.
8. Add tests proving source/current metadata changes do not alter Evidence or revision snapshots.

### Acceptance

- Evidence contains exactly one immutable/versioned source.
- Live Literature/Experiment changes do not change Evidence snapshots.
- Withdrawal preserves the record and reason.
- Old Phase 1 revisions render exactly as before.
- New v2 revisions expose the current scientific-data/evidence context without copying raw bytes or points.

### Verify

Run targeted provenance/revision tests, full backend/frontend suites, and browser checks opening both seeded v1 and newly created v2 revisions.

## Milestone 9 — Synthetic Phase 2 Seed and Demo Story

### Objective

Create a deterministic, honest demo that exercises the real importer and complete Phase 2 path.

### Tasks

1. Add three small tracked synthetic CSV fixtures for EXP-041, EXP-044, and EXP-045 with compatible wavelength/response axes.
2. Extend seed idempotently: create raw Attachments through StorageAdapter and derived data through the same importer service used by the API.
3. Seed three Measurements with distinguishable curves and explicit synthetic/anonymized labels.
4. Seed at least two manual Literature records, Experiment links, and human-authored Evidence records.
5. Do not claim the values are real scientific findings.
6. Extend `docs/DEMO_SCENARIO.md` with the Phase 2 script.
7. Verify seed twice on PostgreSQL and SQLite without duplicate files, imports, measurements, points, links, or Evidence.

### Acceptance

The demo runs:

```text
Open EXP-045
→ inspect raw CSV Attachment
→ preview/map/import a Measurement
→ plot it
→ compare EXP-041/044/045
→ see structured differences and compatible overlays
→ open linked Literature
→ open human-authored Evidence and provenance
→ create/open a v2 revision
```

All data is real persisted application data produced through canonical services, not UI mocks or direct database inserts for derived entities.

### Verify

Run seed twice, assert exact counts/checksums/digests, restart PostgreSQL/API/Web, and repeat the full browser demo.

## Milestone 10 — CI, Full Audit, and Phase 2 Handoff

### Objective

Close Phase 2 only after every P0 contract is proven against PostgreSQL.

### Tasks

1. Rename/extend the existing workflow to a phase-neutral CI workflow while retaining all Phase 1 gates.
2. Backend CI: PostgreSQL 17 service, blank migration, populated `0002 → head` migration, `alembic check`, seed twice, parser/import/provenance/API tests, and full pytest.
3. Frontend CI: tracked npm lock, `npm ci`, lint, typecheck, tests, format check, and production build.
4. Run the complete browser audit against a PostgreSQL-backed API.
5. Inspect browser console, network failures, loading/empty/error states, and direct route reloads.
6. Re-audit license notices for new direct dependencies.
7. Confirm no Phase 3 packages, models, routes, jobs, navigation, or placeholder UI were added.
8. Update source-of-truth docs to actual implementation details.
9. Create `docs/handoff/PHASE_2_HANDOFF.md` with exact schema, routes, commands, results, known debt, and commit.

### Acceptance

- All Definition of Done items pass against PostgreSQL 17.
- GitHub Actions is green on the closeout commit.
- Repository is clean and remote main matches the closeout commit when push is authorized.
- Handoff contains no pending PostgreSQL or demo claims.
- Verdict is `PHASE 2 PASS`; otherwise report `PHASE 2 NOT READY` and exact blockers.

### Verify

```bash
cd api
uv sync --locked
uvx ruff check app tests alembic
uvx ruff format --check app tests alembic
DATABASE_URL=<postgresql17-url> uv run alembic upgrade head
DATABASE_URL=<postgresql17-url> uv run alembic check
TEST_DATABASE_URL=<postgresql17-url> uv run pytest

cd ../web
npm ci
npm run lint
npm run typecheck
npm run test
npm run format:check
npm run build
```

---

# 12. Test Matrix

## 12.1 Backend unit tests

- CSV encoding, quoting, header, shape, row/column limits;
- XLSX sheet enumeration/selection, read-only close, cached formula values, corrupt/encrypted/zip-bomb guards;
- numeric finite conversion and exact source row numbers;
- summary statistics and deterministic point digest;
- JSON Pointer structured comparison and quantity recognition;
- Measurement compatibility signatures;
- author/DOI/URL validation;
- Evidence discriminated sources and source snapshots.

## 12.2 PostgreSQL integration/API tests

- blank and populated Phase 1 migrations;
- seed idempotency;
- preview success/failure persistence;
- atomic commit and rollback fault injection;
- duplicate commit concurrency/locking;
- Attachment delete restriction and existing byte-cleanup behavior;
- immutable Measurement, points, Evidence, template versions, and revisions;
- Compare project/source validation;
- Literature/edit/link behavior and cross-Project rejection;
- Evidence source ownership and withdrawal;
- revision v1/v2 compatibility;
- complete Phase 1 regression suite.

## 12.3 Frontend tests

- typed structured import errors retain row/column details;
- wizard step transitions and retry/discard behavior;
- preview/mapping validation and ignored-column disclosure;
- chart/KPI/provenance data shaping;
- Compare URL state, property rows, compatibility groups, and inaccessible combinations;
- Literature forms/list/link mutations;
- Evidence source union rendering and withdrawn state;
- revision v1/v2 parsing.

## 12.4 Browser audit

Against PostgreSQL 17:

- Phase 1 demo regression;
- supported CSV import;
- supported multi-sheet XLSX import;
- invalid CSV and mapped-row diagnostics;
- raw Attachment download and referenced-delete rejection;
- Measurement table/plot/provenance;
- EXP-041/044/045 Compare and unit incompatibility state;
- manual Literature create/edit/link;
- Evidence create/open/withdraw;
- old and new revision viewers;
- refresh and complete service restart persistence;
- 1024 px and 1280 px layouts;
- no error overlay, unhandled rejection, hydration error, or chart sizing failure.

---

# 13. Explicitly Deferred Scope

The executor must not add any of the following while executing Plan 02:

- universal scientific/instrument parser framework;
- `.xls`, `.xlsb`, `.xlsm`, TSV, HDF5, JCAMP-DX, images/PDF OCR, vendor binary formats;
- multiple tables per file, multi-row headers, arbitrary n-dimensional tensors;
- automatic delimiter/encoding/unit detection;
- unit conversion, normalization, interpolation, smoothing, baseline correction, peak fitting;
- statistical significance, regression, scientific conclusions, automated KPI interpretation;
- persisted Comparison entities or compare history;
- editing/deleting imported Measurements or point rows;
- cross-Project Compare;
- Zotero P0 integration, Zotero sync/write, OAuth screens, citation styles, PDF/annotation management;
- full-text literature search or external search aggregation;
- generic provenance graph/database or generic Relation table;
- direct Evidence from arbitrary Attachments;
- AI-generated claims, Findings, confidence, Evidence Gate decisions, reviews, bad cases, evaluations;
- AI, RAG, LangGraph, Langfuse, MCP, embeddings, pgvector;
- background job infrastructure, queues, S3/MinIO, permissions/RBAC, collaboration, notifications;
- instrument control or regulatory/compliance claims.

If one of these becomes genuinely required, stop and update the product scope and execution plan before implementation.

---

# 14. Implementation Notes Template

Append notes; never delete prior notes.

## Current implementation — 2026-09-01

- Added additive Alembic migrations `0003_scientific_measurements` and `0004_literature_evidence`.
- Added the immutable Measurement/MeasurementPoint model, narrow CSV/XLSX parser, preview/commit API, provenance checks, and attachment-in-use protection.
- Added computed Compare API, manual Literature/Evidence APIs, source snapshots, withdrawal semantics, and an optional `LiteratureProvider` protocol seam; no Zotero provider was added.
- Added Experiment Data, Compare, and Literature/Evidence frontend surfaces using the existing typed client and Recharts 3.8.
- Added deterministic Phase 2 seed data and a PostgreSQL 17/frontend CI workflow.
- Local verification completed with 18 backend tests, frontend tests/typecheck/build, SQLite migration upgrade/check, and idempotent seed counts. PostgreSQL execution remains the CI-authoritative gate when Docker/PostgreSQL is available.

```markdown
## M<N> completed — YYYY-MM-DD

Implemented:
- ...

Schema/API changes:
- ...

Actual commands and results:
- ...

Browser verification:
- ...

Deviation from plan:
- None, or exact approved deviation and reason.

Follow-up:
- Exact next-milestone dependency or remaining bounded debt.
```

Do not mark this plan complete until Milestone 10 produces a PostgreSQL-backed `PHASE 2 PASS` handoff.
