# Canonical Scientific Data Model

## 1. Why Canonical Model

外部组件和未来服务可以变化，但 Scientific R&D Workspace 必须拥有自己的 canonical model。

不得把：

- BlockNote document model
- JSON Forms schema
- Langfuse trace
- Zotero item
- 某个 ELN Record

直接当作整个产品 domain model。

## 2. Identifier Strategy

每个实体同时可以有：

### Internal ID
UUID，作为数据库主键和 API identity。

### Human-readable Code
例如：

```text
PRJ-001
EXP-045
```

code 用于 UI 和口头沟通，不作为跨表唯一技术引用的替代品。

## 3. Phase 1 Entities

### 3.1 Project

```text
Project
- id: UUID
- code: string unique
- title: string
- description: text nullable
- status: enum
- created_at
- updated_at
```

status：

- active
- paused
- completed
- archived

### 3.2 ExperimentTemplate

```text
ExperimentTemplate
- id: UUID
- key: string
- name: string
- version: integer
- json_schema: JSONB
- ui_schema: JSONB nullable
- is_active: boolean
- created_at
```

unique：
`(key, version)`

每个 template version 是 immutable row。已被 Experiment 引用的 `key`、`version`、`json_schema` 或 `ui_schema` 不得原地修改；发布新 schema 时创建同一 `key` 的新 `version` 行，并通过 `is_active` 控制新建 Experiment 可选的版本。历史 Experiment 永久通过 `template_id` 绑定到其创建时的精确 schema row，`template_version` 是该绑定的显式快照字段。

Phase 1 seed 一个模板即可。

模板必须能够表示：

- string
- number
- boolean
- enum
- date
- quantity（value + unit）

Quantity 推荐 schema：

```json
{
  "type": "object",
  "properties": {
    "value": {"type": "number"},
    "unit": {"type": "string"}
  },
  "required": ["value", "unit"]
}
```

不要把 `60 °C` 作为一个不可解析 string 存储。

### 3.3 Experiment

```text
Experiment
- id: UUID
- code: string unique
- project_id: UUID FK
- template_id: UUID FK
- template_version: integer
- parent_experiment_id: UUID nullable self-FK
- title: string
- status: enum
- objective: string nullable
- structured_data: JSONB
- note_document: JSONB
- created_at
- updated_at
```

status：

- draft
- planned
- running
- completed
- cancelled

Phase 1 不要求 workflow enforcement，只展示和保存状态。

### 3.4 Attachment

```text
Attachment
- id: UUID
- experiment_id: UUID FK
- original_filename: string
- storage_key: string unique
- content_type: string nullable
- size_bytes: integer
- sha256: string
- created_at
```

Binary 不进入 DB。

### 3.5 ExperimentRevision

```text
ExperimentRevision
- id: UUID
- experiment_id: UUID FK
- revision_number: integer
- snapshot_json: JSONB
- change_note: string nullable
- created_at
```

unique：
`(experiment_id, revision_number)`

snapshot 示例：

```json
{
  "experiment": {
    "title": "2-POA + KI + starch",
    "status": "completed",
    "template_id": "...",
    "template_version": 1,
    "structured_data": {},
    "note_document": {}
  },
  "attachments": [
    {
      "id": "...",
      "original_filename": "photo.png",
      "sha256": "..."
    }
  ]
}
```

## 4. Phase 2 Implemented Concepts

Phase 2 建立了受限的结构化测量与证据模型，并保持原始附件到科学结果的 provenance。

### Measurement
一次被结构化的数据测量结果。

```text
Measurement
- id
- experiment_id
- import_id
- measurement_type / schema_key / schema_version
- summary_json / points_sha256
- MeasurementPoint rows
```

### Literature
项目级文献实体，可链接到 Experiment；provider/external metadata 是可选的。

### Evidence
某个 scientific claim 的人工维护证据引用，必须恰好来自 Literature、Measurement 或
ExperimentRevision 之一，并保留 immutable source snapshot。

### Relation
通用 provenance relation 未来可引入，但 Phase 1 不为了「通用图」重构所有 FK。

