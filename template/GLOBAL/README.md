# Agent 全局资产空间

`GLOBAL` 是个人 Agent 资产空间的全局治理层，用来保存跨项目、跨会话、跨 Agent 工具都应该稳定继承的规则和索引。

固定路径：

`{{AGENT_ROOT}}\GLOBAL`

## 职责边界

`GLOBAL` 只保存公共制度层内容：项目制规则、全局上下文、项目索引、账号与工具约定、外部知识库连接规则、个人全局 skill 源头。

不要把具体项目的任务记录、业务产物或草稿长期堆在这里。具体内容应进入对应项目。

## 文件说明

- `README.md`：`GLOBAL` 的职责、结构、文件说明和读取路由。
- `GLOBAL_CONTEXT.md`：任何 Agent 会话优先读取的最小全局上下文。
- `PROJECTS.md`：Agent 项目索引和项目制管理规则。
- `OBSIDIAN_LINK.md`：个人 Obsidian 库的只读连接规则和目录理解。
- `SKILL_DEPENDENCIES.md`：需要主动恢复的全局 Skill 依赖清单；默认预装和插件缓存不记录。
- `LARK_PROFILES.md`：飞书 CLI 公司、应用和 profile 对应关系；不记录密钥或 token。
- `SCHEDULE_PREFERENCES.md`：个人稳定排程偏好、容量边界和跨 Profile 日历同步口径；不记录每日计划或执行流水。
- `GITHUB_ACCOUNTS.md`：GitHub CLI 账号用途、权限参考、实时核验方式和切换约定；不记录 token 或 PAT。
- `.agents/skills/`：个人全局 Skill 源稿目录，用于维护、审查、同步和迁移。
- `obsidian-resource`：指向个人 Obsidian 库的 Junction，只用于只读参考。

## 读取路由

默认读取：

- `README.md`：理解 `GLOBAL` 的职责、结构和上下文路由。
- `GLOBAL_CONTEXT.md`：继承全局最小上下文和上层规则。

按任务需要读取：

- `PROJECTS.md`：涉及项目查找、创建、迁移或路由时读取。
- `SKILL_DEPENDENCIES.md`：涉及全局 Skill 创建、安装、同步、检查或恢复时读取。
- `GITHUB_ACCOUNTS.md`：涉及 GitHub 认证、账号用途或账号切换时读取。
- `LARK_PROFILES.md`：涉及飞书 CLI、公司、应用或 profile 选择时读取。
- `SCHEDULE_PREFERENCES.md`：涉及个人时间规划、任务排程、工作节奏或跨 Profile 日历同步时读取。
- `OBSIDIAN_LINK.md` 和 `obsidian-resource`：任务确实需要长期知识、业务背景或既有规划时读取。
- `.agents/skills/`：创建、修改、审查、同步或恢复自维护全局 Skill 时读取；调用已安装 Skill 时不读取本目录源稿。
- `.gitignore` 和 `.gitattributes`：仅在维护 `GLOBAL` 的版本控制规则或排查 `GLOBAL` Git 问题时读取。
- `.git/`：仅在更新、审查、回退或排查 `GLOBAL` 自身变更时通过 Git 命令操作；不直接读取或修改，普通项目任务不查看 `GLOBAL` Git 状态和历史。

除 `README.md` 和 `GLOBAL_CONTEXT.md` 外，不默认全量读取 `GLOBAL`；根据当前任务只加载对应文件。具体项目任务仍以项目内 `README.md`、`STATUS.md`、`AGENTS.md` 和相关任务文件为主要上下文。

## 项目制原则

每个长期目标都应有自己的项目目录。项目目录优先承载该项目的任务、资料、草稿、决策和交付物。

推荐项目基础结构：

```text
项目名/
  README.md
  STATUS.md
  AGENTS.md
  .gitignore
  docs/
    .gitkeep
  tasks/
    .gitkeep
  archive/
    .gitkeep
```

目录和文件不只是存储位置，也承担语义边界。初始化时应提前创建。

`.gitkeep` 只用于让 Git 跟踪空语义目录；当目录中出现实际内容后，应移除对应 `.gitkeep`。

## Skill 管理

`GLOBAL/.agents/skills/` 是个人全局 Skill 的源头目录，不是 Agent 运行时安装目录，也不是项目内部 Skill 默认目录。

- 稳定、跨项目复用的个人 skill 源稿放在这里。
- 项目内部 Skill/agent 内容使用 `.agents/` 机制。
- 系统 skill、插件 skill、缓存文件和运行时安装产物不放入 `GLOBAL`。
- 全局 Skill 恢复遵循 `SKILL_DEPENDENCIES.md`。
- 需要主动恢复的外部或自维护 skill 记录在 `SKILL_DEPENDENCIES.md`；默认预装 skill 不记录。

## 安全约定

Obsidian 库默认只读，除非用户明确授权写入。
