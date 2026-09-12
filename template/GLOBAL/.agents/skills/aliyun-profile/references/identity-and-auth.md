# 身份与授权路由

## 阿里云通用 Profile

使用当前 CLI `aliyun configure --help` 与官方文档发现支持的认证模式。执行写操作时显式带 `--profile <name>` 或在受控子进程设置 `ALIBABA_CLOUD_PROFILE`，并在调用前后回读账号身份。CLI 的当前星标 Profile 只是运行状态，不覆盖项目路由。

尚未建立任何通用 Profile 时，部分 CLI 版本的 `aliyun configure list` 会因配置文件不存在而返回错误；这表示“未配置”，不代表 CLI 安装失败。不得为消除该错误创建伪造或空凭据。

优先顺序不是硬编码，但一般优先短期或联合身份：CloudSSO / OAuth / RAM Role / STS，再考虑长期 AK。任何长期密钥都不得进入仓库或 GLOBAL。

## 云效逻辑 Profile

云效官方插件使用：

- `ALIBABA_CLOUD_YUNXIAO_ACCESS_TOKEN`
- 中心版：`ALIBABA_CLOUD_YUNXIAO_ORGANIZATION_ID`
- Region 版：`ALIBABA_CLOUD_YUNXIAO_API_BASE_URL`

PAT 只在创建时显示，应使用最小权限和合理有效期。不要通过 `--yunxiao-access-token` 明文参数传入。发现泄露时立即撤销并轮换。

`ALIYUN_PROFILES.md` 中的“凭据槽”是逻辑名称，不是环境变量值或文件路径。宿主没有安全凭据库时，使用隐藏输入仅注入当前进程，完成后清理；不要为了自动化便利降级为明文持久化。

## Windows 安全凭据槽

Windows 宿主使用 `scripts/yunxiao-credential-slot.ps1`。它以逻辑 Profile 名计算稳定槽位，使用 Windows DPAPI CurrentUser 加密 PAT，并把槽文件 ACL 限制为当前 Windows 用户。密文绑定当前用户与宿主，不属于 GLOBAL 或项目资产，不得复制到另一台电脑；换机后重新隐藏输入并授权。

连接前先确认 Profile、组织类型和组织 ID。`connect` 会隐藏读取 PAT，执行 `base-get-user-by-token` 与 `base-list-organizations`，只在目标组织 ID 回读一致后写入密文：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File <skill-root>\scripts\yunxiao-credential-slot.ps1 `
  -Action connect `
  -SlotName '<云效逻辑 Profile>' `
  -OrganizationId '<organization-id>'
```

交互式连接固定使用 `-NoProfile`，减少 Conda 或用户 PowerShell Profile 对运行时、编码和模块搜索路径的干扰。脚本直接调用 Windows DPAPI，不依赖 `Microsoft.PowerShell.Security` 模块。失败时先执行 `status`，确认不存在半成品槽，再在干净进程重试；不得改用明文参数。

日常先用 `status` 检查本机槽位可解密，再用 `verify` 实时回读；不得把槽位存在误当成 PAT 仍有效：

```powershell
& <skill-root>\scripts\yunxiao-credential-slot.ps1 -Action status -SlotName '<云效逻辑 Profile>' -OrganizationId '<organization-id>'
& <skill-root>\scripts\yunxiao-credential-slot.ps1 -Action verify -SlotName '<云效逻辑 Profile>' -OrganizationId '<organization-id>'
```

具体云效命令通过 `run` 执行。调用前仍要按项目规则判断授权；凭据槽只解决身份注入，不扩大业务权限：

```powershell
& <skill-root>\scripts\yunxiao-credential-slot.ps1 `
  -Action run `
  -SlotName '<云效逻辑 Profile>' `
  -OrganizationId '<organization-id>' `
  -DevopsCommand 'codeup-list-repositories' `
  -DevopsArguments @('--page', '1', '--per-page', '1')
```

删除槽位会使后续调用失去认证，只有用户明确授权后才运行 `remove -Force`。脚本输出只包含非敏感状态，不输出 PAT；严禁额外添加 `--yunxiao-access-token` 或把 PAT 放进日志、任务和报告。

## 归属规则

- 用户控制、跨项目长期使用的阿里云账号或云效组织身份：登记 GLOBAL 非敏感映射。
- 客户、合作方、沙箱或单项目身份：项目记录主体关系与非敏感路由；如用户明确要求统一治理，再登记 GLOBAL。
- 账号登记只解决“用谁操作”，不授予任何资源写入、发布、删除或费用操作权限。

## 最小验证

安装层：

```text
aliyun version
aliyun plugin list
aliyun devops version
```

通用云账号验证应使用不会产生资源变更的身份查询接口。云效验证优先使用 `base-*` 组织/成员只读接口；当前插件没有合适接口时，可用 `codeup-list-repositories --page 1 --per-page 1` 验证组织访问，但不得把空结果误判为无权限。
