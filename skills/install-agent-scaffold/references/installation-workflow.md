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
collect -> runtime-preflight -> audit -> plan -> confirm -> install -> verify
        -> local-git -> skills -> identities -> knowledge-link
        -> global-prompt -> first-project -> complete
```

任何阶段失败都保留已经验证成功的事实，不跳过失败门禁。文件安装失败时，只允许清理本轮随机 staging；目标目录和模板源不得删除。

## Python 与时区数据预检

护栏和 GLOBAL 内置确定性脚本要求 Python 3.11+。安装前用所选时区实际构造 `zoneinfo.ZoneInfo`；Windows 等缺少系统 IANA 时区库的环境，在安装计划确认后执行 `python -m pip install tzdata`，随后再次构造同一时区并回读版本。不要仅凭 pip 退出码判定可用。

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

- Windows：优先 Junction。
- macOS/Linux：symlink。

创建前确认目标不是 `AGENT_ROOT`、GLOBAL 或其父目录；创建后同时回读链接类型、链接路径和解析目标。不得递归复制 Vault。
