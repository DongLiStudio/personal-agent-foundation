---
name: align-agent-projects-with-global
description: 当 GLOBAL 发生会影响项目的规则、路径、Skill 源头、账号工具约定、项目索引或治理入口更新后，动态读取 GLOBAL_CONTEXT.md 及本次相关 GLOBAL 规则，审计、计划并在授权后逐项目对齐所有已登记 Agent 项目。用于 GLOBAL 规则更新后的递归项目扫描、项目继承/合理覆盖/冲突判断、旧路径或失效入口清理、migrate-agent-root 迁移前后项目对齐门禁，以及生成逐项目/总报告；不用于纯文案修正、GLOBAL 内部实现调整或不影响项目的易变运行状态。
---

# 对齐 Agent 项目与 GLOBAL

使用这个 Skill 在 `GLOBAL` 出现会影响项目的上层规则变化后，安全扫描并对齐 `PROJECTS.md` 中登记的真实项目。目标是动态理解最新 GLOBAL 规则，让项目继承应继承的部分，同时保留合理的项目覆盖规则、历史记录和 Git 边界。

## 判断是否需要触发

先判断本次 GLOBAL 变化是否真的影响项目：

- 需要触发：`GLOBAL_CONTEXT.md`、`PROJECTS.md`、`SKILL_DEPENDENCIES.md`、账号工具约定、Obsidian 入口规则、全局 Skill 源头模型、根路径、Git 协作规则，或其他 GLOBAL 明确声明会影响项目的规则发生变化。
- 通常不触发：错别字、排版、纯说明润色、GLOBAL 内部实现细节、运行时缓存状态、某个项目无关的临时记录。
- 不确定时先做只读审计，输出“影响判断”和证据，不直接改项目。

## 固定边界

- 只从 `GLOBAL/PROJECTS.md` 的“活跃项目”段获取受管项目；不要把核心工作区、Obsidian 入口或其他路径清单当成项目，也不要盲扫磁盘。
- 不跟随 Junction、symlink 或 reparse point；不操作 Obsidian Vault 本体。
- 不覆盖项目 README、STATUS、AGENTS、tasks、docs 或 `.agents` 的整段内容；只做必要的局部修复。
- 区分 GLOBAL 上层规则、项目覆盖规则和历史记录。保留项目业务规则、历史交接和已关闭记录。
- 默认只读审计和计划。实施改动、提交、外部系统操作或推送前必须有明确授权。
- 保护各项目现有未提交内容。每个项目分别检查、验证和提交；不跨仓库暂存，不混入无关改动。commit 不等于 push，默认不 push。
- 不提交密钥、令牌、环境变量文件、日志或临时文件。

## 工作流

1. 读取当前项目入口文件，以及 `GLOBAL/README.md`、`GLOBAL_CONTEXT.md`、`PROJECTS.md`。
2. 按本次变化范围读取相关 GLOBAL 规则文件，例如 Skill 依赖、账号工具约定、Obsidian 入口或迁移任务；不要预设某个具体治理条目必然存在。
3. 记录本次 GLOBAL 变化摘要；如果用户没有提供，用 `git diff`、任务说明或相关文件变化推断，并明确说明推断依据。
4. 使用 `scripts/align_agent_projects.py audit` 生成只读报告。示例：

```bash
python scripts/align_agent_projects.py audit --global-root {{AGENT_ROOT}}\GLOBAL --report report.json
```

调用方已经从“活跃项目”段取得明确项目名或路径时，可以通过 `--scope <项目名或完整路径> ...` 收窄范围；脚本仍会回到 `PROJECTS.md` 校验这些项目，不接受索引外路径。

`PROJECTS.md` 没有解析出任何项目时默认返回失败；只有调用方明确传入 `--allow-empty-projects` 才允许空范围通过。

5. 按报告把每个项目分类为：
   - `aligned`：已对齐。
   - `no_change_needed`：本次 GLOBAL 变化不影响该项目，或只有历史记录命中。
   - `needs_manual_decision`：存在项目覆盖规则、冲突规则、脏工作树、模糊旧路径或需要用户选择。
   - `blocked`：项目不存在、不是可安全访问的目录、检测到链接边界风险或无法验证。
