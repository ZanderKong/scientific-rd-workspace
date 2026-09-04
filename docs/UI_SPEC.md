# UI Specification

## Shell

The shell is Chinese-first with English switchable and no locale URL prefix. The primary sidebar is intentionally restrained:

```text
Research
├── Experiments
└── Samples
```

The generic Process, Data, Material, Equipment, Project and Overview routes remain available directly and through existing object links; they are not deleted by the navigation cut.

The Project/Vault switcher persists the selected project locally and adds `?project=<uuid>` to scoped list routes. Breadcrumbs, locale switcher, theme toggle, skip link and visible loading/error/empty states are part of the shell contract.

The workspace provides dedicated typed surfaces for Project Context/Search, Experiment Record/membership/comparison, Data Record/payload tables and Sample Execution. These surfaces show domain summaries, tables and status badges in normal flows; raw JSON is not required to inspect a record.

## Object pages

Every object kind uses the same typed list/detail language: code, title, status, schema type/version, properties, relations, attachments and revisions. Project detail adds scoped counts and quick links. New-object pages use the active project scope for all kinds that require it.

Object editing has an explicit Save action. Structured properties and rich/block content remain separate. Stored scientific values, codes, filenames and API enum values are not translated.

## Composer interaction

Samples use a dedicated Sample-first Composer rather than the generic raw-properties editor. A new record starts with one Process Block. The same component tree is used for create and edit.

- `/` opens active Process definitions from `ObjectType` / `ObjectTypeVersion`, with a Custom Process fallback.
- `@` opens a two-pane resolver for Material, Equipment and optional precursor Sample. Material and Equipment may be mixed in one token stream; tokens are compact and semantically color-coded.
- Resource identity is previewable, but actual quantity/rpm/temperature/etc. values are rendered as dynamic fields on the current Process use. Adding a field updates that concrete Material/Equipment usage schema; it does not create a new resource.
- Process-own parameters stay in `Process.properties_jsonb.parameters`; resource-use values stay on the Process → resource relation.
- Save uses the aggregate Sample Record API once. The UI never loops over relation POST/PATCH calls to assemble one workflow.
- `基于此样品新建` removes Sample/Process/relation IDs from the draft, keeps existing resource IDs and values, and cannot mutate the source record merely by opening it.

The Process composer is keyboard-first and keeps relation semantics visible:

- type `@` then search by code/title or kind alias;
- Arrow Up/Down selects a result, Enter accepts it, Escape closes the popup;
- Tab traverses relation type, reference, role, quantity and unit controls;
- Cmd/Ctrl+Enter saves the relation set;
- relation type, role and quantity are sent explicitly to the API.
- the complete Process composition is reconciled with one `PUT /processes/{id}/composition`; new Sample/Data outputs can be materialized in that transaction.

The server remains authoritative for semantic validation and duplicate detection; the UI renders returned errors rather than inventing local graph rules.

## Context and data

Sample detail separates direct provenance, role-aware sample inputs, current data, upstream lineage and downstream lineage. Traversal depth is bounded by the API, and the lineage view renders backend edges as a tree rather than a fabricated linear chain. Experiment detail lists contained objects and input samples from other Experiment ownership contexts.

Experiment comparison exposes same/different/missing/unit-conflict states, with an explicit differences-only toggle. Execution detail separates the frozen Planned hash from current As-run observations and changed dimensions. Data detail renders scalar, XY, table and file payload summaries while preserving source/import status.

Data detail separates immutable payload summary/plot from source provenance. CSV/XLSX upload shows a preview, requires explicit X/Y mapping, preserves source row order and exposes checksum/parser/import status. XY chart coordinates use the real X values with O(n) bounds calculation. BlockNote JSON is persisted as JSON and never flattened to plain text. No fake data is shown when the API is unavailable.

## Deferred surfaces

Compare, Literature, AI Analysis, Evidence and Evaluation are intentionally absent from the active navigation and route tree until a separate Plan 2 reintroduces them with a compatible object-graph contract.
