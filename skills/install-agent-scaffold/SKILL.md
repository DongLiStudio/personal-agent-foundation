---
name: install-agent-scaffold
description: 对话式安装、恢复和验证 Personal Agent Foundation。用于用户给出 DongLiStudio/personal-agent-foundation 仓库链接并要求安装，或要求部署完整 GLOBAL、换电脑恢复 Agent 工作环境、配置默认飞书 Profile/GitHub 账号/Obsidian 连接、完成首次项目初始化教程时。自动获取完整产品源、准备运行时，并调用确定性护栏完成 dry-run、staging 渲染、目标保护、安装后验证和 onboarding。
---

# 安装 Personal Agent Foundation

把本 Skill 当作安装协调器；把 `scripts/scaffold_guard.py` 当作模板文件操作的唯一确定性实现。不要用临时 shell 替代占位符校验、渲染或目标保护。

## 读取契约

开始前读取：

- `references/installation-workflow.md`：安装阶段、配置格式和验收门禁。
- `references/host-integration.md`：不同 Agent 的 Skill 与全局提示词边界。
- `references/onboarding.md`：安装后首次项目教程。

用户配置真实 Obsidian Vault 时，再完整读取 `references/obsidian-layout.md`，执行结构访谈、访问边界确认和链接验收。

不要要求用户预先克隆仓库、安装本 Skill、提供产品本地路径或准备 Python。先定位当前 Skill 是否已处于完整产品仓库；如果没有，按 `references/installation-workflow.md` 自动把官方仓库获取到新的系统临时目录。确认实际产品根目录存在 `template/`、`template-manifest.json` 和本 Skill 的完整目录后再继续。

## 交互原则

- 宿主提供图形化提问、选择目录、选项卡片、可视化安装面板或确认能力时优先使用；界面由宿主 Agent 生成，本产品不实现独立 GUI。当前宿主可用时必须优先尝试可视化安装面板或确认摘要；失败或不可用时说明原因，再退回普通对话。
- 没有图形能力时使用普通对话逐项收集。
- 已有明确答案不重复询问；路径、连接意图和外部身份在执行前回读确认。
- 初始安装阶段不得询问用户飞书 Profile 名或 GitHub 账号名；普通用户不应被要求知道这些实现标识。先安装 GLOBAL 和 Skills，再调用 `feishu-profile`、`github-cli` 等能力完成授权、验证码或网页登录，并以工具回读结果写回 GLOBAL。
- 不得把飞书、GitHub 或 Obsidian 静默设为“未配置”。GLOBAL 和 Skills 恢复后，必须分别询问用户是否现在连接；用户明确选择暂不连接、当前没有账号或当前没有 Vault 后，才可保留未配置说明。
- 默认推荐的 Agent 根目录最终文件夹名为 `Agent`。先说明推荐理由：便于跨宿主识别、迁移、GLOBAL 与项目同级管理；用户可以指定其他空目录。目标不存在时创建，目标已存在且为空时使用，目标包含已有文件时停止并说明不会合并或覆盖。
- 不收集、写入或回显 token、密码、App Secret、私钥和恢复码。

## 安装流程

1. 定位或自动获取完整产品源，记录来源 URL、ref/commit 和临时目录；不得写入用户选择的 Agent 根目录。
2. 收集最小非敏感配置：
   - Agent 根绝对路径：先推荐一个最终文件夹名为 `Agent` 的位置，并解释权限、迁移和目录职责；用户可接受推荐或指定其他空目录。
   - IANA 时区。
   - 通用助手项目名。
   - 飞书、GitHub 和 Obsidian 的占位值先写成待连接说明；不得在此阶段向用户索要 Profile 名、GitHub 用户名或 Vault 路径。
