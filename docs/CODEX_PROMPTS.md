# Codex Prompts

这些 prompt 是操作模板。用户可按自己 Codex 客户端中可用的模型选择 planner/reviewer 和 executor。

如果客户端中有你习惯称为「Sol Max」和「Luna Max」的配置，可以：
- 高推理 planner/reviewer：用于 Preflight、阶段审计、下一阶段详细规划。
- executor：用于按照 bounded milestone 实现。

不要让第二个模型重新发明已经确定的产品方向。

---

# Prompt A — Phase 1 Preflight / Plan Review

用途：
第一次开工前，可选但推荐。

```text
You are the repository-aware planner and reviewer for this project.

Read, in this order:
1. AGENTS.md
2. docs/PRODUCT_SPEC.md
3. ARCHITECTURE.md
4. docs/DATA_MODEL.md
5. docs/UI_SPEC.md
6. docs/OPEN_SOURCE_STRATEGY.md
7. docs/exec-plans/01-foundation-eln.md

Then inspect the actual repository state and, where internet/tool access is available, verify the current upstream starter and the third-party packages that Phase 1 depends on.

Your job is NOT to redesign the product and NOT to implement the application.

Your job is to make Execution Plan 01 executable against the real repository and current dependencies.

Rules:
- Preserve the product decisions and Phase 1 scope.
- Do not add AI, LangGraph, Langfuse, MCP, pgvector, Zotero, Measurement, Compare, or other Phase 2/3 features.
- Do not replace the selected stack unless there is a concrete compatibility, licensing, or maintenance blocker.
- If an upstream command/API/version in the plan is stale, correct the execution detail with the smallest possible change.
- Check license constraints, especially the dashboard starter, JSON Forms, and BlockNote packages.
- Check whether the dashboard starter cleanup commands/features have changed.
- Check React/Next compatibility of JSON Forms and BlockNote.
- Check that the proposed backend and database workflow can be run locally.

Update only planning/documentation files where necessary.
Do not write product code.

At the end, provide:
1. PRE-FLIGHT STATUS: READY or BLOCKED
2. Changes made to the plan
3. Concrete blockers, if any
4. The exact first implementation milestone the executor should start with
```

---

# Prompt B — Execute Phase 1

这是核心 prompt，可以直接给执行模型。

```text
Implement Phase 1 of this repository.

Start by reading AGENTS.md and every source-of-truth document it points to for the active phase. The active execution plan is:

docs/exec-plans/01-foundation-eln.md

Work milestone by milestone, in order.

For each milestone:
1. Inspect the current repository state before editing.
2. Reuse existing upstream/starter patterns instead of inventing parallel systems.
3. Implement only that milestone's scope.
4. Run the relevant formatter, lint, typecheck, tests, migrations, build, and browser smoke checks.
5. Fix failures before moving on.
6. Append a factual implementation note to the plan.
7. Keep the repository runnable.

Do not stop just because a normal build, dependency, test, or UI issue occurs. Diagnose and resolve it.

Stop and ask for human input only for the blockers explicitly allowed by AGENTS.md.

Important:
- Do not implement Phase 2 or Phase 3.
- Do not add AI, RAG, LangGraph, Langfuse, MCP, pgvector, Zotero, Measurement, or Compare.
- Do not rewrite BlockNote or JSON Forms.
- Do not silently change the canonical data model.
- Do not directly connect the web app to PostgreSQL.
- Preserve third-party licensing/attribution.

When all milestones are complete:
1. Run the full Phase 1 demo scenario in docs/DEMO_SCENARIO.md.
2. Run all P0 validation checks.
3. Write docs/handoff/PHASE_1_HANDOFF.md using the template.
4. Report what is complete, what commands were run, any remaining non-blocking debt, and whether Phase 1 is ready for planning Phase 2.
```

---

# Prompt C — Execute Only One Milestone

如果一次跑完整 Plan 不稳定，推荐使用这个。

