---
name: tencentcloud-profile
description: 管理腾讯云官方 TCCLI 的安装、浏览器授权或 SSO 登录、多 Profile 身份路由、验证、迁移和删除，并维护 GLOBAL 的腾讯云账号非敏感身份路由。用于用户要求连接、添加、登录、切换、恢复或核验腾讯云账号/Profile，或腾讯云操作因身份、地域、权限和配置不明确而中断；不执行具体云资源创建、变更、发布或删除。
---

# 腾讯云账号与 Profile 管理

本 Skill 只管理腾讯云身份、CLI 和跨项目路由。CVM、DNS、证书、云防火墙、COS、TCR 等业务操作仍由调用方项目按当前授权执行。

## 固定边界

- 先读取 `{{AGENT_ROOT}}\GLOBAL\TENCENTCLOUD_PROFILES.md`，再读取项目 `AGENTS.md` 的覆盖规则。身份选择优先级为：用户当前明确主体 → 项目规则 → GLOBAL 明确默认；没有唯一结果时不执行写操作。
- 官方执行层使用 Tencent Cloud CLI（TCCLI）：https://cloud.tencent.com/document/product/440 。所有 API 调用显式传入 `--profile <name>` 和必要的 `--region`，不得依赖 `default`、`TCCLI_PROFILE` 或残留的腾讯云环境变量推断业务身份。
- 优先使用 `tccli auth login --profile <name>` 的浏览器授权、集团身份 SSO 或角色临时凭据；仅在确有必要时使用长期 SecretId/SecretKey，并使用最小权限子账号。
- `~/.tccli/*.credential`、临时 Token、SecretId、SecretKey、SSO 票据和授权码不得进入 GLOBAL、项目、Git、日志、命令参数或报告。只允许列出凭据文件名，不读取、复制或输出正文。
- `TENCENTCLOUD_PROFILES.md` 只记录逻辑 Profile、主体/UIN、认证类型、用途、最小只读验证方式和状态；不得维护云资源清单或账号到服务器的静态绑定。
- Profile 验证成功不授予云资源创建、变更、重启、网络开放、DNS 修改、证书签发、释放实例或删除数据的权限。
- 安装/升级 TCCLI、发起登录、删除 Profile、撤销授权或改变默认身份会影响本机状态；仅在用户当前指令已覆盖该动作时执行，否则先说明影响并取得授权。

## 工作流

1. 执行 `tccli --version`；缺失时按官方方式安装，并记录实际版本。Windows 优先从干净的 PowerShell 子进程运行 Python/Pip，避免用户环境污染。
2. 只列出 `~/.tccli` 下的文件名，结合 GLOBAL 和项目规则解析目标逻辑 Profile；不得读取 `.credential` 内容。
3. 新增普通腾讯云账号时，优先运行 `tccli auth login --profile <name>`；集团账号优先评估 `tccli sso login ... --profile <name>`；运行在已授权 CVM 内部时可评估 `--use-cvm-role`。
4. 登录后执行 `tccli sts GetCallerIdentity --profile <name>` 回读真实 UIN、主体和账号归属；具体资源在调用时通过目标服务的最小只读接口实时解析。例如 CVM 使用 `DescribeInstances`，并把查询限定为项目或服务器详情提供的目标。
5. 仅把经回读确认的账号身份事实写入 `TENCENTCLOUD_PROFILES.md`。不要缓存云资源列表或建立账号到服务器的反向绑定。服务器自身的稳定标识、SSH、主机指纹、服务目录和端口继续由 `SERVER_PROFILES.md` 与对应详情维护；项目资源只在确有长期路由需要时写入所属项目。
6. 每次写操作前重新核验 Profile、调用主体、地域、目标资源 ID 和项目授权；请求完成后读取资源状态。批量或高影响操作必须有明确目标清单和恢复方案。
7. 换机时重新安装 TCCLI 并重新授权，不复制 `.credential`。删除或重命名 Profile 前搜索 GLOBAL 与项目引用，确认替代路由；完成后验证其他 Profile 未受影响。

## TCCLI 输出解析与异常校验

- TCCLI 的默认 JSON 输出直接是 API 响应主体，常见字段位于根级；不得未经检查假设存在 `Response` 外层。编写解析逻辑前，先结合当前命令帮助和首次成功的原始响应确认实际字段路径。
- 解析计数、分页游标和资源数组前，必须验证必需字段确实存在；字段缺失应显式失败，不得把 `$null` 强制转换为 `0` 后报告“没有资源”。
- 分页必须使用接口实际返回的总数和数组长度完成，并对去重后的数量做一致性检查。结果为零、与用户提供的控制台证据或已知资源矛盾时，先检查解析路径，并用同一服务的原始响应或独立只读接口交叉验证后再下结论。
- 域名清单的当前字段路径为：域名注册 `TotalCount` / `DomainSet`，DNSPod `DomainCountInfo.AllTotal` / `DomainList`；两类清单需要分别查询并按域名去重，不能把注册数量和 DNS 托管数量混为一谈。

## 常用只读验证

```powershell
tccli --version
tccli sts GetCallerIdentity --profile <profile>
tccli cvm DescribeInstances --profile <profile> --region <region> --InstanceIds '["<instance-id>"]'
```

不要把带密钥的 `tccli configure list/get` 输出复制到报告。需要排查时只报告字段是否存在、Profile 文件名、错误码和脱敏后的身份结果。
