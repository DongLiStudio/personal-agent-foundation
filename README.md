# Personal Agent Foundation

Personal Agent Foundation 是一套可移植的个人 Agent 工作基座，用来解决个人 AI 工作流里的“数据孤岛”和“上下文断裂”问题。

不同 Agent 宿主、不同工作空间中，往往安装着不同 Skill，保存着不同上下文，并连接着不同账号与知识库入口。用户一旦换 Agent、换项目或换设备，长期规则、项目经验、身份路由、工具授权和协作方式就很难继续复用。本项目把经过实际使用的 GLOBAL 治理层、项目制协作方式、Skill 依赖、账号路由和知识库连接通用化，并通过对话式安装 Skill 帮助用户建立自己的 Agent 根目录。

你不需要理解模板内部结构。安装过程中，Agent 会先展示计划，在你确认后再写入文件，并继续引导账号连接、个性化设置和第一个项目的创建。

## 核心特色

这套基座的重点不是把几个工具简单放在一起，而是让用户自己的 AI 工作环境变成可安装、可迁移、可恢复、可扩展的长期基座：

- **打通 Agent 数据孤岛**：把不同 Agent 宿主、不同工作空间中的规则、上下文、Skill 依赖和项目入口组织到统一的 Agent 根目录中，让新会话不再从零开始。
- **GLOBAL 治理层**：沉淀长期规则、身份路由、项目索引、安全边界和工作方式，让不同项目能共享同一套基础约定。
- **项目制协作**：为每个项目保留独立上下文、状态、任务和验收边界，同时继承 GLOBAL 的通用规则。
- **飞书多账号管理**：管理多个飞书 Profile，在明确身份路由下连接任务、日历、文档等信息，避免不同账号之间混用。
- **GitHub 多账号管理**：管理多个 GitHub 账号及其项目路由，让仓库、Issue、PR、Actions 等操作始终使用正确身份。
- **Obsidian 知识聚合**：把用户自己的 Obsidian Vault 作为外部知识库连接给 Agent；安装时通过对话理解并适配用户现有的目录结构、知识入口和访问边界，不要求照搬作者的组织方式。
- **全 AI 化操作**：由 Agent 完成跨来源采集、分析、规划、执行和结果回读；用户主要负责目标表达、必要选择和高影响操作确认。

这里的“聚合”不是把个人数据上传或复制进本仓库。公开模板不包含任何用户数据或凭据；运行时只在用户授权范围内通过官方工具连接原系统，凭据仍由各平台的官方认证机制管理。

## 适合谁

- 希望多个 Agent 或多个项目共享一套长期规则的人。
- 希望在 Windows、macOS 或 Linux 上建立可迁移 Agent 工作目录的人。
- 希望通过对话完成安装，而不是手工复制和替换大量文件的人。

本项目不会提供独立 GUI。任何宿主 Agent 支持图形提问、选项卡片、目录选择、可视化安装面板或交互式确认时，都应优先使用宿主界面展示安装选项和确认摘要；例如 Codex 可使用 Visualize 插件/能力。没有图形能力时使用普通对话，并说明没有使用图形交互的原因。

## 开始使用

把仓库链接交给能够读取公开 GitHub 仓库并执行本地工具的 Agent：

```text
请安装这个个人 Agent 基座：
https://github.com/DongLiStudio/personal-agent-foundation
```

剩余准备工作由 Agent 完成。用户不需要手工克隆仓库、安装 Skill、寻找 Python 或编辑模板。

Agent 应当：

1. 把完整产品仓库获取到新的系统临时目录。
2. 读取 `skills/install-agent-scaffold/SKILL.md` 及其按需引用，把它作为本次安装流程。
3. 先推荐 Agent 根目录，并说明推荐理由。默认推荐路径的最后一级目录叫 `Agent`；用户可以指定其他空目录。目标不存在时创建，目标已存在且为空时使用，目标已有内容时停止并说明不会合并或覆盖。
4. 自动检测宿主或系统中的 Python 3.11+；缺失时先展示官方安装方案，经确认后自动安装。
5. 收集最小非敏感配置并执行模板审计、安装计划和 dry-run。飞书、GitHub 和 Obsidian 在初始模板中只写入“待连接”状态，不要求用户提前知道 Profile 名或账号名。
6. 只有在展示计划并获得明确确认后，才执行真实安装和验证。
7. GLOBAL 和 Skills 恢复完成后，再分别询问是否现在连接飞书、GitHub 和 Obsidian；默认推荐并预选“现在连接”。用户选择连接时，由对应 Skill 或官方 CLI 打开授权、验证码或网页登录流程，并回读真实身份后写回 GLOBAL。只有用户主动选择稍后再配或当前没有账号/Vault 时，才保留未配置说明。

