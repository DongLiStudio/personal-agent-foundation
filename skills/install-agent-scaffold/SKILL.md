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

不要要求用户预先克隆仓库、安装本 Skill、提供产品本地路径或准备 Python。先定位当前 Skill 是否已处于完整产品仓库；如果没有，按 `references/installation-workflow.md` 自动把官方仓库获取到新的系统临时目录。确认实际产品根目录存在 `template/`、`template-manifest.json` 和本 Skill 的完整目录后再继续。

## 交互原则

- 宿主提供图形化提问、选择目录或确认能力时优先使用；界面由宿主 Agent 生成，本产品不实现 GUI。
- 没有图形能力时使用普通对话逐项收集。
- 已有明确答案不重复询问；路径和外部身份在执行前回读确认。
- 不收集、写入或回显 token、密码、App Secret、私钥和恢复码。

## 安装流程

1. 定位或自动获取完整产品源，记录来源 URL、ref/commit 和临时目录；不得写入用户选择的 Agent 根目录。
2. 收集六项非敏感配置：Agent 根绝对路径、默认飞书 Profile、默认 GitHub 账号、IANA 时区、通用助手项目名、Obsidian Vault 路径或“未配置”说明。
3. 自动预检 Python 3.11+：依次查找宿主自带运行时和系统常见入口，并记录实际可执行文件。缺失时按 `references/installation-workflow.md` 生成当前系统的官方安装方案，展示命令、来源和权限影响，取得用户确认后自动安装并回读版本；不得静默提权或安装包管理器。
4. 用已确认的 Python 执行 `zoneinfo.ZoneInfo(<IANA 时区>)` 验证时区数据；缺失时把 `<python> -m pip install tzdata` 列入依赖计划，确认后执行并再次构造同一时区。
5. 将配置写入系统临时目录中的临时 JSON；不要写进产品仓库、GLOBAL 模板或长期文档。
6. 运行 `audit-template`，确认模板清单、占位符、编码、换行和链接边界。
7. 运行 `plan`，展示产品源、目标、文件数、运行时变化和风险；取得用户安装确认。
8. 运行 `install`。不得对已存在目标使用覆盖、合并或删除绕过保护。
9. 运行独立 `verify`，确认必需文件、编码和占位符残留。
10. 在新 `GLOBAL` 中初始化本地 Git；完成敏感信息扫描后创建安装基线提交。不创建 remote，不 push。
11. 从 `GLOBAL/.agents/skills/` 恢复当前宿主可发现的全局 Skill，并按 `SKILL_DEPENDENCIES.md` 恢复主动安装的外部 Skills。现有同名安装先比较文件，不能静默覆盖。
12. 使用已恢复的 `feishu-profile` 和 `github-cli` 分别完成登录、默认身份核验和回读；网页登录由用户亲自确认，不处理明文凭据。
13. 用户配置了真实 Vault 时，根据系统创建 `GLOBAL/obsidian-resource` Junction 或 symlink，并验证链接目标；未配置时保持缺失，不创建伪链接。
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
- GLOBAL 本地 Git、Skill 恢复、默认飞书/GitHub 路由和可选知识库连接均有独立回读结果。
- 用户知道当前 Agent 的全局个性化提示词需要在哪里设置；无法自动定位时已引导用户在设置中查找。
- 第一个 Agent 项目已在 GLOBAL 同级创建并打开，项目总经理会话已建立并调用 `init-agent-project`。
- 未完成或仅提示用户的步骤明确标记为未完成，不得把提示等同于成功。
