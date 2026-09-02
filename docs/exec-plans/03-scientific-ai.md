# Execution Plan 03 — Scientific AI + Evaluation

**Status:** COMPLETE — PHASE 3 PASS

**Stable baseline:** Phase 1 and Phase 2 PASS; M1–M4 accepted at `4680dad`; M5–M7 accepted at `6162dc3`; final implementation head is recorded in the Phase 3 handoff

**Release target:** `v0.1-demo`

**Goal:** complete the traceable scientific reasoning loop:

`Compare → Scientific Analysis → Finding → Evidence Gate → Human Review → Bad/Reference Case → Evaluation → Suggested Next Experiment`

**Critical boundary:** AI produces frozen interpretations and proposals. It never directly changes an Experiment, Measurement, Evidence, Literature, Revision, or ReviewDecision.

---

# 0. Reviewed Architecture Decisions

## 0.1 Orchestration: plain Python, not LangGraph

Phase 3 P0 will use explicit Python services and database state transitions. LangGraph is **not selected**.

The workflow is bounded and has no autonomous tool loop:

```text
validate selection
→ build and persist frozen context
→ one structured model call
→ validate evidence references and comparison assertions
→ apply deterministic Evidence Gate policy
→ persist Findings
→ return to the user

later, as a separate human action:
review Finding
→ optionally create EvaluationCase
→ optionally open a prefilled Experiment creation form
```

Human review is an append-only domain action after the analysis has completed, not an interrupted model run that must resume from a graph checkpoint. Evaluation runs need lightweight status tracking, but not graph memory, agent state, or time travel. LangGraph would therefore duplicate state already owned by PostgreSQL and add a second persistence model without a P0 benefit. Reconsider it only after v0.1 if a future workflow requires durable multi-step tools, resumable external actions, or genuine branching within one long-running run. LangGraph's documented strengths are durable checkpoints and interrupts; this Phase 3 deliberately does not need them: https://docs.langchain.com/oss/python/langgraph/persistence and https://docs.langchain.com/oss/python/langgraph/interrupts.

## 0.2 Model provider: internal interface over embedded LiteLLM SDK

Select the actively maintained LiteLLM Python SDK as the real multi-provider layer. Do **not** add the LiteLLM Gateway/Proxy service in v0.1.

The application owns a deliberately small `AIProvider` protocol and two implementations:

- `LiteLLMProvider` — production/demo adapter using the embedded SDK;
- `FixtureProvider` — deterministic structured responses for tests, seed fixtures, offline development, and CI.

This gives one application contract while allowing configured LiteLLM model identifiers for OpenAI, Anthropic, Gemini, DeepSeek, Ollama, and other supported providers. Provider compatibility is explicit: each configured model profile declares one supported structured-output mode and passes the corresponding capability preflight. Models supporting neither mode remain unavailable in the UI.

At implementation preflight, resolve the latest stable non-prerelease LiteLLM release compatible with Python 3.11 and the required structured-output capabilities, then lock the exact tested version in `uv.lock`; do not install `litellm[proxy]`. The planning-day reference (2026-09-01) is PyPI `1.99.0`, but execution must verify again. The SDK portion remains MIT-licensed. References: https://pypi.org/project/litellm/ and https://docs.litellm.ai/.

## 0.3 Structured output belongs to the Workspace

Provider-native structured output is preferred, but it is not trusted as validation. Every response is validated again against Workspace-owned Pydantic models. The provider boundary supports exactly two modes:

- `native_schema`: provider JSON Schema (or equivalent) response format → JSON → Workspace Pydantic validation → scientific reference validation;
- `json_object`: strict JSON-only prompt and provider JSON-object response format → direct JSON decode → Workspace Pydantic validation → scientific reference validation.

Both modes forbid regex extraction, Markdown code-fence extraction, prose repair, autonomous repair/retry agents, and retries after invalid JSON or invalid schema. A provider returning valid JSON that fails the Pydantic schema is still an invalid provider response. Invalid evidence IDs, wrong-project references, duplicate evidence roles, or incorrect structured comparison assertions also fail validation before any Finding is committed.

## 0.4 Evidence Gate: hybrid, with deterministic authority

The model may propose a gate state and rationale, but the authoritative `evidence_gate_status` is produced by a versioned server policy.

The server performs deterministic checks for two distinct support classes:

- `direct_structured_support`: validated Measurement comparison assertions, validated structured Experiment differences, and immutable Revision structured-property observations where the referenced paths and values can be recomputed from the frozen context;
- `curated_evidence`: Literature-backed, Measurement-backed, or ExperimentRevision-backed EvidenceRecords selected by the scientist.

The gate checks selected identity, same-Project ownership, roles, measurement/experiment identity, direct assertions against frozen summaries, changed-factor counts, causal safeguards, declared missing controls, and contradictions. Direct structured support may support descriptive or comparative claims without a separate EvidenceRecord. It never supplies causal proof. Semantic relevance beyond these deterministic checks is displayed for human review and may be scored by the optional judge; it must never silently upgrade the gate.

## 0.5 Conservative causal policy

Phase 3 P0 does not claim general causal inference. The policy distinguishes five Finding types:

- `scientific_observation` — descriptive statement about one frozen record;
- `hypothesis` — testable proposed explanation;
- `comparative_finding` — difference between selected experiments/measurements;
- `causal_claim` — asserts that a named factor caused an outcome;
- `recommendation` — proposed action or next experiment.

For P0, a `causal_claim` can never be automatically classified `supported`. It is:

- `contradicted` when valid contradicting evidence exists and no valid support survives;
- `insufficient_evidence` when the stated contrast changes the target factor plus any other independent factor, lacks an appropriate control, has an invalid comparison assertion, or cites no valid support;
- at most `partially_supported` when the frozen contrast changes only the target factor and has relevant support, because the current model does not encode replication, randomisation, or a formal causal design.

For the demo claim “starch caused EXP-045 to outperform EXP-041,” the factor-diff service must identify both KI and starch as changes. The policy must override any model-proposed `supported` state with `insufficient_evidence`, add `confounded_variables` and `missing_isolating_control`, and propose a baseline-plus-starch/no-KI control. EXP-044 may support an incremental association in the KI-containing formulation, but it does not justify an unqualified starch-caused-the-baseline-improvement claim.

## 0.6 Evaluation: deterministic release metrics plus optional judge

Deterministic metrics are authoritative for regression and CI. An optional LLM-as-judge adds explicitly non-deterministic semantic scores; judge failure never removes deterministic results and never blocks CI or the core demo.

The judge uses the same `AIProvider` boundary with a separate configured model profile and a separate versioned structured prompt. Judge scores always record provider/model/prompt metadata and are labelled `judge` in both PostgreSQL and the UI. Human reviewer scores remain distinct from judge scores.

## 0.7 Execution model

- Interactive Scientific Analysis is synchronous: one bounded provider operation plus deterministic context, validation, and gate processing.
- Evaluation is asynchronous from the HTTP caller: `POST` persists an `EvaluationRun`, returns `202` with its ID, then a FastAPI in-process background task processes cases sequentially and persists progress.
- No Celery, Redis, RabbitMQ, external worker, or durable queue is added.
- v0.1 assumes exactly one API process and one worker owns in-process Evaluation execution; cases run sequentially and PostgreSQL persists Run/Result state.
- The supported launch contract is `uvicorn ... --workers 1`. Running multiple API workers is unsupported because there is no cross-worker ownership or coordination.
- On application startup, that single process marks stale `queued` or `running` evaluation runs `interrupted`; they are never silently resumed. The user may create a new run with the same case set.

This limitation is explicit: a process restart may interrupt an active evaluation. Durable queue execution is post-v0.1.

## 0.8 Langfuse: selected as optional Cloud projection

Use the Langfuse Python SDK v4 as an optional observability/evaluation projection. Langfuse Cloud is recommended for the portfolio demo. Self-hosted Langfuse is not part of v0.1 because the current supported stack adds Web, Worker, PostgreSQL, ClickHouse, Redis, and object storage; the official Docker Compose guidance recommends substantial resources for the full stack. References: https://langfuse.com/self-hosting/deployment/docker-compose and https://langfuse.com/self-hosting/configuration/scaling.

Workspace PostgreSQL remains authoritative for:

- ScientificAnalysisRun identity and state;
- frozen scientific context;
- Findings and gate results;
- ReviewDecisions;
- EvaluationCases, EvaluationRuns, and EvaluationResults;
- deterministic and judge score snapshots;
- suggested-experiment provenance.

Langfuse may receive traces, generations, dataset items, run metadata, and scores. It must not become the only record of scientific context or evaluation outcomes. Prompts remain versioned in the repository and are never fetched from a mutable Langfuse label at runtime.

Langfuse is disabled by default. When configured but unavailable, the scientific operation succeeds, `langfuse_sync_status` becomes `failed`, and the UI remains understandable from PostgreSQL data. At implementation preflight, resolve the latest stable non-prerelease v4 SDK compatible with Python 3.11, verify the required tracing/dataset/score APIs, and lock the exact tested version in `uv.lock`; the planning-day reference (2026-09-01) is `4.15.1`. The SDK supports deterministic trace-ID correlation, datasets, experiments, and scores: https://langfuse.com/docs/observability/sdk/instrumentation and https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk.

