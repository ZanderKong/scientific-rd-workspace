# v1.5 审计修复与剩余交付计划

日期：2026-09-06。状态：已部分实施，尚未完成；当前缺口及复现证据见 [修复后补充审计](V1_5_REPAIR_FOLLOWUP_AUDIT_2026_09_06.md)。本文件基于用户批准的完整 Coding Plan、v1.5 冻结基线及 [项目审计 A01–A15](V1_5_PROJECT_AUDIT_2026_09_06.md)。

实施起点是 `main@93700a6` 加现有全部实现修改；不得仅检出原 main 后遗漏未提交代码。该计划重排修复顺序，不减少原 P0–P6 的产品范围。**第一验收目标仍是可靠的 Sample 闭环，全部完成仍以原 P6 全部门禁通过为准。**

## 1. 执行约束与交付方式

- 保留 PostgreSQL、七种 kind、现有领域服务、REST/MCP、文件存储、React Query、nuqs、BlockNote 0.54.0、Tiptap 3.30.6 及锁文件解析的 ProseMirror 版本，不另写一套系统。
- 先恢复正确性，再完善交互与性能。每个阶段分别提交、测试和记录证据；不再积累为一个大改动。
- 执行开始时记录当前 diff、untracked 文件和依赖锁文件校验值；把实施代码、用户原有文档修改与审计材料区分登记。建立可审查的修复分支及基线检查点，不做通用 reset、clean 或自动清库。
- Alembic 从当前 `0017` 继续追加；实际编号在实施时按线性依赖分配。不改写现有迁移以隐藏结构变化。
- 不建立旧 `steps` 客户端兼容层，不执行旧 v0.2/v0.3 科学记录回填。**当前新系统已产生的真实 revision/identity 仍需保留。** 新增引用索引可从已存在、可核验的 immutable manifest 重建；缺失的历史事实不猜测、不以最新值补造。
- 开发数据重建只能针对明确列出的隔离库和附件目录；若发现数据曾受 A02/A05 影响，先输出一致性诊断，不能把冲突对象静默修成当前目标。
- 只新增修复所需抽象，不引入事件总线、第二编辑内核、第二数据库或全局状态库。
- 本次计划编制只写文档；代码修改从后续实施开始。

## 2. 修复前明确的技术规则

### 2.1 记录命令与事务

新增 `scientific_record_service` 作为 Sample/Data 共用的领域命令入口，将现有 `_sync_record` 按验证、identity、变更计算、版本/投影四项职责拆出。Sample 服务和 Data draft 服务只负责各自 DTO 与业务约束，不再互相调用私有保存函数。

命令层负责事务；内部方法只校验和 flush，不自行 commit/rollback。REST、MCP、ChangeSet 使用同一命令。已有普通对象、模板、独立 Execution、Experiment、View、Claim 命令复用版本/幂等/锁规则，但不强行转换成 ScientificDocument。

统一处理顺序：

1. 规范化命令类型、scope、target、payload，计算幂等请求摘要。
2. 占用幂等 key；同 key 已完成则直接返回原响应，先于陈旧版本检查。并发占位使用唯一约束及 `INSERT … ON CONFLICT` 的等待语义，不通过整个 Session rollback 抹掉外层命令状态。
3. 获取 ChangeSet 锁（适用时）、scope 图锁（适用时）、owner 锁，以及按稳定类型/UUID 顺序排列的受影响行锁。所有改变同一图的入口采用同一顺序，项目锁必须在业务行锁之前获取。
4. 在锁内读取当前 revision、校验期望版本、归属、scope、字段和引用依赖。受影响集合不稳定时，在写入前重试整个事务，不临时倒序补锁。
5. 应用领域变化，追加不可变 revision、引用索引，更新当前投影。
6. 在提交前构造并验证响应 DTO，将响应与幂等结果、ChangeSet applied 状态一起保存，然后一次 commit。

### 2.2 版本 token