替换 `<MILESTONE>`。

```text
Read AGENTS.md and docs/exec-plans/01-foundation-eln.md.

Implement only <MILESTONE>.

Do not begin the next milestone.

Before editing, inspect the current repository and all files affected by this milestone.

After implementation:
- run all relevant verification,
- fix failures,
- perform a browser smoke test if UI changed,
- append a factual implementation note to the active plan,
- leave the repository runnable.

Do not expand scope and do not implement Phase 2/3 functionality.

When finished, report:
1. files changed,
2. key decisions,
3. verification commands and results,
4. any deviation from the plan,
5. whether the next milestone is unblocked.
```

---

# Prompt D — Phase 1 Completion Audit

Phase 1 执行完后，用高推理 reviewer。

```text
Audit the completed Phase 1 implementation.

Read:
- AGENTS.md
- docs/PRODUCT_SPEC.md
- ARCHITECTURE.md
- docs/DATA_MODEL.md
- docs/UI_SPEC.md
- docs/DEMO_SCENARIO.md
- docs/exec-plans/01-foundation-eln.md
- docs/handoff/PHASE_1_HANDOFF.md

Then inspect the actual implementation.

Do not redesign the product and do not begin Phase 2.

Verify:
- every P0 acceptance criterion,
- migration from a blank database,
- seed idempotency,
- project and experiment persistence,
- JSON Forms structured property round-trip,
- BlockNote document round-trip,
- attachment safety and persistence,
- clone semantics,
- revision immutability,
- frontend lint/typecheck/build/tests,
- backend tests,
- browser console/runtime behaviour,
- source-of-truth documentation matches actual code,
- third-party license notices.

Fix small Phase 1 defects if necessary.
For larger issues, record them precisely in the handoff.

Return one verdict:
PHASE 1 PASS
or
PHASE 1 NOT READY

Do not create a detailed Phase 2 plan unless Phase 1 passes.
```

---

# Prompt E — Generate Detailed Plan 2

只有 Phase 1 PASS 后使用。

```text
Create the detailed Execution Plan 02 for this repository.

Read:
- AGENTS.md
- docs/PRODUCT_SPEC.md
- ARCHITECTURE.md
- docs/DATA_MODEL.md
- docs/exec-plans/02-scientific-workflow-scope.md
- docs/handoff/PHASE_1_HANDOFF.md

Inspect the real codebase thoroughly.

Use the Phase 2 scope as the product boundary, but derive implementation details from the actual Phase 1 architecture.

Do not implement code.

The new plan must:
- be milestone-based,
- preserve a runnable product after every milestone,
- define exact domain/schema changes,
- define API contracts,
- define UI flows,
- define import failure behaviour,
- define provenance semantics,
- include tests and browser validation,
- include explicit deferred scope,
- include migration and backwards-compatibility considerations,
- avoid redesigning Phase 1 unless required.

Write:
docs/exec-plans/02-scientific-workflow.md

Keep the existing scope file as historical product intent.
```

---

# Prompt F — Recovery After a Bad Agent Run

```text
Do not continue implementing new features.

Inspect git diff, git status, the active execution plan, and the last known completed milestone.

Determine:
1. which changes belong to the active milestone,
2. which changes are accidental scope expansion,
3. which tests currently fail,
4. whether canonical schema or architecture was changed without documentation.

Restore the repository to a coherent, runnable state without discarding valid completed work.

Remove or revert only unsupported scope expansion.

Then run the milestone's verification suite and update the implementation notes with the recovered state.

Do not start the next milestone.
```

---

# Recommended Operating Mode

最快但仍稳定：

```text
Preflight once
↓
Executor runs M1
↓
Executor runs M2
↓
...
↓
Executor runs M11
↓
Completion Audit
↓
Plan 2 generation
```

如果 executor 能稳定长时间工作，也可以直接使用 Prompt B；但出现一次明显偏航后，改成 Prompt C 的单 milestone 模式。