6. 需要实施时，先给出逐项目计划和风险；得到授权后逐项目修改、验证、检查 diff、创建聚焦本地提交。
7. 生成总报告，至少包含项目名、路径、状态、改动摘要、验证结果、提交哈希或阻塞原因。

## 动态规则解释

不要把当前某条 GLOBAL 治理内容硬编码进 Skill。例如组织治理、目录结构、账号继承、知识库入口是否需要对齐，必须由 `GLOBAL_CONTEXT.md` 和本次相关 GLOBAL 文件的实际差异自然推导。

- 先从 GLOBAL 规则文本和变化摘要提取规则信号：路径、文件名、Skill 名、账号工具名、明确的必须/禁止/默认/除非等规范句。
- 再在项目文本中寻找继承证据、旧规则残留、项目覆盖声明和显性冲突。
- 如果项目声明了覆盖规则，判断它是否被 GLOBAL 允许；无法判断时标为 `needs_manual_decision`。
- 如果规则信号只出现在历史任务或归档记录中，不直接判定为冲突；在报告中说明它可能是历史命中。
- 如果本次 GLOBAL 变化没有给出可应用到项目的规则信号，项目应为 `no_change_needed`，不要为了“对齐”制造改动。

## 项目扫描面

扫描面由项目实际文件和 GLOBAL 规则动态决定。常见候选包括项目入口文档、任务记录、长期文档、项目内 `.agents` 内容和本次规则摘要命中的文件；这些只是发现规则证据的地方，不是固定治理要求。

Git 工作树存在未提交内容时，只读报告即可，除非用户明确授权并能区分改动来源。

## 实施规则

实施时采用最小局部编辑：

- 更新旧绝对路径时，只替换精确的旧根/旧 GLOBAL 路径表示，避免模糊替换普通文本。
- 补齐规则继承或修复冲突时，用项目现有语气和结构写入，不复制 GLOBAL 大段模板。
- 对冲突规则标记 `needs_manual_decision`，不要擅自删除项目覆盖规则。
- 对缺失核心文件、链接目录、无法访问目录或疑似外部知识库标记 `blocked`。
- 每个项目完成后运行可用的轻量验证：编码/LF、Markdown 链接、敏感信息扫描、Git diff 审查，以及项目自己的测试或校验命令。
- 每个仓库单独提交，提交信息聚焦本项目 GLOBAL 对齐；不要 push。

## migrate-agent-root 调用契约

未来 `migrate-agent-root` 可以把本 Skill 作为项目对齐门禁调用，而不要重复实现项目对齐逻辑。稳定输入：

- `old_root`：迁移前 Agent 根目录，可为空。
- `new_root`：迁移后 Agent 根目录或当前根目录。
- `global_change_summary`：本次 GLOBAL 路径和规则变化摘要。
- `scope`：可选项目名/路径列表；不传时从迁移后的 `GLOBAL/PROJECTS.md` 获取全部项目。
- `report`：机器可读报告输出路径。

脚本接口为 `audit --global-root ... --old-root ... --global-change-summary ... --scope ... --report ...`。根目录迁移门禁可额外传 `--accept-migration-rewrites`；它不会笼统忽略 dirty 工作树，只有全部修改都能由 Git HEAD 经过旧根到新根的精确文本替换得到时才放行，其他 dirty 类型仍要求人工决定。`plan/apply` 是 Agent 工作流层面的授权阶段，不是当前脚本子命令；实施改动必须另行获得用户明确授权。

稳定输出：

- 每个项目的状态：`aligned`、`no_change_needed`、`needs_manual_decision`、`blocked`。
- 总状态：只有全部项目为 `aligned` 或 `no_change_needed` 时才算通过。
- 失败时阻止迁移宣布完成，但保留旧根，不执行目录复制、根切换或删除逻辑。

本 Skill 不实现目录复制、根切换、Obsidian 链接重建或旧目录清理。

## 脚本

`scripts/align_agent_projects.py` 提供只读审计、报告生成和 fixture 支持。脚本可用于真实项目 dry-run，也可用于临时 fixture 测试；它不会修改项目文件、不会暂存、不会提交。