- ResearchObject 家族的并发 token 来源于其自己的当前 ObjectRevision；独立 Execution 来源于自己的 ExecutionRevision。token 包含版本身份，不仅依赖内容 hash，避免内容改回原样后旧 token 再次有效。
- View/Claim 的内容 revision 与编辑 token 分工明确：例如 View 修改标题会推进其编辑版本，但不会 repin Data 或创建新的来源/Artifact 内容版本。
- enriched DTO 中的当前标题、关联对象展示数据、关系反向查询结果不参加 token 计算。
- 新写入更新命令必须携带一个期望版本；REST 可接受 If-Match 或类型化 body 字段，两者同时提供必须一致。领域命令只接收归一后的一个版本值，禁止服务端代填“当前版本”。
- 缺版本返回明确的 `revision_required`；陈旧版本沿用 412 `stale_record`；依赖/幂等冲突用 409；字段验证用 422。均保留现有 error envelope，附 occurrence/field 路径或具体依赖，不向用户返回原始 SQL。

### 2.3 稳定 identity 与值权威

- 持久化 occurrence identity/mapping 与可重建查询投影分离，使用 `(owner_id, occurrence_id)` 和明确 kind 约束。Process 映射到唯一 execution；绑定关系保留可恢复身份和有效性，不因重建投影或解绑物理丢弃身份。
- Process 值只在 Execution，bound Object 值只在 binding，unbound Object 值在 canonical document 的 occurrence 数据中。投影只读、可重建、标记来源 owner revision，不作为编辑权威。
- 同一逻辑 Object binding 的 Replace 保留 binding ID，原子更改目标 identity、匹配的 revision pin、字段快照和值，追加 ExecutionRevision。不能只更改 revision 而保留旧 target；不能按 target/name 猜测复用其他 occurrence 的 binding。
- 跨 Process 改关联视为旧关联停用、新关联建立；旧关联身份保留以支持 Undo。恢复必须核验 owner/occurrence，不能凭客户端传入 execution/binding ID 抢占其他记录。
- 输入/context pin 校验“revision 属于目标”；output 只关联产物 identity，不 pin 本事务尚未生成的 owner revision，避免版本循环。
- 文档 schema 校验 Ref 类型、ID、顺序、occurrence kind 和 payload 一致性。API 不接受第二份互相矛盾的实际值；字段验证基于稳定 owner/key 或 local field ID、模板版本及历史快照，不能完全信任客户端 field definition。

### 2.4 历史引用保护

- 新增按**不可变来源 revision** 保存的 `revision_references`，与当前 ViewDataRef、ClaimContextReference 等当前查询投影分开。
- 使用类型化外键列指向 Object/Execution/View/Claim revision，及被引用的 revision、Representation、Asset/对象 identity；CHECK 约束保证每条引用恰有一个来源和一个目标。不使用只有 `kind + 任意 UUID` 的无外键引用作为保护依据。
- 创建来源 revision 时同步追加引用索引，来源 repin、归档、更新当前投影均不删除旧 revision 的引用。
- 删除对象、revision、Representation、Asset 的所有路径，包括物理文件清理和孤儿清理，复用影响查询。受保护内容保留，只允许归档/显式更正；禁止通过删父对象级联绕过。
- 查询依赖使用索引；不在每次保存时扫描所有正文/历史 JSON。重建索引只作为受控维护命令。

### 2.5 编辑草稿与提交恢复

- 一次保存固定 `submitted_generation + submitted_snapshot + command_id`。正文、Slot、binding、标题、状态、tags 的变化全部推进 generation。
- 响应成功总是更新基线及 occurrence→server identity 映射；只在没有后续编辑时清 dirty。identity map 随本地草稿持久化，但不属于可撤销的科学值；旧 Undo frame 仍通过 occurrence 解析当前稳定服务器身份。
- 合并响应不 replace editor document、不重建编辑器、不清 Undo；IndexedDB 用新基线写入尚未提交的剩余草稿，不能先无条件删除。
- 新建成功后立即认领返回 record ID。若尚有新输入，保持当前编辑会话并迁移草稿 key；后续保存是 update，不能重复 create。
- “保存并再建一份”只在用户目标 generation 已全部保存后进入复制页；保存期间产生新修改时保留当前草稿并提示仍有未提交内容，不默默带走或舍弃。
- base 不同的草稿作为冲突草稿保留；提供比较、保留/导出副本、用户选择恢复或丢弃。首版不自动合并实际参数或顺序。

## 3. 阶段与依赖

