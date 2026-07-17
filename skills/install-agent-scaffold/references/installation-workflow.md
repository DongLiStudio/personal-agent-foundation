# 安装工作流

## 配置 JSON

使用以下键；文件只包含非敏感标识，安装完成后删除：

```json
{
  "AGENT_ROOT": "D:\\Agent",
  "DEFAULT_LARK_PROFILE": "my-default-profile",
  "DEFAULT_GITHUB_ACCOUNT": "my-github-user",
  "DEFAULT_TIMEZONE": "Asia/Shanghai",
  "GENERAL_ASSISTANT_PROJECT": "通用助手",
  "OBSIDIAN_VAULT_PATH": "未配置（首次连接 Obsidian 时设置）"
}
```

macOS/Linux 使用对应绝对路径。`AGENT_ROOT` 必须与命令的 `--target` 解析到同一路径。

## 状态机

```text
source-bootstrap -> collect -> runtime-preflight -> audit -> plan -> confirm -> install -> verify
        -> knowledge-layout -> knowledge-link -> local-git -> skills -> identities
        -> global-prompt -> first-project -> complete
```

任何阶段失败都保留已经验证成功的事实，不跳过失败门禁。文件安装失败时，只允许清理本轮随机 staging 和本轮自动获取的临时产品源；目标目录和用户原本提供的模板源不得删除。

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

- 飞书：调用 `feishu-profile`，完成应用、OAuth 和 `whoami` 回读；把治理默认值与 CLI active 区分开。
- GitHub：调用 `github-cli`，完成 `gh auth status` 和 `gh api user` 回读；active 账号必须匹配 `DEFAULT_GITHUB_ACCOUNT`。
- 所有认证页面由用户确认；不得读取或保存 token。

## 知识库链接

只有 `OBSIDIAN_VAULT_PATH` 指向用户确认的真实目录时才创建：

1. 完整读取 `obsidian-layout.md`，先确认 Vault 是否已有内容、是否采用现成目录约定，以及用户希望 Agent 如何理解和使用它。
2. 对用户的现有结构，通过对话确定总览、长期资料、项目资料、日记、附件等实际位置和语义；不得根据目录名称自行猜测，也不得把作者结构当作默认标准。
3. 如需查看现有结构，先征得用户同意，只做根目录和用户指定位置的浅层只读检查；不递归遍历，不进入 `.obsidian`，不读取正文来推断隐私边界。
4. 先展示拟写入 `GLOBAL/OBSIDIAN_LINK.md` 的目录映射、优先入口、默认权限、允许写入位置和排除项；用户确认后只修改已安装实例，不修改产品模板。
5. 映射确认后再创建链接：Windows 优先 Junction，macOS/Linux 使用 symlink。
6. 同时回读链接类型、链接路径、解析目标和 `OBSIDIAN_LINK.md` 的最终内容。

创建前确认目标不是 `AGENT_ROOT`、GLOBAL 或其父目录；创建后同时回读链接类型、链接路径和解析目标。不得递归复制 Vault。

没有配置 Vault 时不创建伪链接，保留渲染后的通用连接约定并明确标记未配置。空 Vault 或全新 Vault 也不得自动套用作者目录；如用户希望建立新结构，应先给出方案并单独确认创建目录。
