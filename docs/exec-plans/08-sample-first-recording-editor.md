# Plan 08 — Sample-first Recording & Editing Workflow Rebuild

**Status:** READY FOR EXECUTION  
**Target branch:** `main`  
**Verified baseline:** `e3362f6f882cb78d0c6e64208a2f72f782da52e0`  
**Core implementation baseline:** `6fc51b56cf5ce610f171113a5bd4151d29727347`  
**Alembic head at baseline:** `0002_v0_2_semantic_stabilization`  
**Verified CI:** GitHub Actions run `33728614776` — `v0.2 Research Object Graph CI` — **success**

---

## 0. Execution instruction

This plan is the active execution contract for the next product-layer rebuild after Plan 07.1.

Before modifying code:

1. Confirm `main` contains `e3362f6`.
2. Read, in order:
   - `AGENTS.md`
   - `docs/exec-plans/07.1-v0.2-core-semantic-stabilization.md`
   - `docs/handoff/V0_2_CORE_SEMANTIC_STABILIZATION_HANDOFF.md`
   - `ARCHITECTURE.md`
   - `docs/DATA_MODEL.md`
   - `docs/UI_SPEC.md`
   - this Plan 08
3. Inspect the actual current implementations of:
   - `api/app/models.py`
   - `api/app/relation_semantics.py`
   - `api/app/composition_service.py`
   - `api/app/services.py`
   - `api/app/routers/objects.py`
   - `api/app/schemas.py`
   - `web/src/features/workspace/components/workspace-app.tsx`
   - `web/src/lib/api-client.ts`
   - `web/src/lib/domain.ts`
   - `web/src/config/nav-config.ts`
4. Do not restore v0.1 Project/Experiment/Measurement domain code.
5. Do not rewrite migrations `0001` or `0002`.
6. Any schema change must be a new migration beginning at `0003`.

If implementation reality conflicts with this plan, preserve the scientific semantics and document the discrepancy before changing the contract. Do not silently reinterpret provenance.

---

# 1. Why this plan exists

Plan 07 and Plan 07.1 successfully stabilised the canonical Research Object Graph, but the active frontend is still primarily an engineering/debug surface:

- all seven object kinds are exposed as roughly equivalent CRUD concepts;
- Sample detail is rendered through the generic `WorkspaceApp`;
- creation/editing still exposes raw `properties_jsonb`;
- the current `ProcessComposer` edits one Process at a time rather than one human-facing Sample record;
- `ObjectReferencePicker` is a simple one-column picker;
- users have to understand Process, Relation, role, quantity and JSON fields that should remain implementation details.

The next product step is **not another object-graph rewrite**.

The goal is to project the stable graph into a researcher-friendly workflow where:

> **Sample is the primary human-facing research record.**  
> **Process Blocks are the primary manual recording unit.**  
> **Material, Equipment and precursor Sample references are resources attached to a Process.**  
> **The object graph stays canonical but becomes mostly invisible to the user.**

The product is also **AI-first**:

- external agents such as Codex may be the default recording path;
- the workspace must expose precise APIs and documentation so an agent can record the same structure safely;
- the GUI exists as a first-class manual recording, review, correction and fallback interface;
- this plan does **not** embed an AI chat, OCR pipeline or model runtime.

---

# 2. Product target

## 2.1 Primary user-facing concepts

The primary navigation should converge on:

```text
Samples
Experiments
```

Project scope selection remains part of the shell because Sample/Process/Data require a project scope.

The following canonical objects remain fully supported in the backend but should no longer dominate primary navigation:

```text
Process
Material
Equipment
Data
Project
```

Existing routes may remain reachable for debugging, deep links and future resource-management work. Do not delete working backend functionality merely to simplify navigation.

## 2.2 Sample

A Sample is the main research record the user creates, opens, edits, duplicates and inspects.

A manually recorded Sample consists of:

```text
Sample
└── ordered Process sequence
    ├── Process 01
    │   ├── references Material / Equipment / optional precursor Sample
    │   ├── stores actual resource-use values on relations
    │   └── stores Process-own parameters on the Process object
    ├── Process 02
    ├── ...
    └── final Process
        └── produces → Sample
```

Do **not** automatically create intermediate Sample objects between every Process.

