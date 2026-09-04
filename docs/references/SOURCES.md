# Reference Sources

本文件记录规划时核对的主要外部来源。开发 Agent 应在真正集成时再次确认当前版本。

## Agent-oriented engineering

Harness engineering:
https://openai.com/index/harness-engineering/

Relevant planning takeaways from the engineering reference:
- Keep AGENTS.md as a map rather than a giant manual.
- Put durable repository knowledge in structured docs.
- Break large goals into smaller building blocks.
- Make tests and the dev environment directly legible to the agent.
- Prefer well-scoped tasks and explicit verification.

## Dashboard Starter

Kiranism next-shadcn-dashboard-starter:
https://github.com/Kiranism/next-shadcn-dashboard-starter

License:
https://github.com/Kiranism/next-shadcn-dashboard-starter/blob/main/LICENSE

Planning-time state:
- Next.js 16
- React 19
- shadcn/ui
- Tailwind CSS v4
- MIT
- feature cleanup script

## BlockNote

Repository:
https://github.com/TypeCellOS/BlockNote

License:
https://github.com/TypeCellOS/BlockNote/blob/main/LICENSE.txt

Planning-time license note:
- main source/packages: MPL-2.0
- XL packages: different GPL/commercial terms
- Phase 1 avoids XL packages

## JSON Forms

Repository:
https://github.com/eclipsesource/jsonforms

MIT license.

## Langfuse

Repository:
https://github.com/langfuse/langfuse

License:
https://github.com/langfuse/langfuse/blob/main/LICENSE

Planning-time note:
Core repository is MIT except separately licensed enterprise directories.
Integration is deferred to Phase 3.

## Zotero

Web API v3:
https://www.zotero.org/support/dev/web_api/v3/

At planning time, API v3 is documented as the default/recommended API.
Integration is deferred to Phase 2.
