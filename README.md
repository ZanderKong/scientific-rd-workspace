# Scientific R&D Workspace

**简体中文** | [English](README.en.md)

让研发人员更简单地用上 AI 辅助科研。Scientific R&D Workspace 将研究对象、实验过程、数据和结论组织为可关联的结构化记录，为人和 AI 提供共同的科研工作台。

推荐通过 Codex 等外部 AI 客户端连接应用的 MCP：AI 帮助整理、查询和提出记录变更，工作台负责结构化存储、关系管理与版本追溯，研究人员在界面中查看和审核。

> 当前为开发版本，v1.5 工作流重构仍在验收中。完整并发、真实中文输入法及规模性能门禁尚未完成，详见[当前状态](docs/handoff/CURRENT_STATE.md)。

## 工作流

- **对象与模板**：维护材料、设备、样品及过程定义，复用字段与模板版本。
- **Sample 与 Data**：在正文中引用对象和过程、填写实际值；组织数据表示、原始附件与获取来源。
- **Experiment**：关联已有记录，为研究任务提供上下文和表格查看。
- **View 与 Claim**：登记分析产物和论断，记录其来源与固定版本。

应用不内置大模型或分析运行时。模型推理和分析由外部工具承担，工作台用于组织依据、记录结果和保留关联。

## 安装与启动

需要 **Git、Node.js 22、Python 3.11–3.13、uv 和 Docker Compose**。以下命令用于全新本地安装；已有数据库升级前请先备份并阅读[当前状态](docs/handoff/CURRENT_STATE.md)。

```bash
git clone https://github.com/ZanderKong/scientific-rd-workspace.git
cd scientific-rd-workspace
docker compose up -d --wait postgres

cd api
cp .env.example .env
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

另开终端，在仓库目录运行前端：

```bash
cd web
npm ci
npm run dev
```

打开 [工作台](http://localhost:3000/dashboard)，API 文档位于 [http://localhost:8000/docs](http://localhost:8000/docs)。默认无需演示数据；如需体验示例，可在 `api` 目录运行 `uv run python -m app.seed`。

配置说明：

- `api/.env`：数据库连接、上传限制和存储路径，参见[配置示例](api/.env.example)。默认 PostgreSQL 端口为 `5432`；已有 PostgreSQL 可直接配置 `DATABASE_URL`，无需启动 Compose 数据库。
- `web/.env.local`：可选设置 `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`，默认即此地址。
- PostgreSQL 保存结构化记录；附件默认保存在 `data/uploads/`。备份时需同时保存数据库与附件目录。

默认配置面向本机开发，尚无多用户权限管理；公网部署需另行配置访问控制。

## 使用 AI 与 MCP

完成安装后，推荐让 Codex 或其他支持 MCP 的客户端直接连接工作台。MCP 与 Web API 使用同一数据库和领域服务。

### Codex：本地 stdio（推荐）

在仓库根目录执行以下命令，将 MCP 注册到 Codex。客户端会按需启动 MCP 进程，PostgreSQL 需保持运行：

```bash
codex mcp add scientific-workspace -- uv --directory "$PWD/api" run --frozen python -m app.agent.mcp_server --transport stdio
```

其他客户端可使用相同启动命令，工作目录设为仓库的 `api` 目录。请确保 MCP 与 API 使用相同的数据库和附件存储配置。

### Streamable HTTP

需要独立 MCP 服务时，在 `api` 目录运行：

```bash
uv run python -m app.agent.mcp_server --transport streamable-http --host 127.0.0.1 --port 8001
```

客户端连接地址为 `http://127.0.0.1:8001/mcp`。Codex 可执行：

```bash
codex mcp add scientific-workspace --url http://127.0.0.1:8001/mcp
```

两种接入方式任选其一。非本机绑定要求设置 `MCP_BEARER_TOKEN`，更多说明见 [MCP 接入文档](docs/current/agent/MCP_CLIENT_SETUP.md)。

### 推荐操作方式

1. 在工作台创建项目，准备研究对象和过程模板。
2. 让 AI 先读取 capabilities、项目上下文与已有记录，避免重复建档。
3. 让 AI 将实验笔记整理为结构化记录、关联样品和数据，并提出 ChangeSet。
4. 在工作台查看变更并审核应用；分析后继续登记数据、产物及论断的来源。

可以这样向 AI 发起任务：

> 请使用 scientific-workspace MCP，先读取能力和项目上下文，再查找已有样品与过程模板。将我提供的实验笔记整理成记录，保留原始值和单位，不补造缺失信息；涉及写入时先提出 ChangeSet，供我审核。

具体可用操作以服务端 capabilities 和 MCP 工具为准，接口说明见 [Agent Interface](docs/current/agent/AGENT_INTERFACE.md)。

## 设计思想

- **结构与正文结合**：保留科研叙述，同时为对象、过程和字段建立明确身份，便于查询和复用。
- **记录事实与来源**：区分过程模板与实际执行、数据与其表示、分析产物与论断，以版本引用表达依据。
- **人和 AI 共用规则**：Web、REST 和 MCP 复用领域服务；外部 AI 默认提出变更，由可信审核流程应用。
- **保持工具边界**：PostgreSQL 管理结构化数据，文件存储保留原始附件；不在工作台内另建模型或分析引擎。

技术栈：Next.js / React / TypeScript / BlockNote；FastAPI / SQLAlchemy / Alembic / PostgreSQL 17；MCP stdio 与 Streamable HTTP。

## 项目文档

[架构](ARCHITECTURE.md) · [产品定义](docs/current/PRODUCT_SPEC.md) · [数据模型](docs/current/DATA_MODEL.md) · [REST API](docs/current/api/DOMAIN_API.md) · [当前进度与验收](docs/handoff/CURRENT_STATE.md) · [文档索引](docs/README.md) · [第三方许可](THIRD_PARTY_NOTICES.md)