Intermediate Sample objects should exist only when explicitly required later, for example because an intermediate is named, tested, branched, stored or independently referenced.

## 2.3 Process Block

The manual editor is a linear block editor, not a graph editor.

A new Sample starts with one empty Process Block.

The user adds further blocks with a lightweight `+ 新建过程` action.

The key command language is:

```text
/   choose or create a Process
@   resolve and attach a resource
```

Do not implement React Flow, free-form node positioning or manual edge drawing.

## 2.4 Resource identity versus actual use

This separation is mandatory.

### Resource identity

Material and Equipment objects describe **what the resource is**.

Examples:

Material:

```text
title / name
code
CAS
supplier
lot
arrival date
other schema-defined identity fields
resource usage-field definitions
```

Equipment:

```text
title / name
code
asset number
other schema-defined identity fields
resource usage-field definitions
```

Each physical piece of Equipment is an independent Equipment object in Plan 08.

Do **not** add an Equipment Type hierarchy, inheritance system or same-model grouping in this plan.

### Actual use

Actual values from this specific experimental step belong to the Process context.

Examples:

```text
KI amount = 1.00 g
MX-03 rpm = 700 rpm
MX-03 duration = 10 min
```

These values must not mutate Material or Equipment identity.

Actual resource-use values belong on the corresponding:

```text
Process --uses--> Material / Equipment / precursor Sample
```

relation metadata.

Process-own values such as:

```text
environment temperature
step duration
process note
custom step property
```

belong on the Process object's structured properties.

---

# 3. Semantic guardrail: Experiment ownership is NOT membership

Plan 07.1 deliberately stabilised:

```text
Experiment --contains--> Process / Sample / Data
```

as a **single ownership relation**, including PostgreSQL partial unique indexes.

The product discussion for the future Experiment UI wants a different concept:

> one Sample may be selected into multiple Experiment comparison groups.

That is **membership**, not ownership.

Plan 08 MUST NOT repurpose `contains`, remove the single-owner constraint, or overload `related_to` to fake membership.

Therefore:

- keep current Plan 07.1 Experiment ownership semantics unchanged;
- keep existing Experiment routes working;
- do not implement multi-Experiment Sample membership in Plan 08;
- document a follow-up Plan 09 requirement for an explicit non-owning membership relation/API.

A future implementation may add a relation such as `includes` or another dedicated membership model, but that decision is outside this plan.

---

# 4. Canonical data changes

## 4.1 New resource usage-field definition storage

Material and Equipment need per-object definitions of which fields should appear when that resource is attached to a Process.

Add a new canonical field to `ResearchObject`:

```text
usage_schema_jsonb
```

Recommended storage:

```json
{
  "fields": [
    {
      "key": "quantity",
      "label": "用量",
      "value_type": "number",
      "default_value": null,
      "default_unit": "g",
      "required": false,
      "options": [],
      "order": 0
    }
  ]
}
```

Supported `value_type` in Plan 08:

```text
number
text
boolean
select
```

Rules:

- `usage_schema_jsonb` is meaningful only for `material` and `equipment`;
- other kinds return `{}` and must not rely on it;
- field keys must be unique within one object;
- field keys are stable storage identifiers;
- labels are user-facing and may be Chinese or English;
- units are metadata, not silently converted;
- default values are suggestions only, never evidence of what actually occurred;
- if a user adds a field while recording a Process, the new field definition is written back to that specific Material/Equipment object;
- adding a field does **not** create a new Material or Equipment object.

Add migration:

```text
api/alembic/versions/0003_sample_recording_workflow.py
```

Do not modify `0001` or `0002`.

`usage_schema_jsonb` must be included in:

- backend Pydantic output/input where appropriate;
- `object_out`;
- revision snapshots;
- frontend `ResearchObject` type;
- seed/demo objects where useful.

## 4.2 Actual relation usage values

New Sample Composer writes actual dynamic resource-use values into relation metadata under a stable envelope:

```json
{
  "usage_values": {
    "quantity": {
      "value": 10,
      "unit": "g"
    },
    "rpm": {
      "value": 700,
      "unit": "rpm"
    }
  }
}
```

Text, boolean and select values use the same field key and a scalar `value`.

Example:

```json
{
  "usage_values": {
    "impeller": { "value": "4-blade" },
    "enabled": { "value": true }
  }
}
```