3. 自动预检 Python 3.11+：依次查找宿主自带运行时和系统常见入口，并记录实际可执行文件。缺失时按 `references/installation-workflow.md` 生成当前系统的官方安装方案，展示命令、来源和权限影响，取得用户确认后自动安装并回读版本；不得静默提权或安装包管理器。
4. 用已确认的 Python 执行 `zoneinfo.ZoneInfo(<IANA 时区>)` 验证时区数据；缺失时把 `<python> -m pip install tzdata` 列入依赖计划，确认后执行并再次构造同一时区。
5. 将配置写入系统临时目录中的临时 JSON；不要写进产品仓库、GLOBAL 模板或长期文档。
6. 运行 `audit-template`，确认模板清单、占位符、编码、换行和链接边界。
7. 运行 `plan`，展示产品源、目标、文件数、运行时变化和风险；取得用户安装确认。
8. 运行 `install`。目标不存在时创建；目标已存在且为空时直接使用；目标已有内容时停止。不得对非空目标使用覆盖、合并或删除绕过保护。
9. 运行独立 `verify`，确认必需文件、编码和占位符残留。
10. 从 `GLOBAL/.agents/skills/` 恢复当前宿主可发现的全局 Skill，并按 `SKILL_DEPENDENCIES.md` 恢复主动安装的外部 Skills。现有同名安装先比较文件，不能静默覆盖。
11. 逐项询问是否现在连接飞书、GitHub 和 Obsidian。用户选择连接飞书时调用已恢复的 `feishu-profile`，打开验证码、OAuth 或官方授权流程，完成 `whoami` 回读后把真实 Profile 写回 `GLOBAL/LARK_PROFILES.md`；不得询问用户预先提供 Profile 名。用户选择连接 GitHub 时调用 `github-cli`，完成 `gh auth status` 和 `gh api user` 回读后把真实账号写回 `GLOBAL/GITHUB_ACCOUNTS.md`；不得询问用户预先提供 GitHub 用户名。用户选择连接 Obsidian 时，再收集 Vault 路径并完整读取 `references/obsidian-layout.md`，确认结构、权限和链接后更新已安装实例。
12. 用户配置了真实 Vault 时，通过对话和经授权的浅层只读检查理解用户实际目录结构、入口文件和读写边界；展示拟写入的映射并取得确认后，只更新已安装实例中的 `GLOBAL/OBSIDIAN_LINK.md`，再创建并验证 `GLOBAL/obsidian-resource` Junction 或 symlink。不得修改产品模板、强套作者结构或递归扫描 Vault。未配置时保持通用说明，不创建伪链接。
13. 在新 `GLOBAL` 中初始化本地 Git；完成敏感信息扫描后创建包含已确认账号与 Obsidian 配置的安装基线提交。不创建 remote，不 push。
14. 执行 `references/onboarding.md` 的全局提示词和首次项目教程。
15. 删除临时配置、staging 和本轮自动获取的临时产品源，输出完成项、人工步骤、未验证项及建议下一步。

## 护栏命令

```powershell
<python> scripts/scaffold_guard.py audit-template --template <product-root>/template --manifest <product-root>/template-manifest.json
<python> scripts/scaffold_guard.py plan --template <product-root>/template --manifest <product-root>/template-manifest.json --values <temp-values.json> --target <agent-root>
<python> scripts/scaffold_guard.py install --template <product-root>/template --manifest <product-root>/template-manifest.json --values <temp-values.json> --target <agent-root>
<python> scripts/scaffold_guard.py verify --manifest <product-root>/template-manifest.json --target <agent-root>
```

`<python>` 必须替换为预检确认的实际可执行文件。只有官方安装方案不可用、用户拒绝依赖安装或安装后回读仍失败时才停止，并给出准确诊断；不能手工执行低保障替代流程。

## 完成条件

- GLOBAL 全部模板文件已安装且无占位符残留。
- GLOBAL 本地 Git、Skill 恢复、飞书/GitHub 授权回读和可选知识库连接均有独立结果；`LARK_PROFILES.md`、`GITHUB_ACCOUNTS.md` 和 `OBSIDIAN_LINK.md` 已匹配工具回读或用户确认的状态，或明确记录为未配置。
- 用户知道当前 Agent 的全局个性化提示词需要在哪里设置；无法自动定位时已引导用户在设置中查找。
- 第一个 Agent 项目已在 GLOBAL 同级创建并打开，项目总经理会话已建立并调用 `init-agent-project`。
- 未完成或仅提示用户的步骤明确标记为未完成，不得把提示等同于成功。
