# Execution Plan 01 — Foundation + ELN Core

**Status:** ACTIVE  
**Release target:** `phase-1-foundation`  
**Goal:** 做出第一个真实持久化、可演示的科研工作台纵向切片。  
**Do not implement:** Phase 2 Measurement/Compare/Literature 或 Phase 3 AI/Eval。

---

# 0. Definition of Done

Plan 1 完成时，必须能：

1. 启动 PostgreSQL、API、Web。
2. 打开 Overview。
3. 打开 seed Project。
4. 打开 seed Experiment。
5. 编辑 structured properties 并保存。
6. 编辑 BlockNote record 并保存。
7. 上传、下载、删除附件。
8. 创建 revision。
9. 查看 revision 的只读 snapshot。
10. clone Experiment。
11. 修改 clone 参数。
12. 刷新浏览器，数据仍存在。
13. 关闭并重启服务，数据仍存在。
14. 自动化测试、lint、typecheck 通过。
15. 有明确 README 启动说明。
16. 产出 Phase 1 handoff。

如果只有 UI mock，不算完成。

---

# 1. Non-negotiable Architecture

- `web/`：Next.js。
- `api/`：FastAPI。
- PostgreSQL 是 authoritative data store。
- `web` 不直接访问 DB。
- BlockNote JSON 与 structured_data 分开。
- JSON Forms 是结构化字段表单引擎。
- Attachment binary 通过 storage adapter。
- Database schema 通过 migration。
- Revision 是 immutable snapshot。
- Clone 创建新 Experiment。

---

# 2. Milestone 1 — Repository Bootstrap

## Objective

从空仓库建立可运行 monorepo，同时保留本 planning pack。

## Tasks

### 1.1 Inspect current directory

确认：
- 当前是否只有 planning docs。
- 是否已 git init。
- 是否有用户代码，不得覆盖。

如果存在已有实现，先适配，不重置。

### 1.2 Initialise Git

如果未初始化：

```bash
git init
```

创建合理 `.gitignore`。

### 1.3 Import dashboard starter into `web/`

使用当前稳定的 Kiranism starter snapshot。

不要建立 nested git repo。

建议流程：

```text
clone upstream into temp
copy working tree to web/
remove temp .git
retain license attribution
```

先阅读 upstream README 和 AGENTS.md。

运行 upstream cleanup 工具的 `--list` 或等价命令，确认当前可删除 feature。

删除明确无关内容：
- chat
- kanban
- billing
- marketing/demo fluff
- sentry（如果它造成额外 setup）
- mandatory hosted auth（如果会阻塞 local demo）

保留：
- shell
- sidebar
- table patterns
- shadcn
- query/client patterns
- basic theme

不得为了 cleanup 把 starter 的工程结构破坏到无法升级依赖或运行。

### 1.4 Create backend skeleton

`api/`：

- pyproject
- FastAPI app
- Pydantic settings
- SQLAlchemy
- Alembic
- pytest
- CORS local config
- `/api/v1/health`

推荐使用 `uv` 管理 Python 环境。如果本机没有 uv 且 Agent 不能安全安装，可使用标准 venv/pip，但必须记录。

### 1.5 Docker Compose

只需要 PostgreSQL P0。

健康检查。

Volume 持久化。

### 1.6 Root developer commands

提供 README 或 scripts，使开发者知道：

- start postgres
- run migrations
- seed
- start API
- start Web
- run tests

不要为了「一条命令启动一切」在本 milestone 花大量时间。

## Acceptance

- [ ] `web` 可以启动。
- [ ] `api` 可以启动。
- [ ] PostgreSQL 可以启动。
- [ ] `/api/v1/health` 返回 healthy。
- [ ] Web 能调用 health API 或至少开发环境 CORS 已验证。
- [ ] 上游许可证已保存。
- [ ] 无 nested `.git`。
- [ ] planning docs 未丢失。

## Verification

Agent 根据实际 package scripts 填写并运行：

```bash
docker compose up -d postgres
cd api && <migration/test commands>
cd web && <lint/typecheck/build commands>
```

更新 `AGENTS.md` 中真实命令。

---

# 3. Milestone 2 — Canonical Database + API Foundation

## Objective

建立 Phase 1 domain model 和 migration。

## Tables

实现：

- projects
- experiment_templates
- experiments
- attachments
- experiment_revisions

严格参考 `docs/DATA_MODEL.md`。

## Tasks

### 2.1 DB base

- SQLAlchemy base
- session lifecycle
- UUID strategy
- timestamps

### 2.2 Models