Backward compatibility:

- existing Plan 07.1 relation metadata using top-level `quantity` must remain readable;
- do not break existing seed graph or Process composition API;
- when a legacy relation has top-level `quantity`, the Sample Record projection should adapt it to a `quantity` usage field for display;
- new Sample Composer writes `usage_values`;
- generic relation validation should validate `usage_values` shape when present;
- no silent unit conversion.

## 4.3 Process-own parameters

Continue using Process `properties_jsonb` for Process-own data.

Prefer a stable envelope:

```json
{
  "parameters": {
    "temperature": {
      "value": 25,
      "unit": "°C"
    },
    "duration": {
      "value": 30,
      "unit": "min"
    }
  }
}
```

Do not store Material amount or Equipment rpm here if those values describe a specific attached resource.

## 4.4 Process definitions for `/`

Use the existing:

```text
ObjectType
ObjectTypeVersion
```

system as the source of available Process definitions.

Do not create a second Process Template subsystem.

Requirements:

- `/` menu lists active ObjectTypes where `kind == process`;
- selecting a Process type sets the Process `type_version_id`;
- the active ObjectTypeVersion JSON schema and UI metadata define default Process-own fields;
- always provide a generic/custom Process option;
- custom instance-only Process fields may be stored in the generic Process parameter map;
- Plan 08 does not require a GUI for creating/editing Process ObjectTypes.

The repeat-safe demo seed may add a small number of non-default synthetic Process types such as mixing, impregnation and drying solely to exercise the UI.

---

# 5. Sample Record aggregate API

The current Process composition endpoint is useful and must remain working:

```text
GET /api/v1/processes/{id}/composition
PUT /api/v1/processes/{id}/composition
```

However, manual Sample recording needs an **aggregate transaction** across multiple Process objects.

Do not implement Sample save as a frontend loop of object and relation POST/PATCH calls.

Add a dedicated service module, for example:

```text
api/app/sample_record_service.py
```

and aggregate routes.

## 5.1 Read projection

```text
GET /api/v1/samples/{sample_id}/record
```

Recommended response:

```json
{
  "sample": {},
  "steps": [
    {
      "process": {},
      "ordinal": 0,
      "resources": [
        {
          "relation_id": "...",
          "object": {},
          "role": "material",
          "usage_values": {}
        }
      ]
    }
  ],
  "data": [],
  "editable": true,
  "edit_blockers": []
}
```

The projection should reconstruct the ordered Process chain by walking backwards from the Sample's single producing Process through `precedes`.

Plan 08 composer supports a **simple linear chain**.

If the existing graph is branched or otherwise cannot be represented losslessly by the linear composer:

```text
editable = false
```

and provide explicit `edit_blockers`.

Never fabricate a linear chain from an ambiguous graph.

The Sample remains viewable even when the composer cannot safely edit it.

## 5.2 Atomic create

```text
POST /api/v1/sample-records
```

Payload must support:

- project scope;
- final Sample draft;
- one or more ordered Process step drafts;
- Process type version;
- Process-own properties/content;
- references to existing Material/Equipment/precursor Sample;
- inline creation of new Material/Equipment;
- usage values;
- per-resource usage-schema additions created during this recording;
- optional change note.

A successful create must atomically:

1. create any inline new Material/Equipment resources;
2. update usage schema of existing resources when the user added fields;
3. create all new Process instances;
4. create or materialise the final Sample;
5. create Process `uses` relations;
6. create ordered `precedes` relations;
7. create final Process `produces → Sample`;
8. preserve project-scope rules;
9. validate current Plan 07.1 lineage/cycle/cardinality semantics;
10. create revision snapshots for the aggregate objects that were created/changed;
11. commit once.

On any failure:

> **zero partial Sample/Process/resource changes may remain committed.**

## 5.3 Atomic edit

```text
PUT /api/v1/samples/{sample_id}/record
```

This is a desired-state update for composer-editable simple chains.

Requirements:

- update Sample basic fields;
- update existing Process objects referenced by `process_id`;
- add new Process objects;
- reconcile Process resource relations;
- reconcile `precedes` ordering;
- keep exactly one final Process producing the edited Sample;
- preserve precursor semantics;
- update resource usage schemas when requested;
- create revisions for changed objects;
- commit once.

