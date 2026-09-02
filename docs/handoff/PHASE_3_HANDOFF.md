# Phase 3 — Scientific AI + Evaluation Handoff

## 1. Release status

- **Verdict: `PHASE 3 PASS`**
- **Release commit:** recorded after this closeout; annotated tag `v0.1-demo` points to the same
  accepted commit.
- **Implementation head before documentation closeout:** `c863495` (`Fix DeepSeek V4 strict JSON
  analysis smoke`).
- **Accepted baseline before this final batch:** `58b74eb`.
- **M1–M7:** accepted and preserved; no redesign was made.
- **M8–M9:** implemented and locally audited.
- **M10:** PostgreSQL 17/fixture CI, frontend gates, offline browser audit, and the required live
  LiteLLM Workspace smoke all passed.

## 2. M8 — gated prefilled draft Experiment

The AI remains proposal-only. `GET /findings/{finding_id}/suggested-experiment-prefill` is available
only when the Finding has a latest `Accept` or `Needs Evidence` ReviewDecision and a valid normalized
suggestion. It returns the exact parent Experiment, immutable template ID/version, editable title,
objective and structured values, the enabling review identity and a canonical suggestion hash. It
never creates an Experiment.

The existing creation route accepts an optional `suggestion_origin`. On submit the API rechecks the
Finding/AnalysisRun, latest review, suggestion hash, same-project parent, exact active immutable
template version and schema validation. Stale review/hash/template/project inputs return `409` and
create no rows. A valid submission is always a `draft`, keeps normal `parent_experiment_id` lineage,
and atomically writes the immutable `ExperimentProvenanceLink` with the suggestion and submitted-value
snapshots. Ordinary Experiment creation remains backward compatible.

The UI exposes `Create Draft Experiment` only after an eligible review, opens the existing creation
form with editable prefilled values, requires explicit submit, and renders provenance read-only on the
Experiment detail page.

Additional API surface:

- `GET /experiments/{experiment_id}/provenance`
- `GET /findings/{finding_id}/suggested-experiment-prefill`

## 3. M9 — deterministic demo set

`python -m app.seed` extends only PRJ-001. On a blank Phase 3 schema it creates three deterministic
FixtureProvider AnalysisRuns, each with visible `fixture_label: synthetic demo data` metadata, then
three accepted Reference Cases and three rejected Bad Cases. Cases carry immutable source Finding and
ReviewDecision snapshots and visible `fixture`, `synthetic`, `demo` tags:

- Reference: verified Measurement comparison, comparison/causality distinction, and selected Evidence
  scope (no curated Evidence is required for direct structured support).
- Bad: unsupported starch causality, invented Evidence ID regression, and missed isolating control.

Repeated seed execution is idempotent. No unrelated Project or scientific dataset is created. The
workflow's seed assertion confirms exactly 3 `reference_case` and 3 `bad_case` rows on a fresh database.

## 4. M10 — verification evidence

| Gate | Result | Evidence |
| --- | --- | --- |
| Backend formatting/lint | PASS | `cd api && uv run ruff format --check app tests && uv run ruff check app tests` |
| Backend tests (local) | PASS | `cd api && uv run pytest -q` — 45 tests |
| Blank migration/seed (local) | PASS | SQLite `alembic upgrade head`, seed twice, exact 3+3 cases |
| Phase 2 upgrade (local) | PASS | SQLite `upgrade 0004` → bounded seed → `upgrade head`; Phase 3 tables are added only after head |
| Frontend gates | PASS | `npm run lint`, `format:check`, `typecheck`, `test` (6), `build` |
| Browser M8 flow | PASS | Fixture review → prefill → edit → explicit draft submit → detail provenance |
| Browser responsive/error check | PASS | 1024px and 1280px; no captured console errors |
| Browser mixed Evaluation | PASS | Fixture dataset 6/6 terminal results, sequential one-worker run |
| PostgreSQL 17 GitHub Actions | PASS | [Phase 3 Scientific AI CI run #33600400812](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33600400812) on `c863495` |
| Phase 1 regression | PASS | [Phase 1 CI run #33600400781](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33600400781) on `c863495` |
| Live LiteLLM analysis smoke | PASS | 2026-09-02 14:45:19 +0800, external to CI; `deepseek-live`, requested `deepseek/deepseek-v4-flash`, resolved `deepseek-v4-flash`, `json_object`, AnalysisRun `d864d74c-4ae6-416d-a17b-f6c018381a11`, prompt SHA-256 `fe5faec4364fb0b71091c499865e38c3d327cf60c7c46197990582305bc24b78`, provider response ID `99f06ebe-9867-4b21-9020-9469e28a28a1` |
| Langfuse | NON-BLOCKING | Disabled by default; no external call required for this batch |

The Phase 3 workflow is the consolidated `.github/workflows/phase-3-ci.yml`. It uses PostgreSQL 17,
checks blank and populated Phase 2→head migrations, parity, seed idempotency and 3+3 fixture counts,
then runs all backend and frontend gates. CI uses FixtureProvider and Langfuse disabled. Evaluation
deployment remains exactly one API process/worker (`uvicorn ... --workers 1`); PostgreSQL is not a
cross-worker queue and multi-worker deployment is unsupported.

### Live provider acceptance detail

The request used the real application path `Workspace API → embedded LiteLLMProvider → DeepSeek
Chat Completions → json_object → direct JSON decode → Workspace Pydantic validation → scientific
reference/direct-support validation → deterministic Evidence Gate → database persistence`. This
Docker-free smoke used the application's SQLite fallback; PostgreSQL 17 persistence and migration
parity were separately verified in the passing GitHub Actions run above. The
run completed with 3 Findings, 0 curated EvidenceRecord links, and verified direct structured
support; all three gates were `partially_supported` with separate `medium` confidence labels and
material-limitations rationale. The provider output decoded as direct JSON and matched the persisted
validated response. A refresh GET returned the same completed run and Findings.

The model produced conservative comparative/observational Findings rather than a causal claim; this
is a scientific-quality note, not a validation bypass. Earlier compatibility failures were retained
as failed Runs with zero Findings, no validated output, and no raw output, confirming atomic failure
behavior. The raw output contained no credential value, and no secret was logged or committed.

## 5. Invariants preserved

- Phase 1 immutable ExperimentTemplate version rows and exact `template_version` bindings remain
  unchanged.
- Revision snapshots, attachment/import/Measurement provenance, Literature/Evidence ownership and
  structured-support versus curated-Evidence semantics remain unchanged.
- AI has no direct write authority over Experiment, Measurement, Evidence, Literature, Revision or
  ReviewDecision. Only an explicit human submit can create the M8 draft.
- No Measurement Compare redesign, LangGraph, RAG, embeddings, pgvector, MCP, queue, or other Phase 2/3
  deferred functionality was added.

## 6. Release closeout

The required live provider gate passed outside CI. The final documentation commit is tagged
`v0.1-demo` only after the accepted code, PostgreSQL 17 CI, frontend gates, and this live AnalysisRun
were verified. The working tree is clean and the local `api/.env` remains ignored by Git.

**PHASE 3 PASS**
