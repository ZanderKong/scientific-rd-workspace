# UI Spec — v0.2 Research Object Graph

## Shell

The shell is Chinese-first with English switchable and no locale URL prefix. The sidebar contains only active v0.2 routes:

```text
Workspace
├── Overview
└── Projects
Research
├── Experiments
├── Samples
├── Processes
└── Data
Library
├── Materials
└── Equipment
```

The Project/Vault switcher persists the selected project locally and adds `?project=<uuid>` to scoped list routes. Breadcrumbs, locale switcher, theme toggle, skip link and visible loading/error/empty states are part of the shell contract.

## Object pages

Every object kind uses the same typed list/detail language: code, title, status, schema type/version, properties, relations, attachments and revisions. Project detail adds scoped counts and quick links. New-object pages use the active project scope for all kinds that require it.

Object editing has an explicit Save action. Structured properties and rich/block content remain separate. Stored scientific values, codes, filenames and API enum values are not translated.

## Composer interaction

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

Data detail separates immutable payload summary/plot from source provenance. CSV/XLSX upload shows a preview, requires explicit X/Y mapping, preserves source row order and exposes checksum/parser/import status. XY chart coordinates use the real X values with O(n) bounds calculation. BlockNote JSON is persisted as JSON and never flattened to plain text. No fake data is shown when the API is unavailable.

## Deferred surfaces

Compare, Literature, AI Analysis, Evidence and Evaluation are intentionally absent from the active navigation and route tree until a separate Plan 2 reintroduces them with a compatible object-graph contract.
