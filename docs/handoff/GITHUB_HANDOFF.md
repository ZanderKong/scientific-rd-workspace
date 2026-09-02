# GitHub 交接报告

## 最新状态（2026-09-02）

- Phase 1 remains frozen and passing from baseline `9bb494d`.
- Phase 2 is formally closed as **PASS**; see [Phase 2 交接报告](PHASE_2_HANDOFF.md).
- Accepted source commit: `939bf82`; implementation commit: `b916292`.
- PostgreSQL 17 acceptance passed in GitHub Actions workflow run `33522448986`; Phase 1 regression workflow run `33522448939` also passed on the same source commit.
- Phase 3 Milestones 1–7 are implemented from the approved plan; work stops before Milestone 8.
  Current verdict: **M5–M7 ACCEPTED — M8 UNBLOCKED**. This is not an overall Phase 3
  PASS or release closeout. PostgreSQL 17 evidence is GitHub Actions run `33587413638` on
  commit `6162dc3`. See
  [Phase 3 交接报告](PHASE_3_HANDOFF.md).

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

## 历史说明和非阻塞项

- 本机没有 Docker，因此早期只执行了 SQLite 本地验证；该限制已由 GitHub Actions 的 PostgreSQL 17 成功验收取代，不再是阶段阻塞项。
- npm audit 报告 starter 依赖树中存在 3 条 advisory，未执行破坏性强制升级。
- 本节是仓库级交接记录；Phase 2 的 Measurement、Compare、CSV/XLSX import、Literature 和 Evidence 当前实现状态见 `PHASE_2_HANDOFF.md`。Phase 3 M1–M7 的 AIProvider、冻结上下文、Finding、Evidence Gate、人工评审、Evaluation runner 和 UI 见 `PHASE_3_HANDOFF.md`；M8 草稿实验、RAG、LangGraph、MCP、pgvector 仍延后。

## 交接建议

Phase 1 与 Phase 2 均已正式关闭并通过 PostgreSQL 17 CI。当前 Phase 3 批次必须保持现有不可变模板、revision 和 provenance 保证，并在 M7 后停止；M8 及后续里程碑需单独验收。
