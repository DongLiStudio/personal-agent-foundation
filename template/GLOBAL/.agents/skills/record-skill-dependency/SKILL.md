---
name: record-skill-dependency
description: 在创建、安装或同步用户自维护全局 Skill 后，或用户主动安装外部 Skill 后，维护 GLOBAL/SKILL_DEPENDENCIES.md。用户要求记录 Skill 依赖、更新 SKILL_DEPENDENCIES.md、安装外部 Skill 后登记、新增全局 Skill 后登记，或维护 GLOBAL/SKILL_DEPENDENCIES.md 时使用。不要用于默认预装 Skill、系统 Skill、插件提供的 Skill、插件缓存 Skill 或临时运行文件。
---

# 记录 Skill 依赖

使用这个 Skill 在新增、安装或同步全局 Skill 后，维护 `GLOBAL/SKILL_DEPENDENCIES.md`。

## 核心规则

源稿位于 `{{AGENT_ROOT}}\GLOBAL\.agents\skills\` 的自维护全局 Skill 必须记录，并保持源稿、用户级安装副本和依赖清单一致。

外部 Skill 只记录用户主动安装、且迁移或重装环境时需要主动恢复的条目。

外部 Skill 如果缺少配套 CLI、桌面应用、运行时、系统能力或授权就无法工作，必须同时记录该运行依赖、恢复步骤和最小验证命令；不能只记录 `SKILL.md` 的安装方式。

记录：

- 用户自己维护、并需要跨项目全局使用的 Skill。
- 用户主动从外部来源安装的 Skill。
- 依赖某个外部仓库、插件或手动步骤才能恢复的 Skill。
- 对长期工作流有稳定影响，换电脑时必须主动恢复的 Skill。

不记录：

- 默认预装 Skill。
- 系统 Skill。
- 插件随安装自动提供的 Skill。
- 插件缓存路径中的 Skill。
- 项目专属 Skill。
- 当前会话或运行时临时产物。

## 工作流程

1. 判断本次对象是 GLOBAL 自维护 Skill、主动安装的外部 Skill、项目专属 Skill，还是默认/插件/缓存/临时内容。
2. 如果是默认预装、系统、插件提供、插件缓存、项目专属 Skill 或临时产物，说明原因并停止，不要污染依赖清单。
3. 如果是 GLOBAL 自维护 Skill，必须记录或更新。
4. 如果是用户主动安装的外部 Skill，确认它是否需要迁移或重装时主动恢复；需要则记录，不需要则说明原因并停止。
5. 判断该 Skill 是否依赖额外 CLI、应用、运行时、系统能力或授权；存在必需依赖时，记录恢复步骤和不产生业务写入的最小验证命令。
6. 读取 `GLOBAL/SKILL_DEPENDENCIES.md`。
7. 判断应该写入哪个章节：
   - `GLOBAL 自维护 Skill`：源稿在 `{{AGENT_ROOT}}\GLOBAL\.agents\skills\` 的个人全局 Skill。
   - `主动安装的外部 Skill`：用户从外部来源主动安装、但源稿不由 GLOBAL 维护的 Skill。
8. 如果条目已存在，更新恢复方式、来源、运行依赖或用途；不要重复添加。
9. 如果 `主动安装的外部 Skill` 当前为“暂无。”，新增第一条外部 Skill 时移除“暂无。”。
10. 保持条目简短、事实化，优先记录恢复所需信息，而不是复制 Skill 内容。
11. 结束时说明记录到了哪个章节，以及是否跳过了默认预装/插件 Skill。

## 条目格式

GLOBAL 自维护 Skill：

```md
### `skill-name`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\skill-name`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 用途：一句话说明用途。
```

主动安装的外部 Skill：

```md
### `skill-name`

- 来源：外部仓库、安装命令、插件或其他可恢复来源。
- 恢复方式：重新执行安装命令，或按来源说明恢复；安装到当前 Agent 可发现的全局 Skill 位置。
- 运行依赖：仅在缺少配套 CLI、应用、运行时、系统能力或授权会导致 Skill 不可用时记录，并附最小只读验证命令。
- 用途：一句话说明用途。
```

## 安全边界

不要复制系统 Skill、插件 Skill 或缓存目录内容到 `GLOBAL`。

不要递归移动、复制或删除 Junction / symlink 指向内容。

如果缺少来源、用途或恢复方式，先尽量从当前安装目录、用户说明或相关文档判断；仍不清楚时，只问必要问题。