Agent 如果无法读取公开仓库、执行本地工具或请求必要权限，应准确说明阻断，不应把克隆、Skill 注册、Python 安装或模板处理重新交给用户手工完成。

## 安装时会询问什么

Agent 会询问以下非敏感配置：

1. 新 Agent 根目录；推荐最终目录名为 `Agent`，并解释为什么适合放在该位置。
2. IANA 时区，例如 `Asia/Shanghai`。
3. 默认助手项目名称。

GLOBAL 和 Skills 恢复后，Agent 才会继续询问是否现在连接飞书、GitHub 和 Obsidian。三个连接项的默认选项都应是“现在连接”，而不是“稍后连接”。用户选择连接飞书或 GitHub 时，不需要提前知道 Profile 名或账号名；Agent 应调用对应 Skill 或官方 CLI 完成授权并回读真实身份。用户选择连接 Obsidian 时，再填写 Vault 路径并确认实际目录结构、优先入口、允许读取或写入的范围和明确排除项，生成专属的 `OBSIDIAN_LINK.md`。

不要在对话中提供 token、密码、App Secret、私钥或恢复码。需要登录时，由对应工具打开官方授权流程。

## 安装过程

Skill 按以下顺序执行：

```text
收集最小配置 → 环境预检 → 模板审计 → 安装计划 → dry-run
→ 用户确认 → 安装 → 独立验证 → 恢复 Skills
→ 询问并连接飞书 / GitHub / Obsidian → 初始化 GLOBAL 本地 Git
→ 全局个性化提示词 → 第一个 Agent 项目 → GLOBAL Skills 快速试用
```

在显示 dry-run 结果并获得明确确认前，Skill 不应执行真实安装。

## 安装后会得到什么

- 一个独立的 `GLOBAL/`，保存全局规则、项目索引、账号路由和 Skill 依赖记录。
- 一套公开脱敏的自维护 Skills。
- 飞书、GitHub 和 Obsidian 的可选连接引导，不包含任何预置凭据。
- 内置的完整全局个性化提示词，以及针对当前宿主设置入口的保存与核验引导。
- 第一个 Agent 项目的创建教程，包括建立项目总经理会话并调用 `init-agent-project`。
- GLOBAL Skills 的分组说明和最小安全试用，区分已可用、需要授权、待安装外部依赖和当前宿主不支持的能力。

## 安全保证

- 模板不包含作者的真实项目、个人目录、账号、App ID、token 或历史记录。
- 只有清单声明的占位符可以被替换。
- 模板源目录不会在安装时被原地修改。
- 目标目录不存在时创建；已存在且为空时使用；已有内容时拒绝覆盖或合并。
- 使用临时 staging 渲染，成功验证后再原子落盘。
- 安装后检查 UTF-8、LF、必需文件和占位符残留。
- 不递归跟随模板中的 Junction 或 symlink。

## 平台与验证状态

- 自动化测试覆盖 Windows、macOS、Ubuntu，以及 Python 3.11 和 3.12。
- Python 和 IANA 时区数据由安装 Skill 自动预检；需要安装 Python 或 `tzdata` 时会先单独征得确认，不会静默修改系统环境。
- 真实宿主中的 Skill 安装位置、账号网页登录、全局提示词入口和图形交互由宿主决定；无法验证的步骤必须如实报告，不能假装完成。

## 仓库内容

- `template/GLOBAL/`：公开脱敏的 GLOBAL 模板。
- `skills/install-agent-scaffold/`：对话式安装、验证和首次项目教程。
- `template-manifest.json`：模板文件与占位符契约。
- `tests/`：模板完整性、脱敏、渲染、目标保护和跨平台测试。
- `docs/`：安装契约、通用化说明和维护资料。

## 开发与验证

```shell
python -m unittest discover -s tests -v
python skills/install-agent-scaffold/scripts/scaffold_guard.py audit-template --template template --manifest template-manifest.json
```

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。

## 作者与联系

- 作者：DongLi
- GitHub：[@DongLiStudio](https://github.com/DongLiStudio)
- 邮箱：[mr_yuxiangyu@163.com](mailto:mr_yuxiangyu@163.com)