## 0.9 Retrieval, RAG, pgvector, and MCP

Semantic retrieval, embeddings, pgvector, generic RAG, and MCP are **deferred**.

P0 users explicitly select 2–5 experiments, immutable measurements, Literature records, and optionally 0–25 human-authored EvidenceRecords. The selected structured context is small and fully traceable; a valid Measurement/Experiment/Revision assertion can provide direct support when no curated EvidenceRecord is selected. Vector retrieval would weaken the demo's explicit evidence boundary and add an index whose historical state would also need freezing. MCP remains a post-v0.1 external-agent access option, not part of the critical path.

## 0.10 Suggested next experiment: gated prefilled draft

The AI never creates an Experiment.

After the latest human review is `accept` or `needs_evidence`, the UI may expose `Create Draft Experiment`. That action:

1. loads a server-validated prefill derived from the frozen `suggested_next_experiment`;
2. opens the existing Experiment creation page;
3. shows every proposed field in the normal schema-driven form;
4. allows the scientist to inspect and edit all values;
5. requires the normal explicit submit action;
6. calls the existing Experiment creation service and exact template validation;
7. creates an Experiment with status `draft` only;
8. writes a separate immutable provenance link back to Finding, AnalysisRun, and the review that enabled the action.

A rejected or unreviewed Finding cannot expose or submit this prefill. No endpoint creates an Experiment directly from a Finding.

---

# 1. Definition of Done

Phase 3 is complete only when all P0 criteria below pass:

1. Upgrade from a populated Phase 2 database at Alembic `0004_literature_evidence` succeeds without changing existing Phase 1/2 rows or snapshots.
2. Blank PostgreSQL 17 upgrade to Phase 3 head succeeds and `alembic check` reports no differences.
3. All existing Phase 1 and Phase 2 PostgreSQL tests and browser paths remain green.
4. A scientist can select 2–5 same-Project Experiment revisions plus explicit Measurements, Literature, and 0–25 active EvidenceRecords from Compare; structured scientific context remains sufficient when EvidenceRecord selection is empty.
5. The backend rejects missing revisions, live records that have drifted from the selected revision, cross-Project references, unselected Evidence sources, and oversized context before calling a model.
6. The deterministic context builder produces canonical JSON and the same SHA-256 for the same frozen selection.
7. Context snapshots include exact Experiment revisions, immutable template identity/schema hash, Measurement/import/source hashes, selected point samples and full point hashes, Evidence snapshots, Literature snapshots, lineage, and structured Compare/factor differences.
8. A successful analysis records provider, requested/resolved model, available provider model version/fingerprint, prompt snapshot/version/hash, response-schema version, workflow version, material generation parameters, usage, and exact validated output.
9. A later Experiment, Literature, prompt, or model change does not alter a prior context, Finding, gate, or EvaluationCase.
10. The real provider path uses embedded LiteLLM SDK behind `AIProvider`; CI uses only `FixtureProvider` and mocks.
11. Malformed model output, invalid JSON-object output, Pydantic schema failures, invalid evidence IDs, wrong-project citations, invalid structured-support assertions, provider timeout, provider unavailable, and missing configuration produce diagnostic persisted failure states.
12. Findings are structured first-class records, not chat messages, and distinguish the five Finding types.
13. Confidence label/rationale is visibly separate from the authoritative Evidence Gate.
14. Gate states `supported`, `partially_supported`, `insufficient_evidence`, and `contradicted` are all covered by deterministic tests.
15. The EXP-041 versus EXP-045 starch causal claim is forced to `insufficient_evidence`, identifies both KI and starch changes, and identifies the missing isolating control.
16. The suggested control is stored as a non-authoritative proposal and cannot write an Experiment.
17. ReviewDecision supports Accept, Reject, and Needs Evidence; decisions are append-only, ordered, and can supersede only the current review.
18. Reject requires a rejection reason and can be converted once into an immutable `bad_case` EvaluationCase with complete scientific provenance and expected behavior; an explicitly accepted Finding can create one controlled immutable `reference_case` through the separate path.
19. An EvaluationRun persists before execution, returns a run ID immediately, reports sequential progress from one API worker, isolates per-case failures, and records interrupted state after process restart.
20. Evaluation replay uses the frozen EvaluationCase context, not current live scientific records.
21. Deterministic metrics cover schema, direct structured support, evidence references, comparison correctness, causal overclaiming, gate correctness, limitation/missing-control detection, citation correctness, and structured next-experiment requirements.
22. Optional judge scores are clearly labelled, independently versioned, and do not change deterministic pass/fail.
23. The Evaluation UI shows dataset version, model/prompt, Bad Case versus Reference Case, deterministic and judge dimensions, regression against a selected previous run, case tags, and links to the source Finding/review; the P0 regression dataset contains 4–8 cases with both case types.
24. With Langfuse disabled or unavailable, analysis and evaluation remain complete in PostgreSQL and the UI shows trace sync state without breaking.
25. With Langfuse Cloud configured, AnalysisRun UUIDs correlate to traces and EvaluationCase/Run/Result identifiers are included in dataset/score metadata.
26. `Create Draft Experiment` is visible only after latest Accept or Needs Evidence review, opens the existing creation form prefilled, remains editable, requires explicit submit, validates normally, creates `draft`, and records origin provenance.
27. Phase 3 seed is idempotent and extends PRJ-001/EXP-041/044/045 rather than creating an unrelated AI project.
28. The complete browser demo runs without terminal/database intervention, error overlays, hydration errors, unhandled rejections, or hidden provider failures.
29. PostgreSQL 17 CI covers blank migration, populated Phase 2 upgrade, parity, seed twice, all backend tests, all frontend gates, and the single-worker Evaluation smoke with no paid/live model or Langfuse call.
30. `docs/handoff/PHASE_3_HANDOFF.md` records factual evidence, and `v0.1-demo` is tagged only after every P0 criterion passes.

If any criterion is missing, report `PHASE 3 NOT READY`; do not create the release tag.

---

# 2. Stable Phase 1/2 Contracts

The implementation must preserve:

- immutable ExperimentTemplate version rows and permanent Experiment binding;
- Experiment lineage through `parent_experiment_id`;
- append-only ExperimentRevision history and rendering of v1/v2 snapshots;
- separate `structured_data` and `note_document`;
- Attachment metadata/byte consistency and storage abstraction;
- `Attachment → MeasurementImport → Measurement → MeasurementPoint` provenance;
- immutable Measurement scientific fields and `points_sha256`;
- mutable Literature current metadata plus immutable Evidence source snapshots;
- append-only/withdraw-only Evidence behavior and exactly-one-source constraint;
- existing Project, Experiment, Attachment, Revision, Measurement, Compare, Literature, and Evidence API meanings;
- typed REST boundary: Web never accesses PostgreSQL or provider credentials directly;
- PostgreSQL 17 as acceptance database and SQLite only as a local fallback.

Phase 3 migrations are additive. Do not rewrite old ExperimentRevision or Evidence snapshots. Do not make AI output authoritative scientific data.

---

# 3. Canonical Domain Additions

Use the existing portable `JSON` with PostgreSQL `JSONB` variant and SQLAlchemy `Uuid` conventions. All snapshots use canonical JSON serialization with sorted keys, UTF-8, finite numbers only, and SHA-256.

## 3.1 ScientificAnalysisRun

Table: `scientific_analysis_runs`

```text
- id: UUID PK
- project_id: UUID FK projects.id, indexed
- purpose: interactive | evaluation_replay
- status: building_context | running | completed | failed | interrupted
- provider_key: litellm | fixture
- model_profile_key
- structured_output_mode: native_schema | json_object
- requested_model
- resolved_model nullable
- provider_response_id nullable
- provider_model_version nullable
- prompt_key
- prompt_version: positive integer
- prompt_sha256: char(64)
- prompt_snapshot_json: exact rendered system/user prompt metadata
- output_schema_version: positive integer
- workflow_version: positive integer
- generation_parameters_json
- model_metadata_json: usage, fingerprint, finish reason; never secrets
- raw_output_text nullable
- validated_output_json nullable
- error_code nullable
- error_message nullable, sanitised
- langfuse_trace_id nullable
- langfuse_sync_status: disabled | pending | synced | failed
- langfuse_error nullable, sanitised
- started_at nullable
- completed_at nullable
- created_at
```

Behavior:

- The row is created before context build/provider work and committed at each status transition.
- Scientific/configuration fields become immutable once status leaves `building_context`.
- A failed run remains inspectable and never creates partial Findings.
- Store provider output content only; never request or store hidden chain-of-thought.
- Interactive list endpoints exclude `evaluation_replay` unless explicitly requested.

## 3.2 AnalysisContextSnapshot

Table: `analysis_context_snapshots`

```text
- id: UUID PK
- analysis_run_id: UUID FK scientific_analysis_runs.id, unique
- schema_version: positive integer, P0 value 1
- snapshot_json
- snapshot_sha256: char(64)
- size_bytes: positive integer
- created_at
```

The immutable snapshot contains:

```text
project identity
selection manifest
experiment revision snapshots and lineage
template id/version plus JSON Schema checksum
measurement metadata, summaries, selected point samples, points_sha256
MeasurementImport id/parser/source attachment/source_sha256
selected Literature snapshots
selected Evidence rows and immutable source_snapshot_json
computed Compare result
normalised scientific factor differences
context limits and sampling policy/version
```

