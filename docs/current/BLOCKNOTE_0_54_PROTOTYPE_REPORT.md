# BlockNote 0.54.0 Scientific Composer Prototype Report

> 2026-09-06 修复后复审更正：下表“通过”仅保留为此前局部自动化结果，不能代表完整 P0 门禁。当前 Slot 导航使用全页面查询，ArrowLeft/Right 可跳过正文，Tab 可跨编辑器；最小 B 对照也未交付。见 [补充审计](../handoff/V1_5_REPAIR_FOLLOWUP_AUDIT_2026_09_06.md)。这些问题与真实 IME 门禁关闭前，不得宣称完整交互矩阵通过。

更新时间：2026-09-08。锁定依赖为 `@blocknote/core`、`@blocknote/react`、`@blocknote/shadcn` 0.54.0；直接使用的 `@tiptap/core`、`@tiptap/react`、`@tiptap/pm` 固定为 3.30.6。当前安装树中 Tiptap/ProseMirror 实例已去重。

## 结论

方案 A 仍是当前实现方向：`ProcessRef`/`ObjectRef` 是原子 Custom Inline Content，React NodeView 内渲染多个原生 PropertySlot。字段草稿写回 Ref payload 的 ProseMirror transaction，正文与字段共用编辑器历史；保存 codec 将文档、occurrence、Execution 和 binding 分开提交。本轮补齐了 editor-root 状态隔离、NodeSelection 点击、局部 Ghost decoration、候选分页和 dirty Data 回读保护，但完整门禁尚未关闭。

当前自动化证据支持在不 fork BlockNote 的情况下继续方案 A。方案 B 只在 A 出现公开扩展无法修复的阻断时用于对照；当前未触发该条件，因此没有发展第二套编辑器内核。

## 交互矩阵

| 场景 | 状态 | 证据或限制 |
| --- | --- | --- |
| 中文 IME | 人工门禁待执行 | 已实现 `compositionstart`/`compositionend` 缓冲，Chromium 自动化可保存中文 Unicode；这不等同真实 macOS 输入法选词。当前 Computer Use 只提供 Codex in-app browser，未提供 Safari 或可控 Chrome/Vivaldi tab，因此不能记为通过。 |
| Tab / Shift+Tab | 局部自动化 | PropertySlot 有编辑器内焦点移动实现；首尾正文边界和真实浏览器证据待补。 |
| Escape | 局部自动化 | Slot 可回到 Ref NodeSelection；浮层、输入法和跨字段人工证据待补。 |
| ArrowLeft / ArrowRight | 局部自动化 | 保留原生输入选区并实现边界跳转；相邻 Ref 与段首/段尾仍需浏览器验收。 |
| Backspace / Delete | 局部自动化 | 原子 Ref 删除 handler 存在；与字段空值、剪贴板和历史组合仍需验收。 |
| Undo / Redo | 局部自动化 | 当前 transaction/history 路径可用；保存回填后的混合历史尚未完成证据。 |
| 相邻 Ref | 待验收 | codec 保留 occurrence 重映射；需要真实复制粘贴和选区证据。 |
| 段首 / 段尾 Ref | 待验收 | 需要真实浏览器边界选区证据。 |
| 内部结构复制粘贴 | 局部自动化 | 已有身份重映射；片段外关系清理和剪切移动场景待验收。 |
| 外部纯文本复制粘贴 | 局部自动化 | 外部 HTML/纯文本 codec 存在；真实浏览器粘贴矩阵待验收。 |
| Replace Ref | 局部自动化 | 保留身份和匹配字段；影响确认浮层与整次 Undo 尚未完成。 |
| Ghost Preview | 部分实现 | 已有正文位置 decoration；候选字段摘要注入和 IME 期间行为待验收。 |
| 保存 round-trip | 部分实现 | Sample 既有闭环和 Data dirty 回读保护存在；编辑器完整闭环仍需真实 API/browser 证据。 |

自动化入口为 `web/e2e/sample-composer.spec.ts`，codec 单测为 `web/src/features/workspace/scientific-document/model.test.ts`，后端聚合测试为 `api/tests/test_sample_record.py`。

## 自实现边界

BlockNote 提供文档 schema、Custom Inline Content、Suggestion Menu、基础 selection/clipboard 和底层 transaction/history。项目自行实现 PropertySlot composition 缓冲、焦点恢复、Tab/Escape/Arrow/Delete key handling、Ref paste 身份重映射、外部 HTML 表达、Replace、Ghost 摘要、保存 codec 和 draft generation。

目前没有必须 fork BlockNote 的证据。仍不可关闭的门禁是 macOS 中文输入法在 Chromium 与 Safari 中的输入、选词、取消、空字段和跨字段切换。只有真实 IME 失败可稳定复现，并且 A/B 都无法通过公开 extension/keymap/NodeView 修复时，才触发 fallback 评审。
