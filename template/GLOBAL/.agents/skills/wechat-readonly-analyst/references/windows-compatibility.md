# Windows 兼容与故障处理

## 已知范围

- Windows 11 x64。
- Python 3.12 x64。固定单一小版本族是为了让离线 wheel 与哈希验证可复现。
- 原始适配实测微信 4.1.13.63；相近版本只能以运行时数据库页 HMAC 校验结果为准。

Windows 扫描器仅使用 `OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION)`、`VirtualQueryEx` 与 `ReadProcessMemory`。代码中不应出现 `WriteProcessMemory`、`CreateRemoteThread`、`VirtualAllocEx` 或 `DebugActiveProcess`。

## 失败处理

1. 确认选择的逻辑 Profile 与当前登录微信账号一致。
2. 只有首次取钥或刷新密钥目录时，才需确认微信已登录并至少打开过一个普通聊天；已有 DPAPI 密钥目录的日常查询不要求微信运行。
3. 确认 Python 与微信都是 x64。
4. 安全软件拒绝进程读取时，只向用户解释；不得自行关闭防护、添加排除项或提升长期权限。
5. 微信升级、新数据库或密钥轮换后若验证失败，停止当前查询并提示在微信运行时刷新密钥目录；不得输出候选密钥、放宽 HMAC 校验、修改微信签名、降级客户端或注入代码。

安装修复可以执行 `install.ps1 -Repair`，它只重建 Skill 私有运行时。Profile 绑定保存在独立 DPAPI 槽，不随 `.runtime` 删除。