Selection rules:

- 2–5 Experiment revisions from one Project;
- 1–10 Measurements belonging to selected Experiments and referenced by the chosen v2 revisions;
- 0–10 Literature records;
- 0–25 active Evidence records;
- every Evidence source must be present in the selected revision/measurement/literature context;
- revisions must match current Experiment scientific fields when Analysis is launched from live Compare; otherwise return `experiment_changed_since_revision` and require an explicit new Revision;
- maximum canonical context size: 512 KiB;
- maximum 200 points per Measurement in provider context and 2,000 total sampled points;
- measurements over the limit use deterministic evenly spaced ordinal sampling including first/last points; store sampling metadata and retain full immutable `points_sha256`.

No mutable live query is used to reconstruct historical model input.

## 3.3 Finding

Table: `findings`

```text
- id: UUID PK
- project_id: UUID FK, indexed
- analysis_run_id: UUID FK, indexed
- ordinal: integer >= 0
- claim: text
- claim_type: scientific_observation | hypothesis | comparative_finding | causal_claim | recommendation
- confidence_label: low | medium | high
- confidence_rationale: text
- applicability_scope: text
- limitations_json
- risks_json
- missing_evidence_json
- comparison_assertions_json
- structured_support_json: immutable server-verified direct support artifact
- causal_target_json nullable
- suggested_next_experiment_json nullable
- model_proposed_gate_status
- model_proposed_gate_rationale
- evidence_gate_status: supported | partially_supported | insufficient_evidence | contradicted
- evidence_gate_rationale_json
- gate_policy_version: positive integer, P0 value 1
- review_status: pending_review | accepted | rejected | needs_evidence
- created_at
```

Unique `(analysis_run_id, ordinal)`.

Finding content, structured support, evidence links, and gate result are immutable. Only the cached `review_status` changes transactionally when an append-only ReviewDecision is written. There is no Finding PATCH or DELETE endpoint.

### Structured model output v1

`ScientificAnalysisResponseV1`:

```text
analysis_summary: 1–4000 chars
findings: 1–5 FindingCandidateV1
```

`FindingCandidateV1` requires:

```text
claim
claim_type
confidence_label
confidence_rationale
applicability_scope
evidence_links[] (0–25): {evidence_id, role, rationale}
structured_support_assertions[] (0–25): one of the following server-verifiable assertion types:
  measurement_comparison: {left_measurement_id, right_measurement_id, metric, relation, rationale}
  experiment_difference: {left_experiment_id, left_revision_number, right_experiment_id, right_revision_number, path, relation, rationale}
  revision_observation: {experiment_id, revision_number, path, operator, expected_value, rationale}
limitations[]: {code, description}
risks[]: {code, description}
missing_evidence[]: {code, description}
comparison_assertions[]
causal_target nullable
suggested_next_experiment nullable
proposed_gate: {status, rationale}
```

`measurement_comparison` assertions use frozen, verifiable fields only:

```text
left_measurement_id
right_measurement_id
metric: y_min | y_max | y_mean
relation: greater_than | less_than | approximately_equal
rationale
```

`experiment_difference` assertions are limited to structured JSON Pointer paths and server-recomputed added/removed/changed/equal values. `revision_observation` assertions are limited to structured revision properties, presence/absence, and exact scalar or quantity values; free-text `note_document` content is never direct support. The server stores the validated results and source paths in `structured_support_json`.

Direct structured support contributes to `scientific_observation` and `comparative_finding` classification. It may validate the observed outcome portion of a `causal_claim`, but it is excluded from causal support and can never upgrade a causal claim to `supported`.

`causal_target` is required only for `causal_claim`:

```text
factor_paths: JSON Pointer list
baseline_experiment_id
outcome_experiment_id
outcome_measurement_ids
```

`suggested_next_experiment`:

```text
title
objective
base_experiment_id
control_strategy
change_operations[]: {op: set | remove, path: JSON Pointer, value, rationale}
addresses_missing_evidence_codes[]
```

After response validation, the server applies suggestion operations to the frozen base revision, validates the resulting complete `structured_data` against the exact immutable template, and stores a normalised suggestion with `validation_status`, template identity, and full prefill. Invalid proposals remain visible as limitations but cannot expose `Create Draft Experiment`.

## 3.4 FindingEvidenceLink

Table: `finding_evidence_links`

```text
- id: UUID PK
- finding_id: UUID FK, indexed
- evidence_record_id: UUID FK, indexed
- role: supporting | contradicting | contextual
- rationale: text
- evidence_snapshot_json
- created_at
```

Unique `(finding_id, evidence_record_id)` prevents one citation occupying contradictory roles. The service requires the ID to be in the frozen context, active at snapshot time, and in the same Project. Supporting links require original Evidence stance `supports`; contradicting links require `contradicts`; any stance may be contextual. A reference outside the allowed set fails the whole model response and persists no Findings.

## 3.5 ReviewDecision

Table: `review_decisions`

```text
- id: UUID PK
- finding_id: UUID FK, indexed
- sequence_number: positive integer
- decision: accept | reject | needs_evidence
- reviewer_name: string(240)
- reason_code nullable
- comment nullable
- supersedes_review_id nullable FK review_decisions.id
- created_at
```

Rejection reason codes:

```text
unsupported_causal_claim
insufficient_evidence
contradicted_by_evidence
incorrect_experiment_comparison
missed_limitation
incorrect_citation
unsafe_recommendation
incorrect_reasoning
other
```

Rules:

- append-only; no PATCH/DELETE;
- unique `(finding_id, sequence_number)`;
- a new review locks the Finding and increments sequence number;
- `supersedes_review_id`, when provided, must be the latest review for the same Finding and may be superseded only once;
- reject requires a reason code and comment; needs-evidence requires a comment; accept comment is optional;
- P0 has no authentication/RBAC, so `reviewer_name` is a required explicit display-name snapshot;
- writing the review and updating Finding.review_status is one transaction;
- ReviewDecision never changes the Finding claim or gate.

## 3.6 EvaluationCase (Bad Case or Reference Case)

Use one canonical table. `bad_case` is the product label for an EvaluationCase created from a rejected Finding; `reference_case` is a manually approved or deterministically seeded known-good behavior created through a separate controlled path.

Table: `evaluation_cases`

```text
- id: UUID PK
- project_id: UUID FK, indexed
- case_type: bad_case | reference_case
- source_finding_id: UUID FK
- source_review_decision_id: UUID FK, unique
- context_schema_version
- context_snapshot_json
- model_output_snapshot_json
- finding_snapshot_json
- gate_snapshot_json
- review_snapshot_json
- expected_behavior_json
- case_tags_json
- source_model_config_json
- source_prompt_snapshot_json
- case_hash: char(64)
- langfuse_dataset_item_id nullable
- langfuse_sync_status: disabled | pending | synced | failed
- langfuse_error nullable
- created_at
```

EvaluationCase is immutable. A `bad_case` requires the latest rejected ReviewDecision; a `reference_case` requires the latest accepted ReviewDecision. Each review creates at most one case of its allowed type through its corresponding controlled path. A later superseding review does not rewrite or delete the historical case. Seed fixtures must create the accepted review snapshot before creating a reference case; there is no free-form unprovenanced reference-case input.

`expected_behavior_json` P0 schema:

```text
expected_gate_status nullable
required_claim_types[]
required_direct_support_kinds[]
forbidden_claim_types[]
required_limitation_codes[]
required_missing_evidence_codes[]
required_evidence_ids[]
forbidden_evidence_ids[]
required_suggestion_change_paths[]
must_have_valid_citations: boolean
must_avoid_unsupported_causal_conclusion: boolean
must_distinguish_comparison_from_causality: boolean
reviewer_notes
```

The existing `POST /findings/{finding_id}/evaluation-cases` path remains Bad Case creation and is idempotent for the rejected review. A separate `POST /findings/{finding_id}/evaluation-cases/reference` path requires the latest accepted review and is idempotent for that accepted review. Both paths copy frozen context, output, Finding, gate, review, model/prompt metadata, and a canonical `case_hash`; neither path accepts arbitrary live scientific snapshots.

The case copies the scientific context and outputs rather than relying only on foreign keys. This makes it portable and replayable even if current metadata changes.

## 3.7 EvaluationRun

Table: `evaluation_runs`

```text
- id: UUID PK
- project_id: UUID FK, indexed
- status: queued | running | completed | completed_with_errors | failed | interrupted | cancel_requested | cancelled
- dataset_version: char(64)
- model_profile_key
- structured_output_mode: native_schema | json_object
- requested_model
- prompt_key
- prompt_version
- prompt_sha256
- prompt_snapshot_json
- workflow_version
- output_schema_version
- generation_parameters_json
- judge_enabled: boolean
- judge_model_profile_key nullable
- judge_structured_output_mode nullable
- judge_prompt_version nullable
- baseline_run_id nullable FK evaluation_runs.id
- total_cases
- completed_cases
- passed_cases
- failed_cases
- error_cases
- aggregate_scores_json
- regression_summary_json
- error_code nullable
- error_message nullable
- langfuse_experiment_name nullable
- langfuse_sync_status
- langfuse_error nullable
- created_at
- started_at nullable
- completed_at nullable
```

