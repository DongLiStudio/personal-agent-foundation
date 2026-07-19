# 安装工作流

## 配置 JSON

使用以下键；文件只包含非敏感标识，安装完成后删除：

```json
{
  "AGENT_ROOT": "D:\\Agent",
  "DEFAULT_LARK_PROFILE": "待连接（安装后通过 feishu-profile 授权回读）",
  "DEFAULT_GITHUB_ACCOUNT": "待连接（安装后通过 github-cli 授权回读）",
  "DEFAULT_TIMEZONE": "Asia/Shanghai",
  "GENERAL_ASSISTANT_PROJECT": "通用助手"
}
```

macOS/Linux 使用对应绝对路径。`AGENT_ROOT` 必须与命令的 `--target` 解析到同一路径。

初始配置 JSON 只用于渲染可验证的 GLOBAL 基座。`DEFAULT_LARK_PROFILE` 和 `DEFAULT_GITHUB_ACCOUNT` 在初始安装阶段写入待连接说明；不得要求用户预先知道飞书 Profile 名或 GitHub 用户名。Obsidian Vault 路径不属于模板渲染输入，真实路径只在连接阶段作为临时输入用于创建和验证 `GLOBAL/obsidian-resource`，不得长期写入 `GLOBAL/OBSIDIAN_LINK.md`。

## 路径推荐

安装开始时先向用户推荐 Agent 根目录，并说明理由。默认推荐路径的最后一级目录为 `Agent`，用于承载 `GLOBAL/` 和后续项目目录，便于跨宿主识别、迁移和备份；用户可以指定其他绝对路径作为 Agent 根目录。

- Windows：优先推荐当前用户可写的 `<用户主目录>\Agent`。如果用户已有专门的项目父目录或工作盘，可以推荐 `<父目录>\Agent`，但必须说明可能需要管理员权限。
- macOS/Linux：优先推荐 `~/Agent`；如用户已有专门工作目录，也可以推荐 `<工作目录>/Agent`。

用户可以接受推荐或指定其他绝对路径。目标不存在时创建；目标已存在且为空时使用；目标已有内容时停止，不合并、不覆盖、不删除用户文件。

## 连接意图门禁

GLOBAL 安装验证和 Skill 恢复完成后，分别询问：

1. 是否现在连接飞书账号或创建默认飞书 Profile。
2. 是否现在连接 GitHub 账号并设置默认账号。
3. 是否现在连接 Obsidian Vault。

每一项都必须得到明确回答。安装器展示选项时，默认推荐和预选项必须是“现在连接”；“稍后连接 / 当前没有账号 / 当前没有 Vault”只能作为用户主动选择的备选项。用户选择连接时，不询问实现标识；直接调用对应 Skill 或官方 CLI 发起授权、验证码或网页登录流程，并用回读结果写入 GLOBAL。用户选择稍后再配、当前没有账号或当前没有 Vault 时，才保留未配置说明。认证过程中只走官方 OAuth、CLI 或宿主授权流程，不能要求用户在对话中提供 token、密码、App Secret、私钥或恢复码。

飞书连接有额外硬门禁：首次连接默认创建新的飞书应用和新的专用 Profile，用于当前 Agent 根目录和 GLOBAL。安装器不得自动复用本机已有 Profile、active Profile、旧应用或其他项目应用；也不得把它们作为默认值、预选项或失败回退。允许只读列出已有 Profile 以避免命名冲突；若建议名称已存在，生成带后缀的新名称或请用户确认新名称。复用已有飞书应用/Profile 只能作为“高级迁移/共用已有配置”路径，并且必须由用户明确选择，同时先说明这会共享原应用权限、身份路由和审计边界。

连接完成后的身份写回必须以官方回读事实为准。飞书写入 `GLOBAL/LARK_PROFILES.md` 时，公司列表章节标题和公司名称使用授权后 `whoami` 或等价接口回读到的真实公司/租户名称；CLI profile 名只用于 `--profile`、profile 字段和冲突处理，不能代替公司名称。GitHub 写入 `GLOBAL/GITHUB_ACCOUNTS.md` 时，账号列表章节标题、username 和 `gh auth switch --user` 都使用 `gh api user --jq '.login'` 回读的真实 login；显示名只能作为补充字段，不能替代 login。程序不得自行编造公司、组织、账号或展示名称。

## 状态机

