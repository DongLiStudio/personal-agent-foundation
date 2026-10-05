# Skill Dependencies

本文件只记录迁移或重装环境时需要主动恢复的 Skill 依赖。

默认预装 Skill、系统 Skill、插件自动附带的 Skill、插件缓存 Skill、运行时缓存和临时目录不记录在这里。

## 记录原则

需要记录：

- 用户自己维护、并需要跨项目全局使用的 Skill。
- 用户主动从外部来源安装的 Skill。
- 依赖某个外部仓库、插件或手动步骤才能恢复的 Skill。
- 对长期工作流有稳定影响，换电脑时必须主动恢复的 Skill。

不需要记录：

- 默认预装 Skill。
- 系统 Skill。
- 插件随安装自动提供的 Skill。
- 插件缓存路径中的 Skill。
- 项目专属 Skill。
- 当前会话或运行时临时产物。

## GLOBAL 自维护 Skill

### `server-profile`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\server-profile`
- 恢复方式：从 GLOBAL 源稿同步到当前 Agent 可发现的全局 Skill 位置。
- 运行依赖：OpenSSH 客户端、Bitwarden 桌面端及 SSH Agent；先验证 `ssh -V`、Agent 公开指纹和平台 socket/通道，再独立连接。人工密钥默认在 Bitwarden 生成和保管，不导出到本机磁盘；Python 3 仅在具体核验脚本需要时使用。
- 用途：服务器首次 SSH 接入、连接诊断、密钥轮换与全局服务器登记；不执行业务部署或重启。
- 会话约定：同一任务的连续操作复用一个 SSH 会话并及时退出；首次身份验收独立连接，签名仍始终提示，进程名称不是可信身份凭据。

### `restore-agent-foundation`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\restore-agent-foundation`
- 恢复方式：换机或宿主 Skill 安装副本不可用时，直接让当前 Agent 读取上述源稿中的 `SKILL.md`；该 Skill 使用自身脚本恢复包括自己在内的全部安装副本，不依赖其他 Skill 先可用。
- 用途：对已经存在、整体复制、迁移过、局部损坏或更换宿主的 Personal Agent Foundation 进行统一发现、路径校准、链接重建、Skill 恢复、GitHub/飞书/Obsidian/阿里云/云效/服务器权限与连接引导、自检修复和最终验收；服务器恢复只处理非敏感 Profile、SSH 运行时和授权门禁，不自动执行远程变更。

### `update-agent-foundation`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\update-agent-foundation`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置；更新时也随公开产品模板进入 `GLOBAL/.agents/skills/`，因此不依赖旧宿主安装副本先可用。
- 运行依赖：Python 3.11+、Git，以及可读取的可信 Personal Agent Foundation 产品源；执行前先核验产品模板审计和实际 source commit。
- 用途：在保留项目、账号/Profile、Obsidian、服务器、排程和个人规则的前提下，检查上游新版、生成计划、备份并更新受管 Skills/新增公共文件，列出治理语义合并项，并提供验证与安全回滚。

### `init-agent-project`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\init-agent-project`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 用途：初始化项目制 Agent 工作区，创建标准项目结构，登记 `GLOBAL/PROJECTS.md`，初始化本地 Git，并把 GitHub 专属/默认账号路由、远程仓库授权边界写入项目规则；项目内部 Skill/agent 内容遵循 `.agents` 机制。

### `record-skill-dependency`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\record-skill-dependency`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 用途：在新增自维护全局 Skill 或主动安装外部 Skill 后，维护 `GLOBAL/SKILL_DEPENDENCIES.md`。

### `github-cli`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\github-cli`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 用途：指导 Agent 安全使用 GitHub CLI (`gh`)，统一账号生命周期、全局默认/项目专属路由、remote 与首次 push 边界，并处理仓库、Issue、PR、Actions、Release、API 和 GitHub CLI Skill 检索。

### `visual-iteration-workflow`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\visual-iteration-workflow`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 用途：在页面设计迭代、点选修改和局部视觉调整时，提醒 Agent 优先考虑 Impeccable Live Mode，并按安全流程完成启动、接受变体和清理收尾。

### `feishu-task`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\feishu-task`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 用途：跨项目解析飞书账号、人员角色、时间、任务详情和附件，安全完成附件局部脱敏、任务去重、创建、更新与回读；项目未指定账号时使用 GLOBAL 记录的全局默认 Profile。

