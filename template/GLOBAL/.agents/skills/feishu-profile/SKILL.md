---
name: feishu-profile
description: 管理飞书/Lark CLI 的多 Profile 与用户授权生命周期。用于用户要求连接、添加、登录、授权、重新授权、检查、切换、重命名、删除或迁移飞书账号/Profile，换电脑或 CLI 工作区后恢复身份，飞书操作因 Profile 缺失、token 失效、授权撤销、身份不明、应用失效或配置冲突而中断，以及需要判断账号规则应放入 GLOBAL 还是具体项目时。负责生成一键创建应用链接、OAuth 链接和二维码，维护项目局部身份路由规则，但不保存任何密钥或动态令牌。
---

# 飞书账号与 Profile 管理

## 核心边界

- 新增 Profile 必须是追加操作。不得覆盖、更新、替换、重命名或删除任何已有 Profile，也不得改变新增前的 active Profile；目标名称已存在或 CLI 可能采用 update 语义时立即停止并核验。
- 执行任何飞书 CLI 操作前先确认 `lark-cli` 可用：优先使用当前 shell 的命令发现机制，例如 `Get-Command lark-cli`；Windows 下如命令不在 PATH，可按当前 npm 全局前缀或 `%APPDATA%\npm` 等用户级 shim 机制定位 `lark-cli.cmd`/`lark-cli.ps1`，不要硬编码单一用户名路径。仍不可用时先恢复或安装 CLI，再继续 Profile 操作。
- 以 `lark-cli profile list`、`auth status --verify`、`whoami` 和当前命令 `--help` 为实时事实；文档只保存稳定规则。
- 全局 Skill 维护方法，项目文件维护主体与资源路由事实，CLI/系统密钥链维护凭据和动态认证状态。
- 不在 Skill、GLOBAL、项目、Git、聊天或普通命令参数中保存 App Secret、access token、refresh token、device code、临时认证链接或认证缓存。
- 不维护复制 CLI 状态的 Profile 动态注册表，不硬编码历史用户 `open_id`。
- 不因 user 授权失败静默回退 bot，不借用其他主体的 Profile，不通过修改全局 active Profile 规避项目规则。
- 当前 workspace 的 `profile list` 只证明该 workspace 的可见状态，不证明企业应用或其他 workspace 中的 Profile 不存在。只要 GLOBAL、项目路由或其他已核验 workspace 留有同一应用证据，就按恢复处理，禁止据此运行 `config init --new`。

## 解析目标身份

按以下优先级解析，低优先级不得覆盖高优先级：

1. 用户当前请求明确指定的公司、租户、账号或 Profile。
2. 当前项目中与目标主体或资源直接匹配的条件化路由。
3. 当前项目 `AGENTS.md` 明确指定的项目默认 Profile。
4. `GLOBAL/LARK_PROFILES.md` 记录的全局默认 Profile。

工作区绑定和 CLI active Profile 是运行状态，不是业务身份决策来源；它们只能用于核验和发现配置冲突，不得覆盖以上治理规则。项目未声明默认 Profile 时继承 GLOBAL 默认，并在后续命令中显式传入该 Profile。只有 GLOBAL 明确规定“跟随 CLI active”时，才可把 active 状态作为选择结果。

“当前一句话未提账号”不等于项目和 GLOBAL 未指定账号。目标主体不明、多个规则同级冲突或资源归属可疑时，在读取敏感数据或写入前询问用户。

## 状态检查与动作矩阵

每次新增、恢复、迁移、重命名或删除前，先读取对应 reference，再执行：

| 实时状态 | 动作 |
|---|---|
| Profile 存在，user 已验证 | 显式固定 `--profile <name> --as user`，执行前后回读身份 |
| Profile 存在，短期 token 可刷新 | 让 CLI 正常刷新，再运行 `auth status --verify` |
| Profile 存在，但 user 未登录、授权撤销或刷新失败 | 发起 OAuth split-flow，展示链接和 PNG 二维码 |
| 当前 workspace 不可见，但 GLOBAL、项目路由或其他 workspace 有原应用/Profile 证据 | 读取 [references/recovery-and-migration.md](references/recovery-and-migration.md)，隔离当前进程冲突并恢复原应用；不得新建 |
| 已核验不存在既有应用/Profile，且用户明确需要新应用 | 读取 [references/onboarding.md](references/onboarding.md)，创建具名 Profile |
| 换机、重装或 workspace 中无 Profile | 读取 [references/recovery-and-migration.md](references/recovery-and-migration.md) |
| 全局/项目放置不明 | 读取 [references/project-routing.md](references/project-routing.md) |
| 重命名或删除 | 读取 [references/rename-and-remove.md](references/rename-and-remove.md) |
| CLI 参数或行为可能随版本变化 | 先运行相应命令 `--help`，不凭记忆拼接参数 |

新增时按 [references/onboarding.md](references/onboarding.md) 完成新增前后清单比较；任一原有 Profile 发生变化都不得报告成功，并停止后续授权与业务操作。

## OAuth split-flow

当用户已经要求执行飞书操作，而唯一阻塞是对应 Profile 缺少或失去 user 授权时，可直接发起认证，无需让用户理解底层凭据：

1. 使用明确 Profile 运行 `auth login --no-wait --json`，只请求当前任务所需 domain/scope。
2. 将返回的 `verification_url` 视为不可修改字符串。
3. 立即用 `auth qrcode` 生成 PNG，并按“链接在前、二维码在后”的顺序展示。
4. 告知用户完成后回来确认；本轮不阻塞轮询。
5. 用户确认后，在后续轮次用当次 `device_code` 完成授权。
6. 运行 `auth status --verify` 和 `whoami`；核验 Profile、user、姓名、应用和所需 scopes。
7. device code、链接和二维码只用于当次流程，不写入项目或 Git；过期后重新发起，不复用。

## 配置冲突

若运行环境注入的临时配置、Agent workspace 绑定、环境变量或 CLI active 值覆盖项目或 GLOBAL 已解析的 Profile/身份，将其视为身份配置冲突。仅在当前命令进程中隔离冲突来源，再显式指定已解析的 Profile 和 `--as user`；不修改其他主体的全局配置、workspace binding 或 active Profile。

## 项目规则维护

项目局部身份是规则和非敏感事实，不是局部 Skill。由本 Skill 按 [references/project-routing.md](references/project-routing.md) 创建、更新、迁移或删除：

- `AGENTS.md` 只保存项目默认 Profile、身份类型和不可跨主体边界。
- `docs/feishu/` 或 `docs/clients/<客户>/飞书资源路由.md` 保存条件化客户身份和非敏感资源定位。
- 项目已有业务 Skill 只保留其业务触发与身份覆盖，不复制 Profile 生命周期流程。

修改项目规则时只改当前授权范围内的项目；不因 Profile 重命名自动跨项目批量改写。完成后检查 diff、敏感信息和引用一致性。

## 写后验证

- 新增/恢复：回读 Profile 名、应用、user 身份、当前用户和 token/scopes 状态。
- 项目操作：写前写后均回读实际 Profile；不符合路由时不得报告成功。
- 重命名/删除：回读 Profile 列表，并报告仍需人工处理的项目引用或飞书后台应用。
- 所有成功判断以 CLI 明确成功结构和回读为准，不以“命令未报错”代替验证。
