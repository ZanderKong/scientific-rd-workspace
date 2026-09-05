# Scientific R&D Workspace Web Agent Guide

This is the Next.js App Router frontend for Scientific R&D Workspace. Read the repository [AGENTS.md](../AGENTS.md) and [`docs/handoff/CURRENT_STATE.md`](../docs/handoff/CURRENT_STATE.md) before changing the UI.

Current pages use the shared Project/Vault shell and seven canonical Research Object kinds. The API client in `src/lib/api-client.ts` is the only frontend data boundary; use the typed domain contracts in `src/lib/domain.ts`. Do not add mock APIs, faker data, Clerk, billing, account routes, or a second query/service abstraction.

Use `src/features/workspace/` for shared workspace behavior, `src/features/equipment/` for resource management, `src/features/settings/` for browser preferences, and `src/app/dashboard/` for thin route entrypoints. Keep the Sample Record aggregate workflow separate from generic object editing.

All new user-visible copy belongs in both `messages/zh-CN.json` and `messages/en.json`. Keep loading, error, empty, keyboard, locale and project-scope behavior visible. The current Experiment Comparison surface is a supported domain capability; legacy generic Compare, Literature, Analysis and Evaluation routes are not active.

Before handoff run:

```bash
npm run lint
npm run format:check
npm run typecheck
npm test -- --run
npm run build
```
