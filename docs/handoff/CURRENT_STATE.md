# Current State — Scientific R&D Workspace

更新时间：2026-09-04。本文是唯一当前 handoff；历史交接、执行计划和旧 runtime 审计不会覆盖本文。

## 当前事实

- 产品是 PostgreSQL-only 的 Scientific R&D Workspace，当前开发版本为 `0.3.0`。
- canonical kinds 是 `research_object`、`process_definition`、`data`、`experiment`、`project`、`view` 和 `claim`；Material、Equipment、Sample 通过 Research Object tags 表达。
- Web、REST API 和 MCP 适配器复用同一套 domain services。MCP 不包含模型运行时；外部写入默认通过 proposal-first ChangeSet。
- Experiment 只维护 references，不承载 ownership、provenance 或 comparison runtime；数据 lineage 由 `subject` / `derived_from` system relations 表达。
- 当前根入口是 `/dashboard/processes`，以 Process Definition 为首个工作入口；Samples、Projects、Experiments、Data、Views、Claims、Change Sets 和 Settings 仍是有效页面或深链接。
- Data landing 是当前主导航入口；Data detail、multiple representations 和 CSV/XLSX import 仍可用。
- Project scope 由路由/query/localStorage/首个项目解析；Research Object tags 支持 Material/Equipment/Sample 分组；语言、主题和 React Query Devtools 偏好属于浏览器设置。
- 演示 seed 是 synthetic/anonymised 数据，用户创建或导入的记录不能被自动标成演示数据。
- 当前真实界面基线截图是 `docs/assets/ui/current/samples-zh-CN.png`；同一截图用于 Web `/scientific-rd-workspace.png` 分享图。

## 当前边界

PostgreSQL 是唯一数据库，附件 bytes 存文件系统。没有 SQLite fallback、嵌入式 AI、Literature/Evidence/Evaluation runtime、RBAC、队列或 React Flow。REST 当前没有完整用户鉴权；ETag/If-Match 只在调用方提供条件时执行并发检查。MCP 非 loopback 部署需要 bearer token 和外部 TLS/auth proxy。

## 当前资料

- 产品、数据模型、UI 与依赖策略：[`docs/current/`](../current/)
- API 与 Agent 契约：[`docs/current/api/`](../current/api/)、[`docs/current/agent/`](../current/agent/)
- 架构地图：[`ARCHITECTURE.md`](../../ARCHITECTURE.md)
- 当前实现的 Plan 10 交接：[`docs/history/handoff/PLAN10_WORKSPACE_SHELL_RESOURCE_SETTINGS_HANDOFF.md`](../history/handoff/PLAN10_WORKSPACE_SHELL_RESOURCE_SETTINGS_HANDOFF.md)

## 验证边界

当前工作区已验证：API health/capabilities、根路径重定向到 Samples、Web Samples HTTP 页面、分享图与 HTML metadata、前端 27 个测试、typecheck、format check、production build、后端 Ruff/format、Alembic parity，以及独立 PostgreSQL 测试库中的 34 个后端测试。前端 lint 通过但保留 1 条 effect dependency warning。干净依赖安装在本机离线缓存中以 `npm ci --ignore-scripts --offline` 验证通过；注册表环境下的普通 `npm ci` 以及 Node Docker image build 在依赖安装阶段因环境网络/注册表停滞而未完成，Dockerfile 的公开构建参数已静态核对但未宣称镜像构建通过。MCP 协议没有独立 CI 检查，不能据此声明协议门禁通过。完整后端 API 测试必须在显式隔离的 PostgreSQL 测试库运行；缺少或误指向开发库的 `TEST_DATABASE_URL` 会在连接/DDL 前失败。历史文件中的旧 SQLite、Phase 1–3、旧 UI 和旧 CI 结果只代表其记录的时间与 commit。

本文件和本次清理描述的是当前工作区实现；Plan 10 与本次清理尚未创建发布提交，也没有修改历史 tag。Git 未提交文件仍须在交付前按清单核对。

## 资料分层

- `docs/current/`：当前契约和运行说明。
- `docs/history/`：当前架构的完成计划与交接证据。
- `docs/archive/`：旧 runtime、旧计划、旧审计和规划参考，不得作为当前事实。
- `docs/assets/ui/current/` 与 `docs/assets/ui/archive/`：当前和历史展示图片。
