# Phase 3 — Scientific AI + Evaluation Handoff

## 1. Status

- **Verdict:** `M5–M7 ACCEPTED — M8 UNBLOCKED`.
- **Scope completed:** Analysis/Review UX, Evaluation schema and runner, Evaluation UI and optional
  Langfuse projection. M8 gated draft Experiment was not started.
- **Phase 1 baseline:** `9bb494d`; **Phase 2 accepted commit:** `939bf82`.
- **Implementation baseline before this batch:** `4680dad` (M1–M4 accepted).
- **Accepted implementation commit:** `6162dc3` (`Implement Phase 3 M5-M7 analysis evaluation workflow`).
- **Corrective closeout commit:** `ee11930` (`Fix Phase 3 M5-M7 evaluation closeout issues`).
- **Closeout date:** 2026-09-02.
- No `v0.1-demo` release tag is claimed; M9/M10 final fixtures, browser audit and release gate remain.

## 2. M5 — Analysis and human review UX

- Compare now exposes `Analyse selected experiments` with explicit latest Revision, compatible
  Measurement, Literature, active EvidenceRecord, model profile, structured-output mode and prompt
  configuration. The API remains authoritative for ownership and revision-drift validation.
- `/dashboard/analysis` lists runs; `/dashboard/analysis/[analysisRunId]` exposes run status, provider,
  model/profile, mode, prompt hash, frozen context hash/size, full provenance disclosure, Compare data,
  Measurement provenance and Finding cards.
- Finding cards visibly separate claim type, confidence, authoritative Evidence Gate, Direct Structured
  Support, Curated Evidence roles, limitations, risks, missing evidence, applicability and suggestions.
- Accept/Reject/Needs Evidence are append-only; Reject requires reason/comment, Needs Evidence requires
  comment, and stale supersession is returned as `409` by the existing review API. No scientific record
  mutation or chat-first UI was introduced.

## 3. M6 — Evaluation schema and single-worker runner

- Additive Alembic migration `0006_scientific_evaluation` creates `evaluation_cases`,
  `evaluation_runs`, `evaluation_results`, and the reserved `experiment_provenance_links` table.
  M8 does not use the provenance table yet.
- EvaluationCase is immutable, project-scoped and carries case type (`bad_case`/`reference_case`), frozen
  context/output/Finding/Gate/review/config snapshots, expected behavior, tags and `case_hash`.
  Bad Cases require the latest rejected review; Reference Cases require the latest accepted review via
  the separate controlled endpoint. Creation is idempotent for a source review.
- Dataset versions hash a canonical UUID-sorted list of `{case_type, case_id, case_hash}` entries, so
  request order does not change the version.
- `POST /projects/{project_id}/evaluation-runs` commits the run and pending result rows before returning
  `202`. A single in-process FastAPI background worker executes cases sequentially, persists progress,
  isolates per-case failures, supports cancellation, and marks stale queued/running runs `interrupted`
  on startup. PostgreSQL stores state; it is not a cross-worker queue. Multi-worker deployment remains
  unsupported (`uvicorn ... --workers 1`).
- Deterministic scores include structured output, evidence IDs/roles, Direct Structured Support scope,
  comparison correctness, causal guard/non-upgrade, expected Gate, limitations, missing evidence and
  suggestion checks. Optional judge invocation is separate and never changes deterministic pass/fail.
- Corrective audit fixes freeze the source Finding ordinal and compatible claim/causal-target semantics in
  every Case; replay selects that ordinal and records an explicit result error when it is missing or
  incompatible. Bad Cases preserve the rejected Finding and review reason as observed behavior, while
  expected behavior is bounded by the rejection taxonomy or supplied by the reviewer. Reference Cases may
  derive expectations from an accepted Finding. Suggestion-path checks read the normalized representation
  and fail closed when required paths are absent.
- The runner distinguishes per-case scientific/schema failures from run-wide provider/auth/profile/capability
  failures. Per-case errors continue sequential execution; global failures persist the current error, mark
  pending results terminal, stop the run and recompute counts. Completed results and Case snapshots remain
  immutable. The Analysis UI opens a controlled Bad Case expectation form before submitting a Case.

## 4. M7 — Evaluation UI and Langfuse projection

- `/dashboard/evaluations` supports project and case-type filters, source Finding links and run launch.
- `/dashboard/evaluations/[evaluationRunId]` shows dataset hash, model/prompt/judge configuration,
  progress, terminal states, deterministic score JSON, optional judge JSON, case tags, errors, source
  links, replay AnalysisRun links and cancellation while active. Polling stops for completed,
  completed-with-errors, failed, interrupted and cancelled states.
