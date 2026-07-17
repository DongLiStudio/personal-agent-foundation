# 全局 Skill 源头

本目录保存个人全局 Skill 的源稿。

这里是用户维护的跨项目 Skill 源头层，不是 Agent 运行时安装目录。

本目录中的内容是可审查、可迁移、可长期维护的源稿；用户级安装目录只是当前机器上的启用副本。

## 收纳范围

适合放在这里的 skill：

- 用户个人维护。
- 可跨多个项目复用。
- 足够稳定，值得版本管理、审查和迁移。

不要放在这里：

- 系统自带 skill。
- 插件提供的 skill。
- 插件缓存文件。
- 项目内部 Agent 自动生成或管理的 Skill/agent 运行内容。
- 运行时安装产物。

项目内部 Skill/agent 内容使用 `.agents/` 机制。本目录只保存个人全局 Skill 源稿。

## 维护流程

新增或修改自维护全局 Skill 时：

1. 优先修改本目录中的 GLOBAL 源稿，不直接把用户级安装副本当作源稿维护。
2. 按当前 Agent 环境适用的 Skill 元数据规范生成或更新 `agents/openai.yaml`，并使用该环境提供的校验能力；没有专用生成器或校验器时，执行本文规定的等价检查。Windows 下只在当前校验进程启用 UTF-8，不修改系统级编码配置。
3. 回读中文元数据、frontmatter 和关键规则，确认没有乱码、替换字符或语义损坏；结构校验通过不能代替内容回读。
4. 将源稿同步到当前 Agent 可发现的全局 Skill 位置，并逐文件比较相对路径与内容哈希，确认安装副本与 GLOBAL 源稿完全一致。
5. 使用全局 `record-skill-dependency` Skill 检查并按需更新 `{{AGENT_ROOT}}\GLOBAL\SKILL_DEPENDENCIES.md`；已有条目且来源、恢复方式和用途未变化时不做无意义改写。
6. 检查 Git diff、编码、敏感信息和临时文件，再创建聚焦、可回退的本地提交；commit 不等于 push。
7. 不把用户级运行时安装路径写成长期规则；恢复方式应描述来源、安装命令或同步方式。

## 展示元数据规范

自维护全局 Skill 应包含 `agents/openai.yaml`，用于 Agent 界面展示；其他 Agent 可按自身元数据规范复用其中的名称、描述和默认提示词。

- `display_name`：统一以 `GLOBAL：` 开头，再使用中文或中英结合的易理解名称，例如 `GLOBAL：GitHub CLI 助手`。该字段只用于界面识别；产品名、CLI 名或英文专有名词可保留英文。
- `short_description`：优先使用中文，以 25–64 个字符简短说明用途；按 Unicode 字符计数，不以字节数代替字符数。
- `default_prompt`：优先使用中文，保持简短、可直接执行，并必须显式包含对应的 `$skill-name`；命令、参数和产品名保留英文原文。
- Skill 目录名、frontmatter `name` 和 `$skill-name` 触发名保持英文 kebab-case，保证路径、触发和跨环境兼容。
- 除非用户明确提供图标或品牌色，不添加可选界面字段。
- 当前 Agent 环境提供确定性元数据生成器时优先使用；没有时按本文字段约束维护，并回读 YAML 与中文内容，避免手工转码或转义造成乱码。
- 修改 GLOBAL 源稿中的 `agents/openai.yaml` 后，立即同步用户级安装目录中的同名文件并回读比较。

## SKILL.md 语言规范

自维护全局 Skill 的 `SKILL.md` 优先使用中文编写，便于长期维护和快速理解。

命令、路径、参数、API 字段、产品名、英文专有名词、代码片段和 `$skill-name` 触发名保留英文原文。

## 文件编码规范

- `SKILL.md`、`agents/openai.yaml` 及其他文本文件统一使用 UTF-8 无 BOM 编码。
- `SKILL.md` 必须直接以 YAML frontmatter 分隔符 `---` 开始，文件开头不得存在 BOM、空行或其他字符。
- 校验至少覆盖：目录名与 frontmatter `name` 一致、frontmatter 仅含允许字段、`openai.yaml` 可解析、中文可读、`short_description` 字符数合规、`default_prompt` 含 `$skill-name`、所有直接引用文件存在。
- 环境提供的自动校验通常只覆盖部分结构约束；不得据此跳过中文语义、元数据约束、引用存在性、敏感信息和源稿/安装副本一致性检查。

## 迁移模型

全局 Skill 恢复遵循 `{{AGENT_ROOT}}\GLOBAL\SKILL_DEPENDENCIES.md`。

默认预装和插件自动提供的 Skill 不记录到依赖清单。

## 推荐结构

每个 skill 通常使用独立目录：

```text
skill-name/
  SKILL.md
  agents/
    openai.yaml
  scripts/
  references/
  assets/
```

本目录中的自维护全局 Skill 固定包含 `SKILL.md` 和 `agents/openai.yaml`；其他支持目录只在确实需要时添加。
