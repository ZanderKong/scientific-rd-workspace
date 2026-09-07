# BlockNote 0.54.0 Scientific Composer Prototype Report

> 2026-09-06 修复后复审更正：下表“通过”仅保留为此前局部自动化结果，不能代表完整 P0 门禁。当前 Slot 导航使用全页面查询，ArrowLeft/Right 可跳过正文，Tab 可跨编辑器；最小 B 对照也未交付。见 [补充审计](../handoff/V1_5_REPAIR_FOLLOWUP_AUDIT_2026_09_06.md)。这些问题与真实 IME 门禁关闭前，不得宣称完整交互矩阵通过。

更新时间：2026-09-06。锁定依赖为 `@blocknote/core`、`@blocknote/react`、`@blocknote/shadcn` 0.54.0；直接使用的 `@tiptap/core`、`@tiptap/react`、`@tiptap/pm` 固定为 3.30.6。当前安装树中 Tiptap/ProseMirror 实例已去重。

## 结论

方案 A 已作为当前实现：`ProcessRef`/`ObjectRef` 是可选择的原子 Custom Inline Content，React NodeView 内渲染多个原生 `input` PropertySlot。字段草稿写回 Ref payload 的 ProseMirror transaction，正文与字段共用编辑器历史；保存 codec 将文档、occurrence、Execution 和 binding 分开提交。

当前自动化证据支持在不 fork BlockNote 的情况下继续方案 A。方案 B 只在 A 出现公开扩展无法修复的阻断时用于对照；当前未触发该条件，因此没有发展第二套编辑器内核。

## 交互矩阵

| 场景 | 状态 | 证据或限制 |
| --- | --- | --- |
| 中文 IME | 人工门禁待执行 | 已实现 `compositionstart`/`compositionend` 缓冲，Chromium 自动化可保存中文 Unicode；这不等同真实 macOS 输入法选词。当前 Computer Use 只提供 Codex in-app browser，未提供 Safari 或可控 Chrome/Vivaldi tab，因此不能记为通过。 |
| Tab / Shift+Tab | 通过 | PropertySlot 正反向移动焦点。 |
| Escape | 通过 | Slot 退出到 Ref NodeSelection，焦点回编辑器。 |
| ArrowLeft / ArrowRight | 通过 | Slot 边界在相邻 Slot 和 Ref 外文档 selection 之间移动。 |
| Backspace / Delete | 通过 | 原子 Ref 删除；Delete 与紧邻 paste 的 history 分组问题已由 Ref key handler 修复。 |
| Undo / Redo | 通过 | 字段、Backspace、Delete 与正文共享历史；Delete 的 undo/redo 已单独覆盖。 |
| 相邻 Ref | 通过 | 内部粘贴形成相邻 Ref，保持独立 occurrence/execution 身份。 |
| 段首 / 段尾 Ref | 通过 | 空段插入、Ref 外 selection 和删除恢复已覆盖。 |
| 内部结构复制粘贴 | 通过 | 保留结构和值，重映射 occurrence，清空 execution/binding 持久化 ID。 |
| 外部纯文本复制粘贴 | 通过 | 导出 `/Process`/`@Object` 与已填字段；纯文本输入按普通正文粘贴。 |
| Replace Ref | 通过 | 保留 occurrence 与稳定 execution/binding 身份，只替换目标和匹配字段。 |
| Ghost Preview | 通过 | 候选菜单显示字段标签摘要，不进入文档与历史。 |
| 保存 round-trip | 通过 | 创建、保存、重开、更正、历史读取和“保存并再建一份”闭环通过。 |

自动化入口为 `web/e2e/sample-composer.spec.ts`，codec 单测为 `web/src/features/workspace/scientific-document/model.test.ts`，后端聚合测试为 `api/tests/test_sample_record.py`。

## 自实现边界

BlockNote 提供文档 schema、Custom Inline Content、Suggestion Menu、基础 selection/clipboard 和底层 transaction/history。项目自行实现 PropertySlot composition 缓冲、焦点恢复、Tab/Escape/Arrow/Delete key handling、Ref paste 身份重映射、外部 HTML 表达、Replace、Ghost 摘要、保存 codec 和 draft generation。

目前没有必须 fork BlockNote 的证据。仍不可关闭的门禁是 macOS 中文输入法在 Chromium 与 Safari 中的输入、选词、取消、空字段和跨字段切换。只有真实 IME 失败可稳定复现，并且 A/B 都无法通过公开 extension/keymap/NodeView 修复时，才触发 fallback 评审。
