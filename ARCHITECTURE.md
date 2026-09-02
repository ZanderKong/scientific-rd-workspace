# Architecture

## 1. Architecture Goal

Scientific R&D Workspace 是一个科研研发工作流产品，而不是多个开源 ELN 的 UI 聚合器。

核心原则：

> 一个 Workspace Shell + 一个 Canonical Scientific Data Model + 可替换的专业能力组件。

Phase 1 保持架构朴素。

```text
Browser
  │
  ▼
Next.js Web
  │ REST/JSON
  ▼
FastAPI
  ├── Domain Services
  ├── Repository Layer
  ├── StorageAdapter
  │      └── Local file storage (Phase 1)
  └── SQLAlchemy
          │
          ▼
      PostgreSQL
```

## 2. Repository Layout

目标结构：

```text
/
├── AGENTS.md
├── ARCHITECTURE.md
├── README.md
├── docker-compose.yml
├── web/
│   ├── app/
│   ├── components/
│   ├── features/
│   ├── lib/
│   └── ...
├── api/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   ├── db/
│   │   ├── domains/
│   │   │   ├── projects/
│   │   │   ├── experiments/
│   │   │   ├── revisions/
│   │   │   └── attachments/
│   │   └── storage/
│   ├── alembic/
│   └── tests/
├── data/
│   └── uploads/
└── docs/
```

不要求机械遵循目录名，但依赖方向必须保持。

## 3. Frontend Boundaries

### 3.1 Web responsibilities

Web 负责：

- 页面与导航
- 表单和编辑器呈现
- 本地交互状态
- API 调用
- 数据可视化
- error/loading/empty state

Web 不负责：

- 直接数据库操作
- 生成 authoritative ID
- revision snapshot 的业务规则
- 文件最终存储规则
- canonical validation 的唯一实现

### 3.2 Main UI libraries

- Dashboard shell：Kiranism next-shadcn-dashboard-starter
- UI primitives：shadcn/ui
- Table：优先复用 starter 已有 TanStack Table pattern
- Rich text：BlockNote 非 XL packages
- Structured schema editor：JSON Forms
- Phase 1 不增加第二个 rich-text editor 或 form engine

## 4. Backend Boundaries

FastAPI 是唯一业务 API。

建议 domain layering：

```text
router
  ↓
service
  ↓
repository / storage
```

不要为了「clean architecture」建立 8 层空壳。目标是：

- router：HTTP contract
- service：业务规则
- repository：DB persistence
- storage：binary persistence

### 4.1 Phase 3 scientific analysis boundary (M1–M4)

Scientific Analysis is an additive backend capability. The router delegates to explicit Python
services that build a frozen, canonical context in PostgreSQL, make one structured provider call,
recompute scientific references, apply the deterministic Evidence Gate, and persist Findings.
`AIProvider` is the only model boundary: `FixtureProvider` is deterministic for tests and demos;
`LiteLLMProvider` embeds the LiteLLM SDK without the LiteLLM Gateway. Profiles declare exactly one
structured-output mode (`native_schema` or `json_object`), and both modes are validated again by
Workspace-owned Pydantic and scientific-reference checks. Prompt text is versioned and hashed in
the repository.

PostgreSQL remains authoritative for AnalysisRun, immutable context snapshots, Findings, Evidence
links, and append-only ReviewDecisions. Direct Structured Support is limited to server-verified
Measurement comparisons, structured Experiment differences, and immutable Revision observations;
it can support descriptive/comparative claims but never proves causality. Curated EvidenceRecords
remain an explicit, project-scoped selection. The model cannot write Experiments or other scientific
records. Phase 3 M5+ UI and Evaluation capabilities are not implemented in this batch.

## 5. Data Storage

### 5.1 PostgreSQL

保存：

- Project
- Experiment
- ExperimentTemplate
- ExperimentRevision
- Attachment metadata
- structured_data JSONB
- note_document JSONB

### 5.2 Attachments

Phase 1：

```text
data/uploads/{experiment_id}/{attachment_id}/{sanitised_filename}
```

数据库保存：

- original_filename
- storage_key
- content_type
- size_bytes
- checksum
- created_at

必须通过 `StorageAdapter`，使 Phase 2 或后续可替换成 S3/MinIO 而不改变业务 service。

## 6. Scientific Record Separation

Experiment 是一个聚合对象，但内部至少区分：

```text
Experiment
├── system metadata
├── structured_data
├── note_document
├── attachments
└── revisions
```

### structured_data

机器可读，Schema 驱动：

```json
{
  "material": "2-POA",
  "concentration": {"value": 5, "unit": "wt%"},
  "drying_temperature": {"value": 60, "unit": "°C"}
}
```

### note_document

BlockNote 原生 JSON document。

不得把 structured_data 作为 Markdown 文本塞进 note。

## 7. Revision Model

Phase 1 不做 event sourcing。

采用显式 snapshot：

```text
ExperimentRevision
├── revision_number
├── snapshot_json
├── created_at
└── change_note
```

snapshot 至少包含：

- title
- status
- template/schema identity
- structured_data
- note_document
- attachment metadata references

Binary attachments 本身不复制。

## 8. Clone Semantics

Clone Experiment：

- 新 UUID
- 新 experiment code
- 同 project
- `parent_experiment_id = source.id`
- 拷贝当前 structured_data
- 拷贝当前 note_document
- 默认不复制 binary attachments
- UI 允许后续明确选择是否复用附件，但 Phase 1 P0 不实现
- revision history 从新实体 revision 1 开始

## 9. API Convention

Base：

```text
/api/v1
```

P0 endpoints：

```text
GET    /health

GET    /projects
POST   /projects
GET    /projects/{project_id}
PATCH  /projects/{project_id}

GET    /projects/{project_id}/experiments
POST   /projects/{project_id}/experiments
GET    /experiments/{experiment_id}
PATCH  /experiments/{experiment_id}
POST   /experiments/{experiment_id}/clone

GET    /experiment-templates
GET    /experiment-templates/{template_id}

POST   /experiments/{experiment_id}/attachments
GET    /experiments/{experiment_id}/attachments
DELETE /attachments/{attachment_id}
GET    /attachments/{attachment_id}/download

POST   /experiments/{experiment_id}/revisions
GET    /experiments/{experiment_id}/revisions
GET    /experiments/{experiment_id}/revisions/{revision_number}
```

API contracts 以 OpenAPI 实际输出为准。前端不得猜字段。

## 10. Phase Boundaries

### Phase 1
ELN Core only.

### Phase 2
增加 Measurement、Import、Compare、Literature、Evidence、lineage 扩展。

### Phase 3
增加 AI Finding、Evidence Gate、Human Review、Bad Case、Evaluation。

禁止 Phase 1 提前引入 Phase 3 的 Agent orchestration。

## 11. Future Extension Points

只保留接口，不实现：

```text
StorageAdapter
LiteratureProvider
AIProvider
EvaluationProvider
MeasurementParser
```

不要为了这些 future adapters 创建假实现或复杂 plugin framework。

## 12. Failure Philosophy

科研系统必须保护 provenance：

- 不 silently coerce unit。
- 不 silently drop unknown structured fields。
- 不覆盖 revision。
- clone 不修改 source。
- 删除附件必须明确确认。
- API validation error 要返回可理解的字段错误。