```text
source-bootstrap -> collect-minimal -> runtime-preflight -> audit -> plan -> confirm
        -> install -> verify -> skills -> identities -> knowledge-layout
        -> knowledge-link -> local-git -> global-prompt -> general-assistant
        -> global-tour-handoff -> first-project -> skill-smoke-tests -> complete
```

任何阶段失败都保留已经验证成功的事实，不跳过失败门禁。文件安装失败时，只允许清理本轮随机 staging 和本轮自动获取的临时产品源；目标目录、目标父目录和用户原本提供的模板源不得删除。

安装器必须把当前阶段当作可恢复状态保存到对话中：每次等待用户输入前，明确当前阶段、已完成证据、下一步会做什么、是否会写入或授权。用户在安装过程中说起其他事情时，不得丢失状态或重新开始；先判断该输入是安装补充、暂停请求还是无关插话。无关插话只简短回应并继续当前阶段；暂停请求必须输出恢复检查点、已完成步骤、未完成门禁和建议恢复命令。

交互式操作和安装护栏贯穿全流程，不只适用于前半段。进入 `identities`、`knowledge-layout`、`knowledge-link`、`local-git`、`global-prompt`、`general-assistant`、`global-tour-handoff`、`first-project` 和 `skill-smoke-tests` 时，仍必须遵守：宿主有可视化能力先尝试、写入前展示计划、外部授权前说明权限、真实操作前取得确认、操作后独立回读证据、失败时保留诊断并停止越权推进。

## 产品源自举

用户只需要提供官方仓库链接或表达安装意图，不需要手工克隆仓库或注册 Skill。

1. 当前 Skill 已位于包含 `template/` 和 `template-manifest.json` 的完整仓库时，直接使用该仓库根目录。
2. 否则在系统临时目录创建新的随机工作目录，禁止复用现有非空目录，也不得把产品源下载到目标 Agent 根目录。
3. 优先通过宿主的公开 GitHub 读取能力或 `git clone --depth 1 https://github.com/DongLiStudio/personal-agent-foundation.git` 获取完整仓库；没有 Git 时可下载 GitHub 官方 ZIP 并安全解压。
4. 网络访问需要授权时直接请求授权，不把下载步骤转交用户。下载失败时报告原始错误，不从镜像站或未知来源取文件。
5. 回读并记录仓库 URL、ref、commit；ZIP 无法提供 commit 时记录下载 URL 和响应中的版本证据。确认 `README.md`、`template/`、`template-manifest.json`、`skills/install-agent-scaffold/SKILL.md` 全部存在。
6. 完成或失败收口后，只清理本轮创建的临时产品源；用户原本提供的本地仓库不得删除。

产品源获取只是只读准备，不构成 Agent 根目录安装确认。任何 Python/tzdata 安装、系统权限变化和 Agent 根目录写入仍分别遵循确认门禁。

## Python 与时区数据预检

护栏和 GLOBAL 内置确定性脚本要求 Python 3.11+，但不要求用户预先手工安装。

按以下顺序自动查找运行时，并用 `sys.version_info` 回读真实版本；不要只依赖命令名或 PATH：

1. 当前宿主公开的内置 Python 运行时。
2. Windows 的 `py -3`、`python3`、`python`；macOS/Linux 的 `python3`、`python`。
3. 当前系统已知的官方安装位置，但不得递归扫描整块磁盘。

找到多个版本时选择满足要求且路径明确的版本，并在计划中显示其绝对路径和版本。

没有合格版本时生成依赖安装计划：

- Windows：优先使用系统已有的 `winget` 安装官方 `Python.Python.3.12` 包。
- macOS：系统已有 Homebrew 时使用 `brew install python@3.12`；不得为了本产品静默安装 Homebrew。
- Linux：识别发行版和现有官方包管理器，选择可提供 Python 3.11+ 的发行版包；任何 `sudo` 或系统级修改都必须在执行前单独确认。

展示将执行的命令、来源、是否需要管理员权限和预计影响。用户确认后执行；随后重新查找运行时并用独立命令回读版本。官方包管理器不可用、用户拒绝或回读仍低于 3.11 时停止安装并给出准确阻断，不得下载来源不明的可执行文件。

获得 Python 后，用所选时区实际构造 `zoneinfo.ZoneInfo`。Windows 等缺少系统 IANA 时区库的环境，把 `<python> -m pip install tzdata` 作为单独依赖项展示并确认；执行后再次构造同一时区并回读 `tzdata` 版本。不要仅凭安装命令退出码判定可用。

