---
name: migrate-agent-root
description: 安全迁移 Agent 根目录、GLOBAL 与已登记项目。用于用户要求移动或更换 Agent 根目录、迁移 GLOBAL 和全部项目、修复旧根绝对路径、重建 Obsidian/知识库链接、同步自维护全局 Skill 安装副本，或在迁移后调用 align-agent-projects-with-global 做项目对齐门禁时。
---

# Agent 根目录迁移

使用这个 Skill 编排完整 Agent 根目录迁移。迁移脚本只负责预检、计划、staging 复制、GLOBAL 内受管文本精确路径重写、`PROJECTS.md` 路径更新、链接/reparse 本体重建、验证、安装副本比对和消费项目对齐门禁结果；项目语义修复交给 `align-agent-projects-with-global`。

## 固定边界

- 默认 `plan`/`--dry-run`；执行前必须有用户明确确认。
- 目标目录存在或非空时拒绝覆盖/合并。
- 不跟随 Junction、symlink 或 reparse point；只记录并重建链接本体，不复制或删除外部目标，尤其不操作 Obsidian Vault。外部目标保持不变，源根内部目标重写到新根；权限不足或平台不支持时阻断并清理 staging/destination。
- 保留嵌套 Git、分支、对象、历史和未提交内容；不得用 reset、checkout、reclone 代替迁移。
- 默认排除可确定再生的依赖、缓存和构建输出（`node_modules`、Python/pytest/mypy 缓存、`dist`、`src-tauri/target*`）；不得把任意 Git ignored 文件视为可再生内容。每个排除目录及其原因、文件数和字节数必须写入 manifest，禁止静默跳过。
- 首次迁移不删除旧根；旧目录清理必须在新根验证且用户另行授权后作为独立步骤处理。
- 任一步骤失败即停止切换，保留旧根并输出修复说明。

## 工作流

1. 读取当前项目入口文件，以及 `GLOBAL/README.md`、`GLOBAL_CONTEXT.md`、`PROJECTS.md`、`SKILL_DEPENDENCIES.md`。
2. 先运行计划：

```bash
python scripts/migrate_agent_root.py plan --source OLD_ROOT --destination NEW_ROOT --report REPORT_DIR
```

3. 审查 `migration-manifest.json` 和 Markdown 报告；确认目标为空、链接边界、待重写文本、Git 目录、可再生目录排除统计和风险提示。
4. 用户确认后执行：

```bash
python scripts/migrate_agent_root.py execute --source OLD_ROOT --destination NEW_ROOT --report REPORT_DIR
```

5. 用 `align-agent-projects-with-global` 对迁移后的 GLOBAL 做门禁审计。脚本调用使用 `audit` 子命令，稳定输入包含：
   - `old_root`
   - `new_root`
   - `global_change_summary`
   - 可选 `scope`
   - `report`
6. 把对齐报告交回迁移验证：

```bash
python scripts/migrate_agent_root.py verify --source OLD_ROOT --destination NEW_ROOT --report REPORT_DIR --align-report ALIGN_REPORT --require-align-pass
```

只有所有项目状态为 `aligned` 或 `no_change_needed` 时，才宣布迁移完成并请用户从新根启动 Agent 确认切换。

## 脚本职责

`scripts/migrate_agent_root.py` 支持 `plan`、`execute`、`verify`：

- `--source`：旧 Agent 根目录。
- `--destination`：新 Agent 根目录。
- `--report`：报告目录，写入 `migration-manifest.json` 和 `migration-report.md`。
- `--dry-run`：强制不写入，`plan` 默认等价 dry-run。
- `--align-report`：读取 `align-agent-projects-with-global` 输出。
- `--require-align-pass`：门禁失败时返回非零。

脚本只对白名单文本类型做精确旧根替换，支持 Windows 反斜杠、正斜杠和 JSON 转义反斜杠形式；除 manifest 明列的可再生目录外，二进制、Git 对象、数据库、未知格式和用途不明确的 ignored 文件均复制但不改写，并接受哈希一致、旧根残留、链接目标、编码/LF、敏感信息和门禁检查。

## 参考

- 迁移和门禁报告字段见 `references/manifest-contract.md`。
- 代表性 fixture 验证使用 `scripts/test_migrate_agent_root.py`，只在临时目录中构造样例，不迁移当前真实 `{{AGENT_ROOT}}`。
