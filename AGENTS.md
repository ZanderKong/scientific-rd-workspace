# Agent Guide — v0.2 Research Object Graph

这是 Scientific R&D Workspace 的当前仓库导航。当前 active product 是 v0.2 Research Object Graph；旧 v0.1 文档只作为历史记录，不代表运行时契约。

## Source of truth

按优先级阅读：

1. `docs/exec-plans/08-sample-first-recording-editor.md`
2. `docs/exec-plans/07.1-v0.2-core-semantic-stabilization.md`
3. `docs/exec-plans/07-v0.2-research-object-graph-core-cutover.md`
4. `docs/PRODUCT_SPEC.md`
5. `ARCHITECTURE.md`
6. `docs/DATA_MODEL.md`
7. `docs/UI_SPEC.md`
8. `docs/DEMO_SCENARIO.md`
9. `docs/handoff/V0_2_CORE_SEMANTIC_STABILIZATION_HANDOFF.md`

如代码与计划冲突，先修正代码或更新 source-of-truth，并记录原因；不要恢复旧 Project/Experiment/Measurement 专用运行时。

## 当前产品边界

- 七种 canonical object：`material`、`sample`、`equipment`、`process`、`data`、`experiment`、`project`。
- 关系只有 `contains`、`uses`、`produces`、`precedes`、`related_to`，由后端按 object kind 约束。
- `sample` 是 object kind；`precursor`、`subject`、`reference`、`control` 只是 `uses` 关系角色。
- 只有 `precursor` 参与 lineage，只有 `subject` 推导当前 Data；Experiment 对 Process/Sample/Data 单一拥有，Process 对 Sample/Data 单一产出。
- 跨 Experiment 复用通过 Process `uses` 和 context `input_samples` 表达，不复制上游 ownership。
- `Experiment contains Process/Sample/Data` remains exclusive ownership, not membership; Plan 08 must not repurpose it for multi-Experiment Sample selection or use `related_to` as a membership substitute.
- Non-owning Experiment/Sample membership is deferred to a dedicated follow-up plan with an explicit relation or model/API.
- 唯一数据库是 PostgreSQL；本地开发、测试和 CI 都不得回退 SQLite。
- 附件二进制存文件系统，PostgreSQL 只保存 object-centric 元数据、校验和及引用。
- Data payload 与 DataImport 是独立于附件的可追溯数据层；原始值不插值、不隐式换算单位。
- 旧 AI、Compare、Evidence、Evaluation、Literature active runtime 已移除；如需恢复，另立 Plan 2。

## 工作约定

- 开始前检查 Git 状态并阅读 active plan。
- 数据库改动只通过 `api/alembic/versions/0001_v0_2_research_object_graph.py` 及后续 Alembic migration。
- `0001` 是已发布基线，不重写；语义稳定化只新增 `0002_v0_2_semantic_stabilization`。
- Plan 08 schema changes begin with `api/alembic/versions/0003_sample_recording_workflow.py`; do not modify `0001` or `0002`.
- 前端 API 类型与后端 Pydantic schema 必须显式对齐；错误、加载、空状态必须可见。
- 不引入第二套数据库、队列、状态管理或表单引擎；不使用 React Flow。
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