### `feishu-exam-builder`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\feishu-exam-builder`
- 恢复方式：从 GLOBAL 源稿同步到当前 Agent 可发现的全局 Skill 位置；具体考试的身份、资源路由与阅卷 Skill 留在对应项目，不复制到 GLOBAL。
- 运行依赖：Python 3.11+（纯标准库离线校验）；已授权的 `lark-cli` 与当前 `lark-shared`、`lark-base`、`lark-wiki`、`lark-doc`、`lark-drive`、`lark-im` Skills；缺失 Profile 由 `feishu-profile` 恢复。表单分页等未获官方 API 支持的配置还需可核验身份的浏览器/UI 能力，缺失时明确人工配置门禁。最小只读验证：`python scripts/exam_guard.py --help`、`python -m unittest discover -s scripts -p "test_*.py"`、`lark-cli --version` 及按明确 Profile 执行 `auth whoami`；不创建测试考试。
- 用途：引导确认考试需求与精确归档位置，完整创建试卷/评分表、分页答题表单、考场群权限、实操阅卷 Skill，独立校验并交付使用教学。

### `feishu-profile`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\feishu-profile`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 用途：统一管理飞书 CLI 多 Profile 的新增、一键创建应用、用户授权、失效恢复、换机迁移、项目局部路由、重命名与安全删除。

### `mail-profile`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\mail-profile`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置；邮箱 OAuth 与本机安全凭据需按 `MAIL_PROFILES.md` 重新授权，不迁移密码、客户端授权码、token或密文。
- 运行依赖：飞书邮箱依赖当前 `lark-mail`；Gmail 等邮箱依赖对应 OAuth 连接器；163、QQ、Outlook等通用邮箱依赖 Python 3、IMAP SSL 和服务商开启的客户端授权。最小只读验证为运行 `scripts/imap_readonly.py --help`，实际账号验证仅执行 `probe` 或窄范围 `search`。
- 用途：统一管理跨项目、多公司和个人邮箱的逻辑 Profile、授权恢复、身份隔离与只读发票/账单附件检索。

### `aliyun-profile`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\aliyun-profile`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 运行依赖：阿里云 CLI 与官方云效插件 `aliyun-cli-devops`；Windows 长期 PAT 槽依赖系统 DPAPI CurrentUser。恢复后先执行 `aliyun version`、`aliyun plugin list`、`aliyun devops version`，再按 `ALIYUN_PROFILES.md` 使用 `scripts/yunxiao-credential-slot.ps1 -Action connect` 隐藏输入并重新授权。DPAPI 密文不随 GLOBAL 或整套基座迁移。
- 用途：统一管理阿里云 CLI 多 Profile、云效组织逻辑身份、插件安装、授权恢复、项目路由和安全删除；具体业务流程由对应的全局业务 Skill 或项目 Skill 承担。

### `wechat-readonly-analyst`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\wechat-readonly-analyst`
- 恢复方式：从 GLOBAL 源稿同步到当前 Agent 可发现的用户级 Skill 位置，再在安装副本执行 `scripts/install.ps1`；安装器只使用 Skill 自带、逐包 SHA-256 锁定的 Windows wheelhouse，不联网安装依赖。
- 运行依赖：Windows 11 x64、Python 3.12 x64、当前 Windows 用户的 DPAPI CurrentUser；首次取钥或密钥刷新时还需要已登录且版本兼容的微信桌面客户端。恢复后执行 `scripts/profile_manager.py self-test`，再按 `WECHAT_PROFILES.md` 逐个 `discover`、`connect` 和一次性取钥。本机 DPAPI 槽、数据库路径、wxid、密钥与聊天内容均不随 GLOBAL 或基座迁移。
- 用途：统一管理多个本机微信数据身份的非敏感逻辑 Profile；用户绑定 Profile 后授予持续只读权限，首次取钥与确定必要的刷新可在账号/数据库匹配门禁内自动完成，不再逐次询问。校验后的密钥目录由 DPAPI 加密保存，日常查询无需微信在线或重复扫描内存；错误日期等普通输入问题不误判为密钥失效。支持按用户指定范围查询、搜索、统计和总结本机可用数据，不设置隐私条数上限；不发送或修改消息，不输出密钥或原始数据库。

