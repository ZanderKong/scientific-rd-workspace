# v1.5 修复后补充审计

日期：2026-09-07。对象：`main@93700a6` 加当前全部未提交实现及本轮修复。原 A01–A15 审计保留为历史证据。

## 结论

本轮已关闭 F01–F04 的四个已复现阻断，并将其转成正式回归测试；随后补上项目图锁、typed revision reference、零结果表格筛选入口、删除保护和严格 Scientific Record 契约。修复计划仍未完成，不能关闭第一 Sample 闭环或 P6 发布门禁；双连接并发故障注入、完整历史读写、真实 IME 和固定性能门禁仍有缺口。

## 本轮修复与回归

以下四项使用真实 REST API 和明确隔离的 `scientific_rd_test` PostgreSQL 库执行，无附件写入；正式回归位于 `api/tests/test_v15_repair_regressions.py`，诊断脚本也已改为正确行为断言。

| 编号 | 优先级/原审计 | 触发与观察 | 根因及修复要求 |
| --- | --- | --- | --- |
| F01 | P1 / A01 | 空白 Sample 的通用 PATCH 现在返回 `409 managed_record`，不会产生无 occurrence 的 Ref。 | `ResearchObject.authoring_kind` 持久化 Sample/Data 归属；领域服务和 REST 共享守卫。空文档仍可通过记录命令保存。 |
| F02 | P1 / A04 | bound Object 解绑、保存、再绑定现在成功，并复用原 binding ID。 | binding 增加 `is_active`；解绑停用而不物理删除，当前输出过滤停用行，恢复按稳定 occurrence/binding 身份重新激活。 |
| F03 | P1 / A09 | 删除 Data 获取正文后，`acquisition_document` assignment 被撤销，manual/producer 来源保持独立。 | Data 更新在 `_sync_record` 后按最终 occurrences 重算 acquisition 来源；finalize 与更新共享提取函数。 |
| F04 | P2 / A07 | 重命名被引用 Object 后，Data `record_sha256` 保持不变。 | token 排除动态 `label_snapshot`，只依赖 Data 自身文档、来源、表示和自身 revision。 |

复现脚本：[repair_followup_reproductions.py](audit-2026-09-06/repair_followup_reproductions.py)。运行方式（在 `api`，先设置明确隔离的 TEST_DATABASE_URL）：

```bash
PYTHONPATH=.:tests uv run pytest -q -s ../docs/handoff/audit-2026-09-06/repair_followup_reproductions.py
```

结果：4 项均通过。后端完整套件目前为 44 项；F02 的恢复断言验证了原 binding 身份保持不变。

## 静态确认与待验证风险

1. **P1 / A07：Data 并发路径已加锁，但双连接验收仍待执行。** Data、View、Claim、Sample 和图关系写入均先获取项目图锁，再在锁内读取 owner；仍需用两个独立连接验证一个 stale、一个成功，并补提交前/后故障注入。
2. **P1 / A05：typed revision reference 结构已补齐。** 迁移 `0021_typed_revision_refs` 增加 Object/Execution/View/Claim 的来源与目标外键和索引，View、Claim、ProcessExecution 主要 revision 写入路径已接入；影响查询、维护命令和完整历史读写仍未关闭。
3. **P2 / A13：Composer 焦点范围已修正。** Tab 和自动聚焦限定当前 ScientificComposer；左右箭头在 Ref 边界恢复 ProseMirror 正文 selection。真实中文 IME、完整 13 类交互和最小 B 对照仍需人工/原型证据。
4. **P2 / A11：零结果筛选撤销入口已修正。** 字段目录独立于匹配 rows，活动筛选和清除按钮在 0 行时保持可见，并由浏览器回归覆盖。
5. **P2 / A15：CI 已纳入六项非首跑浏览器文件。** 本地最新代码的六项 Chromium 流程全部通过；Ubuntu 快捷键和真实 macOS IME 证据仍是独立门禁。

## 本次验证和证据边界

- 重新执行现有后端完整套件：44 项通过。
- 重新执行与 CI 相同范围的 Ruff check/format（app、tests、scripts、alembic/versions）：通过，69 文件已格式化。
- 新增四项正式回归及对应正确行为诊断，均已通过；历史缺陷观察保留在原审计材料中。
- 本轮已重跑前端 lint、format、typecheck、Vitest、production build、六项 Chromium 浏览器流程和 Alembic check；真实 IME、双连接并发、故障注入、规定性能环境仍未执行。
- 原型 B、macOS Chromium/Safari 真实 IME、13 类交互完整证据、双连接并发、1/10/100 Ref SQL 曲线及规定性能分位数仍不能视为完成。单次 100 Ref 读取 10 SQL 的改善不等于性能总门禁通过。
- 本次追加 `0020_authoring_and_binding_lifecycle` 与 `0021_typed_revision_references` 迁移并修改产品代码；隔离验证库已升级至 head，开发数据库未升级，也未建立提交。当前仍是大量未提交改动，阶段交付的可审查提交要求尚未落实。

优先收口：F01/F02 → Data 来源与共用锁内命令 → 不可变引用保护 → 编辑边界及 CI/产品验收。沿用既定修复 Plan，不需要再写一套新计划。