The dataset version is the SHA-256 of the canonically sorted list of `{case_type, case_id, case_hash}` entries. The ordered case set and all model/prompt configuration are frozen before the background task starts; changing case type or content changes the version, while changing request order does not.

## 3.8 EvaluationResult

Table: `evaluation_results`

```text
- id: UUID PK
- evaluation_run_id: UUID FK, indexed
- evaluation_case_id: UUID FK, indexed
- ordinal
- status: pending | running | passed | failed | error | cancelled
- replay_analysis_run_id nullable UUID FK scientific_analysis_runs.id
- deterministic_scores_json
- judge_scores_json nullable
- judge_metadata_json nullable
- failure_tags_json
- error_code nullable
- error_message nullable
- langfuse_trace_id nullable
- langfuse_sync_status
- created_at
- completed_at nullable
```

Unique `(evaluation_run_id, evaluation_case_id)` and `(evaluation_run_id, ordinal)`.

## 3.9 ExperimentProvenanceLink

Table: `experiment_provenance_links`

```text
- id: UUID PK
- experiment_id: UUID FK experiments.id, unique
- finding_id: UUID FK findings.id
- analysis_run_id: UUID FK scientific_analysis_runs.id
- enabling_review_decision_id: UUID FK review_decisions.id
- relation_type: suggested_from_finding
- suggestion_snapshot_json
- submitted_values_snapshot_json
- created_at
```

This table avoids changing historical Experiment identity or overloading `parent_experiment_id`. The created draft still uses the suggested base Experiment as `parent_experiment_id`, preserving normal clone lineage, while this link records why the draft was proposed.

---

# 4. Additive Migrations and Invariants

## Migration `0005_scientific_analysis`

Create:

- `scientific_analysis_runs`;
- `analysis_context_snapshots`;
- `findings`;
- `finding_evidence_links`;
- `review_decisions`.

Add database checks for every enum, positive version/sequence fields, completed/failed timestamp consistency where portable, and required rejection reason semantics. Add indexes for Project lists, AnalysisRun status, Finding review status, and foreign keys. Do not alter Phase 1/2 columns or rows.

## Migration `0006_scientific_evaluation`

Create:

- `evaluation_cases`;
- `evaluation_runs`;
- `evaluation_results`;
- `experiment_provenance_links`.

Use restrictive foreign keys by default. Domain records must not cascade-delete scientific history. Project/Experiment hard delete is not exposed by current APIs, but migration constraints must still avoid deleting Phase 3 provenance silently.

## Immutability enforcement

Service/API rules are primary. Add SQLAlchemy `before_update`/`before_delete` guards for frozen AnalysisContextSnapshot, Finding scientific fields, FindingEvidenceLink, ReviewDecision, EvaluationCase, completed EvaluationResult, and ExperimentProvenanceLink. Lifecycle/status fields may change only through named services.

Migration tests must cover both SQLite compatibility and authoritative PostgreSQL behavior.

---

# 5. Scientific Context Builder

Implement one `ScientificContextBuilder`; routers and providers may not assemble scientific context independently.

Input:

```text
project_id
experiment_selections[]: {experiment_id, revision_number}
measurement_ids[]
literature_ids[]
evidence_ids[]
```

Processing order:

1. Validate selection counts and uniqueness.
2. Load all entities with bounded eager queries.
3. Verify same-Project ownership and active Evidence.
4. Verify each chosen revision exists and is the current scientific state for live Compare launch; return drift diagnostics otherwise.
5. Verify selected Measurements belong to selected Experiments and appear in selected revision v2 references.
6. Verify Evidence sources are included in the selected context.
7. Snapshot current Literature fields and retain Evidence's immutable literature/source snapshots separately.
8. Compute the existing Compare result server-side; never accept a client-supplied Compare payload as authoritative.
9. Compute normalised factor differences.
10. Load bounded Measurement points, apply deterministic sampling, and record full hashes/provenance.
11. Canonicalise, size-check, hash, persist, and only then invoke AI.

### Factor-diff v1

- recurse through objects using JSON Pointer paths;
- treat `{value, unit}` quantities atomically;
- treat arrays of objects with a unique `name` key as keyed factors such as `/additives/@KI` and `/additives/@starch`;
- treat all other arrays atomically;
- distinguish missing, null, added, removed, and changed;
- include pairwise diffs for every selected Experiment pair plus lineage edges;
- preserve the existing Compare API behavior; this is an additive scientific-context representation.

The builder is pure/testable after records are loaded. Provider code receives only the frozen snapshot.

---

# 6. AI Provider, Prompts, and Run Workflow

## 6.1 Internal interfaces

```python
class AIProvider(Protocol):
    def generate_structured(
        self,
        request: AIRequest,
        response_model: type[T],
    ) -> AIResult[T]: ...

class ObservabilityAdapter(Protocol):
    def start_analysis_trace(...): ...
    def record_generation(...): ...
    def sync_evaluation_case(...): ...
    def record_scores(...): ...
```

`AIRequest` contains only resolved server configuration: model identifier, `structured_output_mode`, messages, JSON Schema when using `native_schema`, timeout, maximum output tokens, temperature, optional seed, and safe metadata. `AIResult` returns parsed content, raw response content, requested/resolved model, provider response ID/version/fingerprint when available, usage, finish reason, and latency.

Do not expose LiteLLM response objects outside the adapter.

## 6.2 Model profiles

Add a server-side allowlisted JSON setting:

```text
AI_MODEL_PROFILES_JSON={
  "analysis-default": {"model": "openai/<configured-model>", "label": "Default analysis", "structured_output_mode": "native_schema"},
  "analysis-candidate": {"model": "anthropic/<configured-model>", "label": "Candidate", "structured_output_mode": "json_object"},
  "judge-default": {"model": "gemini/<configured-model>", "label": "Judge", "structured_output_mode": "native_schema"}
}
AI_DEFAULT_ANALYSIS_PROFILE=analysis-default
AI_DEFAULT_JUDGE_PROFILE=judge-default
```

The repository must not hard-code a paid model name as universally available. `.env.example` uses placeholders and documents provider-native API-key variables. API callers submit a profile key, never an API key, base URL, or arbitrary model string. `GET /api/v1/ai/model-profiles` returns safe label/provider/model/structured-output-mode/availability/reason metadata only. Capability discovery combines LiteLLM capability metadata with an implementation-preflight smoke for each configured profile; a profile supporting neither `native_schema` nor `json_object` is unavailable.

P0 limits:

- analysis timeout: 45 seconds;
- maximum output tokens: 4,000;
- temperature: 0 by default;
- one retry for transient timeout/rate-limit/5xx only;
- no retry for authentication, bad request, unsupported capability, invalid JSON, or invalid structured output;
- no tools, function execution, streaming, fallback cascade, or autonomous loop;
- maximum five Findings per response.

Every material parameter is recorded in the run.

## 6.3 Prompt registry

Store prompts in versioned repository files:

```text
api/app/prompts/scientific_analysis/v1.md
api/app/prompts/evaluation_judge/v1.md
```

Use a `PromptRegistry` with stable keys, positive versions, and SHA-256. Never overwrite a published version; add `v2.md`. Persist exact rendered messages plus key/version/hash in every run. Langfuse prompt labels are not the runtime source of truth.

Analysis prompt rules must explicitly state:

- use only supplied scientific context;
- cite only allowed Evidence IDs;
- distinguish observation, hypothesis, comparison, causality, and recommendation;
- never infer causality from co-varying factors;
- state limitations and missing controls;
- return only the declared structured schema;
- never propose tool calls or record changes.

## 6.4 Analysis transaction workflow

1. Validate request shape and model profile.
2. Create AnalysisRun in `building_context`.
3. Build and commit context snapshot.
4. Set run `running`, create deterministic Langfuse trace ID from `analysis-run:{uuid}` when enabled.
5. Execute one bounded provider operation using the resolved `native_schema` or `json_object` mode.
6. Direct-decode JSON where required, then validate Pydantic schema and all direct-support/evidence/comparison/causal references.
7. Apply Evidence Gate policy v1 and normalise suggested experiments.
8. In one transaction, create all Findings/links and set run `completed`.
9. Best-effort flush Langfuse; sync failure changes only sync status.

If failure occurs after context persistence, mark the run failed and return a diagnostic error with `analysis_run_id`; do not persist partial Findings.

---

# 7. Evidence Gate Policy v1

For each Finding:

1. Validate curated Evidence IDs/roles and direct structured-support assertions.
2. Recompute Measurement comparisons, structured Experiment differences, and Revision observations from the frozen context.
3. Count valid direct structured support separately from valid curated supporting/contradicting links; contextual links never count as support.
4. Allow direct support to establish descriptive/comparative claims without a curated EvidenceRecord, but exclude it from causal support.
5. Apply causal guard if claim type is causal.
6. Apply declared material limitations/missing evidence.
7. Emit authoritative status plus ordered reason codes and human-readable explanations.

Base classification:

```text
contradictions > 0 and all support == 0       → contradicted
contradictions > 0 and any support > 0        → partially_supported
no direct or curated support                  → insufficient_evidence
direct/curated support and no material gap    → supported (observation/comparison only for direct support)
support and material gaps remain              → partially_supported
```

