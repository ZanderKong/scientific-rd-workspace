# v1.5 产品目标与实现差异核对

审查日期：2026-09-07。源码基线：`main@bb9a66b`，审查开始时工作区干净。

## 范围与判定规则

本次核对 v1.3 原始产品预期、v1.4 审查、v1.5 冻结设计、会话中批准的 P0–P6 / R0–R7 计划及当前源码。后续明确决策覆盖早期冲突；没有被明确取消的用户交互不能因技术实现简化而自动移出范围。

本报告为源码与契约审查，未重新执行浏览器、数据库故障注入、真实 IME 或性能测试。源码可确认缺少入口、固定简化行为及规则缺口；稳定性和端到端成功仅列待验证，不凭静态检查宣称通过。没有修改产品代码或运行数据。

状态含义：**缺失**＝没有对应用户流程；**部分**＝存在基础实现但缺闭环；**偏离**＝已写出的行为与要求不同；**待验收**＝实现或原型存在，但没有足够通过证据。多个缺口可能同时属于这些状态。

## 一、对象、模板与 Scientific Composer

| ID | 目标与依据 | 当前实现及证据 | 判定 |
| --- | --- | --- | --- |
| G01 | 对象/过程页面维护自身属性、默认使用字段、顺序和模板版本。v1.3 §2、9–11；P2/R4。 | [CreateForm](../../web/src/features/workspace/components/workspace-app.tsx) 主要提交名称、tags 等；创建过程传空 `execution_field_definitions`，详情用 JSON 展示 properties。现有底层版本服务不能代替字段维护/发布 UI。 | 部分：完整字段配置、顺序维护与发布流程未交付。 |
| G02 | 候选缺失时能创建对象/过程，并保留 Composer 草稿。v1.4 §11 的空项目要求；用户补充希望直接从 `@` 创建。 | [ScientificComposer](../../web/src/features/workspace/scientific-composer/scientific-composer.tsx) 仅接收搜索 provider；候选由已有结果 map 生成，无创建回调或返回插入流程。 | 缺失；菜单内创建与自动插入的精确体验在后续计划中也未完整落实。Data/Claim 的特殊创建语法仍在排除范围，不能混淆。 |
| G03 | Ref 最后有新增属性入口；新字段仅属于该 occurrence，拥有独立身份。v1.3 §7.3–7.4；v1.5 §9、§10；P2/R4。 | [RefView](../../web/src/features/workspace/scientific-composer/ref-spec.tsx) 只 map 已有定义，没有新增字段控件；编辑器字段访问主要按 key。 | 缺失：字段身份概念没有变成新增、保存、复制、重开的用户流程。 |
| G04 | 阅读时仅显示已填字段，选中/编辑时展开全部 placeholder。v1.3 §6；v1.5 §9.1。 | RefView 无条件展示全部定义。 | 偏离：阅读/编辑状态未实现。手动隐藏指定字段及其持久化是另一个需明确的要求，不能声称早期已完整定义。 |
| G05 | Ghost 在正文输入位置随高亮候选变化，Enter 后转为 Slot。v1.3 §12.1；P0/P2。 | `ghostPreview()` 只产生最多四个字段名，写入候选 `subtext`；没有正文中的临时预览。 | 偏离：菜单副标题替代了原位 Ghost；未见批准该降级的决策。 |
| G06 | 对象候选辅助显示 CAS、批次、纯度、型号等身份信息。v1.3 §13。 | Object 候选副标题仅包含 code 和默认字段摘要。 | 部分：编号有，其他身份信息展示没有接入。 |
| G07 | 服务器候选搜索与分页，不受固定首批截断。P2/R4。 | [SampleComposer](../../web/src/features/workspace/sample-record/sample-composer.tsx) 对搜索传 `limit: 50`，Composer provider 只返回数组，没有下一页或加载更多契约。 | 部分：服务器搜索已做，候选分页交互未做。 |
| G08 | 保留 number/text/boolean/select 与 unit，并支持相应有效输入。v1.5、P0/P1。 | PropertySlot 统一使用 input，`writeValue` 写字符串；没有 boolean/select 专用操作。后端存在类型处理，不等于前端类型体验完成。 | 部分：需分别验证编辑草稿、保存转换和重开；不能将所有类型输入视为已验收。 |
| G09 | Replace 只继承字段身份一致或明确保留的 local 值。R2。 | `retainMatchingValues` 仅按新字段 key 保留旧值，不比较 owner；Replace/关联在编辑器下方 section，而非 Ref 附近菜单。 | 偏离：跨 owner 同 key 的草稿继承与契约不符；最终保存是否拒绝需动态验证。菜单位置也是未明确确认的交互简化。 |
| G10 | 片段复制完整 remap，清除片段外关联；可识别的剪切移动保留身份。P0/R2/R4。 | [复制插件](../../web/src/features/workspace/scientific-composer/ref-spec.tsx) 对 paste 重映射，找不到 Process 映射时仍保留旧 ID；[复制 codec](../../web/src/features/workspace/scientific-document/model.ts) 同样回退旧关联 ID。未见剪切移动专用识别。 | 偏离/部分：孤立片段可能保留外部关联；移动身份规则未落实。 |
| G11 | 十三类交互、正文与字段统一历史、真实 IME、最小 B 对照先通过门禁再正式接入。P0/R4。 | A 已用于正式 Sample/Data；现有事件处理和测试仅覆盖部分路径。Ref 邻接删除直接删节点；未见完整逐场景证据。 | 待验收，且接入顺序偏离门禁；不能据此认定 BlockNote 不可行或触发 fallback。 |

