# 项目整体审计：v1.5 当前工作树

审计日期：2026-09-06。范围：`main@93700a6` 加当前全部 tracked/untracked 实现；不是只审查已提交的 main。依据：用户批准的 P0–P6 Coding Plan、v1.5 冻结基线、BlockNote 原型报告及实际代码。未修改业务代码，新增的只有本报告和诊断脚本。

## 总体判断

**当前是已有多个可运行场景的开发实现，尚不具备 v1.5 第一闭环的验收条件。** 阻断不仅是真实中文 IME、性能证据和剩余 UI：聚合边界、binding 目标一致性、保存期间编辑、删除后恢复、历史引用保护、Data 来源和版本 token 都存在问题。

之前“代码门禁已清零”“P1/P2 已实现可靠基础”的表述过强，需要纠正。现有测试的通过仅证明已覆盖的路径；本次新增 12 个 API 缺陷诊断用例全部复现了预期问题，另用 Chromium 复现了保存期间继续输入时的旧 token 重用。诊断测试通过表示**缺陷存在**，不是功能通过。

不建议另起一套系统，也没有证据要求 fork BlockNote。七种 kind、PostgreSQL、领域服务、REST/MCP 共用实现、不可变 Representation 和现有编辑器技术栈仍可保留。应先补齐记录命令的边界和历史模型，再扩大入口。

## 证据与验证范围

本轮实际执行：

- 隔离 PostgreSQL `scientific_rd_test`：12 个针对性缺陷复现；1 个 100 Ref × 20 字段查询诊断。每个用例使用仓库原有独立测试 schema fixture。
- Chromium：对当前 Sample 页面拦截全部 API，控制保存响应时序，观察两次真实前端请求；不写入真实记录。
- 当前 CI 使用的 `ruff check app tests scripts alembic/versions` 通过；`ruff format --check` **失败，5 个文件未格式化**。
- 本地安装树核对：BlockNote 0.54.0，直接 Tiptap/PM 3.30.6，检查到的依赖树已 dedupe。

之前的 29 个后端测试、13 个 Vitest、6 个 Chromium 场景和生产构建是上一轮运行记录，本轮没有将它们重复执行，也不把它们当作本次缺陷的反证。本轮没有执行真实输入法、Safari、双连接并发竞争或规定硬件环境下的 p95 验收。

## 必须优先修复的缺陷

### A01 · P1 · 通用 Object PATCH 绕过 Scientific Record 边界【API 已复现】