```text
R0 基线、回归与入口门禁
 ├─ R1 共享命令、版本、scope、幂等
 │    ├─ R2 occurrence/binding 生命周期
 │    └─ R3 不可变引用、删除保护、View/Claim pins
 └─ R4a 编辑保存与草稿恢复、A/B 原型证据

R1 + R2 + R3 + R4a → R4b Sample 完整验收
R1 + R2 + R3 + R4a → R5 Data 获取、更正、可恢复提交
R4b + R5 → R6 表格/Experiment/批量/View/Claim 产品收口
所有阶段 → R7 性能、完整 CI、发布验收
```

真实 IME 可在 R4a 期间执行；未通过前，后端及独立产品工作可继续，正式 Composer 写入口保持受控。

## R0：建立可复查基线，限制未验收写入口

对应：A15、A13；为全部审计项建立追踪。

交付：

- 固定当前工作树检查点和审计输入，建立 A01–A15 → 修复提交 → 回归用例 → 验收证据台账。
- 将现有诊断脚本转换成断言**正确行为**的回归：例如跨 scope 应拒绝、Replace 后两侧目标一致、历史来源删除应被保护。诊断材料继续保留，不能把“证明错误存在”的断言当作正式测试。
- 修复五处 Ruff format；CI 接入全部现有六个浏览器流程；快捷键改为平台适配，保留 macOS 与 Linux 的独立验证。
- 引入明确的实验入口配置：capabilities 区分“契约存在”“实验可用”“已验收启用”。普通 UI 写入口和 REST/MCP 创建/更新策略一致；默认保留现有记录只读访问。原型在隔离环境使用，不恢复旧步骤编辑器写新记录。
- R3 保护完成前，关闭尚无完整依赖检查的物理删除入口；归档和只读访问保持可用。避免修复期间继续破坏历史。

门禁：质量检查命令与 CI 完全一致；所有审计项有正确预期的用例或明确的人工/性能验证任务。修复分支允许展示尚未修好的失败用例，但生产入口不能宣称通过。

## R1：统一命令、版本、scope 和幂等

对应：A01、A07、A08、A12，以及 A09/A10 的基础设施。

主要改造：`services.py`、`sample_record_service.py`、`data_service.py`、`process_execution_service.py`、`experiment_record_service.py`、`view_service.py`、`claim_service.py`、`idempotency_service.py`、`change_set_service.py`、REST/MCP adapters。

交付：

1. 提取第 2 节定义的命令边界；去掉内部方法事务提交，禁止路由提前完成业务校验后裸写。
2. 为已进入 ScientificRecord 的记录建立显式 authoring 标识，不靠当前 tags 推断是否受管理。通用 Object PATCH、关系写入、删除与 ChangeSet 不能绕过文档边界；管理记录的元数据更改也要经过其记录命令。
3. 所有 Ref 无论是否绑定，都校验 target kind、scope、revision 所属和字段身份。全局对象可引用的既定规则继续保留。
4. 建立自身 revision token/current revision 读取；更新无版本请求不再被接受；同 header/body 版本不同必须拒绝。
5. 所有新契约 create/batch/finalize 及关系新增等可重试命令具有持久化 key。对需要处理响应丢失的 save/update 也提供 command id；同一请求 replay 返回原结果，不重新执行 mutation。
6. ChangeSet 保存 `applied_result` 和对应请求摘要；重复 apply 已成功的同一变更集返回原结果。业务、revision、结果与 applied 同事务；失败分类区分验证失败、版本冲突与可重试基础设施故障。
7. 锁规则覆盖所有图变化入口，包括独立 Execution、Data lineage、Claim evidence 环检查，不能只有 Sample 获取项目锁。

验收：

- 通用 PATCH 无法造成 document/occurrence 不一致；相同变更经服务、REST、ChangeSet/MCP 结果一致。
- 仅改目标对象名称或当前值，不改变引用方的 token；引用方自己的 metadata 更改使 token 前进。
- 两个独立 DB 连接对同 token 并发保存：恰一个成功，另一个为明确 stale，不能最后写入者静默覆盖。
- 同 key 并发创建恰有一条记录，返回同一结果；同 key 不同 payload 明确冲突；提交后响应丢失可 replay。
- 双连接同步屏障测试图竞争：分别合法但合并成环的两个命令不能同时成功。不得用两个共享 Session 的串行 TestClient 模拟并发。
- 注入执行/投影/revision/replay 各阶段故障，不能部分提交。

