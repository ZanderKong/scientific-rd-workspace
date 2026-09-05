# Repository Guide for Agents

This repository implements the canonical Scientific R&D Workspace domain. Web UI, REST and MCP must reuse the same domain services and semantic validation.

External clients should prefer domain-level operations over low-level graph mutation. Changes to existing scientific records default to proposal-first ChangeSets with optimistic concurrency and human/trusted review.

## Source of truth

按优先级阅读当前资料：

1. `docs/handoff/CURRENT_STATE.md`
2. `docs/current/PRODUCT_SPEC.md`
3. `ARCHITECTURE.md`
4. `docs/current/DATA_MODEL.md`
5. `docs/current/UI_SPEC.md`
6. `docs/current/api/DOMAIN_API.md`
7. `docs/current/api/ERRORS_AND_CONCURRENCY.md`
8. `docs/current/agent/AGENT_INTERFACE.md`
9. `docs/current/agent/MCP_TOOLS.md`
10. `docs/current/agent/MCP_RESOURCES.md`
11. `docs/current/agent/CHANGE_SET_WORKFLOW.md`

`docs/current/` contains current contracts. `docs/history/` contains completed work on the current architecture. `docs/archive/` contains legacy runtime and planning material and must not be used as current product evidence. `docs/handoff/CURRENT_STATE.md` is the only current handoff.

## 当前产品边界

- 七种 canonical kind：`research_object`、`process_definition`、`data`、`experiment`、`project`、`view`、`claim`。
- Material、Equipment、Sample 是统一 `research_object` 的 tags，不得在 API/UI 新建旧 kind。
- 关系只有 `references`、`subject`、`derived_from`、`related_to`；`subject` 与 `derived_from` 由系统维护。
- Process Definition 是模板 identity；Process Execution 独立保存 pinned version、多个 object/data bindings、field snapshot 与 revisions。
- Experiment 只做 research context/reference，不拥有 Process、Sample 或 Data，也不提供 canonical comparison runtime。
- Data 通过多个 Representations、Origin、Asset 和 system lineage 组织；View 只引用 Data，Claim 保存 statement/evidence/revisions。
- Experiment Record、Project Context、Data Record、Sample projection、View、Claim 和 ChangeSet 是 canonical services/API，不由 MCP 复制实现。
- 唯一数据库是 PostgreSQL；本地开发、测试和 CI 都不得回退 SQLite。
- 附件二进制存文件系统，PostgreSQL 只保存 object-centric 元数据、校验和及引用。
- DataRepresentation 与 DataImport 是独立于 Asset 的可追溯数据层；原始值不插值、不隐式换算单位。
- legacy comparison、AI、Evidence、Evaluation、Literature runtime 不在当前产品中；Experiment 只提供 references。

## 工作约定

- 开始前检查 Git 状态并阅读 `docs/handoff/CURRENT_STATE.md`。
- 数据库改动只通过 Alembic；`0001`–`0006` 是不可修改的 v0.2 历史，v0.3 使用 `0007`–`0010` 正式迁移。
- 前端 API 类型与后端 Pydantic schema 必须显式对齐；错误、加载、空状态必须可见。
- 不引入第二套数据库、队列、状态管理或表单引擎；不使用 React Flow。
- 外部 agent 默认通过 ChangeSet proposal 写入；MCP 只调用 canonical service，不内嵌 LLM。
- 变更后按风险执行 formatter、lint、typecheck、unit/API tests、build 和 browser smoke。后端测试必须使用显式隔离的 PostgreSQL 测试库。

## 常用命令

```bash
cd api
uv sync --frozen
uv run alembic upgrade head
uv run python -m app.seed
uv run ruff check app tests alembic/versions
uv run pytest -q

cd ../web
npm ci
npm run lint
npm run typecheck
npm test -- --run
npm run build
```

正式 API/API tests 需要可连接的 PostgreSQL；无数据库时应明确报告门禁未执行，而不是改用 SQLite。
