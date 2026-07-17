# GitHub CLI 账号对应关系

本文件记录跨项目使用的 GitHub CLI 账号映射。只记录账号、用途、host、权限参考、核验方式和切换命令；不要记录 token、PAT、SSH 私钥、恢复码或其他密钥。

## 当前约定

- GLOBAL 全局默认 GitHub 账号：`{{DEFAULT_GITHUB_ACCOUNT}}`。
- 项目存在专属账号或路由规则时，以项目规则为准；否则使用全局默认账号。
- 写操作前运行 `gh auth status` 和 `gh api user --jq '.login'`，确认 active 账号与目标路由一致。
- active 只是运行状态，不覆盖项目或 GLOBAL 路由。
- 不运行或输出 `gh auth token`、`gh auth status --show-token`。
- 创建远程仓库、确定可见性、配置 remote 和首次 push 前必须获得用户明确授权。

## 账号列表

### 默认账号（安装时配置）

- Host：`github.com`
- GitHub username：`{{DEFAULT_GITHUB_ACCOUNT}}`
- Git protocol：`https`
- 用途：未被项目专属规则覆盖时使用的全局默认账号。
- 查看状态：`gh auth status`
- 切换命令：`gh auth switch --hostname github.com --user {{DEFAULT_GITHUB_ACCOUNT}}`

其他账号在用户明确说明用途后追加，不从本机 active 状态自动推断长期路由。
