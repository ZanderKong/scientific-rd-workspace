# Phase Handoff Template

# Phase

Phase X — Name

## 1. Status

- PASS / PARTIAL / BLOCKED
- Git commit/tag:
- Date:

## 2. What Was Actually Implemented

按真实代码描述，不复制计划。

## 3. Repository Structure

列出关键目录。

## 4. Runtime

### Prerequisites

### Environment Variables

### Start Commands

### Migration Commands

### Seed Commands

### Test Commands

## 5. Actual Data Model

列出当前表、重要字段、重要约束。

如果与 `docs/DATA_MODEL.md` 不同，说明差异和原因。

## 6. Actual API

列出 P0 endpoints。

## 7. Frontend Routes

列出可访问 route。

## 8. Third-party Dependencies

列出关键依赖版本和许可证注意事项。

## 9. Verification Results

- frontend lint:
- frontend typecheck:
- frontend tests:
- frontend build:
- backend tests:
- migration blank DB:
- seed idempotency:
- browser smoke:
- demo scenario:

## 10. Known Issues

只列真实存在问题。

区分：
- blocker
- non-blocking debt
- intentionally deferred

## 11. Architectural Decisions Made During Implementation

记录计划之外但合理的决定。

## 12. Phase 2 Constraints

告诉下一阶段：
- 哪些接口必须保留
- 哪些地方已经预留
- 哪些地方不要碰
- 已知 migration 风险

## 13. Recommended Next Action

一句话说明下一步。
