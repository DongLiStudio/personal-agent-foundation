# 失效恢复与换机迁移

## 先区分故障层级

先把状态分成四层，不用低层现象替代高层事实：

1. 企业应用：从 GLOBAL、项目路由和飞书后台已确认事实判断应用是否存在。
2. Profile：分别判断目标 Profile 是否存在于任一已知 CLI workspace。
3. workspace 可见性：判断当前 Agent workspace、临时配置、环境变量、操作系统用户或 CLI config 路径是否只暴露了另一套 Profile。
4. user 授权：在应用和 Profile 可见后，再用 `auth status --verify` 与 `whoami` 判断 token、scopes 和实际用户。

当前 workspace 的 `profile list` 不含目标名称时，只能报告“当前 workspace 不可见”。先读取 GLOBAL/项目的非敏感映射，再检查已知 workspace；存在原 App ID、Profile 名或历史核验事实时，按 workspace 可见性冲突恢复，不得宣称应用不存在，也不得发起新应用链接。

## 恢复矩阵

| 故障 | 处理 |
|---|---|
| access token 到期但 refresh 有效 | 让 CLI 自动刷新，随后回读 |
| user 未登录、refresh 失效或授权被撤销 | 对原 Profile 重新发起 OAuth split-flow |
| scopes 不足 | 仅补充当前任务所需 domain/scope 后重新授权 |
| Profile 在另一 CLI workspace | 先确认正确 workspace；不复制明文凭据，不改其他主体绑定 |
| 当前 workspace 仅暴露其他主体，但目标 Profile 在 local/其他已知 workspace 可用 | 仅在当前命令进程隔离冲突来源，显式使用目标 Profile；不改变全局 binding/active，不新建应用 |
| 新电脑无 Profile，允许新建应用 | 对明确租户执行具名一键新建流程 |
| 新电脑需沿用原应用 | 优先使用具名 `config init` 引导模式采用原应用；引导不可用时才由授权管理员通过安全凭据备用流程恢复 |
| 企业应用被停用、删除或失去权限 | 报告应用层问题；由管理员恢复或明确创建新应用 |
| Profile 名存在但主体不符 | 停止，不覆盖；重命名旧 Profile 或为正确主体建立新名称 |

## 换机原则

- Profile 与 user token 是本机/当前 CLI workspace 状态，不假设随 Git、项目目录或云端自动迁移。
- 项目只需携带 `AGENTS.md` 和资源路由事实；它们用于告诉新机器应该恢复哪个逻辑 Profile。
- 默认不复制整个 CLI 配置目录或系统密钥链文件，避免泄密、路径不兼容和主体混淆。
- 用户可选择“创建新企业应用”或“复用既有应用”。复用时优先采用官方引导模式；不要为了省一步未经确认创建重复应用，也不要为了复用覆盖已有 Profile。
- 恢复后逐个项目验证默认及例外 Profile，不把某个项目的客户身份提升为全局默认。

## 自动发链接边界

用户已经要求执行飞书操作，且项目规则唯一确定目标 Profile 时，发现 user 授权缺失或失效即可自动发起 OAuth 链接。

只有在 GLOBAL、项目路由、当前及其他已知 workspace 均无既有应用/Profile 证据，且用户明确接受创建新应用时，才能发起一键创建链接。当前 workspace 不可见、非终端引导失败或当前绑定指向其他主体，都不能单独触发 `--new`。

主体不明、候选不唯一、需要新建第二个同租户应用、需要复用既有秘密或会改变全局默认时，先询问用户。