For `causal_claim`, `support` in this table means valid curated support only; direct structured support can verify the observed contrast but is never causal support. For `scientific_observation` and `comparative_finding`, verified direct support and curated support are both eligible.

Causal override:

```text
wrong/invalid comparison assertion             → insufficient_evidence
target contrast has >1 independent factor diff → insufficient_evidence
missing isolating control                      → insufficient_evidence
isolated association but no formal design      → at most partially_supported
direct structured support only                 → never causal support
valid direct contradiction                     → contradicted
```

The gate stores:

- status;
- policy version;
- valid direct structured-support assertions and their source paths/values;
- valid supporting/contradicting/context Evidence IDs;
- invalid assertion details;
- changed factor paths;
- causal safeguard codes;
- missing-control description;
- explanation shown to the scientist.

Confidence remains model self-assessment and never overrides this policy.

---

# 8. Public API Contracts

All endpoints use `/api/v1`, Pydantic request/response schemas, UUID identities, and existing error conventions.

## Analysis and Findings

```text
GET  /ai/model-profiles
GET  /ai/prompt-versions

POST /projects/{project_id}/analysis-runs
GET  /projects/{project_id}/analysis-runs?purpose=&status=
GET  /analysis-runs/{analysis_run_id}

GET  /projects/{project_id}/findings?review_status=&claim_type=&gate_status=
GET  /findings/{finding_id}
```

`POST /projects/{project_id}/analysis-runs` request:

```json
{
  "experiment_selections": [
    {"experiment_id": "uuid", "revision_number": 1}
  ],
  "measurement_ids": ["uuid"],
  "literature_ids": ["uuid"],
  "evidence_ids": [],
  "model_profile_key": "analysis-default",
  "prompt_version": 1
}
```

`evidence_ids` accepts 0–25 IDs. An empty list is valid when the frozen Measurements, Experiment differences, or Revision observations provide sufficient structured context; it does not bypass ownership, revision, or assertion validation.

Success is `201` with completed run detail and Findings. Context/ownership/drift errors return 409/422 before a provider call. Provider unavailable/auth/rate failures return 502, provider timeout 504, and invalid JSON, invalid Pydantic output, or invalid scientific references return 502 `invalid_provider_response`; each post-context error includes the persisted `analysis_run_id`.

## Human review

```text
GET  /findings/{finding_id}/reviews
POST /findings/{finding_id}/reviews
```

Request:

```json
{
  "decision": "accept | reject | needs_evidence",
  "reviewer_name": "R&D Scientist",
  "reason_code": "unsupported_causal_claim",
  "comment": "The selected contrast changes KI and starch.",
  "supersedes_review_id": null
}
```

## Bad Cases and Evaluation

```text
POST /findings/{finding_id}/evaluation-cases
POST /findings/{finding_id}/evaluation-cases/reference
GET  /projects/{project_id}/evaluation-cases
GET  /evaluation-cases/{case_id}

POST /projects/{project_id}/evaluation-runs        → 202
GET  /projects/{project_id}/evaluation-runs
GET  /evaluation-runs/{run_id}
GET  /evaluation-runs/{run_id}/results
GET  /evaluation-results/{result_id}
POST /evaluation-runs/{run_id}/cancel
```

The existing `POST /findings/{finding_id}/evaluation-cases` creates a `bad_case` only for the latest rejected review. `POST /findings/{finding_id}/evaluation-cases/reference` creates a `reference_case` only for the latest accepted review through the separate controlled path. Both accept structured expected behavior and case tags; both are idempotent for the source review and return the existing case with 200 on duplicate conversion. List responses support `case_type=bad_case|reference_case`.

EvaluationRun request:

```json
{
  "evaluation_case_ids": ["uuid"],
  "model_profile_key": "analysis-candidate",
  "prompt_version": 1,
  "judge_enabled": true,
  "judge_model_profile_key": "judge-default",
  "baseline_run_id": "uuid-or-null"
}
```

Limit one to 20 cases. Cases, baseline, and profiles must belong to the same Project/configured allowlist.

## Gated prefilled draft

```text
GET /findings/{finding_id}/suggested-experiment-prefill
GET /experiments/{experiment_id}/origin-provenance
```

There is intentionally no “create Experiment from Finding” endpoint.

The prefill response includes:

```text
project_id
template_id/version
parent_experiment_id
title/objective
validated structured_data
finding_id
analysis_run_id
enabling_review_decision_id
review_sequence_number
suggestion_hash
```

Extend the existing `POST /projects/{project_id}/experiments` request with optional `suggestion_origin` containing those IDs/hash. When present, the normal creation service:

- rechecks that the review is still latest and Accept/Needs Evidence;
- rechecks suggestion validity and same-Project/template lineage;
- requires status `draft`;
- validates the user-edited structured data using the normal exact template path;
- creates Experiment and ExperimentProvenanceLink in one transaction.

If review state changed after prefill, return `409 suggestion_review_changed`. The UI keeps the user's edits and asks them to re-evaluate rather than submitting silently.

---

# 9. Evaluation Workflow and Metrics

## 9.1 Background runner

The `POST` endpoint commits EvaluationRun plus pending EvaluationResult rows, then schedules a FastAPI `BackgroundTasks` function. The worker creates a fresh `SessionLocal`; it never reuses the request session. v0.1 supports one API process with one worker only (`uvicorn ... --workers 1`); PostgreSQL persists state but does not coordinate ownership across workers. A multi-worker deployment is explicitly unsupported until a post-v0.1 durable queue/worker architecture is introduced.

For each case, sequentially:

1. check cancel status;
2. mark result running and commit;
3. create `evaluation_replay` AnalysisRun from the case's frozen context without live queries;
4. call the selected analysis model/prompt through the same provider/validation/gate path;
5. select the corresponding replay Finding by deterministic ordinal/claim target rules stored in the case;
6. compute deterministic metrics;
7. optionally call the judge once and validate judge schema;
8. persist result, scores, tags, progress, and optional Langfuse projection;
9. continue after per-case error unless a global configuration/authentication error makes all remaining calls impossible.

At completion, compute aggregates and regression against baseline. Polling interval is 1–2 seconds while running and stops at a terminal state. Startup interruption handling is tested in the single supported process; it marks stale active runs `interrupted` and never resumes them or claims work from another worker.

## 9.2 Deterministic metrics

Every result records Boolean/categorical checks with explanations, not a fabricated continuous confidence score:

- `structured_output_valid`;
- `direct_structured_support_valid`;
- `direct_support_scope_correct`;
- `all_evidence_ids_allowed`;
- `citation_roles_valid`;
- `comparison_assertions_correct`;
- `comparative_gate_matches_direct_data`;
- `unsupported_claims_absent`;
- `causal_overclaim_guard_correct`;
- `causal_gate_not_upgraded_by_direct_support`;
- `evidence_gate_matches_expected`;
- `required_limitations_present`;
- `required_missing_evidence_present`;
- `required_suggestion_paths_present`;
- `suggestion_template_valid`.

Overall deterministic pass requires every metric marked required by the EvaluationCase to pass. Non-applicable checks are `not_applicable`, never coerced to pass.

## 9.3 Optional judge metrics

Judge schema returns categorical `poor | mixed | good` plus short rationale for:

- evidence grounding/relevance;
- citation correctness;
- risk and limitation quality;
- experiment-comparison reasoning;
- causal restraint;
- Evidence Gate rationale quality;
- suggested-next-experiment quality.

The judge sees only frozen case input, replay output, expected behavior, and deterministic results. It does not see another judge's output and has no tools. Store model/prompt/version/parameters. Judge scores are never averaged into deterministic pass/fail. UI displays them in a separate “Model judge” column.

## 9.4 Regression

For runs with a completed same-dataset baseline:

- compare per-metric pass counts;
- report improved/regressed/unchanged cases;
- show deterministic pass-rate delta as integer counts and percentages;
- compare judge categories only when judge prompt/model/schema match; otherwise label non-comparable;
- link every regression to EvaluationResult and source EvaluationCase.

Avoid significance claims for the tiny demo dataset.

---

# 10. Langfuse Integration Contract

Configuration:

```text
LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_ENVIRONMENT=development
LANGFUSE_CAPTURE_CONTENT=false
```

Content capture defaults off. When false, send hashes, IDs, token/latency/cost metadata, status, prompt version, and score summaries but not scientific note/context text. The portfolio operator may enable content capture only for the synthetic/anonymised PRJ-001 demo.

Identifier mapping:

```text
ScientificAnalysisRun.id
  → deterministic Langfuse trace ID seeded with "analysis-run:{uuid}"

EvaluationCase.id
  → Langfuse dataset item id returned by SDK
  → metadata: case_id, case_hash, project_id, source_finding_id

EvaluationRun.id
  → experiment/run name "scientific-rd/evaluation/{uuid}"
  → metadata: dataset_version, model profile, prompt version, baseline_run_id

EvaluationResult.id
  → replay trace metadata and score metadata
```

Use one Langfuse dataset per Workspace Project and dataset version hash in item/run metadata. Do not query Langfuse to reconstruct Workspace UI state. Do not use Langfuse prompt labels as runtime deployment pointers.

Adapter tests use a fake client. CI sets `LANGFUSE_ENABLED=false` and must make zero network requests.

---

