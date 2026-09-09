# 五栏工作台实施记录

日期：2026-09-09
分支：`codex/workspace-five-sections`

## 已实现

- `/dashboard` 默认进入样品；侧栏顺序固定为样品、分析、数据、论点、资源。
- 旧实验列表重定向分析；旧实验详情显示记录不存在并提供分析入口；旧新建实验路由重定向分析。
- Research Object 增加 `resource_role`（material/equipment/process），新增资源页统一列出原料、设备和过程；过程仍委托过程定义及版本服务。
- `@` 搜索同时返回已保存样品和资源；无匹配只提供新建原料、设备、过程，不提供新建样品。样品候选保留正式记录资格。
- Sample 顶部移除状态、标签和 producer 常驻控件；Data 的低频类型设置移入“更多内容设置”。编辑器外观改为舒展单栏，保留 BlockNote 0.54.0。
- ScientificDocumentV2 复制时重映射 property occurrence ID；属性解析保留全半角原始值；`@data`/`@claim` 语义行以稳定 ID 物化独立实体并同步当前 Sample 主体/上下文，重复保存复用实体和版本映射。
- Claim primary source 允许为空；新增 0024–0027 Alembic 迁移，未带明确角色的历史对象保持未分类。

## 验证证据

- 开发库已执行 `alembic upgrade head`，当前 head 为 `0027_clear_unclassified_roles`。
- 隔离 PostgreSQL：`TEST_DATABASE_URL=...scientific_rd_test_product_completion uv run pytest -q --disable-warnings --maxfail=1`，56 passed。
- API：`uv run ruff check app tests` 通过。
- Web：`npm run lint`、`npm run typecheck`、`npm test -- --run`（21 tests）和 `npm run build` 通过。
- 本地服务：API `http://127.0.0.1:8000`，Web `http://127.0.0.1:3000`。浏览器已检查分析页、资源页、五栏导航、样品编辑器及 `@水` 候选；候选显示原料与新建原料/设备/过程，未显示新建样品。

## 明确未完成或待人工验收

- 真实 macOS 中文 IME、Safari/Chromium 双浏览器、剪贴板粘贴和长文档压力仍需人工验收；本轮只验证了浏览器 composition 相关逻辑和可操作候选菜单。
- 分析页当前复用既有 View 列表与编辑路由；完整的混合样品/Data/Claim 手动集合、动态筛选集合和固定历史快照仍需后续阶段扩展。
- 级联删除确认与一次 Undo 的完整浏览器闭环、保存 result-unknown 恢复、批量复制身份回读和 MCP 全矩阵仍需补充。
- 未执行开发库全量重置；只在核实的本项目开发库上升级迁移并保留现有演示数据。未操作其他数据库、附件目录或浏览器 origin。
