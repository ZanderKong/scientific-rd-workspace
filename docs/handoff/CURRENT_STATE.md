# Current State — Scientific R&D Workspace

更新时间：2026-09-05。本文是当前 handoff；历史交接与执行计划不覆盖本文。

## 当前事实

- 产品是 PostgreSQL-only 的 Scientific R&D Workspace，当前开发版本为 `0.3.0`。
- v0.3 Domain Model、correctness 与 release gate 已通过 PR #4 的 merge commit `e2a4eff` 正式进入 `main`；`main` 是新的 canonical development baseline。
- canonical kinds 是 `research_object`、`process_definition`、`data`、`experiment`、`project`、`view` 和 `claim`；Material、Equipment、Sample 由 Research Object tags 表达。
- Web、REST API 与 MCP 适配器复用 domain services。MCP 写入遵循 proposal-first ChangeSet；不包含模型运行时。
- provenance 以 Process Execution bindings 为准；`subject`、`derived_from` 仅是 system shortcuts。Experiment 仅维护 references，不承载 ownership 或 provenance。
- `/dashboard` 重定向至 `/dashboard/processes`。Samples、Projects、Experiments、Data、Views、Claims、Change Sets 与 Settings 均为有效工作区页面；Research Object、View 与 Claim 有可达的详情页。
- Project scope 由路由/query/localStorage/首个项目解析。Sample Composer 支持 `/` 解析 Process Definition、`@` 解析对象/tag、可编辑的 binding 默认值、排序和原子保存。
- synthetic/anonymised seed 仅用于验收；用户创建或导入的记录不会自动标为演示数据。
- 后续开发必须从 `main` 开始，下一阶段进入产品页面、编辑器与 UI 设计/实现；不再维护任何 v0.2 active runtime。

## 当前边界

PostgreSQL 是唯一数据库，附件 bytes 存文件系统。没有 SQLite fallback、嵌入式 AI、Literature/Evidence/Evaluation runtime、RBAC、队列或 React Flow。REST 没有完整用户鉴权；ETag/If-Match 只在调用方提供时执行并发检查。MCP 非 loopback 部署需要 bearer token 与外部 TLS/auth proxy。

## 验证与发布门禁

- 后端在隔离 PostgreSQL 17 库执行 21 个测试；包含 Sample aggregate、MCP stdio/HTTP 真实协议客户端和共享 reference 删除语义。
- fresh-head 迁移及有真实旧数据的 `0006 → head` 迁移均已验证；`alembic check` 无 drift，且没有旧的 Claim/View 循环依赖 warning。
- 前端已通过 strict lint、typecheck、13 个 Vitest 测试、format check、production build 与 production-dependency audit。
- Playwright 浏览器套件覆盖 no-seed 首跑、Composer aggregate 以及 Cl₂ golden workflow，并在失败时保留 report、trace、video、screenshot 与服务日志。
- v0.3 release gate 已通过六个 GitHub Actions blocking jobs：Backend / PostgreSQL 17、Migration / Legacy 0006 → v0.3、Frontend / Quality、MCP / Contract、Browser / First Run 和 Browser / Golden Scientific Workflow。

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
