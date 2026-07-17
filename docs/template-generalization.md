# GLOBAL 通用化映射

模板源自真实 GLOBAL 提交 `efb719a8cf989bbcc2591dc64013194fc3fc7954` 的全部 56 个受管文件。

## 保留

- GLOBAL 的读取路由、项目制规则、安全边界和 Git 协作规则。
- 全部受管自维护 Skill 源稿、脚本、测试、references 和界面元数据。
- Skill 依赖恢复模型、飞书/GitHub 路由框架、个人排程规则和 Obsidian 只读连接规则。

## 通用化

- 原始本机 Agent 根路径前缀统一改为 `{{AGENT_ROOT}}`。
- 真实默认飞书 Profile 改为 `{{DEFAULT_LARK_PROFILE}}`。
- 真实默认 GitHub 账号改为 `{{DEFAULT_GITHUB_ACCOUNT}}`。
- 时区改为 `{{DEFAULT_TIMEZONE}}`。
- 承担通用协作的项目名改为 `{{GENERAL_ASSISTANT_PROJECT}}`。
- 外部知识库真实路径改为 `{{OBSIDIAN_VAULT_PATH}}`。
- `PROJECTS.md` 删除全部真实项目，等待首次项目教程登记。
- 飞书和 GitHub 文件删除真实组织、App ID、多账号用途与账号清单，只保留安装期默认入口和扩展规则。
- 稳定的个人排程值改为最小初始配置和待确认项。

## 排除

- GLOBAL 自身 `.git/`。
- `obsidian-resource` Junction 及其目标内容。
- 凭据、token、日志、缓存和运行时状态。
- 私人项目、公司、账号、人员、业务描述和历史流水。

## 完整性要求

模板受管文件数应继续为 56；有意新增或删除 GLOBAL 模块时，必须同时更新 `template-manifest.json`、本文件和测试。不能为了通过脱敏扫描静默漏掉源文件。
