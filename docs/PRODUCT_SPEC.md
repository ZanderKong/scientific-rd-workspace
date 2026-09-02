# Product Spec — Scientific R&D Workspace

## 1. Product Positioning

Scientific R&D Workspace 是一个面向实验型科研与研发团队的工作台原型。

它要展示的是：

> 如何把一次科研研发活动从「项目、实验条件、实验记录、数据、证据、AI 判断、人工审核、下一轮实验」组织成可追溯的数字闭环。

它不是：

- 通用聊天机器人
- Chat + RAG demo
- 完整企业 LIMS
- 仪器控制平台
- 库存/采购 ERP
- 全功能 Notion clone
- 全功能 ELN 替代品

## 2. Portfolio Story

最终完整 Demo 要覆盖：

```text
Project
→ Experiment
→ Record Conditions
→ Rich Experiment Note
→ Import Measurement
→ Compare Experiments
→ Link Literature
→ Generate AI Finding
→ Evidence / Risk Gate
→ Human Accept / Reject
→ Bad Case
→ Evaluation
→ Create Next Experiment
```

项目价值来自：

1. Scientific data schema。
2. 科研工作流数字化。
3. Experiment lineage 与 provenance。
4. AI 介入位置和边界。
5. Evidence Gate。
6. Human feedback → evaluation lifecycle。

## 3. Primary User

MVP 只有一个 persona：

**R&D Scientist / Materials Research Engineer**

主要诉求：

- 快速记录实验。
- 不重复输入大量相同条件。
- 从上一轮实验克隆并修改少量参数。
- 以后能够比较 batch。
- 所有判断可追溯到实验和文献。
- AI 不能把猜测伪装成事实。

Phase 1 不实现 manager persona 的独立权限体验。

## 4. Core Domain Language

### Project
一个持续的研发目标。

例：
`Improve high-concentration Cl₂ colorimetric response`

### Experiment
一次计划和执行单元。

例：
`EXP-045 — 2-POA + KI + starch`

### ExperimentTemplate
定义某类 Experiment 可填写的 structured properties。

### Structured Properties
可比较、可查询、机器可读的实验条件。

### Rich Note
科研人员的自由记录：Objective、Procedure、Observation、Discussion。

### Attachment
原始或辅助文件。

### Revision
Experiment 某个可追溯时间点的 snapshot。

### Parent Experiment
本 Experiment 从哪一次实验 clone 而来。

## 5. Product Phases

### Phase 1 — Foundation + ELN Core

必须交付：

- Workspace shell
- Projects
- Experiments
- Experiment detail
- Schema-driven structured properties
- Rich note
- Attachments
- Clone Experiment
- Revision History
- Demo seed data

用户故事：

> 我可以进入一个项目，打开一次实验，看见结构化实验条件和实验正文，修改并保存；我可以从这次实验 Clone 下一次实验，只改一个参数；我可以看到历史 revision。

### Phase 2 — Scientific Workflow

必须交付：

- CSV/XLSX import
- Measurement
- Column mapping
- Plot
- Compare
- Literature records
- Experiment ↔ Literature links
- Evidence
- stronger lineage/provenance

### Phase 3 — Scientific AI

必须交付：

- AI Analysis
- Finding
- Evidence
- Risk
- Confidence boundary
- Evidence Gate
- Accept / Reject / Needs Evidence
- Bad Case
- Evaluation Dataset
- Benchmark/Regression view
- final demo polish

当前实现进度：Phase 3 M1–M9 已实现并通过本地回归门禁；M10 的 PostgreSQL/前端/离线浏览器
审计已完成，仍需一次配置凭据的 live LiteLLM smoke 才能发布。AI 仅产生冻结上下文上的结构化 Finding
与非权威建议，Evidence Gate 由服务端确定性策略计算，不能直接修改 Experiment、Measurement、
Evidence、Literature、Revision 或 ReviewDecision。

通过 Accept 或 Needs Evidence 的 Finding 才能打开 gated prefilled Experiment creation。科学家可
检查并编辑所有预填值，显式提交后才创建 `draft` Experiment；服务端重新验证 exact immutable
template version、review/suggestion hash 与 parent lineage，并原子写入 `ExperimentProvenanceLink`。

## 6. Phase 1 P0 User Stories

### US-01 Project list
作为科研人员，我可以看到项目列表和每个项目的基本状态。

### US-02 Create Project
我可以创建一个项目，填写 title、description、status。

### US-03 Experiment list
我进入项目后，可以看到该项目的 experiments。

### US-04 Create Experiment
我可以使用一个 Experiment Template 创建 Experiment。

### US-05 Structured properties
我可以填写 schema-driven 实验参数，数值和单位保持独立。

### US-06 Rich note
我可以像使用 block editor 一样记录 Objective、Procedure、Observation。

### US-07 Attach file
我可以上传实验附件，看到文件名、类型、大小，并下载或删除。

### US-08 Clone
我可以 clone Experiment，并修改少量参数作为下一轮实验。

### US-09 Revisions
我可以创建 revision snapshot，并查看历史 revision 的只读内容。

### US-10 Persistence
刷新浏览器或重启服务后，数据仍存在。

## 7. Phase 1 Non-goals

不做：

- AI
- RAG
- Embeddings
- pgvector
- LangGraph
- Langfuse
- MCP
- Zotero
- CSV auto-parser
- Measurement
- batch compare
- 多人实时协作
- granular RBAC
- SSO
- enterprise audit log
- inventory
- sample barcode
- instrument connector
- scheduler
- workflow approval
- electronic signature
- regulatory compliance claims

## 8. Product Rules

1. Experiment structured properties 必须可由 schema 替换。
2. Structured properties 与 rich note 不混存。
3. Clone 是主要工作流，不是边角功能。
4. Revision 只读，不允许修改历史。
5. Experiment code 对人友好，但系统引用使用 UUID。
6. 产品不假装 Phase 1 已经是合规 ELN。
7. 所有 Demo 科研数据是演示数据，不宣称为真实科学结论。

## 9. Demo Dataset Theme

使用材料研发风格的匿名演示数据：

Project：
`Colorimetric Sensor Formulation Optimisation`

Experiments：
- EXP-041 Baseline formulation
- EXP-044 + KI
- EXP-045 + KI + starch

Phase 1 不需要真实测量曲线，但 structured properties 要有足够差异，便于 Phase 2 继续使用。

## 10. Success Criteria

Phase 1 成功不是功能数量，而是以下体验成立：

> 新用户进入 Demo project 后，3 分钟内能理解项目目标，打开 EXP-045，看到结构化配方和科研记录，clone 出 EXP-046，修改一个实验条件，创建 revision，并能返回查看上一版本。

如果这条路径不顺畅，即使 CRUD 全部存在也不算完成。