## 二、Sample 保存与批量

| ID | 目标与依据 | 当前实现及证据 | 判定 |
| --- | --- | --- | --- |
| G12 | 保存并批量写入类似样品：临时表、双层列组、逐行变量与文末备注、100 行原子创建。v1.3 §21、24–29；P4/R6。 | [API client](../../web/src/lib/api-client.ts) 有 `createSampleBatch`，后端有端点和事务/幂等测试，但 `web/src` 没有调用该方法的批量编辑 UI。 | 缺失：批量 API 已有，用户批量创建闭环没有。 |
| G13 | 明确“产出当前 Sample”，不自动推断最后一个 Process。P2/R4。 | 通用 ObjectRef binding 可选 output，但 SampleComposer 没有“产出当前 Sample”动作，新建时也没有借此表达自身身份的产品流程。 | 缺失：一般 output 关联不等于此操作。 |
| G14 | 共用 save session：提交 generation、command ID、独立 identity map；响应只合并身份与基线。R4。 | Sample 内部已有 generation、createdRecordId 和避免覆盖新输入逻辑，但未抽共用会话，也未维护独立于可撤销正文的 identity map；Data 使用另一套状态流程。 | 部分：保存竞态切片存在，共享会话及 Undo 后身份规则未完成。 |
| G15 | base revision/格式不一致时保留冲突草稿，比较、导出、恢复或明确丢弃。R4。 | SampleComposer 读取草稿时，base 不同直接调用 `deleteScientificDraft`。 | 明确偏离，并有丢失本地草稿风险；不是单纯“未补 UI”。 |
| G16 | 保存差异、保护依赖列表、冲突处理、复制新建闭环。P2/R4。 | 存在保存、历史读取、复制和错误文字；缺结构化保存差异及可审阅的依赖/冲突处理。save-and-new 在有后续编辑时留在当前记录。 | 部分：不可把普通错误显示或一次保存测试当完整闭环。 |

## 三、Data 获取、上传与更正

