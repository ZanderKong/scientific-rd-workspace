# ChangeSet Review Workflow

ChangeSets are proposal-first records scoped to one Project. A proposal stores the operation kind, normalized request payload, preview, deterministic diff, source client metadata and optional base record hash.

REST endpoints:

- `POST /change-sets/propose`
- `GET /change-sets` and `GET /change-sets/{id}`
- `POST /change-sets/{id}/review` with `decision: approve|reject`
- `POST /change-sets/{id}/apply`

Approval rechecks the base hash before canonical service application. A changed target becomes `stale`; the server does not apply a stale proposal. Applied revisions are tagged with ChangeSet id and client provenance. Direct generic object/relation writes remain available for internal UI workflows, while external agent defaults are proposal mode.
