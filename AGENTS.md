# Repository Guide for Agents

This repository implements the canonical Scientific R&D Workspace domain. Web UI, REST and MCP must reuse the same domain services and semantic validation.

External clients should prefer domain-level operations over low-level graph mutation. Changes to existing scientific records default to proposal-first ChangeSets with optimistic concurrency and human/trusted review.

## Source of truth

按优先级阅读：

1. `docs/PRODUCT_SPEC.md`
2. `ARCHITECTURE.md`
3. `docs/DATA_MODEL.md`
4. `docs/UI_SPEC.md`
5. `docs/api/DOMAIN_API.md`
6. `docs/api/ERRORS_AND_CONCURRENCY.md`
7. `docs/agent/AGENT_INTERFACE.md`
8. `docs/agent/MCP_TOOLS.md`
9. `docs/agent/MCP_RESOURCES.md`
10. `docs/agent/CHANGE_SET_WORKFLOW.md`

Execution plans and handoff files are historical engineering records. Current product behaviour is defined by the source-of-truth documents and validated implementation. Historical files must never override the current source-of-truth documents when they disagree.

## 当前产品边界

- 七种 canonical object：`material`、`sample`、`equipment`、`process`、`data`、`experiment`、`project`。
- 关系有 `contains`、`includes`、`uses`、`produces`、`precedes`、`related_to`，由后端按 object kind 约束；`includes` 只表示 Experiment 对 Sample 的非拥有成员关系。
- `sample` 是 object kind；`precursor`、`subject`、`reference`、`control` 只是 `uses` 关系角色。
- 只有 `precursor` 参与 lineage，只有 `subject` 推导当前 Data；Experiment 对 Process/Sample/Data 单一拥有，Process 对 Sample/Data 单一产出。
- 跨 Experiment 复用通过 Process `uses` 和 context `input_samples` 表达，不复制上游 ownership。
- `Experiment contains Process/Sample/Data` remains exclusive ownership, not membership; `includes` is the canonical multi-Experiment Sample membership relation.
- Experiment Record、Project Context、Data Record、Sample Execution、Experiment Comparison 和 ChangeSet 是 canonical domain service/API，不由 MCP 复制实现。
- 唯一数据库是 PostgreSQL；本地开发、测试和 CI 都不得回退 SQLite。
- 附件二进制存文件系统，PostgreSQL 只保存 object-centric 元数据、校验和及引用。
- Data payload 与 DataImport 是独立于附件的可追溯数据层；原始值不插值、不隐式换算单位。
- 旧 phase-specific AI Analysis、generic Compare、Evidence、Evaluation、Literature runtime 已移除。当前 `ExperimentComparisonService` 是 v0.2 canonical runtime，不属于旧 generic Compare。

## 历史资料处理约定

- `docs/exec-plans/` 只记录工程演进，不定义当前产品状态。
- `docs/handoff/` 只保留仍能准确描述当前系统或当前交接状态的文件；旧阶段 handoff、旧 runtime 审计和失效验收材料应删除或归档。
- `docs/assets/` 只保留与当前 UI 一致、并且仍被文档引用的资源。旧 Analysis、Evaluation、Literature、generic Compare 等截图不得作为当前产品截图继续保留。
- Git 历史已经承担历史追溯职责；不需要为了“保留历史”而让失效材料继续污染 tracked tree。

## 工作约定

- 开始前检查 Git 状态并阅读 active plan。
- 数据库改动只通过 `api/alembic/versions/0001_v0_2_research_object_graph.py` 及后续 Alembic migration。
- `0001` 是已发布基线，不重写；语义稳定化只新增 `0002_v0_2_semantic_stabilization`。
- Plan 08 schema changes begin with `api/alembic/versions/0003_sample_recording_workflow.py`; do not modify `0001` or `0002`.
- Plan 09 schema changes begin with `api/alembic/versions/0004_experiment_membership.py`; migrations `0001`–`0003` remain immutable.
- 前端 API 类型与后端 Pydantic schema 必须显式对齐；错误、加载、空状态必须可见。
- 不引入第二套数据库、队列、状态管理或表单引擎；不使用 React Flow。
- 外部 agent 默认通过 ChangeSet proposal 写入；MCP 只调用 canonical service，不内嵌 LLM。
- 变更后按风险执行 formatter、lint、typecheck、unit/API tests、build 和 browser smoke。

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