位置：[`services.py:238`](../../api/app/services.py#L238)、[`objects.py:400`](../../api/app/routers/objects.py#L400)。

创建带两个 Ref 的 Sample 后，通过 `PATCH /objects/{sample_id}` 提交 `content_document: []`，接口返回 200。随后 Sample GET 返回空正文，却仍有两个 occurrence 和对应执行。通用 PATCH 没有检查文档归属，也没有同步 projection/manifest；ChangeSet 的 `update_research_object` 同样调用这条路径。

影响：同一条科学记录出现互相矛盾的正文和执行事实，绕开计划要求的唯一聚合命令。修复应放在共享服务边界，并覆盖 Sample/Data，不应只隐藏 UI。

### A02 · P1 · Object Ref Replace 产生错误 binding 目标【API 已复现】

位置：[`process_execution_service.py:280`](../../api/app/process_execution_service.py#L280)、[`scientific-composer.tsx:143`](../../web/src/features/workspace/scientific-composer/scientific-composer.tsx#L143)。

把已绑定对象 A 的 Ref 替换为 B，前端清空 binding ID，但保留 occurrence ID。后端按 authoring occurrence 找回 A 的 binding 后，没有再次校验或更新 `research_object_id`，却把 B 的 revision 写入该 binding。

复现结果：保存返回 200；ObjectOccurrence 指向 B，ProcessExecution 的 object binding 仍指向 A。它不是简单显示错误，而是对象 identity/revision pin 发生混配。需要明确 Replace 的稳定身份策略，并原子维护目标、revision、实际值和历史。

### A03 · P1 · 保存期间继续输入会保留旧基线，草稿还可能被删除【Chromium 已复现＋代码确认】

位置：[`sample-composer.tsx:163`](../../web/src/features/workspace/sample-record/sample-composer.tsx#L163)、[`sample-composer.tsx:77`](../../web/src/features/workspace/sample-record/sample-composer.tsx#L77)。

只有 generation 未变时才合并 `saved.record_sha256`。用户在等待响应时继续输入，第一次保存成功后，下一次请求仍提交旧 token。本轮浏览器记录：第一次 base 为 `aaaa…`，服务器响应为 `bbbb…`，第二次 base 仍为 `aaaa…`。

此外，成功分支无条件删除 IndexedDB 草稿；重开时只要本地 base 与当前 base 不同也直接删除草稿。标题/状态/tags 修改不增加 generation，保存期间更改这些字段可能被错误标为 clean。新建成功后的跳转也不保留请求发出后的输入。

应始终合并服务器基线和身份，同时保留较新的本地编辑；冲突草稿必须可恢复，不应按版本不同自动丢弃。

### A04 · P1 · 已保存删除的 Process 无法按原身份恢复【API 已复现】

位置：[`sample_record_service.py:397`](../../api/app/sample_record_service.py#L397)、[`sample_record_service.py:426`](../../api/app/sample_record_service.py#L426)。

删除 Process 并保存后，执行保留为 retracted，当前 occurrence 行被删除。恢复原 occurrence 并保存时，只查询当前 occurrence 来找 execution，找不到就新建，撞上 `(authoring_record_id, authoring_occurrence_id)` 唯一约束，返回 409。

另一个复现：只删 Process、保留其已关联 Object Ref，保存返回 422 `binding references an unknown Process occurrence`。编辑器删除处理没有清理剩余 Object 的内部关联。

需要从保留的 authoring identity 恢复原执行，并把删除引起的内部解绑及值迁移纳入同一事务/编辑器历史。

### A05 · P1 · 历史 View 来源不受持续保护【API 已复现】

位置：[`view_service.py:97`](../../api/app/view_service.py#L97)、[`models.py:963`](../../api/app/models.py#L963)、[`objects.py:423`](../../api/app/routers/objects.py#L423)。

View v1 引用 Data A 的 revision，随后更新 View 来源移除 A，再删除 A：删除成功返回 204。旧 ViewRevision 仍有 A 的 Data revision ID，但 Data 身份及其来源内容已不可读。

当前外键主要保护 View 的当前引用，历史 manifest 只是 JSON；没有计划中的通用、按不可变 revision 维护的引用保护索引。Claim 的 context reference 也按当前记录整批替换，不能替代历史保护。Artifact 历史引用也需同样审查和保护，不能只依赖当前 ViewState 或当前对象附件链接。

### A06 · P1 · View 能把旧 Data revision 与后来新增的 Representation 拼成无效 manifest【API 已复现】

位置：[`view_service.py:111`](../../api/app/view_service.py#L111)。

服务只验证 Representation 属于同一 Data，没有验证它存在于指定 Data revision 的 Representation manifest。先固定 Data r1，再新增 Representation R2，提交 `r1 + R2` 创建 View 仍返回 201。

必须按指定版本验证 Representation 成员资格，不能把“同一对象”当作“同一历史版本”。

### A07 · P1 · 聚合 token 会随关联对象变化，并发检查没有统一放入锁内【部分 API 已复现；并发部分静态确认】

位置：[`sample_record_service.py:238`](../../api/app/sample_record_service.py#L238)、[`view_service.py:84`](../../api/app/view_service.py#L84)、[`objects.py:1152`](../../api/app/routers/objects.py#L1152)。

Sample hash 包含 enriched occurrence 的当前 Object 内容和 Execution 输出。仅重命名被引用对象，Sample 自己没有新增 revision，token 却发生变化；此现象已复现。View/Claim/Data 的 hash 也含关联对象的当前 DTO。

另外，无 `If-Match/base_record_sha256` 的 View 更新返回 200。Data、Claim、View、独立 Execution 等契约仍存在可选 token、路由先读后写或服务不锁 owner 的路径；Experiment 的拆分命令也未把检查放入记录锁保护范围。只有 Sample 命令中的行锁和项目锁不能证明全系统并发正确。

本轮未运行双连接竞争，不能宣称某种具体竞争结果已经复现。修复方向是采用聚合自身不可变 revision token，统一在领域命令锁内校验，并补真实并发测试。

### A08 · P1 · 未绑定 Object Ref 可以跨项目保存【API 已复现】

位置：[`sample_record_service.py:370`](../../api/app/sample_record_service.py#L370)。

P1 项目中的 Sample 引用 P2 项目对象，只要不绑定 Process，就能保存成功。`_sync_record` 检查 target kind 和 revision 所属对象，却未检查 target scope；绑定后才经过 Execution binding 的 scope 检查。

同一 Object Ref 的合法性不应取决于是否绑定。所有 occurrence 都要在共享命令入口校验项目/全局可见性。

### A09 · P1 · Data 获取正文尚未形成完整的写入—回读—固定来源闭环【API 复现＋代码确认】

位置：[`data_draft_service.py:223`](../../api/app/data_draft_service.py#L223)、[`sample_record_service.py:339`](../../api/app/sample_record_service.py#L339)、[`data_service.py:135`](../../api/app/data_service.py#L135)、[`process_execution_service.py:396`](../../api/app/process_execution_service.py#L396)。

finalize 复用私有 `_sync_record`，可以生成文档及 authoring Execution；但 DataRecordOut 没有 enriched occurrences，也没有对应的现有 Data ScientificRecord 更正接口。复现中带 Ref 的获取正文成功保存，但正常 Data DTO 不含 occurrence，Data execution 查询返回空列表，因为仅按 Data binding 查询。

这里不是要求自动把最后一步设为 producer：v1.5 要求显式选择。当前 occurrence 契约和 Composer 都没有“产出当前 Data”或 input Data 的完整提交方式，`_execution_payload` 一律写 `data_bindings=[]`。

subject 语义也不符基线：从 Sample 创建的 Data 被记作 acquisition_document，前端 `subject_ids` 恒为空；文档里的明确 subject Object binding 没有独立提取为 acquisition subject。既有 `_sync_provenance` 仍在外部 Execution 更新时重新同步下游 Data 并建 revision；Data manifest 未完整固定 producer execution revision/input Data revisions。

### A10 · P1 · Data finalize 响应丢失后，前端无法进入已有 replay 路径【代码路径确认】

位置：[`data-composer.tsx:148`](../../web/src/features/workspace/data-composer/data-composer.tsx#L148)、[`data_draft_service.py:199`](../../api/app/data_draft_service.py#L199)。

后端支持以同 key replay finalize 结果；前端每次点 Finalize 却先 `saveDraft()`。若第一次 finalize 已成功但响应丢失，第二次先 PUT 已 finalized 草稿，被拒绝，永远到不了后端 replay。刷新又会生成新的 finalize key，加载 finalized 草稿也未跳转到 finalized_result。

上传错误目前只保留文件名和错误文本；重试重新生成 client attachment ID，没有稳定的失败项映射。主 origin 未选择或选错时，后端静默取第一附件，违反用户明确选择要求。需要把 begin/upload/finalize 的身份与恢复状态作为可持久化流程，而不仅是组件 useRef。

## 其他重要问题

### A11 · P2 · 字段目录只发现已填值，重复 occurrence 的空位丢失【API 已复现】

位置：[`record_table_service.py:102`](../../api/app/record_table_service.py#L102)、[`sample_record_service.py:104`](../../api/app/sample_record_service.py#L104)。

字段目录从 OccurrenceFieldValue 推导，空值不生成该表记录。引用了带 Reading 字段的 Process 但未填写任何值，查询 total=1，columns 却为空。用户无法从列选择器选中该字段。

重复 Ref 的返回数组也跳过未填 occurrence，现有测试甚至断言只返回 first/third。虽然 ordinal 保留了部分顺序线索，UI 的 `join` 不显示中间空位，不能完整表达多次使用。目录应来源于字段快照/定义投影，展示值保留 occurrence 级存在/未填状态。

### A12 · P2 · ChangeSet apply 不重放成功结果，创建幂等覆盖也不完整【API 已复现＋代码确认】

位置：[`change_set_service.py:241`](../../api/app/change_set_service.py#L241)、[`objects.py:1128`](../../api/app/routers/objects.py#L1128)。

同一 ChangeSet 第一次 apply 成功，第二次返回 422 `ChangeSet cannot be applied from applied`；没有保存和重放原结果。它防止了重复应用，但不满足“成功响应丢失仍可重试拿回结果”。

Sample/batch/draft begin 的数据库幂等占位方向正确，但 View/Claim 创建仍直接调用服务，没有要求 key 或统一 replay；独立 Execution/Data 创建的 key 仍可省略。不能把局部实现记为新契约全面覆盖。

### A13 · P2 · P0 门禁未完成，正式入口已启用；编辑器还有未覆盖边界【静态确认】

位置：[`BLOCKNOTE_0_54_PROTOTYPE_REPORT.md`](../current/BLOCKNOTE_0_54_PROTOTYPE_REPORT.md)、[`ref-spec.tsx:69`](../../web/src/features/workspace/scientific-composer/ref-spec.tsx#L69)、[`scientific-composer.tsx:111`](../../web/src/features/workspace/scientific-composer/scientific-composer.tsx#L111)。

真实 macOS IME/Safari 尚无证据；计划要求的最小 B 对照、NodeView/Selection/transaction 事件证据未交付。报告把 B 改成 A 阻断后才实现，与已批准 P0 交付范围不同。当前 capabilities 直接开启 inline slots，Sample 已全面替换，未遵守“原型门禁通过再正式接入”。

Slot 左右箭头复用全 document 的 `focusSibling`，可能跳过 Ref 中间的正文直达下一个 Ref；不是按当前 Ref 内字段和正文边界导航。粘贴孤立已绑定 Object 时也可能保留当前文档不存在的 process occurrence。以上未做浏览器最小复现，应补覆盖，不应继续写“全部交互通过”。

这些是实现/证据问题，不构成自动触发产品 fallback 或 fork BlockNote 的理由。

### A14 · P2 · 存在明确 N+1 和整份编辑草稿遍历，正式性能不能判定通过【SQL 实测＋静态确认】

位置：[`sample_record_service.py:172`](../../api/app/sample_record_service.py#L172)、[`scientific-composer.tsx:111`](../../web/src/features/workspace/scientific-composer/scientific-composer.tsx#L111)。

本轮本机诊断：**100 Ref × 20 字段的单次 Sample GET 发出 503 条 SQL，响应 489,316 bytes，耗时约 0.126 秒。** 这是本机隔离库单次观测，不是指定环境、1 万条项目或 p95 数据。SQL 数量足以确认 N+1，需要批量加载。

每次 editor change 都读取整份 document、更新 React blocks，并在 `canonicalizeDocument` 中 structuredClone/遍历全部 Ref；父页面也更新 blocks。它不等同每次重建编辑器，但存在随文档规模增长的逐键成本。没有 2,000 Slot 的交互测量，不能认为 p95 输入目标已满足。

### A15 · P2 · 发布 CI 与测试声明不匹配【命令实测＋配置确认】

位置：[CI 配置](../../.github/workflows/scientific-workspace-ci.yml)、[当前状态说明](CURRENT_STATE.md)。

- 实际 CI 后端命令要求 Ruff format；本轮执行失败：`0017_claim_provenance.py`、`claim_service.py`、`models.py`、`routers/objects.py`、`test_v03_domain_correctness.py` 共 5 文件。此前只通过 Ruff check 不能等同后端质量门禁通过。
- CI 浏览器任务仍只列出 first-run、sample-composer、golden，新增 data-composer、sample-table、workflow-v15 未接入。
- sample-composer 在 Ubuntu CI 使用硬编码 `Meta+z/c/v`，未按平台选择 ControlOrMeta；存在跨平台执行风险，本轮未在 Linux 复现。
- 新后端测试没有真实双连接并发、同 key 竞争、图成环竞争；故障注入只覆盖部分 ChangeSet 回滚。不能凭 29 个串行用例宣布并发门禁通过。
- 当前所有重构仍堆在 main 的未提交工作树，没有计划要求的阶段性可审查变更。CURRENT_STATE/原型报告对部分能力的描述超出实现及证据。

## 阶段完成度重新核定

| 阶段 | 可保留的成果 | 仍阻断验收的内容 |
| --- | --- | --- |
| P0 | 锁定依赖、A 原位输入、部分自动交互 | 真实 IME/Safari、B 最小对照、完整边界/日志证据、正式入口门禁 |
| P1 | 追加迁移、Sample 行锁、幂等占位、基础快照 | 聚合绕过、稳定身份恢复、通用历史引用保护、版本 token、锁内并发与 schema 严格校验 |
| P2 | 连续编辑、搜索、基础保存/历史/复制 | Replace binding、保存 generation、冲突草稿、模板/字段完整维护、候选分页、显式 output 和删除闭环 |
| P3 | draft identity、附件上传、raw/description finalize | 丢响应恢复、现有 Data 更正/回读、subject 语义、producer/input pins、解析后续闭环 |
| P4 | SQL 筛选/排序/分页基础、Sample 列选择、Peek、批量 API | Data 查询表、空字段目录、筛选/排序 UI、分组与列重排、可复用 Experiment 表、批量创建 UI |
| P5 | 显式 View refs、Artifact hash、Claim 主来源/context | 历史引用保护、版本成员验证、完整历史只读展示、evidence/归档/来源更正 UI、View context 的 Data subjects |
| P6 | 部分文档、构建和本机自动测试 | 完整 CI、真实并发/故障、IME、性能、可访问性与双语、阶段提交和门禁记录 |

Experiment Picker 当前只查询 `limit=50, offset=0`，没有搜索/翻页；有更多 Sample 的项目无法完整选择。Experiment detail 仍渲染 references 链接列表，未复用完整 SampleTable。Data landing 仍是统计/入口页面，尚非计划中的 Data 表格。Claim 详情仍以静态 statement/evidence 为主。这些属于明确未完成的产品工作，不能归为“仅剩视觉打磨”。

## 复杂度与耦合判断

目前延续原仓库演进是合理方向，但共享命令层还没有真正独立出来。Data finalize 直接 import Sample 服务的私有 `_sync_record`；该函数同时承担 target 校验、执行创建/更新、binding、撤回、图顺序、投影和版本生成。多个服务仍各自决定 commit，REST 路由承担并发检查，读 DTO 又被用于生成版本 token。这些边界使同一种语义在不同入口下表现不同。

前端 ScientificComposer 已隔离业务 API，这是可保留的设计；但通用 domain-workspaces 文件仍聚集多个领域页面，服务端状态大量使用局部 useEffect/useState，Data 提交流程没有独立持久化状态。表格 URL 是未版本化的手工 token 编码，跟计划的带版本查询配置仍有差距。

建议优先顺序：先修 A01/A02/A03/A04/A05；随后统一 A06/A07/A08/A09/A10 的契约及恢复语义；最后补表格、产品入口和发布证据。先把现有发现转成**期望正确行为**的失败回归，再修实现，不应将诊断脚本中断言错误行为的测试直接加入主套件。

## 可复查材料

- [API/PostgreSQL 诊断脚本](audit-2026-09-06/api_reproductions.py)：12 个缺陷复现＋1 个 SQL 诊断。
- [Chromium 延迟保存脚本](audit-2026-09-06/browser-save-reproduction.cjs)：API 全 mock，观察保存期间输入后的实际 base token。

从 `api` 执行诊断脚本时，需设置 `PYTHONPATH=.:tests`、明确的隔离 `TEST_DATABASE_URL`，再运行 `uv run pytest -q -s ../docs/handoff/audit-2026-09-06/api_reproductions.py`。仓库 fixture 会重建该测试库的 public schema，不能指向开发或生产库。

浏览器脚本从 `web` 运行：`node ../docs/handoff/audit-2026-09-06/browser-save-reproduction.cjs`，使用已运行的 `127.0.0.1:3000` 页面。本报告中的 SQL 耗时仅是诊断观测，不作为性能通过证据。