### Removing an existing Process step

Do not hard-delete scientific history by default.

For a composer-owned simple chain, an omitted existing Process should be:

1. disconnected from the active chain;
2. marked `archived`;
3. retained for revision/history inspection.

If a Process has external graph dependencies that make removal unsafe, reject the edit with HTTP 409 and a clear reason.

## 5.4 Create from existing Sample

Do not clone Process IDs.

The UI action:

```text
基于此样品新建
```

loads the source Sample Record as an editable **new-record draft**.

When saved:

- final Sample receives a new ID/code;
- every Process receives a new ID/code;
- existing Material/Equipment references are reused;
- existing precursor Sample references are reused;
- Process parameter values and resource usage values are copied as initial draft values;
- Data, attachments and revision histories are not copied;
- no source object is mutated merely by opening the draft.

The frontend may implement this by transforming `SampleRecordOut` into `SampleRecordCreate`; a dedicated clone endpoint is not required unless it materially simplifies correctness.

---

# 6. Resource search and resolver

## 6.1 Search requirements

`@` resource resolution must support at least:

- object title/name;
- canonical object code;
- Material CAS;
- Equipment asset number;
- schema-defined common identity fields when practical.

Search remains project-aware and may include global Material/Equipment library objects according to current scope semantics.

The existing object search currently focuses on code/title. Extend backend search for resource resolution rather than implementing client-only fuzzy filtering over a tiny fetched list.

The result must be deterministic enough for keyboard navigation.

## 6.2 Two-pane Object Resolver

Build one reusable component, for example:

```text
ObjectResolver
```

Desktop behaviour:

```text
┌──────────────────────────────────────────────────────────┐
│ left: grouped matches        │ right: selected preview   │
│                              │                           │
│ Material                     │ title                     │
│ > Potassium iodide           │ code                      │
│   MAT-003                    │ CAS                       │
│                              │ supplier                  │
│ Equipment                    │ lot / asset no.           │
│   ...                        │                           │
│                              │                           │
│ + create "query"             │                           │
└──────────────────────────────────────────────────────────┘
```

Rules:

- left pane is grouped by object kind;
- right pane shows only enough identity information to distinguish candidates;
- changing keyboard highlight updates the right preview;
- Arrow Up/Down moves selection;
- Enter selects;
- Escape closes;
- no page navigation is required to inspect a result;
- use the same resolver infrastructure later for other object kinds.

Responsive fallback may stack preview below results rather than forcing two narrow columns.

Use existing project dependencies (`cmdk`, shadcn/Base UI primitives, `match-sorter` where appropriate). Do not add a second command-menu framework.

## 6.3 Inline create

When no acceptable match exists, show:

```text
+ 新增「query」
```

The right pane becomes a lightweight create form.

The typed query is prefilled into `title`.

The user selects the resource kind if it cannot be inferred:

```text
原料
设备
```

Render identity fields from the current default ObjectTypeVersion rather than hardcoding an entirely separate Material/Equipment schema.

New resource creation stays within the Sample draft where practical and is committed in the final Sample Record transaction.

Do not open a separate full page or nested modal workflow.

---

# 7. Process Block editor

## 7.1 Block structure

A block should visually resemble a Notion-style document block rather than a dashboard card.

Example:

```text
01  配液

[磁力搅拌] [2-苯氧基苯胺] [乙醇]  @

磁力搅拌
转速        [700] rpm
时间        [ 10] min

2-苯氧基苯胺
用量        [10.00] g

乙醇
用量        [90.00] g

过程参数
环境温度    [25] ℃
备注        ______________________

+ 属性
```

Visual rules:

- generous whitespace;
- weak separators;
- minimal border treatment;
- no card-inside-card hierarchy;
- hover/focus may reveal a subtle block background and controls;
- resource tokens are compact, low-saturation chips.

## 7.2 Resource token row

Resource input is mixed.

The user does not click separate:

```text
+ 原料
+ 设备
```

buttons.

Instead:

```text
@磁力搅拌
@2-苯氧基苯胺
@乙醇
```

all enter through the same resource input.

After selection:

- token text displays the object **name/title only**;
- Material and Equipment use different low-saturation theme colours;
- precursor Sample, if supported in the block, uses a third subtle visual token;
- do not print explicit `原料:` or `设备:` labels in the token strip;
- display order may normalise resources by kind for visual consistency;
- input order does not need to equal display order;
- tokens naturally wrap to another line when needed.

