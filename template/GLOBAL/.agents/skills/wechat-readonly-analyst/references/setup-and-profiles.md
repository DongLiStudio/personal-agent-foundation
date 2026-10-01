# 安装与 Profile 生命周期

## 安装

只在用户级安装副本运行安装脚本，不在 GLOBAL 源稿目录生成 `.runtime`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

安装器使用 Python 3.12 x64，在 Skill 内创建私有虚拟环境；依赖 wheel 随 Skill 保存并锁定 SHA-256，安装时不访问软件源，也不读取微信。安装后先执行：

```powershell
.\.runtime\Scripts\python.exe .\scripts\profile_manager.py self-test
```

## 多 Profile 模型

- GLOBAL `WECHAT_PROFILES.md`：逻辑名称、非敏感主体描述、用途、状态和恢复方法。
- 当前宿主：`%LOCALAPPDATA%\DongLi\AgentFoundation\credentials\wechat-readonly`；路径与经验证的数据库密钥目录使用 Windows DPAPI CurrentUser 加密，不进入 Git、GLOBAL、日志或报告。
- 不设默认 Profile。项目可以声明推荐 Profile，但每条命令仍须显式传入。

## 发现与连接

发现候选只返回宿主专用指纹和最后活动时间，不返回 wxid 或路径：

```powershell
.\.runtime\Scripts\python.exe .\scripts\profile_manager.py discover
```

让用户依据当前登录账号和活动时间选择候选并明确确认其拥有或获授权访问，然后连接：

```powershell
.\.runtime\Scripts\python.exe .\scripts\profile_manager.py connect --profile "逻辑名称" --candidate "候选指纹" --confirm-owner
```

连接确认同时建立该 Profile 的持续只读授权。随后直接运行最小 `sessions` 查询，包装器会自动获取与所选 Profile 数据库匹配的密钥并加密保存；无需再次询问授权或附加确认参数。执行 `list` 回读，只有 `available` 与 `offline_key_available` 都为 `true`，才把非敏感 Profile 条目标记为 `可用`。不得把指纹当作跨电脑身份；它只用于当前宿主候选选择。

微信升级、数据库新增或密钥轮换导致明确的密钥/解密错误时，在微信运行状态下直接执行查询，包装器会自动尝试一次刷新。手动强制刷新只需 `--refresh-key-catalog`，但同样必须先验证与绑定数据库匹配。刷新采用先校验、查询成功后原子覆盖；失败时保留原 DPAPI 凭据槽。普通查询错误不会触发刷新。

## 删除、迁移与恢复

删除只移除本机 DPAPI 绑定，不删除微信数据：

```powershell
.\.runtime\Scripts\python.exe .\scripts\profile_manager.py remove --profile "逻辑名称" --confirm
```

换电脑时从 GLOBAL 恢复 Skill 和 `WECHAT_PROFILES.md`，重新运行安装、自检、发现、逐 Profile 连接和一次性取钥；不得复制旧电脑 DPAPI 槽。修改或移除 GLOBAL 条目前，先搜索项目引用。删除 Profile 会同时撤销持续只读授权并删除本机加密路径/密钥槽，但不删除微信数据。
