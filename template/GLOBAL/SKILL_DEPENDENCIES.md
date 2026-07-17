# Skill Dependencies

本文件只记录迁移或重装环境时需要主动恢复的 Skill 依赖。

默认预装 Skill、系统 Skill、插件自动附带的 Skill、插件缓存 Skill、运行时缓存和临时目录不记录在这里。

## 记录原则

需要记录：

- 用户自己维护、并需要跨项目全局使用的 Skill。
- 用户主动从外部来源安装的 Skill。
- 依赖某个外部仓库、插件或手动步骤才能恢复的 Skill。
- 对长期工作流有稳定影响，换电脑时必须主动恢复的 Skill。

不需要记录：

- 默认预装 Skill。
- 系统 Skill。
- 插件随安装自动提供的 Skill。
- 插件缓存路径中的 Skill。
- 项目专属 Skill。
- 当前会话或运行时临时产物。

## GLOBAL 自维护 Skill

### `init-agent-project`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\init-agent-project`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 用途：初始化项目制 Agent 工作区，创建标准项目结构，登记 `GLOBAL/PROJECTS.md`，初始化本地 Git，并把 GitHub 专属/默认账号路由、远程仓库授权边界写入项目规则；项目内部 Skill/agent 内容遵循 `.agents` 机制。

### `record-skill-dependency`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\record-skill-dependency`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 用途：在新增自维护全局 Skill 或主动安装外部 Skill 后，维护 `GLOBAL/SKILL_DEPENDENCIES.md`。

### `github-cli`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\github-cli`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 用途：指导 Agent 安全使用 GitHub CLI (`gh`)，统一账号生命周期、全局默认/项目专属路由、remote 与首次 push 边界，并处理仓库、Issue、PR、Actions、Release、API 和 GitHub CLI Skill 检索。

### `visual-iteration-workflow`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\visual-iteration-workflow`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 用途：在页面设计迭代、点选修改和局部视觉调整时，提醒 Agent 优先考虑 Impeccable Live Mode，并按安全流程完成启动、接受变体和清理收尾。

### `feishu-task`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\feishu-task`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 用途：跨项目解析飞书账号、人员角色、时间、任务详情和附件，安全完成附件局部脱敏、任务去重、创建、更新与回读；项目未指定账号时使用 GLOBAL 记录的全局默认 Profile。

### `feishu-profile`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\feishu-profile`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 用途：统一管理飞书 CLI 多 Profile 的新增、一键创建应用、用户授权、失效恢复、换机迁移、项目局部路由、重命名与安全删除。

### `align-agent-projects-with-global`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\align-agent-projects-with-global`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 用途：在 GLOBAL 发生影响项目的规则或路径更新后，审计、计划并在授权后逐项目对齐所有已登记 Agent 项目；也作为 `migrate-agent-root` 的项目对齐门禁。

### `migrate-agent-root`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\migrate-agent-root`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 用途：安全规划、执行和验证完整 Agent 根目录迁移，负责 GLOBAL 路径重写、链接重建、Skill 安装副本比对，并消费 `align-agent-projects-with-global` 的项目对齐门禁结果。

### `personal-schedule-planner`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\personal-schedule-planner`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 运行依赖：全局 `feishu-profile`、当前 `lark-cli` 内嵌的 `lark-shared`、`lark-task` 与 `lark-calendar`，以及外部 `json-canvas`、`obsidian-cli`；仪表盘实际关联 `.base` 时还需要 `obsidian-bases`。各依赖按本清单对应条目恢复并执行最小只读验证。
- 用途：汇总所有 GLOBAL 飞书 Profile 的任务与日历、Obsidian 仪表盘和已登记项目进度，协商个人时间安排，并在用户确认后幂等同步到全部 Profile 日历。

### `decide-next-action`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\decide-next-action`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 运行依赖：全局 `feishu-profile`、当前 `lark-cli` 内嵌的 `lark-task` 与 `lark-calendar`，以及外部 `json-canvas`、`obsidian-cli`；仪表盘实际关联 `.base` 时还需要 `obsidian-bases`。各依赖按本清单对应条目恢复并执行最小只读验证。
- 用途：只读汇总全部治理层飞书任务与近期日历、Obsidian 仪表盘和活跃项目状态，推荐当前最值得立即执行的一个下一步，并在需要时转交任务维护或完整排程 Skill。

## 主动安装的外部 Skill

### `json-canvas`

