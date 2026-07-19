# 安装契约

## 输入

- Agent 根绝对路径。
- IANA 时区。
- 通用助手项目名。

这些输入不得包含密码、token、App Secret、恢复码或私钥。

飞书、GitHub 和 Obsidian 不属于初始模板渲染输入。GLOBAL 与 Skills 恢复后，安装器再分别询问是否现在连接，默认选项必须是“现在连接”；连接时调用对应 Skill 或官方 CLI 完成授权并回读真实身份或路径，不要求用户预先知道飞书 Profile 名、GitHub 用户名或 Obsidian 目录结构。

Obsidian Vault 真实路径是连接阶段的临时输入，不属于模板占位符，不得长期写入 `GLOBAL/OBSIDIAN_LINK.md`。安装器必须先确认或有界发现用户 Vault 的基础结构、目录理解和优先阅读入口；只创建 `GLOBAL/obsidian-resource` 软连接/Junction 不构成 Obsidian 配置完成。生成的 `OBSIDIAN_LINK.md` 应与产品模板同构，只替换“目录理解”和“优先阅读”中涉及用户个人目录设计的条目。

飞书首次连接的默认行为必须是创建新的飞书应用和新的专用 Profile，不得自动复用本机已有 Profile 或其他应用。安装器可以只读检查已有 Profile 以避免命名冲突，但不得把已有配置作为默认值、预选项或静默回退。复用已有飞书应用/Profile 仅允许作为用户明确选择的高级迁移路径，并且必须先说明会共享原应用权限、身份路由和审计边界。

身份写回必须使用官方回读事实。飞书写入公司列表时，标题和公司名称使用授权后 `whoami` 或等价接口回读到的真实公司/租户名称；CLI profile 名只作为命令参数，不得替代公司名称。GitHub 写入账号列表时，使用 `gh api user` 回读的真实 login/账号名称，不得由程序自拟账号名、组织名或展示名。

## 阶段

1. `audit-template`：验证清单、编码、换行、占位符白名单和链接边界。
2. `plan`：检查输入、目标和渲染结果，只输出计划，不写目标。
3. 用户确认计划。
4. `install`：在目标同级临时 staging 渲染，验证后原子移动到目标。
5. `verify`：从目标重新读取并检查必需文件、占位符残留和编码。
6. Skill 恢复 GLOBAL Skills。
7. Skill 询问并调用对应能力完成飞书、GitHub 和 Obsidian 连接；“现在连接”为默认选项，用户主动选择稍后再配时才保留未配置说明。飞书连接默认新建专用应用/Profile，禁止自动复用已有 Profile。
8. Skill 完成 GLOBAL Git、知识库连接和 onboarding。

## 目标保护

- 目标不存在时创建并执行首次安装。
- 目标已存在且为空时允许首次安装到该目录。
- 目标已有内容时停止；升级流程未定义前不得合并、覆盖或删除用户文件。
- staging 名称随机且限定在目标父目录；失败时仅清理本次 staging。
- 不递归跟随 symlink、Junction 或其他 reparse point。

## 平台边界

模板渲染使用跨平台文件 API。知识库链接由 Skill 根据宿主系统选择 Windows Junction 或 macOS/Linux symlink，并在创建前单独确认真实目标。