Project、ExperimentTemplate、Experiment、Attachment、ExperimentRevision。

### 2.3 Migration

创建 initial migration。

从空 DB 可升级到 head。

### 2.4 API schemas

Pydantic request/response schemas。

避免直接把 ORM model 当 API schema。

### 2.5 Project API

P0：
- list
- create
- get
- patch

### 2.6 Experiment Template API

P0：
- list
- get

Phase 1 不需要 template designer UI。

### 2.7 Experiment API

P0：
- list by project
- create
- get
- patch

structured_data 保存必须 validate against template JSON Schema。

可以使用成熟 Python JSON Schema validator。

不要复制 JSON Forms 前端验证逻辑作为唯一验证。

## Acceptance

- [ ] migration from blank DB succeeds。
- [ ] project CRUD P0 works。
- [ ] experiment create/get/update works。
- [ ] invalid structured_data 返回 4xx 可解释错误。
- [ ] template version 写入 experiment。
- [ ] API tests cover happy path + validation failure。
- [ ] OpenAPI schema 可访问。

---

# 4. Milestone 3 — Demo Seed Data

## Objective

从此之后 UI 不使用 lorem ipsum 或临时 mock。

## Tasks

创建 idempotent seed command。

Seed：

- `PRJ-001`
- `materials-formulation-v1`
- EXP-041
- EXP-044
- EXP-045

parent lineage：

```text
EXP-041
  ↓
EXP-044
  ↓
EXP-045
```

所有 scientific names 使用 anonymised/demo wording。

note_document 可以生成兼容 BlockNote 的基础内容。如果此时尚未确认 BlockNote JSON 格式，可先在 Milestone 6 补充 note seed，不要手写猜测格式。

## Acceptance

- [ ] seed 可重复执行，不产生重复实体。
- [ ] project/experiments 可通过 API 查询。
- [ ] parent relationship 正确。
- [ ] README 有 seed 命令。

---

# 5. Milestone 4 — Workspace Navigation + Project UX

## Objective

把 starter 改造成 Scientific R&D Workspace。

## Tasks

### 4.1 Branding

去掉明显 starter demo 品牌。

文本：
`Scientific R&D Workspace`

不要花时间设计 logo。

### 4.2 Sidebar

Phase 1：
- Overview
- Projects
- Experiments

隐藏未实现 Phase 2/3 导航。

### 4.3 API client

建立单一 typed API client pattern。

前端不得散落 `fetch()`。

如果 starter 已有 query pattern，沿用。

### 4.4 Overview

真实 API 数据：
- active project count
- experiment count
- recent experiments

如果为这三个数字增加专用 aggregate endpoint 太早，可以用已有 list 数据计算；避免过度 API 设计。

### 4.5 Project List

真实 Projects API。

### 4.6 Project Detail

展示 Project metadata + experiments table。

### 4.7 Create/Edit Project

使用现有 starter form pattern。

## Acceptance

- [ ] UI 无 mock project data。
- [ ] create project 后列表立即更新。
- [ ] project detail 可打开。
- [ ] experiments list 真实。
- [ ] loading/error/empty states 存在。
- [ ] desktop browser smoke test 通过。

---

# 6. Milestone 5 — Experiment CRUD + Detail Shell

## Objective

建立核心 Experiment 页面，不先接编辑器。

## Tasks

### 5.1 Experiment create

创建时选择：
- project
- template
- title

默认：
- draft
- empty structured_data
- valid empty/default note_document

### 5.2 Detail page

Tabs：
- Overview
- Record
- Files
- Revisions

### 5.3 Header

展示：
- code
- title
- status
- project
- parent link
- Clone button

### 5.4 Base editing

Overview 先支持 title、status、objective。

## Acceptance

- [ ] new experiment created and persisted。
- [ ] detail loads after refresh。
- [ ] parent link visible when present。
- [ ] no editor-specific mock required。

---

# 7. Milestone 6 — JSON Forms Structured Properties

## Objective

用 schema-driven form 实现 Experiment structured properties。

## Required dependencies

优先：
- `@jsonforms/core`
- `@jsonforms/react`
- 官方 renderer package

先验证当前 JSON Forms 与 React 19/Next.js compatibility。

如存在兼容问题：
1. 查官方 issue/docs。
2. 做最小依赖版本选择。
3. 不自行重写 form engine。

## Tasks

### 6.1 Load schema

Experiment detail 同时获得：
- experiment
- template schema
- ui schema

### 6.2 Render

Overview tab 中展示 structured form。

### 6.3 Hydrate

