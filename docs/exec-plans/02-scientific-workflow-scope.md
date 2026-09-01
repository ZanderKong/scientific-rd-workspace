# Phase 2 Scope — Scientific Workflow

**Status:** SCOPE ONLY — DO NOT EXECUTE AS A DETAILED PLAN YET.

Phase 1 完成并产出 `PHASE_1_HANDOFF.md` 后，先让 planning/review model 阅读真实 repo，再把本文转成详细 Execution Plan 02。

## Goal

让系统从「ELN Core」变成真正能处理实验数据和证据的研发工作台。

完整用户路径：

```text
Experiment
→ Upload Raw Data
→ Import Wizard
→ Measurement
→ Plot
→ Compare Experiments
→ Link Literature
→ Evidence
→ Provenance
```

## P0 Capabilities

### 1. Measurement model
- structured measurement
- source attachment
- schema/version
- x/y or tabular data representation

### 2. CSV/XLSX Import
- upload
- preview first rows
- column mapping
- required field validation
- unit mapping
- save raw attachment
- create Measurement

不做 universal instrument parser。

### 3. Visualisation
- standard line/scatter/table
- Experiment measurement page

### 4. Compare
选择多个 experiments：
- structured property differences
- measurement plot overlay
- KPI table

### 5. Literature
先实现内部 Literature entity。
根据 Phase 1 实际情况决定：
- local/manual metadata first
- 或 Zotero API integration

### 6. Evidence
Evidence 至少能 link：
- Literature → claim context
- Experiment/Measurement → claim context

Phase 2 不生成 AI claim。

### 7. Provenance
扩展 lineage：
- Experiment derived_from Experiment
- Measurement derived_from Attachment
- Evidence references Literature/Experiment/Measurement

不要一开始做完全通用 graph database。

## Interfaces Phase 1 Must Preserve

- Experiment ID stable。
- attachment source可被 Measurement引用。
- structured_data JSON 可比较。
- parent_experiment_id 不删除。
- StorageAdapter 继续使用。

## Exit Criteria

Phase 2 结束时应能：

> 选择 EXP-041、EXP-044、EXP-045，看到关键实验条件差异和真实导入 measurement 的叠加图，并打开与这些实验关联的文献 evidence。

完成 Phase 2 后才生成 Detailed Plan 3。
