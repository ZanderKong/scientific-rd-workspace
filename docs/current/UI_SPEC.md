# UI Specification v1.6

The Next.js shell exposes the v1.5 continuous authoring and fixed-version traceability workflows.

## Navigation

The shell keeps project scope, locale, theme, settings and visible loading/error/empty states. The primary workspace has five entries: Samples, Analysis, Data, Claims and Resources. Project selection is in the sidebar and `/dashboard` opens Samples. Legacy Experiment URLs are redirected or show a not-found handoff to Analysis.

## Research Object language

The UI displays one Research Object identity with code/title/status/tags/properties/relations/revisions. Resource filters use the controlled `resource_role` (`material`, `equipment`, `process`). Samples are searchable references only when a saved Sample record exists; an `@` search with no match offers material, equipment or process creation, never Sample creation.

## Process and Sample Record

Scientific Composer uses a two-level BlockNote document. A top-level bullet is natural language with `@` Object/Process declarations; a direct child bullet uses `@reference｜property: raw value` and can only reference an occurrence declared by its parent. Repeated declarations receive stable occurrence identities and are shown as “第 N 次”. `@data` and `@claim` are parser commands usable at either level and are stored against the current Sample/Data authoring subject. Properties remain free text; the vocabulary only supplies bilingual suggestions and unit hints. Candidate search is server-backed and composition-aware. Sample/Data detail supports canonical reload, immutable history, conflict-safe drafts and identity-remapped copy creation.

## Data, Analysis and Claim

Data Composer uses recoverable drafts and `begin → upload → validate → finalize`; Data detail renders representations, origin hash and explicit subject sources. Sample tables use server filtering/sorting/pagination, URL field columns, cross-page selection and URL Peek. Analysis detail shows explicit members and pinned revisions. Claims have human/agent author provenance, an optional typed pinned primary source, a finite context snapshot and optional evidence.

All network paths remain under `/api/v1`. The frontend does not send the removed `steps`, View `data_ids` or Claim `source_type` formats.
