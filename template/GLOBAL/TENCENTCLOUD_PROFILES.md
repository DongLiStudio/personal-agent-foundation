# 腾讯云 CLI / 账号 Profile 对应关系

本文件只记录由 GLOBAL 统一维护的腾讯云非敏感账号身份路由。官方执行层为 Tencent Cloud CLI（TCCLI）；凭据只保存在宿主的 TCCLI 凭据目录或腾讯云授权体系中，不进入本文件。

## 使用规则

- 身份新增、浏览器授权、SSO 登录、验证、切换、迁移和删除统一使用全局 `tencentcloud-profile` Skill。
- 每次调用显式使用 `--profile` 和目标 `--region`；不得把 CLI 默认 Profile、环境变量或当前浏览器登录态当作业务路由依据。
- 优先使用浏览器授权、SSO 或角色临时身份；长期 SecretId/SecretKey 仅在必要时使用，并采用最小权限子账号。
- 本文件不维护云资源清单，也不维护账号到服务器的静态绑定；资源范围在操作时通过项目上下文和腾讯云 API 实时解析、回读。
- 本文件登记身份只提供路由，不扩大项目操作授权。
- 不记录 SecretId、SecretKey、Token、授权码、Cookie、凭据文件正文或恢复码。

## 腾讯云账号 Profile

当前未配置。连接时先确定稳定的逻辑 Profile 名称，再执行浏览器授权、SSO 或角色授权，并用 STS 回读真实主体。不得由 Agent 编造账号主体或默认 Profile。

## 恢复与迁移

- 重新安装官方 TCCLI，执行 `tccli --version`。
- 按本表逻辑 Profile 重新授权，不复制旧宿主的凭据文件。
- 用 STS 身份回读恢复账号映射；资源归属和权限通过最小只读 API 实时验证。
- SSH 路由独立按 `SERVER_PROFILES.md` 恢复；云 API 身份成功不替代 SSH 指纹和主机身份验证。
