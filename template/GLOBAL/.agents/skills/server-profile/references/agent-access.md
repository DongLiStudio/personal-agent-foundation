# Bitwarden Agent 接入与验收

依据：[Bitwarden 官方 SSH Agent 说明](https://bitwarden.com/help/ssh-agent/)；执行前按当前版本复核。

## Windows

在桌面端启用 SSH Agent、保持后台运行、签名授权设为始终提示。核验实际客户端 `Get-Command ssh` / `ssh -V`。按官方说明停止并禁用 Windows OpenSSH Authentication Agent，避免占用同一通道；服务修改先确认影响，不擅自清空其他身份。

`ssh-add -l` 仅列公开指纹；枚举不等于签名成功。Git for Windows、GUI 客户端可能使用不同 SSH 实现，需检查实际实现和认证，不能全局改 Git 配置冒充验收。

## macOS

按实际安装来源选一条，不同时写两条覆盖：

```bash
# App Store 版
export SSH_AUTH_SOCK="$HOME/Library/Containers/com.bitwarden.desktop/Data/.bitwarden-ssh-agent.sock"
# 官方 dmg 版
export SSH_AUTH_SOCK="$HOME/.bitwarden-ssh-agent.sock"
```

将使用的一条写入对应 shell 的 `~/.zshrc` 或 `~/.bashrc`，保留旧内容、避免重复；新终端回读并执行 `ssh-add -l`。这不证明 GUI 客户端或未登录桌面的环境也可签名。服务端接受远程客户端公钥与其本机对外 Agent 接入是两个方向，分开验收。

## 会话生命周期与客户端身份

完成独立身份核验后，同一任务、同一服务器、同一主体的连续操作可通过一个交互 SSH 会话执行。任务完成、取消或需要等待用户决策时退出，断线后重新申请签名；不为减少弹窗降低 Bitwarden 授权策略，不默认使用跨任务常驻 ControlMaster。保留 `StrictHostKeyChecking=yes` 和 `ForwardAgent=no`。

复用会话中的命令不再逐条向 Agent 请求签名；锁定密码库不能撤销已经认证的连接。进程名可以仿冒，将客户端命名为 `ai-agent-ssh.exe` 只能增加可辨认性。实际客户端应以明确路径调用，并核验发行来源及可用的数字签名或哈希；批准时核对请求时机与目标密钥，不把名称视为 Agent 身份证明。若要维护专用命名副本，必须单独处理可执行文件来源、依赖、更新与权限，不能覆盖系统 `ssh.exe`。

## 独立认证

先取得可信主机指纹并建立 known_hosts。以下 PORT/USER/HOST 必须替换为已确认值，不自动跳过未知主机校验：

```text
ssh -o IdentityFile=none -o IdentitiesOnly=no -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o ControlMaster=no -o ControlPath=none -o StrictHostKeyChecking=yes -p PORT USER@HOST "whoami; hostname"
```

观察目标条目授权、过滤认证日志和命令结果；必要时加 `-v`，不保存完整日志。正常使用提供 `ssh -p PORT USER@HOST`。没有本地私钥仍能从 Agent 获得公开候选并签名。Agent 关闭后拒绝/开启后成功可作补充，但关闭不会终止已有会话。

多钥超过上限可用目标公开 `.pub` 配合 `IdentitiesOnly=yes`，私钥仍留 Agent；不强制保存选择器。用户不想保留时说明上限，再按明确授权处理服务端配置，不自动修改其他主机。Agent 转发默认关闭，终端受控仍是前提。
