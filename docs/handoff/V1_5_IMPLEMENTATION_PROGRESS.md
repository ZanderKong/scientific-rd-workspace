# v1.5 核心工作流实施进度

更新时间：2026-09-07。实施基线为 `main@93700a6` 与 v1.5 冻结基线。本文件记录当前工作树的运行事实；未完成门禁不记为通过。

本轮产品补齐以当前工作树为实施基线，覆盖对象/模板维护、Composer 快捷创建与 occurrence-local 字段、保存竞态修复、Sample 批量变量表、Experiment 受控表格和 Data/View 详情切片。它不是对 R0–R7 全部门禁的完成声明。

## 已实现

- P0：方案 A Scientific Composer、原位 PropertySlot、Ref identity/clipboard/Replace/Ghost、统一历史、IndexedDB 草稿与保存 generation。局部 Chromium 自动化已通过；完整交互矩阵、最小 B 对照和真实 macOS 中文 IME 仍待人工/原型门禁。
- P1：ScientificDocument/Occurrence 契约、Execution authoring identity、稳定 binding、顺序来源、revision manifest、聚合事务、幂等 replay、并发版本检查、Data subject 多来源及追加迁移 0013–0014；本轮补上显式 `authoring_kind`、binding 生命周期、通用对象 PATCH 记录边界、跨 scope 校验、自身 revision token、ChangeSet applied result replay、项目图锁和 typed revision references，并追加迁移 0020–0021。
- P2：连续 Sample Composer、服务器候选搜索、无 Process 保存、历史只读、复制新建和公开 ScientificRecord 写入契约。
- P3：可恢复 Data draft、稳定 Data identity、附件 client ID/hash 映射、description/raw Representation、manual 与 acquisition-document subject 分离、原子 finalize 与 replay；Data GET/PUT 已回读并复用 ScientificDocument/Occurrence，追加迁移 0015；本轮补上更正后的 acquisition subject 重算、稳定 Data token、附件幂等冲突和显式 origin 校验；producer 的显式 UI/完整 pin 仍未关闭。
- P4：统一 typed occurrence 表格查询、同 occurrence 条件、服务器排序分页、全结果集字段目录、URL 动态字段列、多 occurrence 有序值、跨分页 selection 与 Peek 路由状态；Sample/Data 表格已接入 required refs、字段筛选、排序和键盘列重排；Experiment Sample Picker 支持服务器搜索/分页与新建返回、metadata/reference 独立命令、100 行上限的原子幂等 Sample batch。
- P5：显式 Data revision/Representation View manifest、Artifact asset/hash、新来源生成 ViewRevision、metadata 不 repin；Claim 作者来源与类型化主来源分离、有限 context snapshot、evidence 增删、归档和 revision/context 展示、反向引用索引及来源页创建入口，追加迁移 0016–0019，保护 View/Claim 历史依赖并持久化 ChangeSet replay 结果。
- A11：Occurrence 投影为每个字段保留空值行，字段目录不再依赖已填写值；表格可区分未引用、已引用未填和重复 occurrence 的空位。
- A14 修复切片：Sample/Data occurrence 读取改为批量加载 target、Execution、binding 和顺序边，原有 100 Ref × 20 字段诊断从 503 条 SQL 降至 10 条；规定硬件的 p95 仍待测量。
- R0/R1/R2/R3 修复切片：空白 Sample、解绑恢复、来源清理、稳定 token、项目图锁、managed record 旁路和 typed revision reference 已加入正确行为回归；表格字段目录与零结果筛选状态已解耦。
- 历史读取切片：ProcessExecution、Data、View、Claim 均提供按明确 revision 的只读 API；Execution token 现在来自自身 revision，不随被引用对象改名漂移。
- 共享命令边界切片：新增 `scientific_record_service.lock_record_owner`，Sample/Data 的锁内写入统一先锁项目图再锁 owner 行；各自 DTO、Occurrence 和 provenance 规则仍由对应领域服务负责。
- 产品交互补齐切片：对象和 Process Definition 页面使用结构化字段/属性编辑器；`@`/`/` 候选提供项目内快捷创建并在原位置插入 Ref；Ref 支持模板字段和 occurrence-local 字段、类型控件、自动收起/编辑展开、Ghost、Replace 与保存后的身份回填。
- 批量与表格切片：Sample 编辑页和详情页提供基于固定 source revision 的 3–100 行变量表，逐行独立提交并支持响应丢失重试；RecordTable 增加独立候选目录、动态 occurrence 分组列、跨页选择、列键盘重排；Experiment 复用 Sample 表格并提供成员增删/排序。
- 详情展示切片：Data 使用共用 DetailBody 显示只读正文和 Representation；View 创建可明确选择 Data revision/Representation，历史 View revision 显示固定来源和现有 Artifact。

## 当前验证

- 后端：隔离 PostgreSQL 上 47 项测试通过（含对象/模板发布、字段目录、producer 和批量回归）；全新隔离数据库从 0001 升级至 0022，Alembic parity 通过。Ruff check/format 通过。开发数据库仍未升级或清理。
- 前端：format、lint、typecheck、14 项 Vitest、Next.js production build 通过；BlockNote 0.54 Composer、快捷创建、过程模板维护和批量变量表 Chromium 闭环已在 0022 隔离数据库执行。开发 API 未迁移到 0022，因此需要迁移的最新表格路径应在隔离数据库或部署迁移后复验。
- 浏览器：六项 Chromium workflow 通过，构成为 5 项真实 API 流程、1 项 mocked 保存竞态；本轮新增零结果筛选回归并通过。CI 已改为运行除 no-seed 外的全部六项测试；真实 macOS IME、Linux 快捷键和完整套件结果仍待执行。

## 尚未关闭

- 真实 macOS 中文 IME 的 Chromium 与 Safari 人工证据；自动化 Unicode 输入不能替代这项门禁。
- 4 vCPU/8 GB/PostgreSQL 17 固定环境下的 1 万条记录与 100 Ref × 20 字段性能报告。
- P4 更大规模表格性能、完整查询配置 URL 验证与 Data occurrence 投影的全流程仍待固定环境验收；本轮已交付受控表格和批量 Sample UI 的首个闭环。
- P5 独立历史详情页面、受保护来源更正/影响预览、View/Claim 历史 Artifact 的完整展示与反向查询 UI。
- P6 全量中英文文案、可访问性复核、CURRENT_STATE/API/MCP 文档整体切换与发布 CI。
- R1/R3：Data/View/Claim 双连接并发与故障注入、影响查询与显式更正仍未关闭；typed revision reference 的模型、迁移及主要写入路径已落地，仍需完整历史读写覆盖。
- R4：跨编辑器 Slot 边界、冲突草稿保留与正式 B 对照仍未关闭。
- 本轮尚未执行真实 macOS Chromium/Safari 中文 IME、规定硬件性能、完整 MCP/REST 新契约浏览器矩阵；这些仍是发布门禁，不以自动化通过替代。