## R2：修复 occurrence、Replace、撤回和恢复

对应：A02、A04；依赖 R1。

交付：

- 按持久 identity mapping 解析 Execution，包括 retracted 的执行；不从当前查询投影判断是否新建。
- 实现 Object Replace 原子迁移 target/revision/field snapshot/value；同 key 但不同字段 owner 不自动作为相同字段，兼容值保留必须有明确映射与差异展示。
- Process 替换模板或换版本保留 execution identity，验证依赖并保存前后快照；新增执行必须新 occurrence。
- occurrence 投影可差量维护或重建，但不能因此删除稳定身份。active binding 与历史 binding 状态明确；唯一约束按实际有效性和归属建立。
- 未保存删除无副作用；已保存且无外部依赖时 retract；恢复时复用原 execution/binding ID 并追加新 revision。
- 删除 Process 后，同一编辑 transaction 清理本记录内部关联，把 Object 使用值迁回文档；服务端也从已锁定的原状态计算这项确定的连带变更。不能仅依赖前端清理，也不能猜测任意不存在的 Process。
- 删除绑定 Object 时校验 input/output 事实影响。外部受保护撤回调用 R3 的影响/更正协议；普通保存不得留下隐藏有效 binding。
- 文档 sequence 只修改自己的来源记录，保留 explicit 依据；在移除自身旧 sequence 后校验完整最终图，相同有效边按 source/target 去重展示。

验收：

- A→B Replace 后，occurrence、binding target 和 revision 一致；旧版本仍读取 A。
- 同对象两个 occurrence 的值和 ID 不串用；重排、解绑、改关联、Undo/Redo、重开保持各自身份。
- 删除→保存→Undo→保存复用原 execution ID，返回新 revision，不再触发唯一约束。
- 删除 Process 后留下的 Object 保留 occurrence 和值；Undo 恢复关联；外部依赖错误返回具体引用。
- 顺序反转不受旧投影误判；explicit 依据不被普通 save 删除。

## R3：历史引用保护与精确版本读取

对应：A05、A06、A07 的历史部分；依赖 R1，身份引用对接 R2。

交付：

1. 追加 typed revision reference 结构和删除约束，覆盖所有修订来源与对象/执行版本、Representation、Asset。
2. 追加/重建引用索引的维护命令：只使用可信已存 manifest；提供 dry-run、缺失引用和冲突清单。修复期间曾经存坏的 A/B 混合 pin 不按最新数据自动纠正。
3. View 保存验证 Representation 出现在**指定 Data revision** 的 manifest；资产验证可用性、归属、hash 和受支持类型。重复/无效/跨 scope refs 统一拒绝。
4. View metadata 更新保持原 Data/Representation/Artifact pin；显式改变来源或 Artifact 创建新 ViewRevision。历史读取只走指定 manifest，不从当前对象“补齐”科学值。
5. Claim primary/context/evidence 分开。Context 按基线仅保留直接成员；从 View 创建时还固定其 Data revisions 的 subjects；Peek 场景保存明确的 Experiment revision。statement 更新保留 context，refresh 为显式命令。
6. 当前 reverse lookup 与历史 reverse lookup 分开支持。历史索引不随当前 source/context 替换而丢失。
7. 提供版本化影响预览与显式来源更正命令：提交时重新锁定、核对版本和依赖集合。更正只创建新的当前事实，旧版本不重定向。自身历史引用不阻止本记录普通更正，但仍阻止物理删除历史内容。

验收：

- r1 不可与 r2 后新增 Representation 混用。
- View/Claim repin、context refresh、归档后，旧来源/Artifact 仍可读且受保护。
- 对象删除、revision 删除、Asset 删除、父对象级联及清理任务都不能绕过引用保护。
- 当前来源数值更正后，历史页面与 API 返回旧数值、旧 revision 和原文件 hash。
- 影响预览后被其他命令新增依赖，提交更正时重新检测，不能套用陈旧预览。

## R4a：修复编辑保存、恢复协议和原型证据