The block's expanded parameter section may still group values under each resource title so value ownership remains unambiguous.

## 7.3 `/` Process command

A new Sample begins with one empty Process Block focused for entry.

`/` opens active Process definitions.

Examples:

```text
/混合
/浸渍
/烘干
/自定义过程
```

Keyboard:

- type to filter;
- Arrow Up/Down;
- Enter;
- Escape.

`+ 新建过程` appends another empty block and focuses it.

## 7.4 `@` Resource command

Resource input placeholder may communicate:

```text
输入 @ 添加原料、设备或前驱样品
```

Typing `@` plus query opens Object Resolver.

The user should be able to record a common Sample primarily from the keyboard.

Minimum keyboard contract:

- `/` process search;
- `@` resource search;
- Arrow keys + Enter select;
- Escape close;
- Tab moves through generated fields;
- Cmd/Ctrl+Enter submits the Sample;
- optional Alt+ArrowUp/Down reorders Process blocks.

Do not add drag-and-drop as a dependency requirement in Plan 08. A later visual drag handle may be added if useful.

---

# 8. Dynamic resource fields

## 8.1 Rendering

When a resource is selected, the Process Block reads its `usage_schema_jsonb`.

Example Equipment schema:

```text
转速
时间
桨叶直径
```

causes the block to render:

```text
磁力搅拌
转速        [      ] rpm
时间        [      ] min
桨叶直径    [      ] mm
```

Example Material schema:

```text
用量
```

renders:

```text
2-苯氧基苯胺
用量        [      ] g
```

## 8.2 Add field

Under one resource:

```text
+ 属性
```

opens a very small inline definition editor.

Minimum fields:

```text
label
value type
default unit where applicable
optional default value
select options when type == select
```

When saved in the Sample transaction:

- actual current value is stored on the Process→Resource relation;
- new field definition is appended to that specific resource's `usage_schema_jsonb`;
- no new resource object is created;
- no same-model Equipment group is updated.

## 8.3 Defaults

Defaults are convenience only.

If a resource says:

```text
转速 default = 700 rpm
```

the new Process may prefill 700 rpm, but the UI should visually distinguish a suggested/default value until the user accepts or changes it.

Never treat a default as an observed As-run value without explicit save.

---

# 9. Sample creation UX

Create route:

```text
/dashboard/samples/new
```

or an equivalent route that retains current project scope.

Initial state:

```text
Sample basic information
Process Block 01
[+ 新建过程]
[录入样品]
```

No raw JSON editor.

No requirement to first create Process, Material or Equipment on separate pages.

## 9.1 Save success state

After successful create, do not immediately throw the user back to the list.

Show an explicit committed state:

```text
✓ SMP-042 已录入

[查看样品]
[基于此样品新建]
[录入全新样品]
```

Recommended Chinese labels:

- `查看样品`
- `基于此样品新建`
- `录入全新样品`

The old phrase `录入平行样品` is too narrow because the same reuse mechanism also applies to gradients and variant samples.

---

# 10. Sample detail and edit UX

## 10.1 View mode

Sample detail should stop looking like generic object CRUD.

Target visual language:

- document/record page;
- wide but readable central column;
- strong typography hierarchy;
- whitespace;
- thin or subtle separators;
- very limited decorative cards;
- no raw `properties_jsonb`.

Suggested structure:

```text
SMP-042
2-POA + KI 纸带
2026-09-03                          [编辑] [···]

制备记录
────────────────────────────────

01  配液
    [磁力搅拌] [2-苯氧基苯胺] [乙醇]
    700 rpm · 10 min
    ...

02  浸渍
    ...

03  烘干
    ...

数据
────────────────────────────────
Cl₂ response
...

来源与谱系
────────────────────────────────
precursor / upstream / downstream

相关实验
────────────────────────────────
current ownership context only in Plan 08
```

Do not silently aggregate quantities across separate Process steps.

## 10.2 Resource inspection

Resource names/tokens in view mode are clickable.

Clicking should expose lightweight identity information using a popover/side preview, not force navigation to a resource CRUD page.

A direct full-resource link may exist as a secondary action.

