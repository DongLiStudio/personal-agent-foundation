# 宿主恢复

## 宿主 Skill 目录

优先使用宿主提供的 Skill 管理或安装接口。只有宿主没有接口时，才通过设置、环境变量和官方文档发现用户级 Skill 目录。发现结果必须展示给用户确认，不能仅按当前用户名拼接路径。

可能存在多个受管目录，例如不同 Agent 各自的用户级 Skill 目录。逐一作为 `--skill-target` 传入，并分别验证。不要用 symlink 共享不同宿主的安装副本。

## 图形交互

宿主支持目录选择、授权卡片、浏览器登录或安装进度界面时优先使用。图形界面只是交互层，计划哈希、写入门禁、备份和验证仍由恢复脚本负责。

## 换 Agent

更换 Agent 宿主时重点检查：

1. 新宿主是否能直接读取随基座携带的本 Skill。
2. 新宿主的用户级 Skill 目录及重载方式。
3. 全局个性化提示词入口。
4. 项目目录打开/绑定方式。
5. 宿主是否支持所需插件、工具调用和长期任务；不支持的能力如实列为平台差异。

不要为了追求逐字节一致而覆盖宿主专属设置。验收目标是治理、数据、Skill 和使用能力等价。

## 授权恢复

凭据不随基座复制。新电脑应使用官方登录或 OAuth 流程重新授权：

- GitHub：以 `gh auth status` 和 `gh api user` 回读为准。
- 飞书：逐个 GLOBAL Profile 使用当前 CLI 支持的 `auth status --verify --json --profile <Profile>` 显式验证用户身份；业务 API 仍按 Profile 规则显式使用用户身份。缺失 Profile 时恢复应用配置或重新建立授权，不复制明文 secret。
- 阿里云与云效：安装并验证 `aliyun` 与 `aliyun-cli-devops`；通用阿里云账号按 `ALIYUN_PROFILES.md` 逐个恢复 Profile，云效按逻辑身份重新输入 PAT 并回读目标组织。PAT 与 AK/SK 不随基座复制，不写入报告或命令行。
- 本机微信只读分析：从 GLOBAL 同步 `wechat-readonly-analyst` 后，在用户级安装副本运行其离线安装和 DPAPI 自检；按 `WECHAT_PROFILES.md` 逐个重新发现、绑定并执行一次性取钥，验证 `offline_key_available=true`。旧宿主 DPAPI 槽、数据库路径、wxid、密钥和聊天内容均不迁移；新宿主绑定后重新建立持续只读授权。
- Obsidian：先确认 Vault 位置和边界，再重建稳定链接。Windows 只接受 1.12.7+ 安装器随附并经设置注册的 `Obsidian.com` CLI 重定向器，不把 `Obsidian.exe` 的存在视为 CLI 可用。
- 服务器：从 `SERVER_PROFILES.md` 恢复非敏感路由，默认接入 Bitwarden 桌面 SSH Agent；不导出私钥到本机目录。连接前核验 Agent 通道、目标公开指纹和可信主机指纹，再以明确 Profile 做新的 Agent 认证及目标服务只读回读。文件身份例外须再次确认风险和范围；不自动接受变化的主机密钥或回退到密码。

授权完成只说明外部身份恢复；仍需运行最终 `verify` 和宿主 Skill 可发现性检查。