| ID | 目标与依据 | 当前实现及证据 | 判定 |
| --- | --- | --- | --- |
| G17 | 已保存 Sample 内便捷记录 Data；共用 Data Composer。v1.3 §91–93；P3。 | 已有链接跳至 `/data/new` 并携带 Sample 来源；[DataComposer](../../web/src/features/workspace/data-composer/data-composer.tsx) 为独立路由组件，要求先开始草稿再上传。 | 部分/手段变化：Sample 内嵌内容编辑和顺畅的一次提交未交付。多阶段服务协议是批准设计，不代表 UI 必须暴露所有阶段。 |
| G18 | 无 Process 也能声明 subject；producer、input、subject 可明确选择和更正。P3/R3/R5。 | Data content 固定 `subject_ids: []`，支持入口传来的 source Sample；Composer 对 Object 的 role 控件依附 binding；无独立 subject、canonical producer 和 input Data 完整选择器。 | 部分：后端来源能力存在，用户输入意图的入口不完整。 |
| G19 | 文件选择即固定身份，上传/关联重试不重建，待上传失败和 key 刷新可恢复。R5。 | 每次 onDrop 重新生成 UUID；bytes 上传与附件关联分两次请求；失败仅本地字符串数组，没有可恢复待上传清单，begin/finalize key 在 useRef。 | 部分：已上传关联可恢复，失败附件/响应丢失恢复不完整。 |
| G20 | finalize 不覆盖并发修改，未知结果先 replay。R1/R5。 | handleFinalize 已先 GET 并识别 finalized_result；但未 finalized 时用刚读到的 token 提交当前本地 content，而非始终以用户原编辑基线校验。 | 部分/偏离：成功响应丢失已有补救；新取 token 可能掩盖期间他人修改，需双连接验证。 |
| G21 | CSV/XLSX raw-first，成功后复用 preview/commit 增强解析；解析失败不撤销原始 Data。P3/R5。 | 当前 DataComposer 无保存后解析调用；已有旧解析 API 不能证明此流程接入。 | 缺失：新 Composer 的解析增强链路未接。 |
| G22 | 已保存 Data 接入同一编辑器和 save session，更正前展示影响；正文/Representation 可读。R5/R6。 | [DataWorkspace](../../web/src/features/workspace/domain-workspaces.tsx) 展示 Representation 名称/hash 和 occurrence JSON；无同一 Composer 的更正入口，未按原正文渲染完整获取记录。 | 缺失/简化：API 的更新与历史读取不等于可操作更正页面。 |

## 四、表格与 Experiment

| ID | 目标与依据 | 当前实现及证据 | 判定 |
| --- | --- | --- | --- |
| G23 | 按 Ref 分组双层表头、组和组内列移动、DnD 与键盘替代。v1.3 §37–43；P4/R6。 | [RecordTableList](../../web/src/features/workspace/sample-record/sample-list.tsx) 有动态列和顺序控制，但无完整分组表头及 dnd-kit 集成。 | 部分：锁定依赖不等于交付交互。 |
| G24 | required refs 独立候选，可选无字段 Ref；字段目录不依赖筛选结果。R6。 | 目录已由服务器按 scope 独立生成；但 UI 的 `targetOptions` 从字段目录推导。 | 部分：零结果目录已修复，无字段对象仍无法经此选择器选入。 |
| G25 | `对象:属性:值` 结构化搜索、自然文本排序及明确重复 occurrence 排序规则。v1.3 §39–52。 | 现有 q、单独结构化筛选控件和 SQL 类型排序；文本直接按 text_value 排，重复项取 ordinal 第一项。未见冒号语法解析与自然排序实现。 | 部分/手段变化：结构化筛选能力已有，原搜索交互和自然排序未做；第一项排序需明确产品规则。 |
| G26 | Experiment 复用 SampleTable，默认成员字段并集；Data/View/Claim 分页签和成员增删排序。v1.3 §62–69；P4/R6。 | Experiment 详情仅 References ObjectLink 列表与 ClaimCreator；没有复用 RecordTableList 或完整 tabs、成员编辑 UI。 | 缺失：异构比较与成员管理产品流程尚未交付。 |
| G27 | 新建 Experiment 必须先选 Sample，自动命名；Picker 搜索分页、创建返回保留完整上下文。v1.5 §10；P4/R6。 | Picker 搜索分页及返回链接存在；创建函数只检查 scope/title，不检查 selectedSamples 非空，用户须填标题；返回 URL 未承载原选择/搜索集合。 | 部分/偏离：仍能发起零 Sample 创建，默认命名与返回完整上下文未落实。 |
| G28 | URL 带版本和验证；Peek Back 恢复查询、选择、滚动；DetailBody 共用。P4/R6。 | nuqs query/peek 和页内 selection 已有；Peek 自行展示字段/JSON，与完整页不是共享 DetailBody。没有完整非法配置恢复、离页选择和滚动恢复验收。 | 部分；不能把 URL 有参数等同于完整返回体验。 |

