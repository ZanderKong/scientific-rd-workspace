# Scientific R&D Workspace — Codex Project Pack v0.1

本文件包用于从一个空目录启动 **Scientific R&D Workspace** 的第一个可执行开发阶段。

目标不是从零开发完整 ELN/LIMS，而是快速组合成熟开源能力，先完成一个可以真实录入实验、保存、克隆和追溯版本的科研工作台底座，再逐步扩展到实验数据比较、Evidence Gate 和 AI Evaluation。

## 这个包里有什么

```text
AGENTS.md
ARCHITECTURE.md
README.md
docs/
├── PRODUCT_SPEC.md
├── DATA_MODEL.md
├── UI_SPEC.md
├── DEMO_SCENARIO.md
├── OPEN_SOURCE_STRATEGY.md
├── CODEX_PROMPTS.md
├── exec-plans/
│   ├── 01-foundation-eln.md
│   ├── 02-scientific-workflow-scope.md
│   ├── 02-scientific-workflow.md
│   └── 03-scientific-ai-scope.md
├── handoff/
│   ├── PHASE_1_HANDOFF.md
│   ├── PHASE_2_HANDOFF.md
│   └── PHASE_HANDOFF_TEMPLATE.md
└── references/
    └── SOURCES.md
```

## 当前阶段

**Closed phases：Phase 1 — Foundation + ELN Core；Phase 2 — Scientific Workflow**

Phase 1 已完成并通过：

> Project → Experiment → Structured Properties → Rich Note → Attachment → Save → Clone → Revision History

Phase 2 已完成并通过：

> Raw Attachment → Import → Measurement → Plot → Compare → Literature → Evidence

Phase 1 基线为 `9bb494d`。Phase 2 的 PostgreSQL 17 GitHub Actions 验收在提交 `939bf82` 上通过；详情见 `docs/handoff/PHASE_2_HANDOFF.md`。Phase 3 已完成 Milestones 1–4（冻结分析上下文、AIProvider/双结构化输出模式、Finding、确定性 Evidence Gate 与人工评审 API），当前批次在 M4 后停止；M5 及 Evaluation/UI/草稿实验功能尚未开始。详见 `docs/handoff/PHASE_3_HANDOFF.md`。

## 阶段执行记录

1. Phase 1 按 `docs/exec-plans/01-foundation-eln.md` 完成并关闭。
2. Phase 2 基于冻结的 Phase 1 架构生成并执行 `docs/exec-plans/02-scientific-workflow.md`。
3. Phase 2 的 PostgreSQL 17、后端和前端门禁已通过 GitHub Actions。
4. Phase 1/2 的最终证据分别记录在 `docs/handoff/PHASE_1_HANDOFF.md` 和 `docs/handoff/PHASE_2_HANDOFF.md`。
5. Phase 3 M1–M4 已按批准计划实现；M5–M10 保持未开始，不能据此宣称 Phase 3 PASS。

## 核心原则

- 一个主产品壳，一个 canonical data model。
- 开源项目作为 starter、组件或独立 service 使用，不把多个完整产品源码硬 merge。
- Phase 1/2 不引入 LangGraph、Langfuse、MCP、pgvector 或 Zotero 运行时集成。
- 不为了未来需求提前制造微服务。
- 不重新开发富文本编辑器或通用 Schema Form Engine。
- 每个阶段必须保持可运行。
- UI 可以先做到一致、清晰、可演示，不追求最终视觉 polish。
- Scientific schema、workflow、evidence 和 provenance 才是项目原创价值。

## Phase 1 技术基线

前端：
- Next.js 16
- React 19
- TypeScript
- Tailwind CSS
- shadcn/ui
- Kiranism `next-shadcn-dashboard-starter` 作为主壳
- JSON Forms 用于结构化实验字段
- BlockNote 用于实验富文本记录

后端：
- Python
- FastAPI
- SQLAlchemy 2
- Alembic
- PostgreSQL
- Pydantic

存储：
- PostgreSQL 保存结构化数据和 JSON 文档
- Phase 1 使用本地文件存储适配器保存附件
- 文件元数据写入 PostgreSQL

开发：
- Docker Compose 只负责 PostgreSQL 和必要的本地基础设施
- 前后端可以直接本机启动
- 必须提供一条明确的开发启动路径

## 阶段完成状态

Phase 1 和 Phase 2 的所有 P0 acceptance criteria 均已通过，并分别产出正式 handoff。Phase 2 的权威验收由 PostgreSQL 17 GitHub Actions workflow run `33522448986` 提供。

## Phase 1/2 本地启动

Prerequisites: Node.js 22+, npm, Python 3.11+, uv, and Docker Desktop (for PostgreSQL 17). Phase 1 has been audited against a real PostgreSQL 17.11 server; see `docs/handoff/PHASE_1_HANDOFF.md` for the closeout evidence.

```bash
cp api/.env.example api/.env
docker compose up -d postgres

cd api
uv sync
uv run alembic upgrade head
uv run python -m app.seed
uv run fastapi dev app/main.py
```

In another terminal:

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:3000/dashboard/overview](http://localhost:3000/dashboard/overview). The Phase 1 routes are `/dashboard/overview`, `/dashboard/projects`, `/dashboard/projects/[projectId]`, `/dashboard/projects/[projectId]/experiments/new`, `/dashboard/experiments`, and `/dashboard/experiments/[experimentId]`.

Quality checks:

```bash
cd api && uv run pytest
cd web && npm run test && npm run lint && npm run typecheck && npm run build
```

The API persists PostgreSQL records through SQLAlchemy/Alembic and attachment bytes through the local adapter at `data/uploads` (configurable with `STORAGE_ROOT`). `NEXT_PUBLIC_API_URL` can point the web client at another API base, defaulting to `http://localhost:8000/api/v1`.

### Docker-free local deployment

If Docker/PostgreSQL is not installed, use the local-only SQLite fallback. It uses the same Alembic schema and demo seed, stores the database at `data/local/scientific_rd.db`, and keeps PostgreSQL as the production/default path:

```bash
./scripts/start-local.sh
```

Open [http://127.0.0.1:3000/dashboard/overview](http://127.0.0.1:3000/dashboard/overview). Press `Ctrl-C` in the terminal to stop both services. To use the production-like path, install Docker Desktop and follow the PostgreSQL commands above instead.