对应：A03、A13、A14 的编辑器部分。可从 R0 后开始；使用 fixtures/mock 验证，再与 R1–R3 联调。

交付：

- 建立共用的 editor save session：generation、提交快照、command id、基线、identity map、dirty/conflict、持久化草稿。不建新的全局状态库。
- 按第 2.5 节实现普通更新、新建、保存并再建一份、超时重试、refetch、语言切换和 IndexedDB 冲突恢复。草稿格式校验/升级失败要保留可导出的原内容。
- 尽量将 identity 回填放在非历史元数据中；需要 PM transaction 时显式不加入用户编辑历史，并测试其与旧 Undo frame 的交互。
- 修正 ArrowLeft/Right：字段内遵循原生 selection；当前 Ref 末端进入紧邻正文，不跨正文直接跳到另一个 Ref。Tab 在本编辑器规定的 Slot 顺序内移动，不查询全页面其他编辑器的 Slot。
- 内部粘贴重映射整个片段的 block/occurrence IDs；孤立 Object 的外部 binding 不随复制进入新文档；可确定的同文档剪切移动保留 ID。删除、Replace、binding 意图参与同一历史。
- 完成最小 B 父 Ref/Slot 子节点对照，仅用于技术比较。A/B 使用同一字段身份、剪贴板、codec fixtures，保留事件/Selection/transaction/NodeView 生命周期日志。
- 执行全部 13 类交互、composition 输入/取消/选词、保存期间编辑与响应回填，以及 Chromium/Safari 的真实 macOS 中文输入法测试。浏览器 Unicode fill 不能替代 IME。

门禁：无可复现丢字、串身份、历史分叉、selection 跳转错误或 round-trip 丢值。真实 IME 未执行则 R4a 不记为完成；A/B 公开扩展排查证据满足原 fallback 条件时才提产品变更，不自行降级体验。

## R4b：恢复 Sample 第一完整闭环

对应原 P2；依赖 R1、R2、R3、R4a。

- 模板/对象名称、tags、自身属性、默认使用字段、顺序和发布版本维护完整；字段历史不随模板更新改写。
- 候选服务器搜索与分页覆盖项目及全局 scope，超过 50/100 条仍能定位候选；Process 可显式选版本。
- 补 Process 侧关联入口及“产出当前 Sample”的显式意图；不推断最近 Process/最后一步 output，不填写未知实际发生时间。
- 保存差异、依赖错误、当前编辑/历史只读页面共用正确版本读取；历史切换不丢 dirty draft。
- 复制新建重映射 block/occurrence，清除 execution/binding 持久 ID、output、Data input、source View、lineage、完成状态和实际时间。

门禁：真实 API＋浏览器完成“新建 → 原位输入 → 保存期间继续输入 → 再保存 → 重开 → Replace → 撤回/恢复 → 旧版本 → 复制新建”。无 Process Sample 同样完整可用。通过后才能标记第一实施闭环完成并启用正式 Sample Composer。

## R5：修复 Data 获取、更正与可恢复提交

对应：A09、A10；依赖 R1–R3 及 R4a，独立 Data draft 工作可提前开发但不提前验收。

交付：

1. Data 的 read/write DTO 包含 ScientificDocument、enriched occurrences、revision/identity map、Representation 和 subject/provenance manifest；现有 Data 更正复用共用记录命令。Execution 查询区分“本记录 authoring 的获取执行”与“明确生产该 Data 的 producer”。
2. 类型化的 input Data、显式 output 当前 Sample/Data 和 producer 选择；保持一个有效 canonical Data producer。无 Process 不造虚拟执行，也不自动选最后一个 Process。
3. 从 Sample 入口创建 Data 写 manual subject；明确 subject role 的文档 occurrence/binding 写 acquisition source；producer subject 从固定 execution revision 读取。来源各自有稳定 ID/pin，去掉一种来源不删除其他依据。
4. Data revision 固定 producer execution revision、input Data revisions、subjects、Representation/Asset manifest。外部 Execution 更正不自动推进已固定的下游 Data；本 Data 获取文档内的显式来源更正只推进本 Data，新旧下游各自保留 pin。
5. 持久化 Data 提交状态：editing、uploading/failed、validated、finalizing/unknown_result、finalized；pending command 的 payload 和 key 跨刷新保留。
6. Finalize 首先检查/重放已提交命令；unknown_result 状态不得先 PUT 草稿。GET 返回 finalized_result 时直接恢复成功状态和详情入口，不重新生成 Data identity。
7. 文件选择即分配稳定 client_attachment_id；分开记录 bytes 上传和附件关联结果。服务端上传/关联以该 ID 幂等；同 ID 不同文件摘要拒绝。失败项可重试/明确移除，未上传 File 刷新后要求重选并核验大小/hash，不丢掉失败状态。
8. Finalize 不能静默跳过 unresolved 附件；origin 必须明确选择已有 Representation/附件。没有文件时允许明确选择 description 等可用表示；无可用表示时保留空 origin，不任意猜测。
9. 最终文件可用性、大小/hash 校验按既有大小上限执行；文件 IO 与 SQL 事务分离。验证结果绑定不可变 Asset metadata，失败不发布 ready Data。
10. 复用 CSV/XLSX preview/commit，在 raw 成功保存后增强解析；失败页面明确保留原始成功记录，支持重试与恢复。