## 五、View、Claim 与 AI

| ID | 目标与依据 | 当前实现及证据 | 判定 |
| --- | --- | --- | --- |
| G29 | View 可选择多个 Data 的明确 revision/Representation，登记 Artifact，旧版本可读。P5/R6。 | Data 页 ViewCreator 走单 Data 快捷创建；ViewWorkspace 能上传 Artifact，但展示 hash，无图像/PDF 预览；版本列表仅编号/hash，无可点击历史详情。 | 部分：固定来源后端已有，完整来源选择与历史产物展示缺失。 |
| G30 | Data/View/Claim 固定历史 DetailBody、稳定 revision URL；缺失事实不补当前值。R3/R6。 | API 有 revision 读入口，但页面主要读取当前 record、链接当前对象；未接完整历史数值/来源/文件详情。 | 部分：不能凭返回 revision JSON 宣称历史产品闭环。 |
| G31 | Claim 来源创建、evidence、context 保持与显式刷新、反向查询、归档。P5/R6。 | 来源页创建、evidence 和归档部分已实现；后端有 refresh_context；当前页面缺对应完整 context refresh/影响审阅流程，context 仍有 JSON 展示。 | 部分；不应把已做 evidence/归档一起列成缺失。 |
| G32 | 新增领域命令与 MCP/ChangeSet 同阶段可用。P1–P5/R6。 | MCP 有 Sample/Data/Experiment/View/Claim 创建提案和历史读取等；工具注册中没有 batch、Data draft/finalize、完整更正/影响流程的对应专用能力。 | 部分：UI/REST 新能力未全面进入 AI 工作流，不能声称 AI 可执行全部新流程。 |

## 六、实现基础与验收约束

| ID | 目标与依据 | 当前实现及证据 | 判定 |
| --- | --- | --- | --- |
| G33 | Sample、Data finalize/更正共用 scientific_record 聚合命令，外层一次提交。R1。 | [scientific_record_service](../../api/app/scientific_record_service.py) 仅共享锁；Data 两条路径仍 import Sample 私有 `_sync_record`；内部服务仍有 commit/整个 Session rollback 路径。 | 部分：已提取共享锁，未完成批准的聚合编排层。 |
| G34 | 编辑 token 来自不可变 revision 身份，内容改回不能复活旧 token；锁后刷新。R1。 | Sample 返回最新 revision 的 snapshot hash；Data 仍组合内容 hash；共享锁查询没有 populate_existing。 | 部分/规则缺口：关联改名回归已修复，不足以证明自身版本、锁内新鲜读和并发契约全部成立。 |
| G35 | occurrence 持久身份与当前投影分离；稳定 subject 来源、未变更 pin 不重建。R2/R3。 | [Sample sync](../../api/app/sample_record_service.py) 删除再建 DocumentOccurrence；没有独立 occurrence identity 模型。[subject helper](../../api/app/data_service.py) 删除当前来源集合再生成行并读取目标最新 revision。 | 部分/偏离：binding 已软停用，但不能据此说所有身份和 pin 都稳定。 |
| G36 | 影响查询→摘要确认→显式更正，完整历史资产引用保护和维护诊断。R3。 | typed revision reference 及部分引用写入存在；完整影响/更正端点、确认摘要与修复维护命令未找到。 | 部分：结构已落地，跨所有删除/更正入口的保护仍待完成和验证。 |
| G37 | React Query 管服务器状态，共用 DetailBody/save session，中英文同构。P2–P6/R6。 | 表格用 React Query，多个业务页仍 useEffect + useState 加载；大量新界面硬编码中英文，详情/Peek 分别实现。 | 部分：明确的架构和产品收口任务未做完。 |
| G38 | 未验收写入口由服务端关闭；P0/P1 通过才正式接 Composer。R0/P0。 | [capabilities](../../api/app/capabilities.py) 返回 enabled/experimental 注解；未见统一执行这些声明的服务端写门禁。A 已进入正式页面。 | 偏离：能力标记不能替代实际门禁。 |
| G39 | 真实 IME、A/B、双连接/故障注入、规定硬件性能、完整产品浏览器验收。P0–P6/R7。 | 旧报告已承认多项未执行；本次未补执行证据。 | 待验收。不能以单测数量、构建或 API 200 替代。 |

