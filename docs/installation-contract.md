# 安装契约

## 输入

- Agent 根绝对路径。
- 默认飞书 CLI Profile。
- 默认 GitHub 账号。
- IANA 时区。
- 通用助手项目名。
- Obsidian Vault 绝对路径，或明确的“未配置”值。

这些输入不得包含密码、token、App Secret、恢复码或私钥。

## 阶段

1. `audit-template`：验证清单、编码、换行、占位符白名单和链接边界。
2. `plan`：检查输入、目标和渲染结果，只输出计划，不写目标。
3. 用户确认计划。
4. `install`：在目标同级临时 staging 渲染，验证后原子移动到目标。
5. `verify`：从目标重新读取并检查必需文件、占位符残留和编码。
6. Skill 完成 GLOBAL Git、Skill 恢复、账号配置、知识库连接和 onboarding。

## 目标保护

- 目标不存在时才允许首次安装。
- 目标存在时停止；升级流程未定义前不得合并或覆盖。
- staging 名称随机且限定在目标父目录；失败时仅清理本次 staging。
- 不递归跟随 symlink、Junction 或其他 reparse point。

## 平台边界

模板渲染使用跨平台文件 API。知识库链接由 Skill 根据宿主系统选择 Windows Junction 或 macOS/Linux symlink，并在创建前单独确认真实目标。