### `tencentcloud-profile`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\tencentcloud-profile`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 运行依赖：官方 Tencent Cloud CLI（TCCLI）与 Python/Pip；恢复后执行 `tccli --version`，再按 `TENCENTCLOUD_PROFILES.md` 重新走浏览器授权、SSO 或角色授权，并用 `tccli sts GetCallerIdentity --profile <name>` 做最小只读身份验证。`~/.tccli/*.credential` 不随 GLOBAL 或整套基座迁移。
- 用途：统一管理腾讯云 TCCLI 安装、浏览器授权/SSO、多 Profile 生命周期、真实主体验证及账号的非敏感 GLOBAL 身份路由；具体云资源操作仍由对应项目负责。

### `yunxiao-mr-review`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\yunxiao-mr-review`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 运行依赖：全局 `aliyun-profile`、阿里云 CLI 与官方云效插件 `aliyun-cli-devops`；实际逻辑 Profile、组织和仓库业务路由由目标项目规则或薄覆盖层提供。
- 用途：跨项目执行云效 Codeup 合并请求的证据化审查，发现问题时发布精确行内评论，证据完整且无问题时通过评审，但不自动合并或部署。

### `align-agent-projects-with-global`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\align-agent-projects-with-global`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 用途：在 GLOBAL 发生影响项目的规则或路径更新后，审计、计划并在授权后逐项目对齐所有已登记 Agent 项目；也作为 `migrate-agent-root` 的项目对齐门禁。

### `migrate-agent-root`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\migrate-agent-root`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 用途：安全规划、执行和验证完整 Agent 根目录迁移，负责 GLOBAL 路径重写、链接重建、Skill 安装副本比对，并消费 `align-agent-projects-with-global` 的项目对齐门禁结果。

### `personal-schedule-planner`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\personal-schedule-planner`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 运行依赖：全局 `feishu-profile`、当前 `lark-cli` 内嵌的 `lark-shared`、`lark-task` 与 `lark-calendar`，以及外部 `json-canvas`、`obsidian-cli`；仪表盘实际关联 `.base` 时还需要 `obsidian-bases`。各依赖按本清单对应条目恢复并执行最小只读验证。
- 用途：汇总所有 GLOBAL 飞书 Profile 的任务与日历、Obsidian 仪表盘和已登记项目进度，协商个人时间安排，并在用户确认后幂等同步到全部 Profile 日历。

### `decide-next-action`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\decide-next-action`
- 恢复方式：从 GLOBAL 源稿安装或同步到当前 Agent 可发现的全局 Skill 位置。
- 运行依赖：全局 `feishu-profile`、当前 `lark-cli` 内嵌的 `lark-task` 与 `lark-calendar`，以及外部 `json-canvas`、`obsidian-cli`；仪表盘实际关联 `.base` 时还需要 `obsidian-bases`。各依赖按本清单对应条目恢复并执行最小只读验证。
- 用途：只读汇总全部治理层飞书任务与近期日历、Obsidian 仪表盘和活跃项目状态，推荐当前最值得立即执行的一个下一步，并在需要时转交任务维护或完整排程 Skill。


### `allinssl-certificate-automation`

- 源稿：`{{AGENT_ROOT}}\GLOBAL\.agents\skills\allinssl-certificate-automation`
- 恢复方式：从 GLOBAL 源稿同步到当前 Agent 可发现的全局 Skill 位置；API Key、DNS/SSH/通知凭据通过独立安全渠道恢复，不随 Skill 或 Git 迁移。
- 运行依赖：可读取的 GLOBAL 服务器 Profile，以及经核验可复用的 ALLinSSL 实例及对应版本 API；没有合适实例时，须由用户确认长期宿主并授权部署后再建立接入。还需 HTTPS/SSH 客户端；使用 Python API 适配时需 Python 3。按目标需要恢复 server-profile、tencentcloud-profile 或 aliyun-profile，并准备实际 TLS 入口（Nginx 或其他适配器）。最小只读验证：ssh -V、python --version，以及经安全注入认证的 ALLinSSL 只读列表调用；不输出配置正文。
- 用途：编排证书接入、授权补齐、DNS 验证、申请/自动续期、SSH/TLS 部署、双来源失败通知、每域名双来源监控及验收与迁移恢复。

## 主动安装的外部 Skill

### `json-canvas`