## 已批准的调整，不应算作漏做或擅自降级

- Ref 内使用原子节点＋原生输入，是 v1.5 明确批准的 A 方案；不必每个字段都成为 PM 子节点。尚欠门禁不意味着路线已失败。
- v1.3 的纯文本字段方案改为保留 number/text/boolean/select 和 unit，是后续明确修订。G08 是落实不足，不是应退回纯文本。
- 不自动把 Object 绑定最近 Process；不自动把 Sample 设为末步输出；正常 Process 保存默认 recorded，是冻结语义。缺的是显式操作入口。
- Data 允许无 Process，subject 来源并集；不制造虚拟执行。没有 Process 不能成为缺少 subject 操作的理由。
- 全项目任意手动行序被限制为有界 Experiment；服务端分页/排序替代全量客户端处理，是批准的规模约束。
- 上传采用 begin/upload/finalize、固定 revision、Data 原始文件优先，是批准的技术契约。客户端恢复未做完需继续完成。
- 不迁移旧客户端数据、不维持永久旧协议层；历史迁移文件仍保留。开发数据清理不能等同于保留新系统历史的要求被取消。
- AI/分析 runtime、协作编辑、离线自动合并、数值 DSL、单位换算、HTML 交互 Artifact 明确排除，不列为欠交付。

## 对既有进度描述的更正

1. “100 行 Sample batch 已有”仅代表服务端能力；应明确“批量编辑 UI 未交付”，不写成“更完整的 UI 待补”。
2. “Ghost Preview 已有”应改成“候选摘要已有，原位 Ghost 未实现”。
3. “草稿恢复已有”仅覆盖部分同基线恢复；跨基线草稿实际被删除，与修复计划冲突。
4. “历史读取已有”要分别注明 API、页面、固定内容/文件展示；三者不能互相替代。
5. 当前 CI 文件**确有独立 `browser-first-run` job**，此外另一个 job 显式列出六个浏览器文件。旧文档里“CI 不包含 no-seed”不准确；仍不等于新增文件自动发现或本次执行全部通过。
6. 实现已于 `3c30645` 提交，README 于 `bb9a66b` 提交并推 main；“尚未提交”已过时。发布到 main 不等于 R7 验收。
7. 本地数据库在随后重启操作中已被重建并 seed；旧文档的“开发库未升级或清理”已过时。本次审查没有对数据库作变更。

## 结论

目前是具有部分业务可用路径的实现集合，尚未完成 v1.5 承诺的完整产品。主要差异不是产品范围被正式缩小，而是 UI 入口、工作流衔接、恢复/历史保护和验收未完成，且若干交互被简化后没有标为偏差。

本表按 39 个可追踪差异单元组织，不代表 39 个独立 bug，也不代表未列出的全部功能已通过验收。下一步任何实现或验收应逐项附上：原需求、用户入口、实际操作、保存/重开结果、失败恢复、证据和关闭状态；技术接口完成与用户功能完成分开登记。
