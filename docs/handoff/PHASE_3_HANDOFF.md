# Phase 3 — Scientific AI + Evaluation Handoff

## 1. Status

- **Plan status:** `READY FOR EXECUTION`.
- **Implementation status:** Phase 3 has **not** started; this handoff records a documentation-only plan revision.
- **Date:** 2026-09-02.
- **Stable Phase 1/2 baseline:** `fc0a944` (`Close Phase 2 documentation`).
- **Phase 1 baseline:** `9bb494d`.
- **Phase 2 accepted source:** `939bf82`.
- **Documentation commit:** recorded in the GitHub commit that adds this handoff and the revised plan.
- **Release tag:** no `v0.1-demo` tag; Phase 3 acceptance has not been claimed.

## 2. What Was Actually Delivered

Only the existing Phase 3 execution plan was revised in place:

- Direct Structured Support is distinct from Curated Evidence. Validated Measurement comparisons, structured Experiment differences, and immutable Revision structured properties may support descriptive/comparative claims without an EvidenceRecord, but never establish causality.
- Analysis accepts 0–25 curated EvidenceRecords when the selected structured context is sufficient.
- EvaluationCase now covers immutable `bad_case` and controlled `reference_case` records, with review provenance, case-type-aware dataset hashing, and a small 4–8-case P0 dataset.
- AI model profiles explicitly support `native_schema` and `json_object`; both require direct JSON/Pydantic/scientific-reference validation and forbid extraction, repair, or autonomous retries.
- Evaluation execution is explicitly limited to one API process and one worker with sequential in-process execution; multi-worker deployment is unsupported in v0.1.
- LiteLLM and Langfuse wording now requires implementation-time stable-version verification and exact lockfile pinning rather than treating a planning-time version as permanently current.
- The 10-milestone structure, Phase 1/2 guarantees, gated prefilled Experiment draft flow, PostgreSQL source-of-truth boundary, optional Langfuse projection, and deferred LangGraph/RAG/pgvector/MCP scope remain intact.

No migrations, ORM models, routers, providers, frontend routes, CI workflows, seed data, or runtime behavior were implemented by this change.

## 3. Repository Files

- [Execution Plan 03](../exec-plans/03-scientific-ai.md) — complete implementation specification and acceptance contract.
- [Phase 3 Handoff](PHASE_3_HANDOFF.md) — this status and scope record.

Phase 1 and Phase 2 handoffs remain authoritative for delivered product behavior:

- [Phase 1 Handoff](PHASE_1_HANDOFF.md)
- [Phase 2 Handoff](PHASE_2_HANDOFF.md)

## 4. Planned Interfaces and Schema Changes

These are planned implementation changes, not current runtime endpoints or tables:

- `findings.structured_support_json` and typed `structured_support_assertions[]`.
- `evaluation_cases.case_type`, `case_tags_json`, expanded expected-behavior fields, and a controlled Reference Case creation path.
- `structured_output_mode` on model profiles, AnalysisRun, and EvaluationRun.
- Analysis request `evidence_ids` cardinality 0–25.
- `POST /findings/{finding_id}/evaluation-cases/reference` and `case_type` list filtering.
- Single-worker Evaluation runner contract using FastAPI `BackgroundTasks` and PostgreSQL-persisted status.

The plan explicitly keeps Phase 1 immutable template-version binding, append-only revisions, revision snapshot compatibility, and Phase 2 Measurement/import/Literature/Evidence provenance unchanged.

## 5. Verification Performed

| Check | Result | Evidence |
| --- | --- | --- |
| Plan file present and complete | PASS | `docs/exec-plans/03-scientific-ai.md` |
| Milestone structure | PASS | 10 milestones retained |
| Markdown whitespace check | PASS | `git diff --no-index --check /dev/null docs/exec-plans/03-scientific-ai.md` |
| Product code changes | NONE | No `api/` or `web/` files changed |
| Phase 3 migrations/tests/CI/browser audit | NOT RUN | Intentionally deferred until implementation |
| PostgreSQL 17 Phase 3 acceptance | NOT RUN | No Phase 3 runtime exists yet |

## 6. Known Issues and Deferred Work

### Intentional non-blocking scope

- Phase 3 implementation, migrations `0005`/`0006`, provider adapters, Evaluation runner, UI, CI, seed fixtures, and browser audit remain to be built according to the plan.
- LiteLLM and Langfuse exact versions must be re-verified during implementation preflight and locked in `uv.lock`.
- LangGraph, LiteLLM Gateway, RAG, embeddings, pgvector, MCP, autonomous retrieval, and self-hosted Langfuse remain deferred.

### Not accepted yet

- No `PHASE 3 PASS` verdict.
- No PostgreSQL 17 Phase 3 acceptance.
- No live-provider smoke result.
- No `v0.1-demo` release tag.

## 7. Next Action

Begin Phase 3 implementation only after using this plan as the approved contract; complete each milestone's acceptance criteria and the final PostgreSQL 17/browser audit before claiming `PHASE 3 PASS`.
