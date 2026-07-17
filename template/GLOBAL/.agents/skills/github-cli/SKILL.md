---
name: github-cli
description: "当 Agent 需要通过 GitHub CLI (`gh`) 操作 GitHub 时使用：检查认证和 active 账号、在多个 GitHub 账号之间切换、查看仓库/Issue/PR/Actions、搜索或安装 GitHub CLI skills、使用 `gh api`，或规划评论、创建 PR、Release、Secrets、Variables、Workflow 运行、仓库变更等安全写操作。用户询问 GitHub CLI 的使用、安装、登录、配置或排错时也使用。"
---

# GitHub CLI

使用 `gh` 处理 GitHub 托管状态和协作流程。使用本地 `git` 处理本地仓库状态、diff、分支、commit 和 remote。优先使用官方 `gh` 子命令；只有高层命令无法满足时才使用 `gh api`。

## 安全起步

1. 使用 `gh` 前先确认目标仓库。在本地仓库中检查 `git remote -v`；不在仓库中时，要求或推断 `OWNER/REPO`，并传入 `-R OWNER/REPO`。
2. 执行 GitHub 操作前先检查认证：
   ```powershell
   gh auth status
   ```
3. 多账号场景下，如可用，先读取 `{{AGENT_ROOT}}\GLOBAL\GITHUB_ACCOUNTS.md`，再确认 active 账号与目标项目或用户意图匹配。
4. 如果 active 账号不对，不要继续写操作。显式切换账号：
   ```powershell
   gh auth switch --hostname github.com --user <username>
   ```
5. 除非用户明确要求诊断凭据，否则不要打印或索要 token。避免使用 `gh auth token` 和 `gh auth status --show-token`。
6. 涉及账号新增、重新授权、默认/专属账号路由、换机恢复、安全退出、远程仓库创建或首次 push 时，读取 [references/account-routing.md](references/account-routing.md)。

## 先读后写

任何写操作前，先用只读命令建立上下文：

```powershell
gh repo view OWNER/REPO
gh issue view 123 -R OWNER/REPO --comments
gh pr view 123 -R OWNER/REPO --comments
gh pr checks 123 -R OWNER/REPO --json bucket,completedAt,link,name,state,workflow
gh run list -R OWNER/REPO
gh run view <run-id> -R OWNER/REPO --log
```

优先使用 `--json` 配合 `--jq` 或模板获得机器可读结果。命令支持 `--web` 时，除非用户希望打开浏览器，否则不要使用。

## 写操作和确认

以下操作必须有明确用户意图后再执行：创建/编辑/关闭 Issue 或 PR、PR 评论/Review、push 分支、merge PR、创建/发布/删除 Release、workflow dispatch/rerun/cancel、Secret 或 Variable 变更、仓库创建/删除/归档/可见性变更、deploy key、SSH/GPG key，以及 GitHub CLI extension/skill 安装。

高影响写操作前，说明目标账号、仓库、操作和主要参数。可行时先使用非变更预览，例如 `gh pr diff`、`gh pr view`、`gh release view`、`gh workflow view`、`gh api --method GET`。

## 常见工作流

任务涉及 PR、Issue、Actions/CI、Release、`gh api` 或 GitHub CLI skills 时，读取 [references/commands.md](references/commands.md) 获取具体命令模式。账号生命周期、项目路由、remote 与首次 push 读取 [references/account-routing.md](references/account-routing.md)。

## 错误处理

- 如果找不到 `gh`，在 Windows 上先检查 `%LOCALAPPDATA%\Programs\GitHub CLI\gh.exe`，再询问是否安装或修复 PATH。
- 如果尚未登录，运行 `gh auth login --hostname github.com --git-protocol https --web`，并把浏览器/设备授权指引返回给用户。
- 如果缺少 scopes，先说明为什么需要该 scope，再使用 `gh auth refresh --scopes <scope>`。
- 如果 rate limited 或 unauthorized，先确认 active 账号、host 和仓库访问权限；不要重试破坏性命令。
- 如果输出包含 secrets，回复前先脱敏。

## 官方参考

- GitHub Docs: https://docs.github.com/zh/github-cli/github-cli/about-github-cli
- GitHub CLI quickstart: https://docs.github.com/zh/github-cli/github-cli/quickstart
- GitHub CLI manual: https://cli.github.com/manual/