已有 structured_data 能正确进入表单。

### 6.4 Save

P0 推荐 explicit `Save changes`，避免一开始做复杂 autosave。

如果 starter 现有 mutation pattern 很成熟，可以实现 debounce autosave，但不得降低可靠性。

### 6.5 Validation

前端显示 JSON Forms validation。

后端再次 authoritative validate。

### 6.6 Quantity

至少验证：
- concentration value + unit
- drying temperature value + unit
- drying time value + unit
- additives array

### 6.7 Styling

只做 container、spacing、typography 最低视觉统一。

不要在此 milestone 写一整套 shadcn renderer。

## Acceptance

- [ ] schema drives fields。
- [ ] no material-specific hard-coded field JSX。
- [ ] data loads correctly。
- [ ] save persists。
- [ ] invalid data cannot become authoritative DB state。
- [ ] value/unit separate。
- [ ] additive list works。
- [ ] refresh retains data。

## Test Cases

1. EXP-045 loads all seed fields。
2. change drying temperature 60 → 65 and save。
3. refresh → 65。
4. invalid enum unit → rejected。
5. add/remove additive row。

---

# 8. Milestone 7 — BlockNote Rich Experiment Record

## Objective

将 rich note 交给成熟 block editor。

## Guardrails

- 使用非 XL BlockNote packages。
- 不修改 BlockNote 上游源码。
- 保存 BlockNote 原生 JSON。
- 不做 collaborative editing。
- 不做 comments。
- 不做 AI slash command。

## Tasks

### 7.1 Confirm package/version

查当前官方 docs 和 peer dependencies。

### 7.2 Client component boundary

Next.js 中正确处理 browser-only editor。

避免 SSR hydration error。

### 7.3 Load initial document

Experiment `note_document` → BlockNote。

### 7.4 Save

P0 explicit save。

可以提供 dirty indicator。

### 7.5 Default new experiment note

新 Experiment 默认文档包含：
- Objective
- Procedure
- Observation
- Discussion

必须通过 BlockNote API 生成/序列化，不手写不确定格式。

### 7.6 Read-only mode

为 Revision viewer 准备只读渲染能力。

## Acceptance

- [ ] editor loads without hydration error。
- [ ] rich note persists after refresh。
- [ ] headings/lists/basic formatting survive round trip。
- [ ] default sections appear for new experiment。
- [ ] no XL packages in dependency tree because of direct import。
- [ ] tests or browser verification cover persistence。

---

# 9. Milestone 8 — Attachments

## Objective

实现真实 binary upload。

## Backend

### 8.1 StorageAdapter

Interface：

```text
put
get/open
delete
exists
```

实现：
`LocalStorageAdapter`

### 8.2 Upload endpoint

约束：
- 25 MB default max
- sanitised filename
- server-generated storage key
- sha256
- MIME best effort

### 8.3 Download

通过 attachment ID。

禁止客户端自己拼 storage path。

### 8.4 Delete

DB metadata 与 file 保持一致。

如 file delete 成功而 DB delete 失败或反之，需要可诊断处理。

Phase 1 不要求分布式 transaction，但不能静默。

## Frontend

Files tab：
- upload
- progress 或明确 loading state
- list
- download
- delete confirmation

## Security Basics

- 禁止 `../` path traversal。
- storage key 不直接使用原始 filename。
- 不执行上传文件。
- download 使用 safe content disposition。

## Acceptance

- [ ] upload persists。
- [ ] download bytes match。
- [ ] delete works。
- [ ] duplicate filenames 不冲突。
- [ ] path traversal filename 被处理。
- [ ] oversized file rejected。
- [ ] API tests cover upload/download。

---

# 10. Milestone 9 — Clone Experiment

## Objective

把「从上一轮实验继续」做成一等工作流。

## Backend

`POST /experiments/{id}/clone`

Request：
- new_title
- optional target_project_id（P0 默认同 project，可不暴露）
- copy_note bool default true
- copy_structured_data bool default true

Phase 1 attachments 不复制。

Rules：
- source 不修改
- new UUID/code
- parent_experiment_id = source
- new revision history
- created status default draft

## Frontend

Clone dialog 参考 `docs/UI_SPEC.md`。

成功后进入 clone detail。

## Acceptance

- [ ] clone has distinct ID/code。
- [ ] source unchanged。
- [ ] parent relationship correct。
- [ ] structured data copied。
- [ ] note copied。
- [ ] attachment binary not copied。
- [ ] revisions not copied。
- [ ] user edits clone do not affect source。

---

