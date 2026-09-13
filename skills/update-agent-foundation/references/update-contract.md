# Personal Agent Foundation 更新契约

## 来源

- 默认上游为 `DongLiStudio/personal-agent-foundation`。
- 使用 tag 时记录 tag 与解析后的 commit；使用分支时记录实际 commit，不能只写 `main`。
- 本地产品源必须包含 `template-manifest.json` 和 `template/GLOBAL/`，并先通过产品模板审计。
- 源目录、模板目录或任一模板文件是 symlink/reparse point 时停止。

## 文件分类

### 用户状态：只保留，不替换

`PROJECTS.md`、所有账号/Profile 文件、Obsidian 规则、服务器索引及详情、排程偏好、基座状态文件，以及不属于上游模板的用户文件和 Skill。

### 治理文本：语义合并

现有 `README.md`、`GLOBAL_CONTEXT.md`、`SKILL_DEPENDENCIES.md`、`.gitignore` 等与新版不同时，脚本只报告 `review_merge`。Agent 必须比较新旧规则，保留用户指向性内容，以最小补丁引入新版通用规则，并单独验证。

### 受管程序：计划确认后更新

新版 `GLOBAL/.agents/skills/` 中的文件按相对路径更新。目标中存在但上游不存在的用户 Skill 或文件不删除。内容里的 `{{AGENT_ROOT}}` 只渲染为当前根；仍有其他占位符时阻断该文件写入。

### 新增公共文件

目标不存在的普通文件可以新增，但渲染后仍含占位符、落在用户状态目录、或目标父级经过链接时必须停止并转人工处理。

## 计划与并发保护

- `plan_sha256` 覆盖来源、目标、文件哈希、分类和动作。
- `apply` 前重新核对每个目标的 before hash；计划后变化即停止。
- 写入使用同目录临时文件和原子替换。
- 不自动删除任何文件或目录。

## 备份与回滚

- 备份目录：`GLOBAL/.foundation-update/<run-id>/before/`。
- `run-manifest.json` 记录来源 commit、计划哈希、相对路径、更新前/后哈希及是否原本存在。
- 回滚前必须确认当前文件仍等于更新后哈希；否则拒绝覆盖用户后续修改。
- 新增文件只有在仍等于更新后哈希时才删除；删除范围只能来自 manifest 中的精确文件路径。

## 验证

- 上游受管 Skill 文件渲染后与当前 GLOBAL 一致。
- 应新增的公共文件存在。
- 受管文件为 UTF-8 无 BOM、LF，且没有模板占位符残留。
- 用户状态文件、额外 Skill、项目目录和链接目标未被脚本修改。
- 治理语义合并项逐项记录为已处理或明确待处理。
- 最后再运行 `restore-agent-foundation verify`；更新器验证不能替代宿主恢复验收。
