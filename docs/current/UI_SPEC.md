# UI Specification v0.3

The existing Next.js shell is semantically adapted to v0.3; this cutover does not attempt a final visual redesign.

## Navigation

The shell keeps project scope, locale, theme, settings and visible loading/error/empty states. Main surfaces are Projects, Research Objects (tagged Material/Equipment/Sample groupings), Process Definitions, Samples, Experiments, Data, Views, Claims and Change Sets.

## Research Object language

The UI displays one Research Object identity with code/title/status/tags/properties/relations/revisions. Material, Equipment and Sample filters are tag filters, and inline creation sends `kind=research_object` plus shortcut tags. No client submits old kinds.

## Process and Sample Record

Process search selects a Process Definition and explicit version. The composer saves one aggregate Sample Record request whose steps become Process Executions. Each step renders definition/version, execution fields, bound Research Objects and bound Data, including multiple outputs. A Sample detail page renders the Process Execution projection and subject Data.

## Data, Experiment, View and Claim

Data detail renders all representations, origin hash, subjects and derived-from sources. Experiment detail renders grouped references only. View detail renders Data references and config/revision state without copying scientific values. Claim detail renders statement, source/confidence and ordered supporting/counter evidence.

All network paths are v0.3 paths. Deprecated payload, composition, comparison and old execution calls are absent from the frontend client.
