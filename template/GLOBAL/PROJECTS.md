# 项目索引

本文件记录真实的 Agent 项目根目录和路由规则。

## 核心工作区

- Agent 全局治理工作区：`{{AGENT_ROOT}}\GLOBAL`
- Obsidian 入口：`{{AGENT_ROOT}}\GLOBAL\obsidian-resource`

## 活跃项目

安装后暂为空。完成首次项目教程并由项目总经理调用 `init-agent-project` 后，在这里登记第一个真实项目。

## 路由规则

- 项目专属任务、草稿、文档、资产、决策和交付物进入对应项目工作区。
- `GLOBAL` 只保存跨项目规则、全局上下文、项目索引、全局 Skill 源稿、账号与工具约定、外部知识库连接规则和长期工作区约定。
- Obsidian 只作为只读知识来源，除非用户明确要求写入。

## 项目登记

新项目进入初始化阶段时，就登记到“活跃项目”。

每个项目条目应包含项目名、项目根目录，以及可选的简短目标或状态。只登记真实项目工作区；外部知识库、临时任务上下文和运行缓存不登记为项目。

## 项目初始化结构

新建长期 Agent 项目时，默认创建：

```text
README.md
STATUS.md
AGENTS.md
.gitignore
docs/.gitkeep
tasks/.gitkeep
archive/.gitkeep
```

`.gitkeep` 只用于保留空目录；目录中有实际内容后应移除。