- Langfuse projection is best-effort and optional. Dataset-item and score metadata use Workspace IDs and
  hashes; when `LANGFUSE_CAPTURE_CONTENT=false`, scientific content is not sent. Local PostgreSQL
  EvaluationCase/Run/Result state never depends on Langfuse availability, and automated tests make no
  external Langfuse calls.

## 5. API surface added

- `POST /findings/{finding_id}/evaluation-cases` (Bad Case)
- `POST /findings/{finding_id}/evaluation-cases/reference` (Reference Case)
- `GET /projects/{project_id}/evaluation-cases[?case_type=...]`
- `GET /evaluation-cases/{case_id}`
- `POST /projects/{project_id}/evaluation-runs` → `202`
- `GET /projects/{project_id}/evaluation-runs`
- `GET /evaluation-runs/{run_id}`
- `GET /evaluation-runs/{run_id}/results`
- `GET /evaluation-results/{result_id}`
- `POST /evaluation-runs/{run_id}/cancel`

## 6. Verification evidence

| Gate | Result | Evidence |
| --- | --- | --- |
| Backend formatting/lint | PASS | `cd api && uv run ruff format --check app tests && uv run ruff check app tests` |
| Backend tests | PASS | `cd api && uv run pytest -q` — 43 tests, including M1–M4 regression and corrective M6 replay/case/runner coverage |
| Blank migration/parity | PASS locally | `DATABASE_URL=sqlite+pysqlite:///... uv run alembic upgrade head`; `uv run alembic check` reports no new operations at `0006` |
| Evaluation smoke | PASS locally | Fixture analysis → Accept/Reject → controlled case → `202` run → sequential result and deterministic score |
| Frontend format/type/tests/build | PASS | `cd web && npm run format:check && npm run typecheck && npm run test && npm run build` |
| Frontend lint | PASS | `cd web && npm run lint`; only inherited starter warnings remain |
| Browser route compilation | PASS | Next production build includes `/dashboard/analysis`, `/dashboard/analysis/[analysisRunId]`, `/dashboard/evaluations`, `/dashboard/evaluations/[evaluationRunId]` |
| Browser workflow | PASS | Local fixture flow at 1024px/1280px: Compare → Analyse → Accept/Reject → Bad Case expectation form → Reference Case → mixed Evaluation `202` run → terminal results and replay/source links; no console errors |
| Live model/Langfuse | NOT REQUIRED | FixtureProvider/mocks only; Langfuse disabled by default and projection is best-effort |

PostgreSQL 17 is the authoritative acceptance database. The corrective closeout passed the
[Phase 2 Scientific Workflow CI run #33592081341](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33592081341)
on commit `ee11930aba696afd9c3986fda4967f480aa2dc88` (`completed / success`, 2026-09-02 UTC).
Its `Backend / PostgreSQL 17` job passed blank migration, migration/model parity, populated Phase 2
upgrade to the `0006` M7 head, seed idempotency, Ruff checks and all 43 backend tests; its Frontend job
passed lint, format check, typecheck, 6 tests and production build. The parallel [Phase 1 CI run
#33592081336](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33592081336)
also completed successfully on the same commit, preserving the Phase 1 regression gate. The earlier M5–M7
CI evidence remains recorded in [run #33587413638](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33587413638).

## 7. Files changed

- API: `api/alembic/versions/0006_scientific_evaluation.py`, `api/app/models.py`,
  `api/app/schemas.py`, `api/app/evaluation_service.py`, `api/app/routers/evaluation.py`,
  `api/app/ai_provider.py`, `api/app/main.py`, `api/app/scientific_ai_service.py`, and M6 tests.
- Web: typed Analysis/Evaluation domain and client contracts, Compare analysis configuration,
  `/dashboard/analysis*`, `/dashboard/evaluations*`, navigation and components.
- Source-of-truth docs: `README.md`, `AGENTS.md`, `ARCHITECTURE.md`, `docs/DATA_MODEL.md`,
  `docs/UI_SPEC.md`, `docs/PRODUCT_SPEC.md`, `docs/DEMO_SCENARIO.md`, and the Phase 3 execution plan.

## 8. Remaining scope and risks

- M8 gated prefilled draft Experiment and `ExperimentProvenanceLink` write path remain deferred.
- M9 deterministic six-case seed/demo polish and M10 final release audit/tag remain.
- Optional judge is intentionally allowed to be unavailable; deterministic results remain authoritative.
- Multi-worker/durable Evaluation execution is unsupported by design; do not deploy v0.1 with more than
  one API worker.
- No LangGraph, RAG, embeddings, pgvector, MCP, queue, automatic Experiment mutation or other Phase 2/3
  deferred functionality was added.

## 9. Handoff decision

`M5–M7 ACCEPTED — M8 UNBLOCKED`. Continue with M8 only under the approved execution plan; do not infer
full `PHASE 3 PASS` until M9/M10 criteria and PostgreSQL/browser evidence are complete.
