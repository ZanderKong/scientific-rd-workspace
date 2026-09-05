# Open Source and Dependency Strategy

## 当前原则

产品代码只依赖当前 package manifests 和 lockfiles 中实际需要的库。第三方源码、许可证和归属信息与产品身份分开记录；上游 Starter 是历史来源，不是当前产品作者或当前 Agent 指令。

当前直接依赖包括 Next.js/React、next-intl、TanStack React Query、BlockNote、base UI、lucide-react、Zod、Sonner 和当前构建工具。后端依赖 FastAPI、SQLAlchemy、Alembic、Psycopg、MCP SDK、JSON Schema、OpenPyXL 和 defusedxml。

当前后端不依赖 LiteLLM、Langfuse、Zotero、LangGraph 或 pgvector。它们的历史评估与规划位于 `docs/archive/`。

## 许可证与归属

BlockNote 的直接包许可证为 MPL-2.0；next-intl 为 MIT；lucide-react 为 ISC。JSON Forms 仅作为历史 Starter 归属记录保留，不是当前直接依赖。具体版本和传递依赖以 lockfiles 与包自身 license metadata 为准。

web 中保留上游 Starter 的许可证文件和 attribution，因为当前 UI 壳来自该历史快照。该归属不表示产品由上游作者创建，也不应出现在产品 author、赞助或 OpenGraph metadata 中。第三方通知见根目录 `THIRD_PARTY_NOTICES.md`。

## 维护规则

- 依赖必须先有当前代码或构建配置的消费者，再加入 manifest。
- 新增依赖时更新 lockfile、第三方通知和必要的许可证文件。
- 不把完整外部应用源码合并进产品。
- 不为历史 Phase 恢复旧 runtime；如需新能力，先更新当前产品契约和架构。
- 不修改上游许可证文件，也不把上游 attribution 当作产品版本或产品作者。
