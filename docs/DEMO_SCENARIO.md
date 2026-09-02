# Demo Scenario

## 1. Final Three-Phase Story

最终 v0.1-demo 演示：

```text
Project
→ Experiment
→ Conditions
→ Record
→ Data Import
→ Compare
→ Literature Evidence
→ AI Finding
→ Evidence Gate
→ Reject
→ Bad Case
→ Evaluation
→ Next Experiment
```

## 2. Phase 1 Demo Script

Phase 1 完成后应能录制一个 2–3 分钟 Demo。

### Step 1 — Open Overview

展示：

- Scientific R&D Workspace
- PRJ-001
- Recent experiments

说明：
「这里不是一个 AI chat，而是研发项目工作台。」

### Step 2 — Open Project

进入：

`PRJ-001 — Colorimetric Sensor Formulation Optimisation`

看到：

- EXP-041
- EXP-044
- EXP-045

### Step 3 — Open EXP-045

Overview：
- 结构化 formulation
- drying condition
- status
- parent EXP-044

说明：
「实验参数是 schema-driven structured data，不是写在正文里的自由文本。」

### Step 4 — Open Record

展示富文本：
- Objective
- Procedure
- Observation
- Discussion

说明：
「实验自由记录与结构化参数分开保存。」

### Step 5 — Files

上传一个 demo 文件，例如：

`exp-045-photo.txt` 或一个安全的小样例文件。

展示上传、下载。

### Step 6 — Create Revision

Change note：
`Before next formulation iteration`

创建 revision。

### Step 7 — Clone

Clone EXP-045。

新 title：
`EXP-046 — Lower starch loading`

修改：

starch amount：
`1.0 → 0.5`

保存。

### Step 8 — Revision

确认：
- EXP-045 历史 revision 没变。
- EXP-046 显示 parent EXP-045。
- 刷新后数据仍存在。

## 3. Demo Acceptance

如果演示中任何一步需要：
- 手工改数据库
- 打开终端补数据
- 刷新才能救页面
- 使用 mock API

则 Phase 1 不算完整。

## 4. Phase 3 M5–M7 browser checkpoint

The M5–M7 browser checkpoint is now runnable: select exact revisions and Measurements in Compare,
launch FixtureProvider analysis with zero curated EvidenceRecords, inspect frozen provenance and the
separate confidence/Evidence Gate/Direct Structured Support surfaces, append Accept/Reject/Needs
Evidence, create controlled Bad/Reference Cases, and run the mixed dataset sequentially. Evaluation
progress, deterministic metrics, optional judge state, and replay links are visible in Workspace.
M8 draft-Experiment screens are intentionally not part of this batch.

Seed data 可以自动生成，但 Demo 中的编辑和 clone 必须真实持久化。