## 5. Phase 3 Implemented Concepts (M1–M7)

### ScientificAnalysisRun
一次同步、单 provider-call 的科学分析，记录 project、冻结 context、provider/model profile、
structured-output mode、prompt/schema/workflow versions、validated output、failure state 和可选
Langfuse trace metadata。Run 状态不会改变已持久化的 context 或 Findings。

### AnalysisContextSnapshot
AnalysisRun 的不可变 canonical JSON 快照，包含精确 ExperimentRevision、template/schema hash、
Measurement/import/source hashes 与采样点、Literature/Evidence snapshots、Compare 和 factor
differences。`snapshot_sha256` 校验同一选择的确定性。

### Finding
AI 返回的结构化科研判断，分为 observation、hypothesis、comparative、causal 和 recommendation。
`structured_support_json` 保存服务端重算的 Direct Structured Support；`evidence_gate_status` 是
版本化确定性策略的权威状态，与模型 confidence/gate 建议分开保存。模型建议不能直接写入实验。

### FindingEvidenceLink
Finding 到项目内 EvidenceRecord 的不可变链接，并保存当时的 Evidence 快照。它不代表直接结构化
支持；直接支持保存在 Finding 自身。

### ReviewDecision
Accept、Reject、Needs Evidence 的 append-only、有序人工评审。后续决定必须 supersede 当前最新
决定；Finding 仅允许更新 review_status。

M6–M7 additionally implement immutable `EvaluationCase` (bad/reference), `EvaluationRun`,
`EvaluationResult`, deterministic metric snapshots, and optional judge/Langfuse projection. Evaluation
execution is sequential inside one API process/worker; PostgreSQL stores status but is not a queue.
`ExperimentProvenanceLink` remains reserved for M8 and is not created by Evaluation.

## 6. Experiment Template Seed

建议 Phase 1 seed：

`materials-formulation-v1`

示意：

```json
{
  "type": "object",
  "properties": {
    "primary_material": {
      "type": "string",
      "title": "Primary material"
    },
    "primary_material_concentration": {
      "type": "object",
      "title": "Material concentration",
      "properties": {
        "value": {"type": "number"},
        "unit": {
          "type": "string",
          "enum": ["wt%", "g/L", "mol/L"]
        }
      },
      "required": ["value", "unit"]
    },
    "solvent": {
      "type": "string",
      "title": "Solvent"
    },
    "additives": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "amount": {"type": "number"},
          "unit": {"type": "string"}
        },
        "required": ["name"]
      }
    },
    "drying_temperature": {
      "type": "object",
      "properties": {
        "value": {"type": "number"},
        "unit": {
          "type": "string",
          "enum": ["°C", "K"]
        }
      }
    },
    "drying_time": {
      "type": "object",
      "properties": {
        "value": {"type": "number"},
        "unit": {
          "type": "string",
          "enum": ["min", "h"]
        }
      }
    },
    "substrate": {
      "type": "string"
    }
  }
}
```

Agent 可以根据 JSON Forms 实际 renderer 支持对结构做最小调整，但必须保持 value/unit 分离和通用性。

## 7. Demo Seed Data

### Project

```text
PRJ-001
Colorimetric Sensor Formulation Optimisation
status: active
```

### EXP-041

Baseline：
- primary material: Material A
- concentration: 5 wt%
- solvent: ethanol
- no additive
- drying: 60 °C, 20 min

### EXP-044

clone of EXP-041：
- additive KI: 1 g

### EXP-045

clone of EXP-044：
- additive starch: 1 wt%

为了避免把作品集数据误解为科学事实，UI 可以标记：

`Demo dataset — synthetic / anonymised`

## 8. Validation Rules

- title 非空。
- project_id 必须存在。
- template 必须 active 或明确加载历史 version。
- structured_data 保存前必须通过对应 JSON Schema。
- unknown fields 不得静默丢弃。
- attachment size P0 可限制 25 MB。
- filename 必须 sanitise。
- clone 不复制 source revision rows。
- revision_number 单调递增。