# 11. Frontend UX

Reuse the existing Next.js shell, shadcn components, typed API client, Recharts, loading/error patterns, and 1024/1280 responsive target. Do not add a chat sidebar.

## 11.1 Compare → Analyse

Add `Analyse selected experiments` after a successful Compare.

Open a configuration panel showing:

- selected Experiments and latest Revision number;
- warning/action for missing or drifted Revisions;
- compatible Measurements with hashes/units;
- Literature and optional 0–25 active EvidenceRecord checkboxes;
- direct structured-support preview showing which Measurement/Experiment/Revision assertions can be recomputed;
- model profile, prompt version, and capability mode (`native_schema` or `json_object`) with availability reason;
- explicit context limits/cost notice;
- `Run Scientific Analysis`.

The server remains authoritative for all selection validation.

## 11.2 Analysis pages

Routes:

```text
/dashboard/analysis
/dashboard/analysis/[analysisRunId]
```

Analysis detail shows:

- run status, model/provider/prompt/workflow metadata;
- frozen context manifest and hashes;
- Compare summary and measurement provenance;
- one Finding card per structured Finding;
- claim-type badge and separate confidence label;
- prominent Evidence Gate badge/rationale;
- separate Direct Structured Support and Curated Evidence sections, including verified source paths/values;
- supporting, contradicting, and contextual Evidence with snapshots;
- limitations, risks, applicability scope, missing evidence;
- suggested next experiment and validation status;
- Langfuse trace state/link only when available;
- provider failure diagnostics without secrets/raw stack traces.

## 11.3 Review UX

Each Finding shows review history and an explicit Review dialog:

- Accept;
- Reject;
- Needs Evidence;
- reviewer name;
- reason taxonomy;
- comment;
- superseding warning if a current decision exists.

After Reject, show `Create Bad Case`. After Accept, show `Create Reference Case` through the controlled reference path. After Accept or Needs Evidence and a valid suggestion, show `Create Draft Experiment`. Never show the latter for pending/rejected/invalid suggestions.

## 11.4 Prefilled draft flow

Navigate to the existing route:

`/dashboard/projects/[projectId]/experiments/new?originFindingId={id}`

The page fetches the gated prefill, labels all values “AI suggestion — review before saving,” renders the ordinary title/objective/template/structured form, permits edits, and uses the normal Save button. No auto-submit, hidden create call, or model-controlled tool invocation.

After creation, Experiment detail shows `Suggested from Finding …` and links back to AnalysisRun while retaining normal `Cloned from …` lineage.

## 11.5 Evaluation pages

Routes:

```text
/dashboard/evaluations
/dashboard/evaluations/[evaluationRunId]
```

The index combines Bad Cases and Evaluation Runs. Run detail shows:

- dataset version/hash and case count;
- Bad Case versus Reference Case badges, filters, and source-review provenance;
- model/prompt/judge configuration;
- queued/running/interrupted/completed status and progress;
- deterministic score matrix;
- separate optional judge scores;
- baseline regression counts;
- case tags and filters;
- links to case, original Finding, review, and replay AnalysisRun;
- explicit per-case errors;
- cancel action while queued/running.

---

# 12. Failure and Recovery Matrix

| Condition | Backend behavior | UI behavior |
| --- | --- | --- |
| AI not configured | 503 before provider call; no billable work | setup message, no fake output |
| Missing/cross-Project selection | 404/409/422 before run | identify exact record |
| Missing or drifted Revision | 409 `experiment_changed_since_revision` | link to create Revision |
| Context exceeds limits | 413 `analysis_context_too_large` with counts | reduce selection guidance |
| Provider auth/unavailable/rate failure | persist failed run; 502 with run ID | inspectable failure, retry as new run |
| Provider timeout | persist failed run; 504 | timeout message and configuration shown |
| Unsupported structured-output capability | reject model profile/call; no Finding | mode and capability diagnostic |
| Invalid JSON object | persist failed run; no partial Finding | invalid-JSON diagnostic; no extraction or repair |
| Pydantic schema failure | persist failed run; no partial Finding | schema diagnostic |
| Malformed scientific reference | persist failed run; no partial Finding | invalid Evidence/support/comparison reference list |
| Model cites missing/wrong Evidence | fail response validation; no Finding | invalid evidence reference list |
| Model cites contradictory Evidence | persist Finding; gate becomes contradicted/partial | contradiction is prominent |
| Causal overclaim | deterministic downgrade | changed factors and missing control shown |
| Langfuse unavailable | scientific transaction succeeds; sync failed | local detail remains complete |
| Judge unavailable/invalid | deterministic result preserved; judge status error | judge unavailable, no fake score |
| Evaluation case fails | result error; continue remaining cases in the single worker | row-level error and partial run |
| Global model auth failure in evaluation | stop remaining; run failed | exact completed/error counts |
| Process restarts during evaluation | the single API worker marks run interrupted; no resume or cross-worker claim | offer new run using same cases |
| Cancel requested | stop before next case; pending rows cancelled | terminal cancelled state |
| Review superseded after prefill | Experiment submit returns 409 | preserve edits and require review refresh |
| Suggested data fails template validation | action disabled; Finding remains | display invalid paths/limitations |

---

# 13. Security and Cost Boundaries

- Server-side calls only; provider and Langfuse secrets never enter API responses, browser bundles, snapshots, or logs.
- Model profile keys are allowlisted; clients cannot submit arbitrary provider URLs/models/keys.
- No model tools, arbitrary code execution, web retrieval, filesystem access, or autonomous loop.
- Only explicitly selected same-Project scientific context is sent.
- Enforce context/point/evidence/case/output limits from this plan.
- Evaluation processes at most 20 cases sequentially, one replay call each, plus at most one optional judge call each.
- v0.1 Evaluation execution is supported only with one API process and one worker; multi-worker ownership/coordination is not implemented.
- Record provider usage/cost when LiteLLM exposes it; show “unknown” rather than estimating when unavailable.
- Sanitize provider errors and never persist headers/credentials.
- Langfuse content capture is opt-in and intended only for synthetic demo data.
- FixtureProvider responses are visibly labelled and cannot be confused with a live model.

---

# 14. Milestone Plan

Every milestone ends with formatter/lint/tests, migration checks where relevant, and a runnable application. Do not begin the next milestone until its acceptance criteria pass.

## Milestone 1 — Lock contracts, dependencies, and core analysis schema

Implement:

- update source-of-truth architecture/data-model documents with reviewed decisions;
- at implementation preflight resolve compatible latest stable non-prerelease LiteLLM/Langfuse SDKs, lock exact tested versions, update notices/licenses;
- model-profile settings, prompt registry, AIProvider/FixtureProvider interfaces;
- `structured_output_mode` capability model for `native_schema` and `json_object`;
- migration `0005_scientific_analysis` and ORM/Pydantic types;
- Finding `structured_support_json` and direct-support response unions;
- EvaluationCase `case_type`, `case_tags_json`, and reference-case constraints/types;
- append-only/immutability guards.

Acceptance:

- blank SQLite and PostgreSQL migration reach `0005`;
- upgrade from populated `0004` preserves Phase 2 row counts and hashes;
- Alembic parity passes;
- model profile output exposes no secret;
- model profiles expose safe mode/availability/reason metadata and reject unsupported modes;
- prompt version/hash is stable;
- immutable-field and review constraint tests pass;
- Phase 1/2 tests remain green.

## Milestone 2 — Deterministic context builder and factor differences

Implement:

- selection validator;
- canonical snapshot/hash builder;
- revision-drift detection;
- Measurement point sampling/provenance;
- Literature/Evidence snapshot assembly;
- optional 0–25 EvidenceRecord selection with deterministic direct-support assertion inputs;
- Compare integration and factor-diff v1.

Acceptance:

- identical selections produce byte-identical canonical snapshot/hash;
- later Experiment/Literature mutations do not change stored context;
- cross-Project, withdrawn, unselected-source, stale-revision, and oversize cases fail before provider invocation;
- empty EvidenceRecord selection remains valid when structured context is sufficient;
- EXP-041→045 factor diff separately reports KI and starch;
- large Measurement sampling is deterministic and preserves first/last/full hash;
- query count remains bounded for maximum selection.

## Milestone 3 — LiteLLM analysis workflow and optional Langfuse traces

Implement:

- `LiteLLMProvider` and deterministic FixtureProvider;
- structured response v1 and strict validation for both `native_schema` and `json_object`;
- versioned analysis prompt;
- synchronous AnalysisRun service/endpoints;
- optional Langfuse observability adapter and trace correlation;
- run list/detail APIs.

Acceptance:

- FixtureProvider completes a run and records full metadata;
- mocked LiteLLM adapter maps success, timeout, auth, rate-limit, unavailable, and malformed responses;
- profiles supporting neither structured-output mode are unavailable;
- invalid JSON, Pydantic output, Evidence, direct-support, or comparison references persist a failed run and zero Findings;
- Langfuse disabled/unavailable does not change scientific result;
- no test makes a network/model call.

## Milestone 4 — Findings and Evidence Gate policy v1

Implement:

- Finding/evidence persistence;
- deterministic direct structured-support and comparison validators;
- four-state gate policy and causal override;
- suggested-experiment normalisation/template validation;
- Finding list/detail APIs;
- deterministic Phase 3 fixture for the causal overclaim.

