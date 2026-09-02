# UI Direction + i18n Foundation — Plan 1 Handoff

状态：`PLAN 1 PASS — UI DIRECTION + I18N FOUNDATION ACCEPTED`

本 handoff 只关闭附件 `04-ui-direction-i18n-foundation.md` 的 Plan 1。Plan 2 未开始。

## 交付范围

- `zh-CN` 是默认 UI locale，`en` 是第二 locale；没有 URL locale prefix。
- locale 通过 first-party cookie 持久化；切换语言不改变 dashboard URL，`<html lang>` 与 active locale 一致。
- translation catalogs 位于 `web/messages/zh-CN.json` 与 `web/messages/en.json`，并由自动化测试校验 key tree parity。
- global shell、导航分组、header、search、theme、breadcrumbs、状态、表单、表格、空/加载/错误状态和当前可达 Workspace 页面均接入 active locale。
- Overview、Experiment Detail、Analysis Detail 建立 Plan 2 可复用的科学工作台视觉方向：紧凑摘要、研究活动、实验元数据/溯源、Evidence Gate 与 Confidence 分离、Direct Structured Support 与 Curated Evidence 分离。
- 项目、实验、文献标题/摘要、实验记录和 Finding prose 保持 API 原文；canonical API/database enums 保持英文值。
- 日期、数字和文件大小使用 active locale formatter；状态/gate/review 文案通过集中映射生成。

## 第三方集成

- BlockNote 使用上游 `@blocknote/core/locales` 的 `zh` / `en` dictionary；`zh-CN → zh`、`en → en`。locale 切换会重建 editor instance，但不改写 persisted document JSON 或用户内容。
- JSON Forms 使用官方 `i18n` prop、active locale、app-owned `translate` / `translateError` adapter，并对 schema presentation labels 做窄范围映射；没有 fork 或 broad renderer rewrite。
- 已核对安装的 JSON Forms Vanilla renderer 源码：`TableArrayControl` 的 `Valid` 表头是 renderer 内部 literal，官方 i18n translator 没有暴露该 literal 的覆盖点。当前已尽可能通过官方 translator、schema labels 和 action strings 本地化；该单一 `Valid` 表头作为已记录的 upstream limitation 保留，避免为了一个不可扩展的 literal 替换/分叉整个 renderer。其余代表性 Experiment Detail 表单 UI 已按 locale 呈现。

## 验收证据

### 本地 frontend gates

在 `web/` 执行并通过：

- `npm run test -- --run`：3 个 test files、10 个 tests 通过。
- `npm run lint`：exit 0；仅有基线 `calendar.tsx`、`kbar/render-result.tsx`、`info-button.tsx` warnings。
- `npm run typecheck`：通过。
- `npm run build`：通过，15 个 App Router 页面/动态路由完成 production build。
- `npm run format:check`：通过。

### Browser audit

使用本地 API 演示数据和干净重启的 frontend dev server `http://localhost:3000` 验收：

- 1280px：Overview、Experiment Detail、Analysis Detail 均分别检查 `zh-CN` 与 `en`。
- 1024px：以上三条关键页面均分别检查 `zh-CN` 与 `en`；sidebar 收缩可用，没有 horizontal overflow。
- 当前所有可达路由快速巡检（中英文）：Overview、Projects、Project Detail、New Experiment、Experiments、Experiment Detail、Compare、Literature、Analysis、Analysis Detail、Evaluations。
- 每个检查页均有内容、URL path 保持原样、没有应用错误、没有 horizontal overflow；干净页控制台没有 error/warning。
- 语言切换后 URL 不变；切换到 English 后刷新仍保持 English。
- BlockNote 记录页的中文/英文 toolbar aria labels 随 locale 切换；实验记录内容保持原文。
- 深色模式在 1024px English Overview 已切换并恢复，页面无 overflow 或错误。
- 代表性 Analysis Detail 验证了 Confidence、Evidence Gate、Direct Structured Support、Curated Evidence 的独立呈现；原始 payload 默认折叠，不是 primary analysis UI。

### CI

- [Phase 3 Scientific AI CI — run 33616425909](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33616425909)：success。
- [Phase 1 CI — run 33616425820](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33616425820)：success。

## Git 与边界

- 接受基线：`v0.1-demo` / `9518dd5d9c3ee228a7b543d01bb9a907811c21ef`。
- 实现提交：`1280977029b54abe4fbcfeaa52e3b53e75a8391c`，已推送到 `origin/main`。
- 本批次未修改 `api/`，未添加 backend locale 参数，也未引入新 release tag。
- 本地 SQLite、uploads 和 `.next` 等生成物未纳入 Git。
- Plan 2（全站更深层视觉重建、lineage/provenance visualization、portfolio polish 等）明确延期；本 handoff 完成后停止。
