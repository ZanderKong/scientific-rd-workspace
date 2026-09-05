# Web Agent Guide

这是 Scientific R&D Workspace 的 Next.js App Router 前端。当前页面只围绕七种 Research Object 和 Project/Vault scope 展开。

## 结构

- `src/features/workspace/components/workspace-app.tsx`：共享 object list/detail/editor/composer/context surface。
- `src/lib/domain.ts`：前端 domain 类型。
- `src/lib/api-client.ts`：唯一 REST client；API 不可达时显示明确错误。
- `src/config/nav-config.ts`：active workspace 导航。
- `src/app/dashboard/`：按 object kind 的薄路由页面。

## 约束

- 旧 generic Compare、Analysis、Literature、Evaluation 入口不在当前导航；当前 `Experiment Comparison` 是正式支持的 Experiment domain surface，不得与旧 Compare 混称。
- 不把 Project/Experiment/Measurement 做成第二套 domain model。
- 结构化字段与 BlockNote-compatible content 分开；不要把关系推导结果写回对象属性。
- `@` reference、箭头键、Enter、Tab、Escape 和 Cmd/Ctrl+Enter 是 Process composer 的核心交互。
- 所有可达 copy 来自 `messages/zh-CN.json` 与 `messages/en.json`，两套 key tree 必须一致。

## 命令

```bash
npm ci
npm run lint
npm run typecheck
npm test -- --run
npm run build
```
