# GitHub 交接报告

## 仓库

- Repository: `scientific-rd-workspace-codex-pack-v0.1`
- Visibility: private（为避免在未确认前公开科研工作区）
- Owner: `ZanderKong`
- Remote URL: https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1
- Initial commit: `80dbf63` (`Implement Phase 1 scientific R&D workspace`)

## 本次完成内容

- 建立 Next.js 16 / React 19 web 工作区，并清理 starter 的产品、用户和 mock API 路由。
- 建立 FastAPI / SQLAlchemy / Alembic API，覆盖 projects、experiment templates、experiments、attachments、clones、immutable revisions。
- 使用 JSON Forms 渲染 schema-driven structured properties；使用 BlockNote 保存独立的 rich note 文档。
- 实现本地附件存储、路径安全、文件大小限制、SHA-256 元数据和下载接口。
- 实现实验 clone lineage 和 revision snapshot 追溯。
- 添加 PostgreSQL 17 Docker Compose、seed data、API tests、storage tests、frontend Vitest tests。
- 添加 Docker-free 本地部署脚本 `scripts/start-local.sh`：使用同一套 Alembic schema 和 seed，在 `data/local/scientific_rd.db` 中运行 SQLite 开发环境，并同时启动 API/Web。
- 保留第三方许可证和 attribution 文件。

## 验证结果

- `cd api && uv run pytest`：5 passed。
- `cd api && uv run python -m compileall -q app`：通过。
- `cd web && npm run test`：2 passed。
- `cd web && npm run lint`：通过（仅 starter UI 遗留 warnings）。
- `cd web && npm run typecheck`：通过。
- `cd web && npm run build`：通过。
- `cd web && npm run format:check`：通过。
- 本地浏览器 smoke：overview、projects、experiments 路由加载，无 error overlay 或 console error。
- Docker-free 本地部署：API `GET /api/v1/health` 返回 `{"status":"healthy"}`，`GET /api/v1/projects` 返回 PRJ-001 和 3 个演示实验；Web `/dashboard/overview` 返回 HTTP 200。

## 运行方式

```bash
cp api/.env.example api/.env
docker compose up -d postgres
cd api && uv sync && uv run alembic upgrade head && uv run python -m app.seed
uv run fastapi dev app/main.py
cd ../web && npm install && npm run dev
```

打开 `http://localhost:3000/dashboard/overview`。

若本机没有 Docker/PostgreSQL：

```bash
./scripts/start-local.sh
```

该 SQLite 路径仅用于本地开发，生产默认配置仍为 PostgreSQL。

## 尚待确认

- 当前执行环境没有 Docker，因此 PostgreSQL 空库 migration、生产数据库 seed 和 PostgreSQL 连接验证尚未在本机完成；SQLite 本地开发部署已完成并通过健康检查。
- npm audit 报告 starter 依赖树中存在 3 条 advisory，未执行破坏性强制升级。
- Phase 2/3 的 Measurement、Compare、Literature、AI、RAG、LangGraph、Langfuse、MCP、pgvector、Zotero 等均未实现。

## 交接建议

首次在 Docker 可用环境执行上述启动命令，完成 `docs/DEMO_SCENARIO.md` 全流程后，再将 handoff 状态从 PARTIAL 更新为 PASS。