## GLOBAL 本地 Git

安装验证通过后，在 `<AGENT_ROOT>/GLOBAL` 运行：

```text
git init -b main
git status --short
git add <经过脱敏扫描的安装文件>
git commit -m "初始化 Agent GLOBAL 基座"
```

commit 不构成上传授权。除非用户另行明确要求，不配置 remote、不创建 GitHub 仓库、不 push。

## Skill 恢复

1. 以 `<AGENT_ROOT>/GLOBAL/.agents/skills/` 为自维护全局 Skill 权威源稿。
2. 确认当前宿主的用户级全局 Skill 安装位置或官方安装器。
3. 对每个源稿先比较同名目标；目标缺失时安装，目标存在且不同则展示差异并确认。
4. 根据 `SKILL_DEPENDENCIES.md` 恢复外部 Skills；固定来源存在时遵循其当前官方安装流程。
5. 回读宿主可发现的 Skill 列表或文件哈希，不能只以复制命令退出码作为成功证据。

## 身份配置

- 飞书：用户选择现在连接时，调用 `feishu-profile`，默认创建新的飞书应用和新的专用 Profile，完成验证码/OAuth 和 `whoami` 回读；把工具回读出的真实 Profile 写回 `GLOBAL/LARK_PROFILES.md`。不要向用户询问“Profile 名是什么”作为前置条件；必要名称由 Skill 创建或从工具回读。不得自动复用本机已有 Profile、active Profile、旧应用或其他项目应用；已有 Profile 只用于只读冲突检查。复用已有配置只能在用户明确选择高级迁移/共用路径并确认共享权限、身份路由和审计边界后执行。公司列表标题和公司名称使用回读到的真实公司/租户名称，不使用程序自拟名或 CLI profile 名。
- GitHub：用户选择现在连接时，调用 `github-cli`，完成 `gh auth status` 和 `gh api user --jq '.login'` 回读；把工具回读出的真实账号写回 `GLOBAL/GITHUB_ACCOUNTS.md`。不要向用户询问“GitHub 用户名是什么”作为前置条件；必要账号由 CLI 授权和回读确定。账号列表标题、username 和切换命令必须使用回读到的真实 login，不使用程序自拟名。
- 所有认证页面由用户确认；不得读取或保存 token。

## 知识库链接

只有用户在连接阶段确认真实 Obsidian Vault 目录时才创建：

1. 完整读取 `obsidian-layout.md`，先确认 Vault 是否已有内容、是否采用现成目录约定，以及用户希望 Agent 如何理解和使用它；不能只询问软连接路径。
2. 对用户的现有结构，用通俗语言说明“我先看第一层目录，猜一下用途，再请你纠偏”；用户同意后做有界只读发现并列出初步解析。用户不同意发现时，再请用户用自己的话描述结构。不得把目录名称猜测直接写成事实，也不得把作者结构当作用户事实。
3. 如需查看现有结构，先征得用户同意，只做根目录和用户指定位置的浅层只读检查；不递归遍历，不进入 `.obsidian`，不读取正文来推断隐私边界。
4. 先展示拟写入 `GLOBAL/OBSIDIAN_LINK.md` 的完整草案。草案应与模板整体结构同构，只替换“目录理解”和“优先阅读”中涉及用户实际 Vault 的条目；不得写入 Vault 原始绝对路径，不得生成过度泛化的替代表格。用户确认后只修改已安装实例，不修改产品模板。
5. 映射确认后再创建链接：Windows 优先 Junction，macOS/Linux 使用 symlink。
6. 同时回读链接类型、链接路径、解析目标和 `OBSIDIAN_LINK.md` 的最终内容。

创建前确认目标不是 `AGENT_ROOT`、GLOBAL 或其父目录；创建后同时回读链接类型、链接路径和解析目标。不得递归复制 Vault。

没有配置 Vault 时不创建伪链接，保留渲染后的通用连接约定并明确标记未配置。用户已提供 Vault 但明确表示目录理解和优先阅读之后再定时，也应标记为 Obsidian 待配置，不能仅凭软连接创建宣布完成。空 Vault、全新 Vault 或目录很少尚未形成结构时，先推荐默认五类结构（信息、资源、想法、知识、特殊），用户同意后展示将创建的目录和入口文件清单并单独确认；用户不同意时询问想要的结构；用户跳过时才标记为待补充。