Acceptance:

- all four gate states have focused tests;
- a direct Measurement comparison can produce `supported` with zero curated EvidenceRecords;
- confidence and gate stay independent;
- direct support never upgrades a causal claim;
- EXP-041 vs EXP-045 “starch caused improvement” is insufficient regardless of proposed gate;
- response shows KI + starch, confounding, missing control, and baseline+starch suggestion;
- causal claim can be at most partially supported under P0;
- invalid suggestion cannot expose draft action;
- completed Finding fields cannot be edited/deleted.

## Milestone 5 — Analysis and human-review UX

Implement:

- Compare Analyse action/configuration;
- Analysis list/detail pages and Finding cards;
- ReviewDecision service/API/UI with supersession;
- loading/empty/error/provider/Langfuse states;
- navigation/breadcrumbs and typed frontend domain/API client.

Acceptance:

- browser can run fixture analysis from Compare and inspect frozen provenance;
- Evidence Gate, confidence, evidence roles, limits, risks, and suggestion are distinct;
- Direct Structured Support, Curated Evidence, and model capability mode are visibly distinct;
- Accept/Reject/Needs Evidence write append-only decisions;
- reject requires reason/comment; needs-evidence requires comment;
- superseding a stale review returns 409;
- no chat UI or direct scientific-record mutation appears;
- 1024 px and 1280 px layouts pass smoke checks.

## Milestone 6 — Evaluation schema, Bad/Reference Cases, and single-worker runner

Implement:

- migration `0006_scientific_evaluation`;
- immutable Bad Case conversion and controlled Reference Case creation;
- EvaluationRun/Result services and 202/background execution;
- progress, cancellation, interruption recovery;
- deterministic metrics and baseline regression;
- optional structured judge call.

Acceptance:

- only latest rejected review converts, idempotently, to one `bad_case`; only latest accepted review converts through the separate path to one `reference_case`;
- case contains frozen context/output/finding/gate/review/config/expected behavior;
- dataset version is stable under request ordering and includes case type/hash;
- POST returns persisted queued run ID;
- direct runner tests prove one-worker sequential progress and per-case isolation;
- startup marks stale active runs interrupted without rerunning calls; multi-worker execution is documented and rejected as unsupported;
- deterministic pass does not change when judge fails or disagrees;
- regression comparison rejects mismatched dataset baselines;
- PostgreSQL constraints and migration parity pass.

## Milestone 7 — Evaluation UI and Langfuse evaluation projection

Implement:

- Bad Case/Reference Case/Evaluation index and run detail;
- score matrix, regression, tags, polling, cancel, and source links;
- case-type badges/filters and case-type regression summaries;
- best-effort Langfuse dataset-item/trace/score projection;
- sync status and external links when configured.

Acceptance:

- failed cases are inspectable from aggregate to original Finding;
- polling stops on every terminal state;
- deterministic, judge, and human signals are visually distinct;
- Langfuse identifiers map exactly as specified;
- Langfuse failures never remove local results;
- no Langfuse query is required to render Workspace evaluation pages.

## Milestone 8 — Gated prefilled Experiment draft and provenance

Implement:

- prefill endpoint and review/suggestion gate;
- origin query support in the existing creation page;
- editable normal JSON Forms creation flow;
- optional `suggestion_origin` on existing ExperimentCreate contract;
- transactional ExperimentProvenanceLink;
- origin display on Experiment detail.

Acceptance:

- pending/rejected Findings cannot fetch or submit a prefill;
- Accept/Needs Evidence with valid suggestion can open it;
- no Experiment exists until explicit user submit;
- user edits are preserved and validated by the exact template;
- created Experiment is draft, has normal parent lineage, and links to Finding/AnalysisRun/review;
- changed review or suggestion hash returns 409 with no Experiment/link;
- ordinary Experiment creation remains backward compatible.

## Milestone 9 — Deterministic demo data, documentation, and browser story

Implement:

- idempotent Phase 3 additions to PRJ-001;
- three clearly labelled Reference Findings/cases and three Bad Cases covering unsupported causality, invented Evidence, and a missed isolating control;
- final navigation polish and complete demo script;
- update PRODUCT_SPEC, ARCHITECTURE, DATA_MODEL, UI_SPEC, DEMO_SCENARIO, OPEN_SOURCE_STRATEGY, README, AGENTS, and notices.

Acceptance:

- seed twice produces exactly one set of Phase 3 fixtures;
- fixture dataset contains 3 Reference Cases and 3 Bad Cases with immutable review provenance;
- all AI fixture records are visibly synthetic/fixture-labelled;
- no unrelated Project or scientific dataset is created;
- complete offline fixture demo and configured live LiteLLM demo both work;
- refresh and service restart preserve all completed records;
- no Phase 1/2 guarantee or route regresses.

## Milestone 10 — PostgreSQL CI, full audit, and v0.1-demo handoff

Implement:

- `.github/workflows/phase-3-ci.yml` or a reviewed consolidation of existing workflows;
- populated Phase 2 upgrade job plus blank-head job;
- Phase 3 backend/frontend gates;
- final browser audit;
- `docs/handoff/PHASE_3_HANDOFF.md`.

Acceptance:

- PostgreSQL 17 blank migration, `0004` populated upgrade, parity, and seed twice pass;
- all Phase 1/2/3 backend tests run with asserted PostgreSQL dialect;
- CI uses FixtureProvider, Langfuse disabled, and no external credentials/network model calls;
- CI Evaluation smoke runs sequentially with one API process/worker and documents multi-worker as unsupported;
- frontend lint, format check, typecheck, tests, and production build pass;
- one manually triggered live LiteLLM analysis is validated outside CI with provider/model metadata recorded;
- optional Langfuse Cloud smoke passes when credentials are available; graceful-degradation smoke is mandatory regardless;
- final browser scenario passes at 1024/1280 px with no console/runtime errors;
- handoff contains exact commands/results and no pending PostgreSQL/browser claims;
- verdict is `PHASE 3 PASS`; only then create annotated tag `v0.1-demo`.

---

# 15. Test Plan

## Backend unit/service tests

- canonical JSON/hash and point sampling;
- factor diff for scalars, quantities, missing/null, keyed additives, ordinary arrays;
- context ownership/reference/drift/limit validation;
- prompt registry immutability and hashes;
- LiteLLM response/exception mapping;
- native-schema and JSON-object response handling, direct JSON decode, and rejection without repair/extraction;
- evidence role/ID/project validation;
- comparison and direct structured-support assertion recomputation;
- zero-curated-Evidence comparative support and causal non-upgrade;
- four Evidence Gate states and conservative causal cap;
- suggestion JSON Pointer application and template validation;
- ReviewDecision sequencing/supersession/reason rules;
- immutable Bad/Reference EvaluationCase snapshots, provenance, and hashes;
- case-type-aware deterministic metrics and optional judge separation;
- dataset version invariance under request ordering;
- evaluation progress, cancellation, per-case isolation, one-worker execution, and interrupted recovery;
- Langfuse disabled/success/failure adapter behavior;
- prefill review gate, stale review, normal validation, and provenance transaction.

## API tests

- every new endpoint success and 404/409/422/502/504 contract;
- failed analysis returns inspectable run ID and no partial Findings;
- list filtering excludes evaluation replay by default;
- bad-case conversion idempotency;
- evaluation 202/status/result polling;
- ordinary Experiment create payload remains valid without suggestion origin.

## Frontend tests

- typed parsing and error details;
- Analyse selection/revision-drift state;
- Finding/gate/confidence/review rendering;
- review form requirements and supersession conflict;
- Bad/Reference Case creation, filtering, and provenance badges;
- direct-support versus curated-evidence rendering;
- evaluation polling/terminal/error/case-type regression rendering;
- gated prefill visibility and editable submission;
- provider mode/capability, invalid-JSON, Langfuse, and judge unavailable states.

## PostgreSQL CI tests

Use PostgreSQL 17 service and two databases. CI and browser smoke launch exactly one API worker (`uvicorn ... --workers 1`); a multi-worker Evaluation runner is unsupported and is not presented as an acceptance path.

1. blank database: upgrade to head, parity, seed twice, full pytest;
2. upgrade database: migrate to `0004_literature_evidence`, load a bounded Phase 2 fixture, record canonical row/snapshot hashes, upgrade to head, assert every Phase 1/2 hash unchanged, then run Phase 3 tests.

Do not use downgrade/re-upgrade on the authoritative test database. Do not call live LiteLLM providers or Langfuse.

---

# 16. Implementation Notes (M1–M7)

The first implementation batch stopped after Milestone 4 as required. It is additive to the Phase
1/2 schema and keeps PostgreSQL as the source of truth.

- **M1:** Added `0005_scientific_analysis`, immutable AnalysisContextSnapshot/Finding/EvidenceLink/
  ReviewDecision records, typed request/response schemas, versioned prompts, model profiles, and
  the `AIProvider` boundary with deterministic FixtureProvider plus embedded LiteLLM dependency.
- **M2:** Added deterministic context construction for exact revisions, immutable template/schema
  hashes, Measurement/import provenance and bounded point samples, explicit 0–25 EvidenceRecords,
  Compare output, and name-addressable factor differences.
