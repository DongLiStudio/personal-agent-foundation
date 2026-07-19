# 首次使用教程

GLOBAL、Skill 和身份配置完成后立即执行本教程，不把用户丢在“安装成功”页面。

## 1. 解释三层关系

- `GLOBAL`：跨项目治理、账号路由、Skill 源稿和长期规则。
- Agent 项目：管理一个长期目标的上下文、任务、决策和组织。
- 实际产品工程：由某个 Agent 项目管理的代码、设计或业务交付，不必复制 Agent 项目治理结构。

解释时不要只给定义，要用用户能马上行动的方式说明：

- `GLOBAL` 像“全局操作系统”：保存所有项目都要继承的规则、账号、Skill 和知识库入口。
- 与 `GLOBAL` 同级的每个项目目录，才是具体事情的工作区。
- 项目里的 `AGENTS.md`、`README.md`、`STATUS.md` 会让未来的新会话知道这个项目是谁、现在到哪一步、下一步做什么。

## 2. GLOBAL 文件导览

安装完成后，先列出 `GLOBAL` 根目录中的文件和关键目录，再逐个解释“它是什么、为什么这样设计、什么时候要看”。不要假设用户已经懂这些文件。

至少覆盖：

- `README.md`：GLOBAL 的说明书，告诉 Agent 这个全局空间是什么、文件怎么读。
- `GLOBAL_CONTEXT.md`：每次开始工作最该继承的全局规则和最小上下文。
- `PROJECTS.md`：所有 Agent 项目的索引；新项目应该登记在这里。
- `OBSIDIAN_LINK.md`：Obsidian 外部知识库的入口、只读边界、目录理解和优先阅读顺序。
- `SKILL_DEPENDENCIES.md`：需要恢复、安装、同步的全局 Skill 清单。
- `LARK_PROFILES.md`：飞书公司、应用和 Profile 路由；不放 token。
- `GITHUB_ACCOUNTS.md`：GitHub 账号和仓库操作路由；不放 token。
- `SCHEDULE_PREFERENCES.md`：个人排程稳定偏好和跨账号日历同步口径。
- `.agents/skills/`：用户自维护的全局 Skill 源稿，不等于宿主运行时安装目录。
- `obsidian-resource`：指向 Obsidian Vault 的只读入口；不是把 Vault 复制进 GLOBAL。

讲解顺序要互动：

1. 先展示完整文件列表。
2. 用一句话解释每个文件的作用。
3. 问用户：“你想先了解哪个？我可以按你选的顺序一个一个讲，也可以按推荐顺序讲。”
4. 如果用户没有偏好，按推荐顺序讲：`README.md` → `GLOBAL_CONTEXT.md` → `PROJECTS.md` → `OBSIDIAN_LINK.md` → `SKILL_DEPENDENCIES.md` → `LARK_PROFILES.md` / `GITHUB_ACCOUNTS.md` → `SCHEDULE_PREFERENCES.md` → `.agents/skills/`。
5. 每讲完一个文件，给一个很短例子说明未来什么时候会用到，并询问是否继续下一个。

GLOBAL 导览完成前，不要直接跳到“安装成功”。用户选择跳过导览时，说明以后可以让 Agent 读取 `GLOBAL/README.md` 重新讲解。

## 3. 设置全局个性化提示词

按 `host-integration.md` 引导用户在当前宿主设置中找到入口，原样展示其中的完整全局个性化提示词并要求保存。不能只告诉用户“去设置提示词”，也不能临时概括成更短版本。等待用户说明保存入口并确认已保存后继续；宿主支持回读时核对完整文本。

## 4. 创建第一个项目目录

询问项目名和一句话目标，在 `AGENT_ROOT` 下、与 `GLOBAL` 同级创建目录。不要在 GLOBAL 内创建项目。

向用户解释为什么项目要建在这里：

```text
你的 Agent 根目录下面会长这样：

Agent/
  GLOBAL/        ← 全局规则和工具入口
  第一个项目/    ← 具体项目工作区
  以后另一个项目/ ← 另一个独立上下文
```

`GLOBAL` 不放具体项目任务；项目目录与 `GLOBAL` 同级，才能既继承全局规则，又保持每个项目边界清楚。

## 5. 打开项目

引导用户通过当前 Agent 的“打开目录、添加项目或导入工作区”能力打开新目录。宿主支持自动操作时可协助，但不要假装已打开。

## 6. 建立项目总经理会话

让用户创建首个长期会话或任务，建议标题“<项目名>总经理”，并发送：

```text
请作为本项目的项目总经理，先调用 $init-agent-project。
项目名：<项目名>
项目根目录：<绝对路径>
一句话目标：<目标>
完整读取生成的 AGENTS.md、README.md、STATUS.md 后，核验项目结构、GLOBAL 登记和本地 Git，再给出唯一下一步。不要创建远端或 push。
```

## 7. GLOBAL Skill 快速试用

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

## 8. 验收

确认：

- 项目根存在 `AGENTS.md`、`README.md`、`STATUS.md` 和标准语义目录。
- 项目拥有独立本地 Git。
- `GLOBAL/PROJECTS.md` 已登记项目。
- 项目总经理已读取入口并给出下一步。
- 用户已经看到 GLOBAL 文件列表，并至少了解各文件的一句话作用；用户跳过时已说明如何稍后重新导览。
- 用户已看到 GLOBAL Skills 的分组、调用方式和最小试用结果；未授权、待安装或宿主不支持的 Skill 已明确标记。

最后向用户报告“GLOBAL 基座与首个 Agent 项目均已可用”，并列出尚未配置的可选能力。