# 11. Milestone 10 — Revision History

## Objective

实现可解释的 experiment snapshot。

## Backend

### Create revision

`POST /experiments/{id}/revisions`

Request：
- change_note optional

Server:
1. load current experiment。
2. load attachment metadata。
3. calculate next revision number transactionally。
4. create snapshot。
5. immutable insert。

### Read revisions

list + detail。

不提供 PATCH revision。

## Frontend

Revisions tab：
- list
- create revision
- detail drawer/page
- read-only structured properties
- read-only rich note
- attachment metadata list

P0 不提供一键 restore。

## Acceptance

- [ ] revision 1,2,3 monotonic。
- [ ] old snapshot remains unchanged after experiment edit。
- [ ] clone does not inherit revision rows。
- [ ] revision viewer read-only。
- [ ] concurrency至少通过 DB unique constraint 防重复 revision number；如果需要 retry，做小范围处理。

---

# 12. Milestone 11 — End-to-End Demo + Hardening

## Objective

把各功能从「分别能用」变成一条可靠用户路径。

## Tasks

### 11.1 Run full demo scenario

严格按 `docs/DEMO_SCENARIO.md`。

### 11.2 Persistence test

- restart API
- restart Web
- restart Postgres container while preserving volume

确认数据仍存在。

### 11.3 Error states

人为测试：
- API offline
- invalid form
- upload too large
- missing experiment ID

### 11.4 Automated quality

必须找到并运行真实 commands：
- frontend lint
- frontend typecheck
- frontend tests
- frontend production build
- backend pytest
- migration check

### 11.5 Browser verification

至少 desktop：
- Overview
- Project
- Experiment
- clone
- revision
- attachment

检查 browser console，无明显 uncaught runtime error。

### 11.6 README

更新 root README：
- prerequisites
- setup
- env
- DB start
- migration
- seed
- API start
- web start
- tests
- demo route

### 11.7 Handoff

复制：
`docs/handoff/PHASE_HANDOFF_TEMPLATE.md`

生成：
`docs/handoff/PHASE_1_HANDOFF.md`

内容必须基于真实实现，不照抄计划。

## P0 Acceptance Checklist

- [ ] Complete demo flow passes.
- [ ] No mock API in core path.
- [ ] No Phase 2/3 feature accidentally introduced.
- [ ] Lint passes.
- [ ] Typecheck passes.
- [ ] Backend tests pass.
- [ ] Frontend test/build passes.
- [ ] Browser smoke passes.
- [ ] DB migration from empty DB verified.
- [ ] Seed verified.
- [ ] Third-party notices present.
- [ ] Handoff written.

---

# 13. Explicitly Deferred

如果在实现中想到这些，写入 tech debt / Phase 2 notes，不实现：

- Measurement
- CSV/XLSX import
- chart
- batch compare
- Zotero
- literature search
- embedding
- pgvector
- AI
- LangGraph
- Langfuse
- MCP
- permissions
- collaboration
- S3
- MinIO
- background jobs
- notifications
- instrument parsing
- instrument control

---

# 14. Implementation Notes

执行 Agent 每完成 milestone 后在本节追加：

```text
## Mx completed — YYYY-MM-DD

Implemented:
- ...

Actual commands:
- ...

Deviation from plan:
- none / ...

Follow-up:
- ...
```

不要删除历史 notes。

## M1 completed — 2026-09-01

Implemented:
- Bootstrapped the Kiranism Next.js 16 starter under `web/`, removed starter auth/demo routes from the active shell, and added project-specific metadata/navigation.
- Added root ignore rules and retained third-party attribution notices.

Actual commands:
- `git init`
- `cd web && npm install`
- `cd web && npm run typecheck`
- `cd web && npm run lint`

Deviation from plan:
- npm is used because Bun is not installed in the execution environment.

Follow-up:
- The remaining starter UI primitives are intentionally retained as shell dependencies; the active navigation exposes only Scientific R&D routes.

## M2 completed — 2026-09-01

Implemented:
- Added SQLAlchemy models for projects, templates, experiments, attachments, and immutable revisions.
- Added Alembic migration `0001_phase1_foundation.py`, PostgreSQL 17 Compose configuration, Pydantic settings, and local file storage adapter.

Actual commands:
- `cd api && uv lock && uv sync`
- `cd api && uv run python -m compileall -q app`

Deviation from plan:
- Blank PostgreSQL migration execution is pending because Docker/PostgreSQL binaries are unavailable in this environment.

Follow-up:
- Run `docker compose up -d postgres && uv run alembic upgrade head` before the first shared/demo run.

