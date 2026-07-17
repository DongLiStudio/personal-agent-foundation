# Personal Agent Foundation

Personal Agent Foundation 是一套可移植的个人 Agent 工作基座。它把经过实际使用的全局规则、项目制协作方式和常用 Skills 通用化，并通过对话式安装 Skill 帮助用户建立自己的 Agent 根目录。

你不需要理解模板内部结构。安装过程中，Agent 会先展示计划，在你确认后再写入文件，并继续引导账号连接、个性化设置和第一个项目的创建。

## 适合谁

- 希望多个 Agent 或多个项目共享一套长期规则的人。
- 希望在 Windows、macOS 或 Linux 上建立可迁移 Agent 工作目录的人。
- 希望通过对话完成安装，而不是手工复制和替换大量文件的人。

本项目不会提供独立 GUI。宿主 Agent 支持图形提问时使用宿主界面，否则使用普通对话。

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
3. 自动检测宿主或系统中的 Python 3.11+；缺失时先展示官方安装方案，经确认后自动安装。
4. 收集非敏感配置并执行模板审计、安装计划和 dry-run。
5. 只有在展示计划并获得明确确认后，才执行真实安装和验证。

Agent 如果无法读取公开仓库、执行本地工具或请求必要权限，应准确说明阻断，不应把克隆、Skill 注册、Python 安装或模板处理重新交给用户手工完成。

## 安装时会询问什么

Agent 会询问以下非敏感配置：

1. 新 Agent 根目录。
2. 默认飞书 Profile，或“未配置”。
3. 默认 GitHub 账号，或“未配置”。
4. IANA 时区，例如 `Asia/Shanghai`。
5. 默认助手项目名称。
6. Obsidian Vault 路径，或“未配置”。

不要在对话中提供 token、密码、App Secret、私钥或恢复码。需要登录时，由对应工具打开官方授权流程。

## 安装过程

Skill 按以下顺序执行：

```text
收集配置 → 环境预检 → 模板审计 → 安装计划 → dry-run
→ 用户确认 → 安装 → 独立验证 → 初始化 GLOBAL 本地 Git
→ 恢复 Skills → 引导账号连接 → 可选知识库连接
→ 全局个性化提示词 → 第一个 Agent 项目
```

在显示 dry-run 结果并获得明确确认前，Skill 不应执行真实安装。

## 安装后会得到什么

- 一个独立的 `GLOBAL/`，保存全局规则、项目索引、账号路由和 Skill 依赖记录。
- 一套公开脱敏的自维护 Skills。
- 飞书、GitHub 和 Obsidian 的可选连接引导，不包含任何预置凭据。
- 当前宿主的全局个性化提示词设置提醒。
- 第一个 Agent 项目的创建教程，包括建立项目总经理会话并调用 `init-agent-project`。

## 安全保证

- 模板不包含作者的真实项目、个人目录、账号、App ID、token 或历史记录。
- 只有清单声明的占位符可以被替换。
- 模板源目录不会在安装时被原地修改。
- 目标目录已存在时拒绝覆盖或合并。
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
