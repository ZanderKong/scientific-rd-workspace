# v1.5 核心工作流实施进度

更新时间：2026-09-07。实施基线为 `main@93700a6` 与 v1.5 冻结基线。本文件记录当前工作树的运行事实；未完成门禁不记为通过。

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

## 当前验证

- 后端：隔离 PostgreSQL 上 44 项测试通过（含新增修复回归）；全新数据库从 0001 升级至 0021、旧 0006 加 legacy fixture 升级至 head 及 Alembic parity 均通过。Ruff check/format 通过。开发数据库仍未升级或清理。
- 前端：lint、typecheck、13 项 Vitest、Next.js production build 通过；BlockNote 0.54 Composer 相关 Chromium 闭环已执行，另有保存响应竞态的 mocked API 浏览器回归。
- 浏览器：六项 Chromium workflow 通过，构成为 5 项真实 API 流程、1 项 mocked 保存竞态；本轮新增零结果筛选回归并通过。CI 已改为运行除 no-seed 外的全部六项测试；真实 macOS IME、Linux 快捷键和完整套件结果仍待执行。

## 尚未关闭

- 真实 macOS 中文 IME 的 Chromium 与 Safari 人工证据；自动化 Unicode 输入不能替代这项门禁。
- 4 vCPU/8 GB/PostgreSQL 17 固定环境下的 1 万条记录与 100 Ref × 20 字段性能报告。
- P4 表格列分组与拖动、Experiment 中复用同一完整表格组件、Data occurrence 投影查询及更完整的批量 Sample UI。
- P5 独立历史详情页面、受保护来源更正/影响预览、View/Claim 历史 Artifact 的完整展示与反向查询 UI。
- P6 全量中英文文案、可访问性复核、CURRENT_STATE/API/MCP 文档整体切换与发布 CI。
- R1/R3：Data/View/Claim 双连接并发与故障注入、影响查询与显式更正仍未关闭；typed revision reference 的模型、迁移及主要写入路径已落地，仍需完整历史读写覆盖。
- R4：跨编辑器 Slot 边界、冲突草稿保留与正式 B 对照仍未关闭。