- 来源：`kepano/obsidian-skills` 仓库 `skills/json-canvas`；本次核验并安装提交 `a1dc48e68138490d522c04cbf5822214c6eb1202`：https://github.com/kepano/obsidian-skills/tree/a1dc48e68138490d522c04cbf5822214c6eb1202/skills/json-canvas
- 恢复方式：使用当前 Agent 的标准 Skill 安装器，从上述仓库与固定提交选择性安装 `skills/json-canvas` 到全局 Skill 位置。
- 用途：让 Agent 解析和处理 JSON Canvas (`.canvas`) 的节点、连线、分组与文件引用；在本 GLOBAL 下默认遵守 Obsidian 只读边界。

### `obsidian-bases`

- 来源：`kepano/obsidian-skills` 仓库 `skills/obsidian-bases`；本次核验并安装提交 `a1dc48e68138490d522c04cbf5822214c6eb1202`：https://github.com/kepano/obsidian-skills/tree/a1dc48e68138490d522c04cbf5822214c6eb1202/skills/obsidian-bases
- 恢复方式：使用当前 Agent 的标准 Skill 安装器，从上述仓库与固定提交选择性安装 `skills/obsidian-bases` 到全局 Skill 位置。
- 用途：让 Agent 理解和处理 Obsidian Bases (`.base`) 的视图、筛选、公式与汇总；在本 GLOBAL 下默认遵守 Obsidian 只读边界。

### `obsidian-cli`

- 来源：`kepano/obsidian-skills` 仓库 `skills/obsidian-cli`；本次核验并安装提交 `a1dc48e68138490d522c04cbf5822214c6eb1202`：https://github.com/kepano/obsidian-skills/tree/a1dc48e68138490d522c04cbf5822214c6eb1202/skills/obsidian-cli
- 恢复方式：使用当前 Agent 的标准 Skill 安装器，从上述仓库与固定提交选择性安装 `skills/obsidian-cli`；安装或升级 Obsidian 1.12.7+ 桌面安装器，在“设置 → 通用”中启用并注册命令行界面，然后验证 `obsidian version`、`obsidian help` 以及对目标 Vault `仪表盘.canvas` 的只读访问。
- 运行依赖：官方 Obsidian CLI 与桌面应用；执行 CLI 时 Obsidian 需要运行。CLI 只作为增强能力，自动化流程仍应保留直接读取开放文件格式的只读回退。
- 用途：让 Agent 通过官方 CLI 对指定 Vault 执行只读搜索、文件读取、链接解析和任务查询；未经明确授权不使用创建、追加、移动、删除或属性写入命令。

### `lark-*` 飞书 CLI Skills

- 来源：飞书 CLI 官方安装指南：https://open.feishu.cn/document/no_class/mcp-archive/feishu-cli-installation-guide.md
- 恢复方式：按官方安装指南重新安装；Skill 安装命令保持官方形式 `npx -y skills add https://open.feishu.cn --skill -y`。
- 用途：让 Agent 使用飞书/Lark 文档、云盘、IM、日历、多维表格、邮件、妙记等 CLI Skill 能力。

### `ui-ux-pro-max`

- 来源：GitHub/NPM 外部 Skill；GitHub 仓库：https://github.com/nextlevelbuilder/ui-ux-pro-max-skill；NPM 包：`ui-ux-pro-max-cli`；安装命令 `npm install -g ui-ux-pro-max-cli@latest` 后执行 `uipro init --ai codex --global`。
- 恢复方式：重新安装 `ui-ux-pro-max-cli`，再执行 `uipro init --ai codex --global`。
- 用途：为 Agent 提供 UI/UX 设计推理、风格/配色/字体/图表/技术栈规则和设计系统生成能力。

### `impeccable`

- 来源：Impeccable 官方外部 Skill；官网：https://impeccable.cn/；GitHub 仓库：https://github.com/pbakaus/impeccable；安装命令 `npx impeccable skills install`，安装时选择 `Global (~)`。
- 恢复方式：重新执行 `npx impeccable skills install` 并选择 `Global (~)`；更新使用 `npx impeccable skills update`。
- 用途：为 Agent 提供前端 UI/UX 设计、评审、打磨、去 AI slop、设计系统文档和 Live Mode 迭代能力。

## 维护规则

- 新增个人全局 Skill 后，同步补充 `GLOBAL 自维护 Skill`。
- 主动安装外部 Skill 后，同步补充 `主动安装的外部 Skill`。
- 如果某个 Skill 后续变成默认预装或由插件自动恢复，可从本文件移除。
- 本文件只记录恢复线索，不复制外部 Skill 内容。
