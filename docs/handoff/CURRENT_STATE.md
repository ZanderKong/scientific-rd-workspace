# Current State — Scientific R&D Workspace

更新时间：2026-09-09。本文是当前 handoff；历史交接与执行计划不覆盖本文。

最新复审：见 [修复后补充审计](V1_5_REPAIR_FOLLOWUP_AUDIT_2026_09_06.md)；本轮五栏工作台实施记录见 [FIVE_SECTION_WORKSPACE_IMPLEMENTATION_2026_09_09.md](FIVE_SECTION_WORKSPACE_IMPLEMENTATION_2026_09_09.md)。以下能力描述表示实现已存在，不代表真实 IME 和完整发布门禁全部完成。

## 当前事实

- 产品是 PostgreSQL-only 的 Scientific R&D Workspace，当前开发版本为 `0.3.0`。
- 当前工作树以 `main@93700a6` 和 v1.5 冻结基线实施核心工作流重构；详细状态见 [`V1_5_IMPLEMENTATION_PROGRESS.md`](V1_5_IMPLEMENTATION_PROGRESS.md)。本轮追加 `0023_scientific_document_v2`，为两级 bullet 保存语义行。经用户授权，已重置本项目本地开发 PostgreSQL 的 `public` schema，执行完整 Alembic 迁移并重新 seed；测试使用独立临时数据库，测试结束后已删除。
- canonical kinds 是 `research_object`、`process_definition`、`data`、`experiment`、`project`、`view` 和 `claim`；Material、Equipment、Sample 由 Research Object tags 表达。
- Web、REST API 与 MCP 适配器复用 domain services。MCP 写入遵循 proposal-first ChangeSet；不包含模型运行时。
- Scientific Record 以文档、稳定 occurrence、Execution/binding 实际值和固定 revision manifest 为准；typed occurrence 表只服务查询。Data subject 显式保留 manual、acquisition document 与 producer 来源；View/Claim 历史 revision 通过 typed revision reference 保护其固定依赖。
- Sample、Data、ProcessExecution、View 和 Claim 均支持按明确 revision 的只读读取；编辑 token 不包含关联对象当前标题等动态展示字段。
- Sample/Data 写入共享项目图与 owner 锁入口；业务 DTO 和 provenance 仍在各自领域服务中编排。
- `/dashboard` 重定向至 `/dashboard/samples`。侧栏固定为 Samples、Analysis、Data、Claims、Resources；旧 Experiment 列表跳转 Analysis，旧详情显示记录不存在并提供 Analysis 入口。Legacy Research Object、View 与 Claim 详情仍保持可达。
- Project scope 由路由/query/localStorage/首个项目解析。Scientific Composer 当前采用 V2 两级 bullet：一级自然语言声明 `@` occurrence，二级 bullet 以 `@引用｜属性: 值` 补充自由字段，并支持 `@data` / `@claim` 语义行；保存、历史读取、草稿恢复和复制重映射复用现有科学记录服务。旧的 `/Process` 与原位 PropertySlot 编辑路径已移除。
- 当前 V2 将语义行以稳定 ID 保存在当前 Sample/Data 文档并纳入 revision；`@data`/`@claim` 会物化独立实体并同步当前 Sample 主体/上下文，删除文档行解除当前关联但保留实体与历史。级联删除确认、搜索加载更多和完整动态分析集合仍属于后续工作。
- Data draft/finalize、服务器记录表、Experiment Sample Picker、固定版本 View/Artifact 与 Claim context 已进入当前运行契约。
- synthetic/anonymised seed 仅用于验收；用户创建或导入的记录不会自动标为演示数据。
- 不再维护 `steps`、View `data_ids`、Claim `source_type` 等旧客户端写入契约。

## 当前边界

2026-09-09 引用输入修复：新插入的 Object/Process/父级属性引用两侧写入正文空格，引用显示浅色背景；二级引用通过 BlockNote SuggestionMenu 接口插入 `｜` 并立即打开属性菜单。compositionend 延后一帧刷新事务和候选加载，避免最终中文已被观察但未实际查询时必须再输入空格。浏览器验证二级引用→自动属性菜单→温度值，确认只有一个分隔符；lint、typecheck、21 项单测、build 通过。真实 macOS IME 仍待人工验证。

PostgreSQL 是唯一数据库，附件 bytes 存文件系统。没有 SQLite fallback、协同编辑、离线自动合并、内置分析/AI runtime、RBAC 或队列。真实 macOS 中文 IME 与固定性能环境仍是发布前人工门禁；100 Ref × 20 字段读取的本机 SQL 诊断已从 503 条降至 10 条。

## 验证与发布门禁

- 后端在隔离 PostgreSQL 库执行 56 个测试；包含聚合边界、严格 Scientific Record 契约、Replace/恢复、幂等、固定 revision、Data scientific document 回读/更正、语义行实体物化、无 primary source Claim、资源分类、空字段/同 occurrence 表格查询和 MCP 真实协议。
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
