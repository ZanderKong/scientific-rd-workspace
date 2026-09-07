# UI Specification v1.5

The Next.js shell exposes the v1.5 continuous authoring and fixed-version traceability workflows.

## Navigation

The shell keeps project scope, locale, theme, settings and visible loading/error/empty states. Main surfaces are Projects, Research Objects (tagged Material/Equipment/Sample groupings), Process Definitions, Samples, Experiments, Data, Views, Claims and Change Sets.

## Research Object language

The UI displays one Research Object identity with code/title/status/tags/properties/relations/revisions. Material, Equipment and Sample filters are tag filters, and inline creation sends `kind=research_object` plus shortcut tags. No client submits old kinds.

## Process and Sample Record

Scientific Composer is a continuous BlockNote document. `/` inserts an atomic Process Ref, `@` inserts an Object Ref, and each Ref renders its PropertySlots at the source position. Slot editing, Ref deletion and body edits share undo history. Candidate search is server-backed. Sample detail supports canonical reload, immutable history, conflict-safe drafts and identity-remapped copy creation.

## Data, Experiment, View and Claim

Data Composer uses recoverable drafts and `begin → upload → validate → finalize`; Data detail renders representations, origin hash and explicit subject sources. Sample tables use server filtering/sorting/pagination, URL field columns, cross-page selection and URL Peek. Experiment creation uses the Sample picker. View detail shows pinned Data revisions, Representation IDs and Artifact hash. Claims have human/agent author provenance, one typed pinned primary source, a finite context snapshot and optional evidence.

All network paths remain under `/api/v1`. The frontend does not send the removed `steps`, View `data_ids` or Claim `source_type` formats.
