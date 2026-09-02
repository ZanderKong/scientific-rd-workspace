# Open Source Strategy

## 1. Strategy

只允许三种复用方式：

### A. Starter / shell
Fork 或复制一个主项目作为整体 UI 和工程壳。

### B. Package / component
通过 package manager 引入成熟组件。

### C. External service
未来通过 API 接入独立系统。

禁止：
把多个完整 Web App 的源码 merge 成一个产品。

## 2. Main Starter

### Kiranism / next-shadcn-dashboard-starter

用途：
- Next.js App Router shell
- sidebar/layout
- tables
- query patterns
- forms/UI patterns
- shadcn foundation

当前上游说明：
- Next.js 16
- React 19
- Tailwind CSS v4
- shadcn/ui
- MIT
- 带 feature cleanup script
- 带 AGENTS.md，可供 coding agent 理解项目约定

Phase 1 bootstrap 时必须先检查上游 README 和实际 cleanup options。

不要假定历史命令仍然存在。

建议：
1. 复制 starter 到 `web/`。
2. 保留上游 MIT license / attribution。
3. 使用 cleanup script 删除与本项目无关的 chat、kanban、billing 等功能。
4. Auth 在 Phase 1 可以移除或保持最小本地模式；不得为了 Clerk 配置阻塞 Demo。
5. 不要持续 merge upstream，第一版将它视为一次性 starter snapshot。

Upstream:
https://github.com/Kiranism/next-shadcn-dashboard-starter

## 3. BlockNote

用途：
Experiment Rich Note。

使用：
普通开源 packages。

许可：
主体 MPL-2.0。
XL packages 使用不同许可，Phase 1 明确不使用 `@blocknote/xl-*`。

重要：
如果直接修改 MPL 覆盖的 BlockNote 源文件，需要遵守 MPL 对修改文件的要求。优先作为 dependency 使用，不 vendoring 和修改上游源码。

Upstream:
https://github.com/TypeCellOS/BlockNote

## 4. JSON Forms

用途：
Schema-driven Experiment Structured Properties。

优先使用：
- `@jsonforms/core`
- `@jsonforms/react`
- 一个官方 renderer set

如果默认 renderer 视觉与 shadcn 不一致：
- 先通过 wrapper/CSS 做最低统一。
- 不在 Phase 1 重写完整 renderer library。

Upstream:
https://github.com/eclipsesource/jsonforms

License:
MIT。

## 5. LiteLLM

Phase 3 M1–M9 embeds the LiteLLM Python SDK behind the Workspace `AIProvider` interface. The
LiteLLM Gateway/Proxy service is deliberately not included. Exact dependency versions are verified
at implementation time and locked in `api/uv.lock`; provider credentials remain server-side.

Upstream:
https://github.com/BerriAI/litellm

License:
MIT (SDK; transitive licenses remain in lockfiles).

## 6. Langfuse

Phase 3 M1–M9 optionally projects traces, evaluation dataset items and scores; it is disabled by
default and never authoritative.

用途：
- traces
- datasets
- evaluation
- annotation / feedback

不复制 Langfuse UI 源码进主仓库。
通过 SDK/API 或独立 self-hosted service 使用。

核心仓库主体 MIT，`ee` 目录有单独企业许可。Phase 3 必须重新核对当时版本。

Upstream:
https://github.com/langfuse/langfuse

## 7. Zotero

Phase 2 才考虑接入。

用途：
Literature provider。

优先：
Zotero Web API v3 或 Local API。

不自己写完整 reference manager。

Docs:
https://www.zotero.org/support/dev/web_api/v3/

## 8. eLabFTW / Kadi4Mat / NOMAD / Chemotion

定位：
**设计参考，而不是 Phase 1 runtime dependency。**

学习：
- ELN record semantics
- template/metadata
- sample/data relationship
- provenance
- materials schema

Phase 1 不部署这些系统。

## 8. Third-party Notice

Agent bootstrap 后应新增：

```text
THIRD_PARTY_NOTICES.md
third_party_licenses/
```

至少记录：
- dashboard starter MIT
- JSON Forms MIT
- BlockNote MPL-2.0

依赖包自己的许可证由 package manager lockfile 管理，但直接复制的 starter 必须保留 attribution。

## 9. License Guardrail

本计划不是法律意见。

如果 Agent 发现：
- 上游 license 已变化
- package 进入 GPL/AGPL dependency
- 需要复制而不是 link 一个更强 copyleft 的源码

必须停止该具体集成，提出替代方案，不得静默继续。

## 10. Phase 1 verification — 2026-09-01

- Kiranism starter was bootstrapped from commit `7705dfc0d13889e45c26a55ad5908da6a7a9a605` and cleaned using its current cleanup script before project-specific routes were added.
- npm is the reproducible web package manager for this checkout; Bun was not present in the execution environment.
- JSON Forms `3.8.0` uses the official vanilla React renderer set with a wrapper style layer.
- BlockNote `0.54.0` uses `@blocknote/core`, `@blocknote/react`, and `@blocknote/shadcn`; no XL packages are included.
- Direct attribution files are present at `THIRD_PARTY_NOTICES.md` and `third_party_licenses/`.
