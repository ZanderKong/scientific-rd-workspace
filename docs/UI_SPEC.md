# UI Spec — Plan 1 UI Direction + i18n Foundation and Plan 2 Final Rebuild

## 1. Scope and product posture

本规范描述 Plan 1 契约与正式 Plan 2 完成后的最终 UI：一个中文优先、英文可切换、可追溯的 Scientific R&D Workspace。
Plan 1 建立视觉方向与国际化基础；Plan 2 在不改变后端/API/数据库和科学功能边界的前提下完成全站 UI 重建与 portfolio polish。

设计目标：

- 像真实研发工作台，而不是通用 AI SaaS 模板。
- 让项目、实验、测量、文献、分析和评测之间的关系清晰可追溯。
- 优先使用成熟的 starter、shadcn/ui、JSON Forms 和 BlockNote，不重写成熟交互。
- 让空状态、错误状态、保存反馈和不可变快照都成为明确的产品界面。

明确避免：大面积渐变、夸张 AI glow、无意义 KPI 卡、首页巨大聊天输入框、假入口、把所有内容塞在卡片中，以及将科学数据或后端 enum 当作 UI 翻译对象。

## 2. Locale contract

| 项目 | 约定 |
| --- | --- |
| Canonical locales | `zh-CN`（默认）、`en`（fallback） |
| URL | 不增加 locale prefix；所有现有 route 保持不变 |
| Persistence | first-party cookie `scientific_workspace_locale`，一年有效 |
| HTML | `<html lang>` 跟随 active locale |
| Translation boundary | 只翻译 UI copy、navigation、状态呈现、表单标题、帮助文本、错误/空状态和日期/数字格式 |
| Do not translate | API/DB enum、stored scientific content、user-entered values、Finding prose、文件名、论文标题/作者、模型/提供商键 |
| Server boundary | locale 只影响前端展示；不增加 backend/API locale 参数 |

所有可达 workspace UI 必须从 `web/messages/zh-CN.json` 与 `web/messages/en.json` 取文案，两个 catalog 的 key tree 保持一致。状态由 `StatusBadge` 的集中映射呈现；日期和数字使用 active locale。

## 3. Visual direction

- 使用安静的中性背景、清晰的层级和少量语义色；状态色只服务于状态识别。
- 页面内容使用单一主列或有限的双列分区，避免无意义的三卡 KPI 墙。
- 标题、说明、动作、主内容之间保持稳定的垂直节奏；代码、ID、hash 用次级文本或 monospace。
- 卡片只用于有明确边界的任务/证据单元；表格和列表保持轻量。
- 关键动作使用一个主按钮，次级动作使用 outline/ghost；危险动作使用 destructive 并给出确认。
- 深色模式下保持同一信息层级，不把颜色变化误当作状态变化。

## 4. Navigation and shell

侧栏只放当前真实可达页面，并按工作语境分组：

```text
Workspace
├── Overview
└── Projects
Research
├── Experiments
└── Compare
Knowledge
└── Literature
AI & Evaluation
├── Analysis
└── Evaluations
```

Header 提供 breadcrumbs、桌面搜索、locale switcher 和 dark/light mode。locale switcher 显示 `中文` / `English`，当前语言有明确 active 状态；切换只刷新展示，不改变当前 route。

## 5. Overview and workspace pages

Overview 使用紧凑的 summary strip 展示 Active Projects、Experiments、Completed Experiments，下面是 Recent Experiments 和 New Project 快捷动作。合成数据必须用明确的 demo/synthetic 标识。

Projects list 提供 search、status filter、New Project、Open 和 Edit。Project detail 的 header 展示 project code、title、description、status、New Experiment，主体展示实验表与不可变 revision 提示。Experiment row 展示 status、更新时间与 parent/clone lineage。

Experiments list 是跨项目的轻量表格；Experiment detail 是 Plan 1 的核心页面，采用：

```text
← Project     Experiment title / code                 [Status] [Clone]
---------------------------------------------------------------------
Overview | Record | Files | Measurements | Literature | Revisions
---------------------------------------------------------------------
tab content
```

Overview 展示 editable metadata、status、objective、JSON Forms structured properties 与显式保存。Record 使用 BlockNote 原生 JSON；Files 展示上传、文件名、大小、时间、下载和确认删除；Measurements 展示 CSV/XLSX preview、X/Y mapping、immutable points 和 provenance；Literature 展示关联来源与 Evidence；Revisions 展示列表并以只读方式查看 snapshot。

## 6. Scientific and evaluation surfaces

Compare 要求先选择项目与至少两个实验，明确显示 frozen revisions、compatible measurement overlays，以及可选 Literature / Curated Evidence。Analysis Finding card 将 Confidence、authoritative Evidence Gate、Direct Structured Support、Curated Evidence、limitations、risks、missing evidence 和 append-only human review 分区显示。