- **M3:** Added synchronous AnalysisRun orchestration, native-schema and JSON-object provider modes,
  direct JSON/Pydantic/scientific validation, diagnostic failure persistence, and optional Langfuse
  trace projection (disabled by default). No live provider call is used by tests.
- **M4:** Added Finding persistence, server-recomputed Direct Structured Support, curated Evidence
  links, conservative four-state Evidence Gate, causal confounding safeguards, and append-only
  human ReviewDecision endpoints. Suggested next experiments remain non-authoritative JSON only.
- **Verification:** `uv run ruff check app tests` and `uv run pytest -q` pass in the API. SQLite is
  used only for local fallback; PostgreSQL 17 blank/populated migration and full backend acceptance
  passed in GitHub Actions run `33584333549` on synchronized commit `086efc1` (corrective code was
  introduced in `0b5ffc4`).
- **Corrective audit:** provider-context limits now count sampled points, deterministic sampling
  preserves endpoints/full hashes, Langfuse uses the v4 observation API with opt-in content capture,
  run provenance is immutable after context building, capability preflight distinguishes native schema
  from JSON-object mode, and exactly one transient retry is recorded in run metadata.

## M5–M7 implementation record

- **M5:** Added typed frontend Analysis/Review routes, Compare → Analyse configuration, frozen
  context/provenance inspection, Finding cards with separate confidence/Gate/Direct Structured
  Support/Curated Evidence sections, and append-only Accept/Reject/Needs Evidence actions.
- **M6:** Added additive migration `0006_scientific_evaluation`, immutable Bad/Reference EvaluationCase
  snapshots, deterministic order-independent dataset hashes, persisted EvaluationRun/Result records,
  sequential one-process/one-worker execution, progress/cancel/interrupted handling, deterministic
  metric matrix, baseline compatibility checks, and isolated optional judge invocation.
- **M7:** Added Evaluation index/detail routes with case-type badges/filters, progress polling,
  deterministic versus judge score presentation, errors and replay/source links, plus best-effort
  Langfuse dataset/score projection that never gates local PostgreSQL results.
- **Verification:** API Ruff and pytest pass (31 tests), SQLite migration/parity reaches `0006`, and
  Web lint (inherited starter warnings only), format, typecheck, Vitest (6 tests), and production build
  pass. The local browser flow was exercised at 1024px and 1280px. GitHub Actions run
  `33587413638` passed the PostgreSQL 17 blank/populated migration, parity, seed idempotency, backend
  tests, frontend gates, and M5–M7 head commit `6162dc3`; parallel Phase 1 regression run
  `33587413676` also passed. Live provider/Langfuse calls were intentionally not required for that
  earlier batch.

## M8–M10 final implementation batch

- **M8:** Added the gated `GET /findings/{finding_id}/suggested-experiment-prefill` contract. Only a
  latest Accept/Needs Evidence review with a valid, hash-checked normalized suggestion can open the
  prefill. The existing creation form lets the scientist edit title, objective and structured values;
  submit is explicit and must remain `draft`. The server rechecks review, Finding/AnalysisRun,
  suggestion hash, exact immutable template version, project and parent identity, then atomically
  writes `ExperimentProvenanceLink` with suggestion and submitted-value snapshots. Stale inputs return
  `409`; ordinary creation remains unchanged. Experiment detail renders provenance read-only.
- **M9:** Extended the PRJ-001 seed with three deterministic fixture/synthetic/demo analysis runs,
  three accepted Reference Cases and three rejected Bad Cases (unsupported causality, invented Evidence
  ID regression, and missed isolating control). Source reviews/cases are immutable and idempotent;
  case tags visibly identify the demo set. Added deterministic metric checks for forbidden Evidence IDs
  and comparison/causality distinction.
- **M10:** Consolidated the PostgreSQL 17 workflow as `.github/workflows/phase-3-ci.yml`; it runs blank
  and populated Phase 2→head migrations, parity, seed twice with 3+3 case assertions, all backend
  tests, frontend lint/format/typecheck/tests/build, and the one-process/one-worker contract. The
  offline FixtureProvider/browser audit passed, and the final live LiteLLM Workspace smoke passed
  outside CI using DeepSeek `deepseek/deepseek-v4-flash` in `json_object` mode. The accepted run is
  `d864d74c-4ae6-416d-a17b-f6c018381a11`; the release handoff records its validation metadata and
  Evidence Gate result.
- **Live-provider compatibility correction:** `LiteLLMProvider` now disables DeepSeek V4 thinking
  for strict JSON requests and includes the Workspace JSON Schema plus conditional/reference
  orientation rules in the `json_object` system instruction. Direct JSON decoding, Pydantic and
  scientific-reference validation remain strict; no extraction, repair, or autonomous retry was
  introduced. Ruff and all 45 backend tests pass after this correction.

# 17. Final v0.1-demo Browser Scenario

1. Open PRJ-001 and Compare EXP-041, EXP-044, and EXP-045.
2. Inspect structured factor differences and compatible Measurement overlays.
3. Select exact revisions, relevant Literature, no curated EvidenceRecord, a model profile/mode, and prompt version.
4. Run Scientific Analysis and open its frozen context/provenance.
5. Inspect a comparative Finding whose higher frozen `y_mean` is `supported` by Direct Structured Support alone.
6. Inspect the starch-specific causal Finding: changed factors include KI and starch; gate is `insufficient_evidence`; direct comparative support does not upgrade causality; missing control is explicit.
7. Review that Finding as `Needs Evidence` and complete the gated prefilled draft flow.
8. Review an accepted comparative Finding and create a Reference Case through the controlled path.
9. Open another synthetic unsupported Finding, Reject it with `unsupported_causal_claim`, and create a Bad Case with expected behavior.
10. Open Evaluations, verify the mixed Reference/Bad dataset, run it with another allowed model profile or prompt version, and observe sequential queued/running progress from the single worker.
11. Inspect deterministic direct-support/citation/causal metrics, optional judge scores, case-type regression, tags, and links back to Finding/context.
12. With Langfuse enabled, follow the trace link and confirm matching AnalysisRun/Evaluation identifiers; with Langfuse disabled/unavailable, repeat core inspection entirely in Workspace.
13. Refresh and restart API/Web; confirm completed analyses, reviews, cases, evaluations, and draft provenance remain; verify active evaluation is marked `interrupted` rather than resumed.

The scenario must not require terminal edits, manual database changes, a mock HTTP API, or hidden retries.

---

# 18. Explicitly Deferred

- LangGraph and multi-agent personas;
- autonomous research/tool loops;
- LiteLLM Gateway/Proxy service;
- durable evaluation queue/workers and automatic restart resume;
- mandatory LLM-as-judge release gates;
- semantic search, embeddings, pgvector, generic RAG;
- MCP server/client integration;
- external web/literature retrieval;
- automatic Evidence or Literature creation by AI;
- automatic Experiment creation or direct mutation;
- general-purpose causal inference, statistical significance, or regulatory claims;
- arbitrary scientific ontologies and universal factor parsers;
- auth/RBAC/electronic signatures;
- production self-hosted Langfuse infrastructure;
- automated prompt promotion or self-improving loops.

Any future inclusion requires a separately reviewed plan.

---

# 19. Documentation and Handoff Deliverables

During implementation, update:

- `ARCHITECTURE.md` — actual AI/provider/orchestration/Langfuse boundaries;
- `docs/DATA_MODEL.md` — canonical Phase 2 actual model plus Phase 3 entities/invariants;
- `docs/PRODUCT_SPEC.md` — final v0.1 behavior and human authority;
- `docs/UI_SPEC.md` — Analysis/Review/Evaluation/prefill surfaces;
- `docs/DEMO_SCENARIO.md` — complete three-phase script;
- `docs/OPEN_SOURCE_STRATEGY.md` and notices — LiteLLM/Langfuse versions/licenses;
- `README.md` and `AGENTS.md` — active Phase 3 commands/status;
- this plan's Implementation Notes after every milestone;
- `docs/handoff/PHASE_3_HANDOFF.md` after the complete audit only.

The handoff must record migrations, model/profile/prompt versions, CI runs, browser evidence, live-provider smoke, Langfuse state, deferred scope, and the exact `v0.1-demo` tag commit.

---

# 20. Planning Review Outcome

**Recommended Phase 3 architecture:** FastAPI services + PostgreSQL scientific source of truth + embedded LiteLLM SDK behind a small internal provider interface + deterministic Evidence Gate + append-only human review + local Evaluation domain + optional Langfuse Cloud projection.

**LangGraph:** not selected.

**Langfuse:** selected as optional Cloud trace/dataset/score projection; disabled-by-default and never authoritative.

**RAG / pgvector:** deferred.

**Highest implementation risks:** frozen-context correctness and size bounds; distinguishing direct comparative support from causal support; provider variability in `json_object` mode; quality drift in approved Reference Cases; atomic Finding/gate persistence after provider failures; single-worker Evaluation misdeployment and interruption semantics; ensuring optional Langfuse never becomes a hidden dependency; preserving user authority in the prefilled draft flow.

**Execution verdict:** COMPLETE — `PHASE 3 PASS`. The human-review amendments were implemented and
all documented P0 acceptance criteria, including the external live-provider gate, passed. The
annotated `v0.1-demo` release tag is created only on the accepted closeout commit.