## 10.3 Edit mode

Clicking `编辑` should switch the Sample detail into the same Sample Composer language, prefilled from `GET /samples/{id}/record`.

Do not maintain two unrelated implementations for create and edit.

Use shared components:

```text
SampleComposer
ProcessBlock
ObjectResolver
ResourceToken
UsageFieldEditor
```

If `editable == false`, show why the existing graph cannot be safely represented in the linear composer rather than attempting a destructive rewrite.

---

# 11. Sample list

Replace the generic Sample object list with a restrained, information-dense Sample list.

Minimum useful columns/rows:

```text
code
title
updated time
status
optional current data indicator
```

Avoid turning it into a dashboard.

Search should continue to use backend filtering.

Primary action:

```text
新建样品
```

Selecting a row opens Sample detail.

---

# 12. Navigation cut

Update primary navigation so the researcher-facing shell emphasises:

```text
Samples
Experiments
```

The Project/Vault switcher remains.

For Plan 08:

- hide Process, Data, Material and Equipment from primary sidebar navigation;
- hide Overview/Projects from the main research navigation if the shell can still provide project switching without losing access;
- do not delete their routes or backend APIs;
- retain direct/deep links where useful;
- do not build a new Resource Management center in this plan.

This is a presentation cut, not a domain deletion.

---

# 13. Frontend architecture

The current `workspace-app.tsx` is already large and generic.

Do **not** make Plan 08 another large conditional branch inside that monolith.

Recommended feature structure:

```text
web/src/features/workspace/sample-record/
├── sample-composer.tsx
├── sample-detail.tsx
├── sample-list.tsx
├── process-block.tsx
├── process-command.tsx
├── object-resolver.tsx
├── resource-token.tsx
├── usage-fields.tsx
├── sample-record-mappers.ts
├── sample-record-types.ts
└── __tests__/
```

Routes for Sample should use this dedicated feature.

Keep generic `WorkspaceApp` available for the remaining internal object surfaces until a later cleanup.

Reuse existing dependencies and primitives before adding packages.

---

# 14. AI-first agent contract

The workspace should not assume its own built-in AI is the recording agent.

Create:

```text
docs/agent/SAMPLE_RECORDING.md
docs/agent/SAMPLE_RECORDING_API_EXAMPLES.md
```

and update root `AGENTS.md`.

Documentation must teach an external agent to:

1. search before creating Material/Equipment;
2. resolve by title/code/CAS/asset number;
3. preserve resource identity;
4. put actual Material/Equipment use values on Process relations;
5. put Process-own parameters on the Process;
6. use `precursor` for an existing Sample consumed as a precursor;
7. create ordered Process steps;
8. create one final Sample output;
9. avoid unnecessary intermediate Samples;
10. use the aggregate Sample Record endpoint rather than a fragile series of writes;
11. never silently duplicate an ambiguous existing resource;
12. preserve units exactly as entered;
13. use the same API as the GUI.

Include at least:

- one complete create payload;
- one update payload;
- one example using an existing Material and Equipment;
- one example creating a new Material inline;
- one example using an existing Sample as precursor;
- one example of adding a new Equipment usage field.

No model-specific prompt runtime is required.

---

# 15. Backend implementation milestones

## M0 — Baseline and contract update

- verify baseline commit and CI;
- add Plan 08 to repository;
- update `AGENTS.md` active-plan ordering;
- document the Experiment ownership/membership distinction;
- inventory current Sample and Process APIs.

**Gate:** no implementation begins until the semantic guardrail is recorded.

## M1 — Migration and domain primitives

Implement migration `0003_sample_recording_workflow`.

Add:

- `ResearchObject.usage_schema_jsonb`;
- Pydantic schema types for usage fields and usage values;
- validation helpers;
- object serialisation/revision support;
- backwards compatibility for legacy `quantity`.

Do not change existing ownership/producer indexes.

**Backend tests:**

- migration model parity;
- usage field validation;
- existing v0.2 seed still loads;
- legacy quantity relations still serialise.

## M2 — Resource resolution

Extend backend search or add a focused resource-resolver query supporting:

- title;
- code;
- CAS;
- Equipment asset number;
- project/global scope behaviour.

Add deterministic result ordering.

**Tests:**