Evaluation 页面区分 Bad Case / Reference Case、deterministic scores、optional model judge、progress、cancellation、errors 以及 source/replay links。后端 scientific prose 和 case tags 原样保留，UI labels 与 status badge 随 locale 变化。

## 7. Official component integration

- BlockNote 使用 `@blocknote/core/locales` 官方 `zh` / `en` dictionary，并在 active locale 变化时重建 editor；保存的数据仍是原生 JSON，不翻译已保存内容。
- JSON Forms 使用官方 `i18n` prop 的 `locale`、`translate` 与 `translateError`；adapter 只翻译已知 schema presentation titles 与有限 validation messages，不 fork renderer。
- 现有 API/DB schema、canonical English enum、revision/provenance semantics 和 backend route 不改变。

## 8. Responsive and acceptance targets

- 1280 px：桌面布局稳定，header、sidebar、双列内容和表格不溢出。
- 1024 px：可操作，长表格/横向 tabs 允许局部滚动，不出现页面级横向溢出。
- 所有 reachable routes 都应在 zh-CN / en 快速检查；切换 locale 后 route、表单数据、scientific content 不变。
- 检查 light/dark mode、console/hydration errors、loading/error/empty states 和主要动作反馈。

## 9. Plan 1 exit boundary

Plan 1 验收包括 frontend gates、双语 catalog parity、代表页面视觉检查、所有现有 route quick inspect、文档与 handoff。完成后停在 Plan 1；任何后续产品范围不得在本批次实现。

## 10. Plan 2 final UI specification

Plan 2 的最终界面以工作流和证据边界为骨架，不新增产品能力：

- Overview 与 Projects 使用紧凑 summary strip、研究活动表和可筛选的项目表；Projects 不再使用卡片画廊作为主信息架构。
- Project detail 与 Experiment detail 保留既有 tabs、编辑、保存、clone、revision、attachment 和 measurement 行为；Experiment detail 增加清晰的 Entity identity、provenance 和只读 traceability timeline。
- New Experiment 的主要输入使用当前模板的 JSON Forms schema/ui schema；Finding 建议只作为 gated prefill，原始 payload 仅在可折叠 technical details 中查看。
- Measurements 按 `Import → List → Detail` 分层，呈现 stepper-like hierarchy、统计摘要、图表、测量行和冻结 provenance。
- Compare 先以表格明确选择，最多 5 个实验；结果分为 configuration、differences matrix、compatible overlays 和 secondary literature/evidence，不把结构化 payload 作为首要视觉输出。
- Literature / Evidence 以 bibliography table 为主；新增文献和 evidence action 在 modal/sheet 中完成，并保留 source attachment 关系。
- Analysis list 显示 run history；Analysis detail 分开 Evidence Gate、Confidence、Direct Structured Support、Curated Evidence、limitations、risks、missing evidence 和 append-only human review。Finding 详情只展示当前 API 提供的可追溯链接。
- Evaluation list 明确分成 Bad Cases、Reference Cases 与 Runs；Evaluation detail 使用 metric strip、structured result matrix、failure tags、case context、source/replay links；optional model judge 与 deterministic score 分隔呈现。

共享的最小 primitives 位于 `web/src/features/workspace/components/scientific-ui.tsx`，包括 SectionHeader、MetricStrip、MetadataList、TechnicalDetails、EntityIdentity、EvidenceGateSummary、CaseTypeBadge、ScoreSummary、ProvenanceSummary 和 TraceabilityTimeline；纯展示/格式化与选择上限逻辑位于 `web/src/features/workspace/presentation.ts`。没有引入新的 UI framework 或 React Flow。TraceabilityTimeline 是基于现有 experiment/revision/attachment/provenance、analysis/finding/evidence 数据的只读 fallback，不能创建或暗示 API 中不存在的关系。

Plan 2 保持 Plan 1 locale boundary：`zh-CN` 默认、`en` fallback、无 URL prefix、cookie `scientific_workspace_locale`、`<html lang>` 同步；只翻译 UI copy、状态呈现、表单标题、帮助/错误/空状态以及日期/数字格式，不翻译 canonical enum、scientific content、Finding prose、论文元数据、文件名或模型键。BlockNote 与 JSON Forms 继续使用官方 i18n 接口。

响应式验收目标为 1280px 桌面与 1024px 可操作布局；长表格/横向 tabs 允许局部滚动，页面不发生横向溢出。所有关键 route 在 zh-CN/en、light/dark、loading/empty/error/disabled/selected/focus 状态下保持可理解。真实 demo 截图与最终验收记录见 `docs/assets/ui/` 和 `docs/handoff/UI_REBUILD_PLAN_2_HANDOFF.md`。
