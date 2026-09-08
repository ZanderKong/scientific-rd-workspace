# Scientific Composer 编辑器改进进度

更新时间：2026-09-08

本轮改动围绕 v1.5 编辑器方案的前端闭环，继续复用 BlockNote 0.54.0、现有 ScientificDocument codec 和领域 API。当前交付的是第一批可运行改进，不能替代真实中文输入法和人工视觉验收。

## 已实现

- Sample 页面收敛为 960px 单栏文档布局，标题作为主输入，保存并再建/批量创建收进更多菜单。
- Ref 使用轻量阅读样式，只有活动 Ref 显示边界；字段输入取消固定窄宽度，长值可在合理范围内查看。
- Ref 的活动事件在各自 editor root 内冒泡，不再使用 document 全局选择事件；同页多个 Composer 不互相抢状态。
- Ref 点击可建立 ProseMirror `NodeSelection`，Backspace/Delete 仍作用于整节点。
- local 字段的改名、排序和删除收进字段菜单；新增属性表单保持在 Ref 附近。
- `/` 和 `@` 搜索使用 150ms 防抖、AbortSignal、请求序号和稳定 offset 分页；服务端 Process 列表增加 offset 与 ID 平局排序。
- 搜索触发词旁增加只读 ProseMirror decoration Ghost，不进入文档、复制或保存结构。
- 快捷创建 Object/Process 通过 `Idempotency-Key` 调用现有创建命令；重复请求回放同一结果。
- Data 草稿回读只在没有本地 dirty 编辑时更新 BlockNote 初始内容；保存期间的输入不会因回读重挂载而被覆盖。

## 已执行检查

- `web`: `npm run lint`
- `web`: `npm run typecheck`
- `web`: `npm run test`（14 tests passed）
- `web`: `npm run build`
- `api`: `uv run ruff check app tests`

## 待验收

- 尚未在 macOS Chromium 和 Safari 中用真实中文输入法完成拼音、选词、取消、切换 Slot、保存快捷键和回填后继续输入的证据。
- 尚未完成视觉样稿的桌面/窄屏、明暗主题截图及用户确认。
- 候选菜单仍沿用 BlockNote `SuggestionMenuController`；当前已限制首屏 20 条并丢弃过期请求，但“加载更多”按钮和候选错误重试还需要独立 UI 状态。
- Ghost 已进入 ProseMirror decoration，但候选字段摘要尚未从 SuggestionMenu session 注入 decoration；当前显示类型提示。
- A/B 输入原型、剪贴板全场景、真实 API/browser 闭环和性能 p95 仍未通过，不能标记为完成。

