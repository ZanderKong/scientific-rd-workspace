# Scientific R&D Workspace

Scientific R&D Workspace 是一个面向实验研发的结构化科研工作台，用于记录样品制备、组织实验比较、管理科研数据与执行过程，并通过 REST API 和 MCP 与外部智能体安全协作。

## 核心能力

- **Sample Record**：以 Sample 为核心记录多步骤 Process，关联 Material、Equipment 与前驱样品，并保留完整 provenance 与 lineage。
- **Experiment Comparison**：将已有 Sample 以非拥有关系加入多个 Experiment，确定性比较过程参数、资源使用与结构差异，并叠加兼容的 XY 数据。
- **Scientific Data**：支持 `scalar`、`xy_series`、`table` 与 `file` 四类数据载荷，保留来源附件、校验和与导入映射。
- **Planned / As-run Execution**：实验开始时冻结计划快照，后续记录实际执行值、偏差与观察，计划值保持不可变。
- **Safe External Agents**：通过 Domain REST API 与 MCP 暴露科研语义级能力；修改已有科研记录默认进入 ChangeSet 审核流程。
- **Traceability & Safety**：PostgreSQL 负责语义约束、事务、revision、幂等与并发控制，避免客户端直接拼装或覆盖科研事实。

## 架构

```text
Next.js UI ───────────┐
Domain REST API ──────┼──> FastAPI Domain Services ───> PostgreSQL 17
MCP clients ──────────┘              │
                                     ├── Revisions / Provenance
                                     ├── Typed Data / Attachments
                                     └── ChangeSet / Concurrency / Idempotency
```

Web UI、REST API 与 MCP 共用同一套 domain services。MCP 只负责外部客户端适配，不维护第二套科研业务逻辑，也不内嵌模型运行时。

## 核心模型

系统包含七类 canonical research object：

```text
Project
Experiment
Sample
Process
Material
Equipment
Data
```

主要关系：

```text
contains    Experiment 对 Process / Sample / Data 的单一 ownership
includes    Experiment 对 Sample 的非拥有、多对多 membership
uses        Process 使用 Material / Equipment / Sample / Data
produces    Process 产出 Sample / Data
precedes    Process 的执行顺序
related_to  弱关联，不承担 canonical provenance
```

其中 `precursor` 负责 Sample lineage，`subject` 负责推导当前 Data。

## 技术栈

- **Backend**：FastAPI、SQLAlchemy、Alembic、PostgreSQL 17
- **Frontend**：Next.js、React、TypeScript
- **Agent Integration**：MCP stdio、Streamable HTTP、Domain REST API
- **Quality**：Pytest、Vitest、Playwright、GitHub Actions

## 本地运行

要求：Node.js 22、`uv`、Docker Compose。

```bash
docker compose up -d postgres

cd api
uv sync --frozen
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:app --reload --port 8000
```

另开终端：

```bash
cd web
npm ci
npm run dev
```

打开：

```text
http://localhost:3000/dashboard/samples
```

## 验证

```bash
cd api
uv run ruff check app tests alembic/versions
uv run ruff format --check app tests alembic/versions
uv run pytest -q

cd ../web
npm run lint
npm run format:check
npm run typecheck
npm test -- --run
npm run build
```

CI 使用 PostgreSQL 17，并覆盖 fresh migration、migration/model parity、repeat-safe seed、API tests、前端构建、浏览器工作流与 MCP 协议检查。项目不使用 SQLite 作为替代运行时。

## 文档

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — 系统边界与依赖方向
- [`docs/PRODUCT_SPEC.md`](docs/PRODUCT_SPEC.md) — 产品与领域边界
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — canonical data model
- [`docs/UI_SPEC.md`](docs/UI_SPEC.md) — 主要 UI 与交互约定
- [`docs/api/DOMAIN_API.md`](docs/api/DOMAIN_API.md) — domain API
- [`docs/api/ERRORS_AND_CONCURRENCY.md`](docs/api/ERRORS_AND_CONCURRENCY.md) — 错误、并发与写入安全
- [`docs/agent/AGENT_INTERFACE.md`](docs/agent/AGENT_INTERFACE.md) — 外部智能体接口约定
- [`docs/agent/MCP_CLIENT_SETUP.md`](docs/agent/MCP_CLIENT_SETUP.md) — MCP 客户端接入
