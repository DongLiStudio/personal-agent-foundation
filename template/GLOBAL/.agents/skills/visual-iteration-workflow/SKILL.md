---
name: visual-iteration-workflow
description: 用于页面和应用界面的视觉迭代工作流判断，提醒 Agent 在可见 Web 页面上做 UI/UX 修改时优先考虑浏览器点选式迭代，尤其是 Impeccable Live Mode。用户提到“点击修改页面”“点某个位置改”“这里看着不对”“现场看页面调设计”“生成几个变体”“局部视觉修改”，或在浏览器预览中指出 layout/spacing/overlap/color/typography/copy/motion 等具体问题时使用。也用于设计初稿生成后，提醒在继续手动 patch 前先考虑 Live Mode。不用于纯后端、非视觉重构、CLI-only 工作或一次性静态解释。
---

# 视觉迭代工作流

使用这个 Skill 作为视觉设计迭代的路由和安全收尾流程。它的核心作用不是替代 `impeccable`，而是在用户正在看页面、想改某个具体视觉位置时，提醒 Agent 优先考虑浏览器里的点选式迭代。

## 判断规则

同时满足以下条件时，优先使用 Impeccable Live Mode：

- 任务涉及 UI/UX、视觉设计、布局、间距、字体、颜色、动效、响应式、文案位置或组件外观。
- 目标是可以在浏览器中打开的 Web 页面或应用界面。
- 用户指向可见位置，例如“这里”“这个位置”“点选修改”“现场看看”“生成几个版本”，或在看完预览后要求局部视觉调整。

以下情况使用普通文件编辑：

- 任务是纯后端、纯数据、纯 CLI，或无法通过浏览器视觉检查。
- 用户只是要先做一个大范围初稿，而且还没有可预览页面。
- Live Mode 需要明显额外配置，而用户明确想要快速静态改动。
- 目标是纯原生 `ios`、`android` 或 `adaptive` 项目，并且没有 Web 预览。

## 推荐流程

1. 检查当前会话是否可用 `impeccable` Skill。可用时，使用它的 Live Mode 说明；在运行 live 命令前读取 `SKILL.md` 和 `reference/live.md`。
2. 如果用户正在浏览器里看页面，且要改具体视觉问题，优先建议 Live Mode，而不是直接 patch 文件。
3. 如果用户同意，或用户本来就要求点击式编辑，从最小且正确的项目根目录启动 Live Mode，不要从过大的父级通用工作区启动。
4. 如果 Impeccable 提示缺少上下文，只在相关页面/产品目录内创建或更新 `PRODUCT.md`、`DESIGN.md` 和 `.impeccable/live/config.json`。不要把通用父项目污染成某个具体产品的上下文。
5. 当 `file://` 页面无法稳定加载注入脚本或浏览器事件时，优先用本地 HTTP 预览地址。
6. 进入 Live poll loop，等待用户提交 `generate`、`steer`、`accept`、`discard` 或 `exit` 事件。
7. 处理 `generate` 时，生成多个有差异但保持品牌一致的变体。除非用户明确要求偏离原风格，否则保留现有设计身份。
8. 用户 `accept` 后，必须先完成 cleanup，再继续 poll：把被接受的 CSS 合入正式源码，移除 `impeccable-carbonize` 标记，移除 `data-impeccable-*` 包装，删除未接受变体的死代码，并在需要时运行 `live-complete.mjs`。
9. 用户结束后，停止 live helper，移除注入脚本，停止本次临时启动的预览服务器，并确认源码中没有 live 标记残留。

## 安全检查

最终源码中不得留下：

- `impeccable-live`
- `live.js`
- `localhost:8400`
- `impeccable-carbonize`
- `impeccable-variants-start`
- `data-impeccable-variant`
- 临时 `@scope` 变体 CSS

不要做宽泛的进程清理。只停止本次启动的 live helper 和临时预览服务器。如果启动了临时服务器，记录端口，收尾时只停止监听该端口且确认为本次预览用途的进程。

如果 Live Mode 改动了生成文件、临时 wrapper 或 fallback 文件，先按 Impeccable 的 fallback/accept cleanup 规则清理，再向用户报告完成。

## 对用户的沟通方式

当适合 Live Mode 时，直接简短说明：

> 这个适合用 Impeccable Live Mode：你在页面上点具体元素、写修改意见，我生成几个变体，你接受后我再写回源码并清理临时标记。

Live 会话中保持操作型更新：说明 helper 已启动、正在等待点击事件、变体已生成、正在清理接受后的临时标记、Live Mode 已停止。

## 回退方案

如果 Impeccable 不可用，退回最佳浏览器检查流程：打开或 serve 页面，观察可见问题，修改源码，刷新验证，并说明本次未使用 Live Mode 的原因。
