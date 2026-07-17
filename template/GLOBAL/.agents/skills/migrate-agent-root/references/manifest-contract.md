# 迁移 Manifest 与门禁契约

`migration-manifest.json` 必须是 UTF-8、LF、无密钥内容的机器可读 JSON。

## 顶层字段

- `schema_version`：当前为 `1`。
- `mode`：`plan`、`execute` 或 `verify`。
- `generated_at`：UTC ISO 时间。
- `source` / `destination`：解析后的绝对路径。
- `dry_run`：是否未写入目标。
- `same_drive`：是否同盘或同挂载点，无法判断时为 `null`。
- `status`：`planned`、`executed`、`verified` 或 `blocked`。
- `errors`：阻断原因数组。
- `summary`：文件数、目录数、字节数、链接数、重写数、旧根残留数。
- `copy_plan`：普通文件、目录、链接、跳过项列表。`skipped` 只允许记录固定策略识别的可再生依赖、缓存和构建输出，并包含 `path`、`reason`、`action`、`files`、`bytes`；不得依据 Git ignored 状态笼统排除内容。
- `rewrites`：每个被改写文本的相对路径、替换次数和命中的路径表示。
- `copy_plan.links`：链接相对路径、类型、目标、内部/外部判断和处理动作；只记录链接本体，不遍历目标。`execute` 在普通文件通过 staging 验证后重建链接/reparse 本体；外部目标保持不变，内部目标重写到新根，权限或平台失败时阻断并清理本次创建的 staging/destination。
- `git_repositories`：发现的嵌套 Git 根相对路径。
- `verification`：哈希不一致、文本旧根残留、小型非文本文件旧根字节命中、`link_rebuild_results`、`link_target_results`、编码/LF、敏感信息扫描、嵌套 Git 状态和门禁结果。普通文件与 Git 对象严格比较哈希；`.git/index` 可能被只读 `git status` 刷新缓存元数据，因此只校验存在性与仓库状态，并在 `git_metadata_hash_skips` 明列豁免。

## 对齐门禁输入

迁移完成复制和 GLOBAL 路径改写后，调用 `align-agent-projects-with-global`：

```bash
python scripts/align_agent_projects.py audit \
  --global-root NEW_ROOT/GLOBAL \
  --old-root OLD_ROOT \
  --global-change-summary "Agent root migrated from OLD_ROOT to NEW_ROOT; GLOBAL paths and PROJECTS.md were rewritten." \
  --report ALIGN_REPORT \
  --accept-migration-rewrites \
  --fail-on-attention
```

迁移后的项目因受管绝对路径重写会自然呈现 Git dirty。`--accept-migration-rewrites` 只在每个改动均为未暂存 UTF-8 文本修改，且内容可由 Git HEAD 进行确定性的 `OLD_ROOT` → `NEW_ROOT` 替换精确得到时放行；任何未跟踪、暂存、删除、重命名、二进制或额外文本变化仍为人工决策。

项目范围默认由迁移后的 `GLOBAL/PROJECTS.md` 决定；若用户指定项目范围，使用 `--scope` 传入项目名或路径列表。空项目列表默认失败，只有明确传入 `--allow-empty-projects` 才允许。`plan/apply` 是 Agent 工作流授权阶段，不是当前对齐脚本子命令。

## 对齐门禁输出

迁移 Skill 只消费状态，不解释项目治理语义：

- 通过：所有项目为 `aligned` 或 `no_change_needed`。
- 阻断：任一项目为 `needs_manual_decision` 或 `blocked`。

阻断时不得宣布迁移完成，不做旧根删除，不自动修改项目；将报告路径、项目状态和修复建议交给用户或 `align-agent-projects-with-global`。
