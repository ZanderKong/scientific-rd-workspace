# AGENTS.md

本文件是仓库导航，不是完整产品说明。任何 Agent 开始工作前必须先阅读本文件，然后读取与当前任务直接相关的 source-of-truth 文档。

## Source of Truth

按优先级：

1. `docs/PRODUCT_SPEC.md` — 产品目标、MVP 边界、非目标。
2. `ARCHITECTURE.md` — 技术架构、依赖方向、系统边界。
3. `docs/DATA_MODEL.md` — canonical scientific data model。
4. `docs/UI_SPEC.md` — 页面信息架构与基本交互。
5. `docs/exec-plans/01-foundation-eln.md` — 当前 active execution plan。
6. `docs/DEMO_SCENARIO.md` — 最终演示故事。
7. `docs/OPEN_SOURCE_STRATEGY.md` — 上游项目、许可证和复用边界。
8. `docs/handoff/` — 已完成阶段的实际实现状态。

如代码与文档冲突：
- 当前 active execution plan 的明确 acceptance criteria 优先于历史说明。
- 架构或 schema 的重大变更不得静默发生；必须先更新相应 source-of-truth 文档并记录原因。
- 不要仅为了让实现更容易而改变产品语义。

## 当前目标

Phase 1 和 Phase 2 已关闭。Phase 3 M1–M10 已完成，外部 live LiteLLM smoke 已通过，发布标签为
`v0.1-demo`。Phase 1/2 的 immutable template、Revision、Measurement/import、Literature/Evidence
及存储契约保持不变。

Phase 1 目标用户路径：

`Project → Experiment → Structured Properties → Rich Note → Attachments → Clone → Revisions`

## Agent 行为要求

### 开始任务前

1. 检查当前 Git 状态。
2. 阅读当前 milestone。
3. 查找仓库里已有的相似实现，优先复用。
4. 确认依赖版本和真实 API，不凭记忆编造第三方接口。
5. 如果某个计划步骤与当前上游 starter 已变化，做最小兼容修正并记录。

### 实现过程中

- 一次只推进一个 milestone。
- 不扩大 scope。
- 不进行无关重构。
- 不引入第二套状态管理、第二套表单引擎或第二套数据库抽象。
- 所有外部输入在 API 边界做 schema validation。
- 前后端的数据结构必须显式类型化。
- 数据库变更必须通过 Alembic migration。
- 用户可编辑的实验结构化字段不得硬编码为某一种具体材料体系。
- 富文本和结构化字段必须分开存储。
- 附件二进制不得塞进 PostgreSQL。
- 不实现多人协作、复杂 RBAC、仪器直连、完整 LIMS。

### 每个 milestone 完成后

必须执行与该 milestone 相关的：

- formatter
- lint
- typecheck
- unit tests
- API tests
- browser smoke test（有 UI 改动时）

并更新 active plan 中的 Implementation Notes 或单独的阶段日志。

### 阻塞策略

只有以下情况可以停止并要求人工决定：

- 必需 credential 缺失且没有合理 mock 或 local alternative。
- 会造成不可逆数据删除。
- 许可证条款与计划存在实质冲突。
- 需要在两个产品语义明显不同的方案中做人工产品选择。
- 上游项目已发生重大破坏性变化，计划无法通过局部修正继续。

普通编译错误、依赖冲突、测试失败、UI bug 不属于人工阻塞，Agent 应自行诊断和修复。

## 架构硬约束

- `web` 不直接访问 PostgreSQL。
- `web` 只通过 API client 与 `api` 通信。
- `api` 是业务和数据写入边界。
- storage 必须经 `StorageAdapter` 抽象，Phase 1 先实现 `LocalStorageAdapter`。
- Experiment 的 `structured_data` 与 `note_document` 分开。
- Revision 保存的是可追溯 snapshot，不覆盖历史 revision。
- Experiment clone 创建新实体，并记录 `parent_experiment_id`，不得复制原 ID 或 revision history。
- Phase 1 中 Project 和 Experiment 是一级业务实体。

Phase 3 M8 adds a gated `suggested-experiment-prefill` route and immutable
`ExperimentProvenanceLink`; AI suggestions remain non-authoritative and explicit human submit is
required. The deterministic demo seed creates exactly three Reference and three Bad Cases for
PRJ-001, visibly tagged fixture/synthetic/demo. Evaluation and local demo deployment support one API
process and one worker only (`uvicorn ... --workers 1`); multi-worker coordination is unsupported.
Phase 3 is released as `PHASE 3 PASS` at `v0.1-demo`; preserve the live-provider evidence and do not
change the Phase 1/2 guarantees.

## 代码风格

- TypeScript strict。
- Python 开启明确类型注解。
- 组件优先小而可组合。
- 不建立无意义的 `utils` 大杂烩。
- 共享类型放在明确的 domain 或 API client 模块。
- 错误要可见、可诊断，不吞异常。
- 页面必须具备 loading、empty、error 基础状态。

## 命令

Agent 在 bootstrap 后必须把真实可用命令补充到这里。目标约定：

```bash
# frontend
cd web && npm run dev
cd web && npm run lint
cd web && npm run typecheck
cd web && npm run test
cd web && npm run build

# backend
cd api && uv run fastapi dev app/main.py
cd api && uv run pytest
cd api && uv run alembic upgrade head
cd api && uv run python -m app.seed

# infra
docker compose up -d postgres
```

如果上游 starter 使用不同 script，应更新本文档而不是假装这些命令存在。