- 来源：`kepano/obsidian-skills` 仓库 `skills/json-canvas`；本次核验并安装提交 `a1dc48e68138490d522c04cbf5822214c6eb1202`：https://github.com/kepano/obsidian-skills/tree/a1dc48e68138490d522c04cbf5822214c6eb1202/skills/json-canvas
- 恢复方式：使用当前 Agent 的标准 Skill 安装器，从上述仓库与固定提交选择性安装 `skills/json-canvas` 到全局 Skill 位置。
- 用途：让 Agent 解析和处理 JSON Canvas (`.canvas`) 的节点、连线、分组与文件引用；在本 GLOBAL 下默认遵守 Obsidian 只读边界。

### `obsidian-bases`

- 来源：`kepano/obsidian-skills` 仓库 `skills/obsidian-bases`；本次核验并安装提交 `a1dc48e68138490d522c04cbf5822214c6eb1202`：https://github.com/kepano/obsidian-skills/tree/a1dc48e68138490d522c04cbf5822214c6eb1202/skills/obsidian-bases
- 恢复方式：使用当前 Agent 的标准 Skill 安装器，从上述仓库与固定提交选择性安装 `skills/obsidian-bases` 到全局 Skill 位置。
- 用途：让 Agent 理解和处理 Obsidian Bases (`.base`) 的视图、筛选、公式与汇总；在本 GLOBAL 下默认遵守 Obsidian 只读边界。

### `obsidian-cli`

- 来源：`kepano/obsidian-skills` 仓库 `skills/obsidian-cli`；本次核验并安装提交 `a1dc48e68138490d522c04cbf5822214c6eb1202`：https://github.com/kepano/obsidian-skills/tree/a1dc48e68138490d522c04cbf5822214c6eb1202/skills/obsidian-cli
- 恢复方式：使用当前 Agent 的标准 Skill 安装器，从上述仓库与固定提交选择性安装 `skills/obsidian-cli`；安装或升级 Obsidian 1.12.7+ 桌面安装器，在“设置 → 通用”中启用并注册命令行界面，然后验证 `obsidian version`、`obsidian help` 以及对目标 Vault `仪表盘.canvas` 的只读访问。
- 运行依赖：官方 Obsidian CLI 与桌面应用；执行 CLI 时 Obsidian 需要运行。CLI 只作为增强能力，自动化流程仍应保留直接读取开放文件格式的只读回退。
- 用途：让 Agent 通过官方 CLI 对指定 Vault 执行只读搜索、文件读取、链接解析和任务查询；未经明确授权不使用创建、追加、移动、删除或属性写入命令。

### `lark-*` 飞书 CLI Skills

- 来源：飞书 CLI 官方安装指南：https://open.feishu.cn/document/no_class/mcp-archive/feishu-cli-installation-guide.md
- 恢复方式：按官方安装指南重新安装；Skill 安装命令保持官方形式 `npx -y skills add https://open.feishu.cn --skill -y`。
- 用途：让 Agent 使用飞书/Lark 文档、云盘、IM、日历、多维表格、邮件、妙记等 CLI Skill 能力。

### `ui-ux-pro-max`

- 来源：GitHub/NPM 外部 Skill；GitHub 仓库：https://github.com/nextlevelbuilder/ui-ux-pro-max-skill；NPM 包：`ui-ux-pro-max-cli`；安装命令 `npm install -g ui-ux-pro-max-cli@latest` 后执行 `uipro init --ai codex --global`。
- 恢复方式：重新安装 `ui-ux-pro-max-cli`，再执行 `uipro init --ai codex --global`。
- 用途：为 Agent 提供 UI/UX 设计推理、风格/配色/字体/图表/技术栈规则和设计系统生成能力。

### `impeccable`

- 来源：Impeccable 官方外部 Skill；官网：https://impeccable.cn/；GitHub 仓库：https://github.com/pbakaus/impeccable；安装命令 `npx impeccable skills install`，安装时选择 `Global (~)`。
- 恢复方式：重新执行 `npx impeccable skills install` 并选择 `Global (~)`；更新使用 `npx impeccable skills update`。
- 用途：为 Agent 提供前端 UI/UX 设计、评审、打磨、去 AI slop、设计系统文档和 Live Mode 迭代能力。

## 维护规则

- 新增个人全局 Skill 后，同步补充 `GLOBAL 自维护 Skill`。
- 主动安装外部 Skill 后，同步补充 `主动安装的外部 Skill`。
- 如果某个 Skill 后续变成默认预装或由插件自动恢复，可从本文件移除。
- 本文件只记录恢复线索，不复制外部 Skill 内容。