验收：无 Process subject、多来源 subject、显式 producer/input、获取正文回读/更正、附件部分失败、刷新恢复、上传/关联/最终响应丢失、并发 finalize、错误 origin、来源更正后下游旧 pin 均通过。

## R6：表格、Experiment、批量与追溯界面收口

对应：A11、A15 的产品部分，以及原 P4/P5 未完成项；依赖 R4b、R5，历史界面同时依赖 R3。

交付：

- 用字段定义投影生成目录，覆盖已引用未填字段；字段身份包含 target owner/key 或 local field ID。值按 occurrence 返回，保留空位，区分未引用、已引用未填和有值；类型化字段过滤不得跨 occurrence 拼接。
- 抽出受控 `RecordTable`/`SampleTable` 共用组件，Sample、Data、Experiment 共用查询协议。Experiment 默认成员属性并集，required_refs 为空，不因异构配方丢行。
- 完成 required refs、字段筛选、服务器排序、列组/组内顺序、拖动及键盘替代、跨页选择与隐藏选择数；查询先覆盖全范围再分页。继续默认 50、上限 200、ID 破除排序平局。
- URL 使用带 schema version 的查询/展示配置；非法配置可恢复。切 scope 清 selection；默认 URL 不分享 selection。Peek Back 恢复查询、滚动和选择，详情与完整页共用 DetailBody。
- Experiment Picker 增加搜索/分页、选择与返回上下文；成员 add/remove/reorder 和 metadata 分开。手动行序限不超过 200 成员，其外按服务器排序。
- 批量 Sample UI 固定 source revision 和 client_row_id，复用复制 codec，上限 100 行；服务端整批验证/事务/幂等，任一行失败不部分创建。
- View/Claim 的当前及历史详情显示固定版本来源与 Artifact；Claim evidence 编辑、归档、来源/context 反向查询、显式更正与 context refresh 可用；从来源页创建，全局 Claim 列表不提供无来源新建。
- 同步 REST/Pydantic/TypeScript/capabilities/MCP schemas 与 proposal：包括 Data 草稿/finalize、更正、批量和 Experiment reference 操作。MCP 不复制业务转换逻辑，仍由同一命令完成。

门禁：跨页/空值/异构比较、Picker 第 51 条后候选、离开创建再返回、批量失败回滚、Peek 恢复、旧 View/Claim 的数值和文件都经过真实 API/browser 验证。

## R7：性能、完整 CI 与发布验收

对应：A14、A15，原 P6；所有功能阶段通过后收口。

交付与测试：

