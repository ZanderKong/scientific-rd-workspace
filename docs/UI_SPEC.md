# UI Spec — Phase 1

## 1. Design Goal

第一版重点是：

- 清晰
- 快速
- 像真实工作台
- 不像通用 AI SaaS 模板
- 不需要重新设计成熟交互

避免：
- 大面积渐变
- 夸张 AI glow
- 无意义 KPI 卡
- 首页巨大聊天输入框
- 过多边框
- 把所有内容塞在 card 中

## 2. Navigation

Phase 1 sidebar：

```text
Scientific R&D
├── Overview
├── Projects
└── Experiments

底部：
Settings（可保留 starter 基础入口或暂不实现）
```

Phase 2、3 未实现页面不要放可点击假入口。

## 3. Overview

P0 内容：

- Active Projects count
- Experiments count
- Recent Experiments
- Quick action：New Project
- Quick action：New Experiment（如需先选择 Project，则打开选择器）

不要做复杂管理 Dashboard。

## 4. Projects List

Table：

| Code | Project | Status | Experiments | Updated |
| --- | --- | --- | ---: | --- |

Actions：
- Open
- Edit

顶部：
- Search
- Status filter
- New Project

## 5. Project Detail

Header：

```text
PRJ-001
Colorimetric Sensor Formulation Optimisation
[Active]

description

[New Experiment]
```

Main：

- Experiments table
- 最近更新时间
- parent/clone 信息可以在 experiment row 中通过小图标展示

## 6. Experiment Detail

这是 Phase 1 最重要页面。

建议 layout：

```text
┌─────────────────────────────────────────────────────┐
│ ← PRJ-001     EXP-045                    [Completed]│
│ 2-POA + KI + starch                                │
│ cloned from EXP-044                     [Clone]     │
├─────────────────────────────────────────────────────┤
│ Overview | Record | Files | Revisions               │
├─────────────────────────────────────────────────────┤
│                                                     │
│ tab content                                         │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Overview tab

- title
- status
- objective
- structured properties（JSON Forms）
- explicit save or stable autosave

### Record tab

BlockNote。

建议 seed：
- Objective
- Procedure
- Observation
- Discussion

不要强行把 section 固定成不可修改的表单；它们只是默认内容模板。

### Files tab

- Drag/drop 或 file input
- File rows：name、type、size、created
- Download
- Delete with confirmation

### Revisions tab

列表：

```text
Revision 3  2026-08-31  "Adjusted drying temperature"
Revision 2  ...
Revision 1  ...
```

点击打开只读 revision detail。

页面 header 提供：

`Create Revision`

## 7. Clone Flow

用户点 Clone：

Dialog：

```text
Clone EXP-045

New title:
[ EXP-045 copy ]

Project:
[ current project ]

Copy:
✓ Structured properties
✓ Rich note
Attachments: not copied in Phase 1

[Cancel] [Create Experiment]
```

成功后直接进入新 Experiment。

页面显示：

`Cloned from EXP-045`

## 8. Form Behaviour

Structured form：

- 单位和 value 并列。
- array additive 支持 add/remove row。
- validation error 就近显示。
- 不因为 renderer 的默认 UI 不完全匹配 shadcn 而自行重写 JSON Forms。
- Phase 1 可以通过容器 CSS 做基础视觉统一。

## 9. Editor Behaviour

BlockNote：

- 使用常规开源 package。
- 不引入 XL GPL packages。
- 保存原生 JSON。
- Phase 1 不做协作编辑。
- 不做 comments、mentions、track changes。

## 10. Empty/Error States

必须有：

- no projects
- no experiments
- no attachments
- no revisions
- backend unreachable
- failed upload
- failed validation

不要只显示 console error。

## 11. Responsive Scope

P0：
- Desktop 1280 px 以上稳定。
- Laptop 1024 px 可用。

Mobile 不是 Phase 1 acceptance blocker。

## 13. Phase 3 Analysis and Evaluation surfaces

Phase 3 adds `/dashboard/analysis`, `/dashboard/analysis/[analysisRunId]`, `/dashboard/evaluations`,
and `/dashboard/evaluations/[evaluationRunId]`. Compare exposes `Analyse selected experiments` with
explicit revision/Measurement/Literature/Evidence selection. Finding cards keep confidence, the
authoritative Evidence Gate, Direct Structured Support, Curated Evidence, limitations, risks, and
review history visually separate. Evaluation screens distinguish Bad Case/Reference Case, deterministic
scores, optional judge scores, progress, cancellation, errors, and source/replay links. The supported
v0.1 runner is one API process with one worker; multi-worker execution is unsupported. After Accept or
Needs Evidence, a valid Finding suggestion exposes `Create Draft Experiment`, which opens the existing
creation form with editable title, objective and structured JSON fields. The submit action is explicit;
the Experiment detail then shows immutable Finding/AnalysisRun/review provenance. PRJ-001 fixture
cases carry visible fixture/synthetic/demo labels and are split into Reference and Bad filters.

## 12. Demo Polish

Phase 1 最后：
- seed 数据页面不能出现 lorem ipsum。
- 统一日期格式。
- code 使用 monospace 或次级文本。
- 明确标识 Demo synthetic/anonymised dataset。