## M3 completed — 2026-09-01

Implemented:
- Added typed FastAPI endpoints for projects, templates, experiments, cloning, revisions, and attachments.
- Added JSON Schema validation with recursive unknown-field rejection and explicit error responses.

Actual commands:
- `cd api && uv run pytest`
- Result: 5 passed (one upstream Starlette/httpx deprecation warning).

Deviation from plan:
- No deviation.

Follow-up:
- Validate the migration and endpoints against PostgreSQL 17 in a Docker-enabled environment.

## M4 completed — 2026-09-01

Implemented:
- Added overview and projects list/detail pages with search, status filtering, create/edit forms, loading/empty/error states, and experiment counts.

Actual commands:
- `cd web && npm run typecheck && npm run lint`

Deviation from plan:
- No deviation.

Follow-up:
- No Phase 1 follow-up beyond browser verification with a live API.

## M5 completed — 2026-09-01

Implemented:
- Added experiment creation, global experiment list, experiment detail route, editable metadata, status, objective, and template selection.

Actual commands:
- `cd web && npm run build`

Deviation from plan:
- No deviation.

Follow-up:
- No Phase 2 workflow features were added.

## M6 completed — 2026-09-01

Implemented:
- Added JSON Forms 3.8 renderer integration for template-driven structured properties, with a small application wrapper style layer and explicit save action.

Actual commands:
- `cd web && npm run typecheck && npm run build`

Deviation from plan:
- No deviation.

Follow-up:
- Keep template schemas server-owned; do not move scientific validation into the web client.

## M7 completed — 2026-09-01

Implemented:
- Added BlockNote 0.54 ShadCN editor integration for separate `note_document` storage, explicit save, and read-only revision rendering.

Actual commands:
- `cd web && npm run build`

Deviation from plan:
- Google-hosted fonts were removed from the starter font config so production builds remain deterministic/offline-friendly; the theme keeps its Geist/system fallback stack.

Follow-up:
- No BlockNote XL packages are used.

## M8 completed — 2026-09-01

Implemented:
- Added local attachment upload/list/download/delete endpoints, safe filename/key handling, SHA-256 metadata, 25 MB limit, and Files tab UI.
- Added storage path traversal tests.

Actual commands:
- `cd api && uv run pytest`
- Result: 5 passed.

Deviation from plan:
- No deviation.

Follow-up:
- Production object storage is intentionally deferred.

## M9 completed — 2026-09-01

Implemented:
- Added clone action with new experiment identity, parent lineage, copied note/structured data, draft status, and initial clone revision.

Actual commands:
- `cd api && uv run pytest`
- Clone/revision independence is covered by `test_clone_and_revision_are_independent`.

Deviation from plan:
- No deviation.

Follow-up:
- No batch clone or comparison behavior was added.

## M10 completed — 2026-09-01

Implemented:
- Added immutable revision create/list/detail endpoints and a revision viewer showing read-only structured snapshot JSON and note content.

Actual commands:
- `cd api && uv run pytest`
- `cd web && npm run test`

Deviation from plan:
- No one-click restore was added, as required by the Phase 1 boundary.

Follow-up:
- PostgreSQL concurrency behavior should be exercised after Docker is available.

## M11 completed — 2026-09-01

Implemented:
- Added frontend Vitest/jsdom harness and API-client tests.
- Added root README setup/env/migration/seed/test/demo instructions and Phase 1 handoff artifact.
- Removed starter product/user API and dashboard routes from the built route surface.

Actual commands:
- `cd web && npm run test` — 2 passed.
- `cd web && npm run lint` — pass with inherited starter warnings.
- `cd web && npm run typecheck` — pass.
- `cd web && npm run build` — pass.
- `cd api && uv run pytest` — 5 passed, including the API-level Phase 1 demo flow.
- `cd api && uv run python -m compileall -q app` — pass.
- Seed idempotency check against a temporary SQLite database — passed twice without duplicate records.
- Browser smoke against `http://localhost:3000/dashboard/overview`, `/dashboard/projects`, and `/dashboard/experiments` — pages rendered with meaningful content, no error overlay, and no console errors on a clean load; API-offline error state was visible as expected.

Deviation from plan:
- `docker compose config` could not run (`docker` is not installed), so blank-DB migration, PostgreSQL seed, persistence-restart, and the full live-API demo remain environment-pending.

Follow-up:
- Run the documented Compose/API startup path in a Docker-enabled environment and repeat the complete `docs/DEMO_SCENARIO.md` flow.