- search by CAS finds Material;
- search by code finds resource;
- search by asset number finds Equipment;
- global resource visibility follows current scope rules.

## M3 — Sample Record read projection

Implement `GET /samples/{id}/record`.

Build a simple-chain reconstruction service using the canonical graph.

Return:

- ordered steps;
- resource relation values;
- Process fields;
- `editable`;
- blockers.

**Tests:**

- 1-step record;
- 3-step linear record;
- precursor Sample;
- branch/ambiguous graph returns `editable=false`;
- no fabricated ordering.

## M4 — Atomic Sample Record create

Implement `POST /sample-records`.

Use one SQLAlchemy transaction.

Support:

- new Sample;
- multiple new Process instances;
- existing resources;
- inline new Material/Equipment;
- usage-schema updates;
- Process resource relations;
- `precedes`;
- final `produces`;
- revisions.

**Critical rollback test:**

Force validation failure in the final step and assert no new Sample, Process, relation, resource-schema mutation or inline resource remains committed.

## M5 — Atomic Sample Record edit

Implement `PUT /samples/{id}/record`.

Support desired-state simple-chain updates.

Support safe step addition/reorder/removal-by-archive.

Reject unsafe removal with 409.

Create revisions atomically.

**Tests:**

- change Material amount without mutating Material identity;
- change Equipment rpm without mutating Equipment identity;
- add resource usage field and verify it appears on next read;
- reorder Process steps;
- add step;
- safely archive removed step;
- reject removal of externally referenced Process;
- preserve Plan 07.1 cycle/cardinality rules.

## M6 — Frontend Sample Composer

Build dedicated Sample feature components.

Implement:

- `/` Process command;
- `@` Object Resolver;
- two-pane search;
- inline create;
- coloured resource tokens;
- dynamic usage fields;
- Process-own fields;
- add Process;
- keyboard flow;
- aggregate save;
- explicit success state;
- `基于此样品新建`.

No raw JSON editing in this path.

## M7 — Sample Detail, edit and list

Implement:

- record-style Sample detail;
- resource preview;
- data/provenance sections using existing context/data APIs;
- edit using shared Sample Composer;
- non-editable complex graph state;
- restrained Sample list;
- navigation cut.

## M8 — Agent contract and documentation

Add agent documentation and API examples.

Update:

- `ARCHITECTURE.md`
- `docs/DATA_MODEL.md`
- `docs/UI_SPEC.md`
- `docs/PRODUCT_SPEC.md`
- `README.md`
- `AGENTS.md`

Record exact deferred scope.

## M9 — Verification and handoff

Run all required gates.

Create:

```text
docs/handoff/SAMPLE_RECORDING_WORKFLOW_HANDOFF.md
```

Record:

- delivered scope;
- migrations;
- API surface;
- tests;
- browser smoke;
- CI run;
- known limitations;
- exact final commit.

---

# 16. Frontend interaction tests

At minimum add Testing Library/Vitest coverage for:

1. `/` opens Process command and Enter selects.
2. `@` search opens resolver.
3. Arrow movement updates right preview.
4. Enter attaches selected resource.
5. Material/Equipment tokens use different semantic styles.
6. Token strip does not require explicit Material/Equipment headings.
7. selected resources render their usage fields.
8. adding a usage field updates local draft.
9. Process fields remain separate from resource fields.
10. multiple Process blocks render in order.
11. keyboard reorder changes order.
12. Cmd/Ctrl+Enter submits.
13. success state exposes the three next actions.
14. `基于此样品新建` removes Sample/Process IDs but keeps resource references and values.
15. non-editable Sample record cannot enter destructive edit mode.

---

# 17. Backend regression gates

All existing Plan 07.1 guarantees remain gates.

Run:

```bash
docker compose up -d postgres

cd api
uv sync --frozen
uv run alembic upgrade head
uv run alembic check
uv run python -m app.seed
uv run python -m app.seed
uv run ruff check app tests alembic/versions
uv run ruff format --check app tests alembic/versions
uv run pytest -q
uv run python -m scripts.benchmark_object_graph --objects 100 --relations 100

cd ../web
npm ci
npm run lint
npm run format:check
npm run typecheck
npm test -- --run
npm run build
```

CI must run PostgreSQL 17.

Do not replace a missing PostgreSQL test environment with SQLite.

