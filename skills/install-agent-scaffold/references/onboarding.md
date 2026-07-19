# 首次使用教程

GLOBAL、Skill 和身份配置完成后立即执行本教程，不把用户丢在“安装成功”页面。

## 1. 解释三层关系

- `GLOBAL`：跨项目治理、账号路由、Skill 源稿和长期规则。
- Agent 项目：管理一个长期目标的上下文、任务、决策和组织。
- 实际产品工程：由某个 Agent 项目管理的代码、设计或业务交付，不必复制 Agent 项目治理结构。

## 2. 设置全局个性化提示词

按 `host-integration.md` 引导用户在当前宿主设置中找到入口，原样展示其中的完整全局个性化提示词并要求保存。不能只告诉用户“去设置提示词”，也不能临时概括成更短版本。等待用户说明保存入口并确认已保存后继续；宿主支持回读时核对完整文本。

## 3. 创建第一个项目目录

询问项目名和一句话目标，在 `AGENT_ROOT` 下、与 `GLOBAL` 同级创建目录。不要在 GLOBAL 内创建项目。

## 4. 打开项目

引导用户通过当前 Agent 的“打开目录、添加项目或导入工作区”能力打开新目录。宿主支持自动操作时可协助，但不要假装已打开。

## 5. 建立项目总经理会话

让用户创建首个长期会话或任务，建议标题“<项目名>总经理”，并发送：

```text
请作为本项目的项目总经理，先调用 $init-agent-project。
项目名：<项目名>
项目根目录：<绝对路径>
一句话目标：<目标>
完整读取生成的 AGENTS.md、README.md、STATUS.md 后，核验项目结构、GLOBAL 登记和本地 Git，再给出唯一下一步。不要创建远端或 push。
```

## 6. GLOBAL Skill 快速试用

引导用户在当前宿主中查看已恢复的 GLOBAL Skills，并按安全顺序试用。目标是让用户知道“装好了以后能怎么用”，不是强行执行所有外部写操作。

先展示 Skills 分组：

- 项目与治理：`init-agent-project`、`record-skill-dependency`、`align-agent-projects-with-global`、`migrate-agent-root`。
- 账号与工具：`github-cli`、`feishu-profile`。
- 任务与排程：`feishu-task`、`personal-schedule-planner`、`decide-next-action`。
- 知识库：`json-canvas`、`obsidian-bases`、`obsidian-cli`，以及已安装或待安装的 Obsidian 连接能力。
- 视觉与前端协作：`visual-iteration-workflow`，以及可选外部 UI/UX 能力。

然后执行最小无害试用：

1. 对只读或本地文档类 Skill，演示“如何调用”和一次只读检查，例如让 `decide-next-action` 说明需要哪些上下文，或让 `github-cli` 检查当前 GitHub 登录状态。
2. 对需要外部账号的 Skill，先说明依赖和权限，再询问是否现在授权；用户未授权时标记为“已安装、待连接”，不要伪造成功。
3. 对会写入任务、日历、GitHub、Obsidian 或项目文件的 Skill，只展示 dry-run、计划或示例调用；真实写入必须另行确认。
4. 对当前宿主无法发现或无法启用的 Skill，报告“源稿已恢复、宿主尚未启用”，并给出宿主的安装或刷新入口。

试用完成后，向用户输出一张状态清单：已可用、需要授权、待安装外部依赖、当前宿主不支持。不要把“源稿存在”等同于“宿主已经可调用”。

## 7. 验收

确认：

- 项目根存在 `AGENTS.md`、`README.md`、`STATUS.md` 和标准语义目录。
- 项目拥有独立本地 Git。
- `GLOBAL/PROJECTS.md` 已登记项目。
- 项目总经理已读取入口并给出下一步。
- 用户已看到 GLOBAL Skills 的分组、调用方式和最小试用结果；未授权、待安装或宿主不支持的 Skill 已明确标记。

最后向用户报告“GLOBAL 基座与首个 Agent 项目均已可用”，并列出尚未配置的可选能力。
