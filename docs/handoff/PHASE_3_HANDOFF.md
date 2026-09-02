# Phase 3 — Scientific AI + Evaluation Handoff

## 1. Release status

- **Verdict: `PHASE 3 NOT YET RELEASED`**
- **Current head:** `ef1b6c6` (`Record Phase 3 final handoff and release gate`), pushed to `main`.
- **Accepted baseline before this final batch:** `58b74eb`.
- **M1–M7:** accepted and preserved; no redesign was made.
- **M8–M9:** implemented and locally audited.
- **M10:** PostgreSQL 17/fixture CI and offline browser gates passed. The required live LiteLLM
  smoke is not complete because no provider credentials were configured in this environment.
- No `v0.1-demo` tag was created. Do not treat this handoff as a release until the live smoke passes.

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
| PostgreSQL 17 GitHub Actions | PASS | [Phase 3 Scientific AI CI run #33596766443](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33596766443) on `ef1b6c6` |
| Phase 1 regression | PASS | [Phase 1 CI run #33596766422](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33596766422) on `ef1b6c6` |
| Live LiteLLM analysis smoke | NOT RUN | No `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY` or live model profile was configured; no external call was attempted |
| Langfuse | NON-BLOCKING | Disabled by default; no external call required for this batch |

The Phase 3 workflow is the consolidated `.github/workflows/phase-3-ci.yml`. It uses PostgreSQL 17,
checks blank and populated Phase 2→head migrations, parity, seed idempotency and 3+3 fixture counts,
then runs all backend and frontend gates. CI uses FixtureProvider and Langfuse disabled. Evaluation
deployment remains exactly one API process/worker (`uvicorn ... --workers 1`); PostgreSQL is not a
cross-worker queue and multi-worker deployment is unsupported.

## 5. Invariants preserved

- Phase 1 immutable ExperimentTemplate version rows and exact `template_version` bindings remain
  unchanged.
- Revision snapshots, attachment/import/Measurement provenance, Literature/Evidence ownership and
  structured-support versus curated-Evidence semantics remain unchanged.
- AI has no direct write authority over Experiment, Measurement, Evidence, Literature, Revision or
  ReviewDecision. Only an explicit human submit can create the M8 draft.
- No Measurement Compare redesign, LangGraph, RAG, embeddings, pgvector, MCP, queue, or other Phase 2/3
  deferred functionality was added.

## 6. Required next action before release

Configure one live LiteLLM model profile and its provider credential outside CI, execute one manual
analysis smoke, and record provider/model metadata, structured-output mode, prompt hash, response ID
and resulting run status here. If it passes, update this verdict to `PHASE 3 PASS` and create the
annotated `v0.1-demo` tag. Until then the exact release verdict remains:

**PHASE 3 NOT YET RELEASED**
