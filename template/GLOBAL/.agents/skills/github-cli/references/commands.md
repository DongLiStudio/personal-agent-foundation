# GitHub CLI 命令模式

需要选择具体 `gh` 命令时读取本参考。Windows 环境优先使用 PowerShell 示例。

## 认证和账号

```powershell
gh auth status
gh auth login --hostname github.com --git-protocol https --web
gh auth switch --hostname github.com --user <username>
gh auth refresh --scopes repo,read:org,gist
```

注意：

- `gh auth status` 会列出 host、账号、active 账号、协议和 token scopes。
- 同一 host 只有两个账号时，`gh auth switch` 可以自动切换；存在多个账号时使用 `--user`。
- GitHub Enterprise 场景使用 `--hostname <host>`；必要时目标仓库写作 `-R HOST/OWNER/REPO`。

## 仓库上下文

```powershell
git remote -v
gh repo view OWNER/REPO --json nameWithOwner,description,defaultBranchRef,visibility,url
gh repo view OWNER/REPO --web
```

不确定当前目录 remote 是否正确时，Issue/PR/run 命令都传入 `-R OWNER/REPO`。

## Issues

读取：

```powershell
gh issue list -R OWNER/REPO --state open --limit 30
gh issue view 123 -R OWNER/REPO --comments --json number,title,state,author,assignees,labels,body,comments,url
```

只有用户意图明确后才写入：

```powershell
gh issue create -R OWNER/REPO --title "..." --body "..."
gh issue comment 123 -R OWNER/REPO --body "..."
gh issue close 123 -R OWNER/REPO --comment "..."
```

## Pull requests

读取：

```powershell
gh pr list -R OWNER/REPO --state open --limit 30
gh pr view 123 -R OWNER/REPO --comments --json number,title,state,author,baseRefName,headRefName,isDraft,mergeable,reviewDecision,statusCheckRollup,url
gh pr diff 123 -R OWNER/REPO
gh pr checks 123 -R OWNER/REPO --json bucket,name,state,link,workflow,completedAt
```

只有用户意图明确后才写入：

```powershell
gh pr create --draft --base main --head <branch> --title "..." --body "..."
gh pr comment 123 -R OWNER/REPO --body "..."
gh pr review 123 -R OWNER/REPO --comment --body "..."
gh pr ready 123 -R OWNER/REPO
gh pr merge 123 -R OWNER/REPO --squash
```

执行 `gh pr merge` 前，确认账号、仓库、PR 编号、merge 方式，以及是否要删除分支。

## Actions 和 CI

```powershell
gh pr checks 123 -R OWNER/REPO --required
gh run list -R OWNER/REPO --limit 20
gh run view <run-id> -R OWNER/REPO --log
gh run watch <run-id> -R OWNER/REPO --interval 10
gh run rerun <run-id> -R OWNER/REPO
gh run cancel <run-id> -R OWNER/REPO
```

将 rerun、cancel、workflow dispatch 视为写操作。除非用户已明确要求，否则先询问。

## Releases

```powershell
gh release list -R OWNER/REPO
gh release view <tag> -R OWNER/REPO
gh release create <tag> <files...> -R OWNER/REPO --title "..." --notes "..."
gh release upload <tag> <files...> -R OWNER/REPO
```

创建、上传、编辑、删除或发布 Release 都是高影响操作。确认准确 tag、assets、目标仓库，以及是否为 draft/prerelease。

## Secrets 和 variables

```powershell
gh secret list -R OWNER/REPO
gh secret set NAME -R OWNER/REPO
gh variable list -R OWNER/REPO
gh variable set NAME --body "value" -R OWNER/REPO
```

不要 echo secret 值。Secret 输入优先使用 stdin 或交互提示。不要把 secrets 存入仓库文件、任务日志或最终回复。

## API 回退

只有高层命令不足时才使用：

```powershell
gh api repos/OWNER/REPO/pulls/123 --jq '.title'
gh api graphql -f query='query { viewer { login } }'
```

通过 `gh api` 写入前，先说明 method、path、body 并获得确认。

## GitHub CLI skills

只有认证可用后，才通过 GitHub CLI 搜索/安装公开 `SKILL.md` 包：

```powershell
gh skill search "query" --limit 10 --json skillName,description,repo,path,stars
gh skill preview OWNER/REPOSITORY SKILL
gh skill install OWNER/REPOSITORY SKILL
```

`SKILL` 可以是 Skill 名称、带命名空间的名称，或仓库内精确路径。安装目标 Agent 和作用域由当前项目或全局 Skill 管理规则决定；需要非默认目标时，显式传入 `--agent <agent>` 与 `--scope project|user`，不要在通用命令模式中固定为某个 Agent 或作用域。

把第三方 skills 当作供应链输入处理。安装前检查来源/仓库并询问用户。
