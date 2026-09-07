# Current State — Scientific R&D Workspace

更新时间：2026-09-06。本文是当前 handoff；历史交接与执行计划不覆盖本文。

最新复审：见 [修复后补充审计](V1_5_REPAIR_FOLLOWUP_AUDIT_2026_09_06.md)。四个已复现阻断已修复并转为正确行为回归；聚合并发、完整历史读写、编辑器边界和发布门禁仍未完成。以下能力描述表示实现已存在，不代表修复计划或发布验收完成。

## 当前事实

- 产品是 PostgreSQL-only 的 Scientific R&D Workspace，当前开发版本为 `0.3.0`。
- 当前工作树以 `main@93700a6` 和 v1.5 冻结基线实施核心工作流重构；详细状态见 [`V1_5_IMPLEMENTATION_PROGRESS.md`](V1_5_IMPLEMENTATION_PROGRESS.md)。本轮修复追加 `0020_authoring_binding` 与 `0021_typed_revision_refs`，开发数据库仍停在历史 `0006_agent_changes`，没有未经确认进行数据升级。
- canonical kinds 是 `research_object`、`process_definition`、`data`、`experiment`、`project`、`view` 和 `claim`；Material、Equipment、Sample 由 Research Object tags 表达。
- Web、REST API 与 MCP 适配器复用 domain services。MCP 写入遵循 proposal-first ChangeSet；不包含模型运行时。
- Scientific Record 以文档、稳定 occurrence、Execution/binding 实际值和固定 revision manifest 为准；typed occurrence 表只服务查询。Data subject 显式保留 manual、acquisition document 与 producer 来源；View/Claim 历史 revision 通过 typed revision reference 保护其固定依赖。
- Sample、Data、ProcessExecution、View 和 Claim 均支持按明确 revision 的只读读取；编辑 token 不包含关联对象当前标题等动态展示字段。
- Sample/Data 写入共享项目图与 owner 锁入口；业务 DTO 和 provenance 仍在各自领域服务中编排。
- `/dashboard` 重定向至 `/dashboard/processes`。Samples、Projects、Experiments、Data、Views、Claims、Change Sets 与 Settings 均为有效工作区页面；Research Object、View 与 Claim 有可达的详情页。
- Project scope 由路由/query/localStorage/首个项目解析。连续 Scientific Composer 支持 `/Process`、`@Object`、原位 PropertySlot、Replace、统一 Undo/Redo、历史读取、草稿恢复和复制重映射。
- Data draft/finalize、服务器记录表、Experiment Sample Picker、固定版本 View/Artifact 与 Claim context 已进入当前运行契约。
- synthetic/anonymised seed 仅用于验收；用户创建或导入的记录不会自动标为演示数据。
- 不再维护 `steps`、View `data_ids`、Claim `source_type` 等旧客户端写入契约。

## 当前边界

PostgreSQL 是唯一数据库，附件 bytes 存文件系统。没有 SQLite fallback、协同编辑、离线自动合并、内置分析/AI runtime、RBAC 或队列。真实 macOS 中文 IME 与固定性能环境仍是发布前人工门禁；100 Ref × 20 字段读取的本机 SQL 诊断已从 503 条降至 10 条。

## 验证与发布门禁

- 后端在隔离 PostgreSQL 库执行 44 个测试；包含聚合边界、严格 Scientific Record 契约、Replace/恢复、幂等、固定 revision、Data scientific document 回读/更正、空字段/同 occurrence 表格查询、Experiment 命令和 MCP 真实协议。
- 全新数据库从 `0001` 到 `0021`、旧 `0006` 加 legacy fixture 到 head 的迁移链及 `alembic check` 已验证；固定性能环境和开发库正式升级仍属于发布前门禁。
- 前端已通过 strict lint、typecheck、13 个 Vitest 测试、format check、production build 与 production-dependency audit。
- 当前 Playwright 六项 Chromium workflow 通过：5 项真实 API 流程和 1 项保存竞态 mocked API 流程，包含零结果筛选后清除并恢复目录的回归。真实 IME、固定性能环境及 no-seed 首跑仍不记为通过。
- 前端 strict lint、format、typecheck、13 项 Vitest 与 Next.js production build 通过。

## 当前资料

- 产品、数据模型、UI 与依赖策略：[`docs/current/`](../current/)
- API 与 Agent 契约：[`docs/current/api/`](../current/api/)、[`docs/current/agent/`](../current/agent/)
- 架构地图：[`ARCHITECTURE.md`](../../ARCHITECTURE.md)
- Plan 10.2 发布交接：[`V0_3_VERIFICATION_BROWSER_E2E_RELEASE_GATE_HANDOFF.md`](V0_3_VERIFICATION_BROWSER_E2E_RELEASE_GATE_HANDOFF.md)
- Plan 10.1 基线交接：[`V0_3_DOMAIN_CORRECTNESS_TEST_FOUNDATION_HANDOFF.md`](V0_3_DOMAIN_CORRECTNESS_TEST_FOUNDATION_HANDOFF.md)

## 资料分层

- `docs/current/`：当前契约和运行说明。
- `docs/handoff/`：当前版本的交接和执行证据。
- `docs/history/`：已完成的历史交接与计划。
- `docs/archive/`：旧 runtime、旧计划、旧审计和规划参考，不能作为当前事实。
