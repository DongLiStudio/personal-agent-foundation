# 安装契约

## 输入

- Agent 根绝对路径。
- IANA 时区。
- 通用助手项目名。

这些输入不得包含密码、token、App Secret、恢复码或私钥。

飞书、GitHub 和 Obsidian 不属于初始模板渲染输入。GLOBAL 与 Skills 恢复后，安装器再分别询问是否现在连接，默认选项必须是“现在连接”；连接时调用对应 Skill 或官方 CLI 完成授权并回读真实身份或路径，不要求用户预先知道飞书 Profile 名、GitHub 用户名或 Obsidian 目录结构。

## 阶段

1. `audit-template`：验证清单、编码、换行、占位符白名单和链接边界。
2. `plan`：检查输入、目标和渲染结果，只输出计划，不写目标。
3. 用户确认计划。
4. `install`：在目标同级临时 staging 渲染，验证后原子移动到目标。
5. `verify`：从目标重新读取并检查必需文件、占位符残留和编码。
6. Skill 恢复 GLOBAL Skills。
7. Skill 询问并调用对应能力完成飞书、GitHub 和 Obsidian 连接；“现在连接”为默认选项，用户主动选择稍后再配时才保留未配置说明。
8. Skill 完成 GLOBAL Git、知识库连接和 onboarding。

## 目标保护

- 目标不存在时创建并执行首次安装。
- 目标已存在且为空时允许首次安装到该目录。
- 目标已有内容时停止；升级流程未定义前不得合并、覆盖或删除用户文件。
- staging 名称随机且限定在目标父目录；失败时仅清理本次 staging。
- 不递归跟随 symlink、Junction 或其他 reparse point。

## 平台边界

模板渲染使用跨平台文件 API。知识库链接由 Skill 根据宿主系统选择 Windows Junction 或 macOS/Linux symlink，并在创建前单独确认真实目标。