- 后端批量获取 target、Execution/binding、revision 与 subject，消除逐 Ref 查询；Sample enriched read 的 SQL 数量需受查询批次数控制，而不是随 Ref 数线性增长。比较 1/10/100 Ref 的 query count，允许为数据库参数上限做明确分批，不用脆弱的固定 SQL 条数断言代替性能测试。
- 前端逐 transaction 更新必要的 occurrence 信息，避免每次键击完整 canonicalize/clone；保存与持久化时才做全量 codec。保持 BlockNote 实例、Slot 焦点和 undo history，测量 NodeView mount 次数。
- 在固定 4 vCPU、8 GB、SSD、PostgreSQL 17、本地网络、production build 下，项目混合数据 1 万条；最大文档 100 Ref × 20 字段。记录数据生成参数、冷热缓存、样本量和原始分位数。
- 验收维持原目标：Slot 输入/焦点 p95 ≤100ms，首次可交互 ≤2s，常规查询 p95 ≤500ms，排除文件传输的保存 p95 ≤1s。本机单次 0.126s/503 SQL 只作修复前诊断基线。
- CI 必须运行 strict lint、format、typecheck、Vitest、生产 build、完整 PostgreSQL/API、双连接并发/故障注入、MCP stdio/HTTP、六条原浏览器流及新增回归。Linux 快捷键自动化与 macOS 真 IME 留存各自证据。
- 空库到新 head、`0017 → 新 head`、Alembic metadata parity 通过。旧 `0006 → 0012` 历史迁移价值保留；升级新契约不增加用户已取消的旧数据回填任务，新阶段库前置条件单独说明。
- 所有可达文案接入中英文同构 key tree；补 loading/error/empty、键盘可达性、错误定位与稳定历史 URL。
- CURRENT_STATE、API、MCP、原型报告与实施台账按实际证据更新；旧过强结论明确标记被本次审计/修复结果替代。

发布门禁：A01–A15 各有关闭证据；原 P0–P6 产品场景全部可用；真实 IME、并发、历史读取、性能和 CI 都通过。未执行项不标通过，不能用静态类型检查替代业务验收。

## 4. 审计项覆盖表

| 审计项 | 主修复阶段 | 必须留存的证据 |
| --- | --- | --- |
| A01 聚合绕过 | R1 | Object/关系/ChangeSet 入口拒绝旁路；记录一致性断言 |
| A02 Replace binding 错目标 | R2 | occurrence/binding/revision 同目标，旧版本仍读 A |
| A03 保存时输入/草稿丢失 | R4a | 延迟保存两次请求、IndexedDB 恢复、Undo/新建身份回填 |
| A04 撤回/恢复失败 | R2 | 多次删除/恢复保存使用同 identity，内部值迁移正确 |
| A05 历史来源删除 | R3 | 当前 repin 后所有历史资源受保护且可读 |
| A06 revision/Representation 混配 | R3 | 历史成员校验拒绝错配；正确来源保存成功 |
| A07 token/并发 | R1 | 关联对象更改不变 token；双连接同版本竞争 |
| A08 unbound scope | R1 | project/global、bound/unbound 同规则 |
| A09 Data 来源闭环 | R5 | enriched 回读、manual/acquisition/producer、下游 pin 不漂移 |
| A10 finalize/上传恢复 | R5 | 丢响应、刷新、部分失败、同 key 重放完整浏览器测试 |
| A11 空字段/空 occurrence | R6 | 全空字段目录和多 occurrence 空位查询/显示 |
| A12 ChangeSet replay | R1 | success 后重试同结果，不新增业务记录/revision |
| A13 原型与编辑边界 | R0/R4a | A/B 比较、事件日志、真 IME/Selection/历史证据 |
| A14 性能 | R7 | SQL 规模曲线、前端交互测量、规定环境原始报告 |
| A15 CI/声明/剩余入口 | R0/R6/R7 | CI 配置/结果、产品闭环、阶段提交和证据台账 |

## 5. 阶段启用与回退

- R0 后仅隔离环境启用新写契约。R1–R3 可独立交付后端基础，但不提前宣布 Sample 已验收。
- R4b 通过启用 Sample；R5 通过启用 Data；R6 各完整能力经验证后启用，capabilities 与实际 UI/MCP 保持一致。
- 某阶段回归失败，关闭对应新写入口并保留新格式只读访问，优先前向修复；不把新文档交给旧步骤编辑器，不回滚删除已生成 revision。
- 数据、IME 或环境证据受阻时，继续无依赖工作并记录阻断；不得擅自跳过门禁或降低原位输入目标。

第一组实际修复应交付 **R0＋R1 的聚合边界/scope/自身 token 与回归基础**，同时开始 R4a 的保存和草稿缺陷修复。基础完成后按 R2/R3 依赖推进，避免先补大量 UI、再重改底层契约。
