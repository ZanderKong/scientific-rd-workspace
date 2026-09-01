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
│   └── 03-scientific-ai-scope.md
├── handoff/
│   └── PHASE_HANDOFF_TEMPLATE.md
└── references/
    └── SOURCES.md
```

## 当前阶段

**Active Phase：Phase 1 — Foundation + ELN Core**

Phase 1 做完之后，产品应能够完成：

> Project → Experiment → Structured Properties → Rich Note → Attachment → Save → Clone → Revision History

这是第一个真实可运行的纵向切片。

Phase 2 和 Phase 3 目前只定义产品边界和接口，不应在 Phase 1 中提前实现。

## 推荐工作方式

1. 新建一个空文件夹。
2. 将本文件包中的所有文件复制到该文件夹根目录。
3. 用 Git 初始化仓库。
4. 可选但推荐：先让你 Codex 客户端中用于高推理规划的模型读取整个目录，执行 `docs/CODEX_PROMPTS.md` 中的「Preflight / Plan Review」。
5. 然后让执行模型读取 `AGENTS.md` 与 `docs/exec-plans/01-foundation-eln.md`，按照 milestone 顺序实现。
6. 每个 milestone 都必须通过指定验证，再继续下一个。
7. Phase 1 完成后，不要直接执行 Phase 2 scope。先基于真实仓库生成新的详细 Phase 2 Execution Plan。

## 核心原则

- 一个主产品壳，一个 canonical data model。
- 开源项目作为 starter、组件或独立 service 使用，不把多个完整产品源码硬 merge。
- Phase 1 不引入 LangGraph、Langfuse、MCP、pgvector、Zotero 集成。
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

## 完成定义

Phase 1 的「完成」不是页面画出来，而是 `docs/exec-plans/01-foundation-eln.md` 中所有 P0 acceptance criteria 均通过，并产出一份 Phase Handoff。

## Phase 1 本地启动

Prerequisites: Node.js 22+, npm, Python 3.11+, uv, and Docker Desktop (for PostgreSQL 17). The current environment did not have Docker installed, so database-backed runtime checks are recorded as pending in the handoff.

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
