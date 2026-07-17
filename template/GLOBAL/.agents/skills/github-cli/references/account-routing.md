# GitHub 账号生命周期与项目路由

新增、恢复、切换、迁移或退出 GitHub 账号，或创建远程仓库、配置 remote、首次 push 时读取本参考。

## 事实层级

- 用户当前要求和项目规则决定目标账号、OWNER、仓库与可见性。
- GLOBAL/GITHUB_ACCOUNTS.md 记录全局默认账号、专属账号用途、权限参考和执行前实时核验方式。
- gh auth status 与 gh api user 反映当前机器的实时认证和 active 账号。

低层运行状态不得覆盖高层路由。项目存在专属账号时优先使用；没有专属规则时才使用 GLOBAL 默认账号。gh active 账号不自动等于目标项目账号。

## 操作前核验

- 读取项目持续上下文和适用任务文件。
- 按需读取 GLOBAL/GITHUB_ACCOUNTS.md，确定目标账号。
- 在仓库运行 git remote -v 和 git status --short --branch。
- 运行 gh auth status；需要确认 active 用户时，使用只读 gh api user --jq '.login'。
- 账号不匹配时先显式切换，不在错误账号下试探写操作。

不要运行 gh auth token 或 gh auth status --show-token，不要把 token、PAT、SSH/GPG 私钥、恢复码或凭据文件写入项目、GLOBAL、日志或回复。

## 新增、恢复与切换

新增前回读已有账号和 active 状态。先用当前 gh auth login --help 核对参数，再使用官方网页登录：

    gh auth login --hostname github.com --git-protocol https --web

浏览器已有会话会影响授权主体；在确认页核对用户名。完成后同时回读 gh auth status 和 gh api user --jq '.login'。新账号未进入 CLI 凭据库时，不把网页授权成功误报为登录成功，也不得删除或覆盖已有专属账号。

用户决定新账号为全局默认时更新 GLOBAL/GITHUB_ACCOUNTS.md；只服务某项目时记录在项目规则中。认证异常先区分 token 失效、scope 不足、账号未保存和网络故障；scope 不足时说明用途后使用 gh auth refresh --scopes <scopes>。

切换时明确用户名，并在切换后重新核验：

    gh auth switch --hostname github.com --user <username>

## Git 与 GitHub 身份分层

- git config user.name/user.email 决定 commit 作者元数据。
- git remote -v 决定默认 fetch/push 目标。
- Git credential helper 决定 HTTPS push 凭据。
- gh active 账号决定 GitHub CLI API 操作身份，并可能参与 gh auth setup-git。

不要仅凭其中一层推断其他层已经正确。任何 GitHub 写操作前都确认 active 账号、目标 OWNER/REPO 和项目路由一致。

## 远程仓库与首次 push

本地 commit 或全局默认账号不构成上传授权。首次建立远程前明确确认目标账号或组织、仓库名称、可见性、是否新增或替换 remote、是否立即 push 及目标分支。

先用 gh repo view OWNER/REPO 确认同名仓库是否存在。创建后回读 OWNER、可见性和默认分支；配置 remote 后回读 git remote -v；首次 push 后比较本地 HEAD 与远端分支并确认 upstream。

不得静默替换已有 remote，不得把同名远端当作同一项目，也不得把创建仓库授权扩大为公开发布、Release 或其他项目推送。

## 换机恢复

GitHub 登录、credential helper、SSH/GPG 密钥和 PAT 不随项目 Git 或 GLOBAL 自动迁移。换机时从项目规则和 GLOBAL/GITHUB_ACCOUNTS.md 恢复路由，逐个重新登录账号，再核对 scopes、remote、默认分支和访问权限。SSH/GPG、PAT、GitHub App 与组织 SSO 按各自安全流程恢复。

## 安全退出

gh auth logout 会移除本机认证，必须由用户明确指定 host、账号和范围。执行前回读全部账号，搜索授权范围内的项目规则、GLOBAL 映射和 Git remote，确认是否需要先切换默认账号或修正路由；读取当前 gh auth logout --help 后只退出明确账号。退出后确认其他账号未受影响并报告残留引用。

不要自动退出默认账号或项目专属账号；认证失效优先重新登录，不以删除账号作为常规修复。
