# Scientific R&D Workspace — v0.2 Research Object Graph

这是一个以 PostgreSQL 为唯一数据库、以 object graph 为 canonical domain 的科研研发工作台。用户可以在 Project/Vault 作用域内记录材料、样品、设备、过程、数据和实验，并通过有语义的关系、附件导入、数据 payload 和 revision snapshot 保持可追溯性。

## 当前能力

- 七种 object：`material`、`sample`、`equipment`、`process`、`data`、`experiment`、`project`。
- 六种 relation：`contains`、`includes`、`uses`、`produces`、`precedes`、`related_to`；其中 `includes` 是 Experiment → Sample 的非拥有成员关系。
- `sample` 保持 object kind；`precursor` / `subject` / `reference` / `control` 是 `uses` 角色，只有前驱体驱动 lineage、只有 subject 驱动当前 Data。
- Experiment ownership 与 Process producer cardinality 由 PostgreSQL partial unique index 和后端语义校验共同保证；Process composition 使用单次 desired-state PUT。
- Sample-first recording 使用 `GET /samples/{id}/record`、`POST /sample-records` 和 `PUT /samples/{id}/record`；Sample Composer 将 Process、自身参数、资源 identity 与本次使用值一次性提交。
- Material/Equipment 的 `usage_schema_jsonb` 定义具体资源可记录的使用字段；实际值写在 Process `uses` relation，`基于此样品新建` 会生成新的 Sample/Process IDs 并复用资源 identity。
- JSON Schema 驱动类型版本、并发安全 code counter、PostgreSQL JSONB/pg_trgm 索引。
- Sample direct/upstream/downstream lineage 与 Experiment context API。
- CSV/XLSX 预览、显式 X/Y 映射、immutable XY payload、scalar/table/file typed payload、source checksum 和 provenance guard。
- Project/Experiment/Data/Execution domain records、ETag/idempotency、ChangeSet review 和官方 MCP stdio/Streamable HTTP adapter。
- 中文优先的 Next.js shell、Project/Vault switcher、`@` reference composer、双语 UI。

Compare、Literature、AI、Evidence 和 Evaluation 暂不属于 active v0.2 runtime；详见 `docs/PRODUCT_SPEC.md`。

## 启动

要求：Node.js 22、`uv`、Docker Compose。

```bash
docker compose up -d postgres

cd api
uv sync --frozen
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:app --reload --port 8000
```

另开终端：

```bash
cd web
npm ci
npm run dev
```

打开 `http://localhost:3000/dashboard/overview`。

## 验证

```bash
cd api
uv run ruff check app tests alembic/versions
uv run pytest -q

cd ../web
npm run lint
npm run typecheck
npm test -- --run
npm run build
```

API tests 需要 PostgreSQL；仓库不会以 SQLite 作为替代。CI 使用 PostgreSQL service 执行 migration、重复 seed、API tests 和前端门禁。

## 文档

- `AGENTS.md` — agent 工作约定
- `ARCHITECTURE.md` — 系统边界与依赖方向
- `docs/PRODUCT_SPEC.md` — 产品边界
- `docs/DATA_MODEL.md` — canonical schema
- `docs/UI_SPEC.md` — shell 与交互契约
- `docs/DEMO_SCENARIO.md` — synthetic/anonymised demo 路径
- `docs/exec-plans/07-v0.2-research-object-graph-core-cutover.md` — 本次执行计划
- `docs/handoff/V0_2_RESEARCH_OBJECT_GRAPH_CORE_HANDOFF.md` — 交付与验证记录
- `docs/exec-plans/07.1-v0.2-core-semantic-stabilization.md` — 核心语义稳定化计划
- `docs/handoff/V0_2_CORE_SEMANTIC_STABILIZATION_HANDOFF.md` — 语义稳定化交付与验证记录
- `docs/exec-plans/08-sample-first-recording-editor.md` — Sample-first recording/editor execution contract
- `docs/exec-plans/09-scientific-workspace-agent-platform.md` — Plan 09 completion record
- `docs/agent/SAMPLE_RECORDING.md` — external agent contract
- `docs/agent/SAMPLE_RECORDING_API_EXAMPLES.md` — aggregate API examples
- `docs/api/DOMAIN_API.md` and `docs/api/ERRORS_AND_CONCURRENCY.md` — domain API contracts
- `docs/agent/MCP_TOOLS.md`, `docs/agent/MCP_RESOURCES.md`, `docs/agent/CHANGE_SET_WORKFLOW.md` — external agent contract
