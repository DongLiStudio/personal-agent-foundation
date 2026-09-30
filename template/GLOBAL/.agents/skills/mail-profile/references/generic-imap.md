# 通用 IMAP 只读接入

适用于163、QQ、Outlook及其他提供 IMAP SSL 的邮箱。

## 接入要求

- 用户必须在邮箱服务商处自行开启 IMAP，并生成客户端授权码或应用专用密码。
- 授权码通过隐藏输入或系统安全存储提供，不得发送到聊天、写入 Markdown/JSON、放进命令行参数或提交到 Git。
- 首次接入先确认服务商官方 IMAP 主机、端口、TLS要求和账号地址；不要仅凭常见默认值写入长期路由。
- 使用只读模式打开邮箱文件夹；抓取正文使用 `BODY.PEEK`，避免隐式标记已读。

## 工具

`scripts/imap_readonly.py` 提供只读身份探测、搜索和附件下载：

```powershell
$env:AGENT_MAIL_SECRET = '<仅在安全注入流程中设置>'
python scripts/imap_readonly.py --host <host> --username <email> probe
python scripts/imap_readonly.py --host <host> --username <email> search --query '<IMAP query>'
python scripts/imap_readonly.py --host <host> --username <email> download --uids <uid,...> --output <directory>
Remove-Item Env:AGENT_MAIL_SECRET
```

不要让用户在普通命令或聊天中提供秘密。实际长期凭据应由宿主系统凭据存储或服务商 OAuth 管理；若宿主没有安全存储能力，每次运行采用临时隐藏输入，并在进程结束后清理。

Windows 宿主优先使用 `scripts/imap_credential_slot.ps1`。它通过隐藏输入接收客户端授权码，并使用 Windows CurrentUser DPAPI 加密保存到 `%LOCALAPPDATA%\Codex\mail-profiles`；该目录不进入 Git，也不随 GLOBAL 迁移：

```powershell
pwsh -File scripts/imap_credential_slot.ps1 -Action save -Profile <逻辑名称> -HostName <host> -Port 993 -Username <email>
pwsh -File scripts/imap_credential_slot.ps1 -Action probe -Profile <逻辑名称>
pwsh -File scripts/imap_credential_slot.ps1 -Action search -Profile <逻辑名称> -Mailbox INBOX -Query '<IMAP query>' -Limit 50
pwsh -File scripts/imap_credential_slot.ps1 -Action download -Profile <逻辑名称> -Mailbox INBOX -Uids '<uid,...>' -Output '<workspace directory>'
```

用户必须亲自在本机隐藏输入提示中填写授权码；Agent 不得通过聊天、普通命令参数或自动化输入该值。

## 验证

- `probe` 只报告服务端欢迎信息、账号和邮箱文件夹数量，不列出邮件内容。
- `search` 输出 UID、日期、发件人、主题和附件名，不下载正文或附件。
- `download` 仅处理明确选定 UID，并计算 SHA-256；保存目录必须位于当前任务工作区。
- 认证失败时停止，不尝试其他邮箱、密码或主体。