---

# 18. Browser acceptance scenario

Use the synthetic chlorine project.

The final browser smoke should demonstrate:

1. choose the demo Project/Vault;
2. open Samples;
3. create a new Sample;
4. first Process Block is already present;
5. type `/` and select a Process;
6. type `@` and search an existing Material by CAS/name;
7. verify two-pane preview;
8. attach the Material;
9. attach an Equipment object;
10. verify Material and Equipment render as compact, differently styled tokens without explicit category headings in the token strip;
11. fill Material usage value;
12. fill Equipment usage values;
13. add a new usage field to that Equipment;
14. add a second Process;
15. save;
16. observe explicit success state;
17. open Sample detail;
18. verify clean record-style layout;
19. enter edit mode and confirm the same Composer is reused;
20. return and choose `基于此样品新建`;
21. change one parameter;
22. save;
23. confirm the new Sample and new Process IDs differ while referenced Material/Equipment IDs are reused;
24. verify original Sample was not mutated.

Capture screenshots at approximately:

```text
1440px desktop
1024px compact desktop/tablet landscape
```

The UI should remain usable at both sizes.

---

# 19. Explicit non-goals

Plan 08 does **not** implement:

- embedded AI chat;
- OCR or handwritten-image parsing;
- AI Change Review / Scientific Diff;
- HTML/PDF experiment-manual export;
- Experiment comparison charts;
- non-owning Experiment Sample membership;
- Literature;
- Evidence Gate;
- Evaluation;
- inventory/ERP;
- instrument control;
- Equipment Type inheritance/grouping;
- generic visual template editor;
- React Flow;
- free-form workflow graph editing;
- multiplayer/RBAC;
- a full Material/Equipment management application;
- automatic unit conversion;
- automatic creation of intermediate Sample objects.

Leave extension points; do not prebuild these systems.

---

# 20. Known follow-up plans

## Plan 09 candidate — Experiment membership and comparison

The future Experiment product concept is:

```text
Experiment = a reusable scientific collection of Samples
```

where one Sample may belong to multiple Experiments for comparison.

This requires a dedicated non-owning membership semantic.

Do not use current exclusive `contains` ownership for that purpose.

Plan 09 should decide the exact relation/API and then build:

- create Experiment from existing Samples;
- multi-membership;
- difference matrix;
- Data comparison.

## Later — Printable Experiment Manual

The Sample Record API introduced here should be suitable as a source for a future stable ExportData DTO:

```text
Research Object Graph
→ Sample / Experiment ExportData
→ single-file HTML template with inline CSS
→ browser print / PDF
```

Do not implement the template editor in Plan 08.

## Later — AI record ingestion

External agents can already use the aggregate API after Plan 08.

A later plan may add:

```text
photo / handwritten record
→ AI proposal
→ Scientific Diff
→ human accept
→ Sample Record transaction
```

without changing the Sample storage model.

---

# 21. Definition of done

Plan 08 passes only when all of the following are true:

- Sample create/edit no longer requires the user to edit raw JSON.
- A new Sample starts with one Process Block.
- `/` selects Process definitions.
- `@` resolves Material/Equipment and optional precursor Sample.
- resolver is keyboard-operable and two-pane on desktop.
- resource tokens show names only and are visually distinguished by kind.
- Material and Equipment can be mixed in one input stream.
- actual resource-use values are stored on Process relations.
- Process-own parameters are stored on Process objects.
- per-resource usage-field definitions persist on the concrete Material/Equipment object.
- adding a usage field does not create a new resource object.
- each physical Equipment object remains independent; no Equipment Type hierarchy is introduced.
- a Sample with several Process steps is created atomically.
- the final Process produces the Sample.
- intermediate Samples are not automatically generated.
- `基于此样品新建` creates new Sample and Process IDs while reusing resource identities.
- Sample detail uses a clean record/document visual language.
- complex non-linear legacy graphs are never destructively flattened by the composer.
- current Plan 07.1 Experiment ownership semantics remain intact.
- external agents have precise Sample Recording API documentation.
- all PostgreSQL/backend/frontend CI gates are green.
- handoff records exact implementation and remaining limitations.

Final verdict string after successful execution:

```text
PLAN 08 PASS — SAMPLE-FIRST RECORDING WORKFLOW READY
```
