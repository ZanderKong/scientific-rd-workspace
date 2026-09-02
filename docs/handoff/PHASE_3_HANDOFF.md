# Phase 3 — Scientific AI + Evaluation Handoff

## 1. Status

- **Implementation status:** Milestones 1–4 corrective closeout fixes complete; work intentionally
  stops before Milestone 5. This is not a Phase 3 release closeout or `PHASE 3 PASS` claim.
- **Corrective closeout verdict:** `M1–M4 ACCEPTED — M5 UNBLOCKED`.
- **Implementation baseline:** Phase 3 work started from `4384191` (approved plan and handoff).
- **Implementation commit:** the commit containing this handoff (`Implement Phase 3 milestones 1-4`);
  use `git log -1` for its final hash.
- **Phase 1 baseline:** `9bb494d`; **Phase 2 accepted commit:** `939bf82`.
- **Release tag:** no `v0.1-demo` tag has been created.

## 2. What Was Delivered

### Milestone 1 — contracts and persistence

- Added additive Alembic migration `0005_scientific_analysis`.
- Added `ScientificAnalysisRun`, immutable `AnalysisContextSnapshot`, immutable `Finding`, immutable
  `FindingEvidenceLink`, and append-only `ReviewDecision` ORM records.
- Added typed Pydantic contracts for analysis selection, five Finding types, typed Direct Structured
  Support assertions, gate/review states, and the two structured-output modes.
- Added versioned `scientific_analysis/v1` and `evaluation_judge/v1` prompts, model-profile capability
  metadata, and exact LiteLLM `1.99.0` / Langfuse `4.15.1` lockfile entries after implementation-time
  dependency verification.

### Milestone 2 — frozen scientific context

- Context builder requires 2–5 same-Project Experiment revisions and explicit 1–10 Measurements.
- It rejects revision drift, cross-Project records, unselected Evidence sources, withdrawn Evidence,
  and oversized/non-finite data before a provider call.
- Context snapshots include exact revision/template identity and schema hashes, Measurement → Import →
  Attachment provenance, full point hashes with bounded samples, Literature/Evidence snapshots,
  server-side Compare output, lineage, and name-addressable factor differences such as
  `/additives/@KI` and `/additives/@starch`.
- Evidence selection is explicitly 0–25; valid direct structured comparisons do not require an
  EvidenceRecord.

### Milestone 3 — provider and analysis workflow

- Added the small `AIProvider` boundary with deterministic `FixtureProvider` and embedded
  `LiteLLMProvider`; no LiteLLM Gateway, LangGraph, queue, RAG, embeddings, pgvector, or MCP was added.
- `native_schema` uses provider JSON Schema response format; `json_object` uses strict JSON-object
  response format. Both perform direct JSON decode, Workspace Pydantic validation, and scientific
  reference validation without regex/prose repair or invalid-output retries.
- Added synchronous AnalysisRun creation, frozen context persistence, diagnostic failure state
  persistence, provider/model/prompt/output metadata, and optional Langfuse trace projection
  (disabled by default and never authoritative).
- Added API endpoints for profiles, prompt versions, AnalysisRun create/list/detail, Finding list/detail,
  and append-only human review decisions.

### Milestone 4 — Findings and Evidence Gate

- Findings persist model output separately from deterministic gate output and confidence.
- Direct Structured Support is server-recomputed from frozen Measurement summaries, structured
  Experiment differences, and Revision structured-property observations. Revision free text is not
  used to infer support.
- Curated EvidenceRecord links are project-scoped, role-checked, immutable, and snapshot-backed.
- Gate states are `supported`, `partially_supported`, `insufficient_evidence`, and `contradicted`.
  Direct support can support descriptive/comparative claims but cannot prove causality. The fixture
  demonstration forces the KI+starch causal claim to `insufficient_evidence` and records the missing
  isolating control.
- Suggested next experiments are normalized, template-validated, non-authoritative JSON proposals;
  no endpoint creates or mutates an Experiment.

## 3. Corrective closeout fixes

- Provider context limits now count sampled points (maximum 200 per Measurement and 2,000 total),
  while retaining original row counts, endpoint-preserving sampling metadata, and the full immutable
  `points_sha256`.
- Langfuse 4.15.1 now uses the v4 `create_trace_id(seed=...)` and `start_observation(...,
  as_type="generation")` APIs with `base_url`. `LANGFUSE_CAPTURE_CONTENT=false` is the default;
  disabled capture sends only IDs/hashes, model/profile, prompt/version metadata, usage, latency and
  status, never context, notes, abstracts, rendered prompts, or model output.
- ScientificAnalysisRun configuration/provenance fields are ORM-guarded once the run leaves
  `building_context`; named lifecycle/result fields remain writable by the run service.
- Capability preflight no longer treats generic `response_format` as native-schema proof:
  `native_schema` requires explicit profile smoke verification, while `json_object` may use provider
  response-format support. Unsupported profiles report an unavailable reason.
- Exactly one retry is allowed for timeout, rate-limit, unavailable, or retryable 5xx provider
  failures. Authentication, bad request, unsupported capability, invalid JSON/schema, and scientific
  reference failures are never retried; attempt/retry counts are recorded in run metadata.
- The PostgreSQL 17 populated-Phase-2-upgrade/parity check is now part of the Phase 2 CI workflow so
  the M1 acceptance can be evidenced on GitHub without live model or Langfuse calls.

## 4. Verification Performed

| Check | Result | Evidence |
| --- | --- | --- |
| API formatter/lint | PASS | `uv run ruff format app tests && uv run ruff check app tests` |
| API regression and Phase 3 tests | PASS | `uv run pytest -q` — 28 tests |
| Blank-database Alembic upgrade | PASS locally | SQLite fallback smoke to `0005_scientific_analysis` |
| PostgreSQL 17 blank/populated migration acceptance | PASS | GitHub Actions run [33584109673](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33584109673) on corrective commit `0b5ffc4`; blank head, populated `0004` upgrade, hash parity and `alembic check` |
| Backend regression against PostgreSQL 17 | PASS | Same run; full pytest suite (28 tests) |
| Frontend gates/browser audit | PASS for existing Phase 1/2 gates | Same run; lint, format check, typecheck, Vitest and production build; M5 UI remains unimplemented |
| Live LiteLLM/Langfuse calls | NOT RUN | tests use FixtureProvider/mocks; Langfuse content capture is disabled |

The repository remains additive to Phase 1/2. Existing immutable template-version rows, revision
snapshots, Measurement/import provenance, Literature/Evidence semantics, and attachment storage
contracts were not rewritten.

## 5. Intentionally Deferred

M5 analysis/review UX; M6–M7 EvaluationCase/EvaluationRun/runner and evaluation UI; M8 gated prefilled
draft Experiment provenance flow; M9 demo fixtures/browser story; M10 PostgreSQL 17 CI, full audit and
release handoff. Multi-worker evaluation is unsupported by design and no queue was introduced.

The M1–M4 corrective acceptance is complete and PostgreSQL 17 is green. Overall Phase 3 remains
**IN PROGRESS** because M5–M10 are intentionally outside this batch; no `PHASE 3 PASS` or release tag
is claimed. Continue from the approved execution plan and preserve the Phase 1/2 contracts above.
