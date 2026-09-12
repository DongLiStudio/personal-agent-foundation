---
name: aliyun-profile
description: 管理阿里云 CLI 多 Profile 与云效组织授权上下文。用于安装或恢复 aliyun CLI/云效插件，新增、登录、验证、切换、迁移或删除阿里云账号 Profile，管理云效 PAT 的安全注入与组织路由，以及判断账号信息应进入 GLOBAL 还是项目；不执行具体项目的仓库创建、流水线配置或 MR 审查。
---

# 阿里云与云效账号管理

本 Skill 只管理跨项目身份、连接和授权生命周期。具体云效业务流程由项目 Skill 负责。

## 先理解两套认证

- 阿里云通用 OpenAPI 使用 `aliyun configure` 的多 Profile，可选 AK、CloudSSO、OAuth、RAM Role 等认证方式。
- 云效 `aliyun devops` 数据面不读取上述 AK/SK Profile，而使用 PAT；中心版还需要组织 ID，Region 版需要 API Base URL。
- 对用户提供统一的“逻辑 Profile”体验，但不得把两套底层认证混为一谈或从一种身份推导另一种身份。

## 固定边界

- 按需读取 `{{AGENT_ROOT}}\GLOBAL\ALIYUN_PROFILES.md`，再读取项目 `AGENTS.md` 的覆盖规则。优先级为：用户当前明确主体 → 项目规则 → GLOBAL 默认；同级冲突时先确认。
- `ALIYUN_PROFILES.md` 只记录非敏感映射。AK/SK、STS、PAT、OAuth/SSO 票据和恢复码不得写入 GLOBAL、项目、日志、命令参数或报告。
- 云效 PAT 优先由宿主安全凭据库或隐藏输入进入当前进程环境；仅为单次命令设置 `ALIBABA_CLOUD_YUNXIAO_*`，结束后清理。不得把 PAT 持久化到仓库、PowerShell profile、shell rc、普通环境变量或明文配置。
- Windows 宿主需要长期复用 PAT 时，使用 `scripts/yunxiao-credential-slot.ps1` 建立 DPAPI CurrentUser 凭据槽。脚本必须先只读验证用户与组织，再加密落盘；调用时只把 PAT 注入当前目标进程，结束后清理。不得复制凭据槽文件到其他电脑或用户。
- 修改凭据槽脚本后，必须同时用 Windows PowerShell 5.1 (`powershell.exe`) 与当前 PowerShell (`pwsh`) 执行 `-Action self-test`；不得只在较新的 .NET 运行时验证。
- 交互式连接优先从 `powershell.exe -NoProfile` 的干净子进程启动，减少 Conda 或用户 Profile 对运行时、编码和模块搜索路径的干扰。凭据实现直接调用 Windows DPAPI，不依赖 `Microsoft.PowerShell.Security` 模块；现有 Agent 进程直接调用脚本时，先完成 `self-test`。
- 不依赖 CLI 当前激活 Profile 或残留环境变量判断业务身份。每次操作都显式解析逻辑 Profile，并在写前只读验证。
- 删除 Profile、撤销 PAT、改变默认身份或安装系统软件会影响后续工作，执行前说明影响并取得明确授权。

## 工作流

1. 读取 [身份与授权路由](references/identity-and-auth.md)。发现 `aliyun`；缺失时使用阿里云官方安装方式。执行 `aliyun version`。
2. 云效任务额外执行 `aliyun plugin install --names aliyun-cli-devops`（安装/升级需授权），再用 `aliyun devops version` 与 `aliyun devops --help` 验证插件。
3. 对阿里云通用账号：回读 `aliyun configure list`，选择最小风险的官方认证方式；优先短期/联合身份（CloudSSO、OAuth、RAM Role），只在确有必要时使用长期 AK。
4. 对云效：从 GLOBAL 与项目规则解析中心版/Region版、组织 ID/API Base URL和逻辑凭据槽；Windows 优先使用 [宿主凭据槽](references/identity-and-auth.md#windows-安全凭据槽)，其他宿主使用隐藏输入仅注入当前进程，再执行最小只读请求验证真实组织访问。
5. 新增或恢复成功后，回读实际身份、组织和权限边界；只把稳定非敏感映射写入 `ALIYUN_PROFILES.md`。项目专属命名空间、仓库、流水线和环境路由写入对应项目。
6. 换机时重新安装 CLI/插件并重新授权，不复制明文凭据。删除或撤销前搜索 GLOBAL 与项目引用，确认替代路由并在操作后复验其他 Profile。

## 转交项目 Skill

身份已验证后立即回到调用方项目 Skill。仓库创建、成员权限、保护分支、流水线、MR 评论/批准/合并和部署都不因本 Skill 的认证成功而自动获得授权。
