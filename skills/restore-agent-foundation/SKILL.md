---
name: restore-agent-foundation
description: 对已经存在、整体复制、迁移过、局部损坏或更换 Agent 宿主的 Personal Agent Foundation 执行统一恢复、自检、修复和最终验收。用于用户换电脑后恢复 Agent 基座、移动 Agent 根目录、换 Codex 或其他兼容 Agent、发现 GLOBAL/项目/Skill/链接/账号工具不可用，或要求全面检查并恢复到完整可用状态时。Skill 自包含核心恢复程序，不以其他 Skill 已可用为前提。
---

# 恢复 Personal Agent Foundation

把本 Skill 当作已存在 Agent 基座的唯一恢复入口。核心路径校准、链接重建、Skill 重装、状态验证、备份和回滚均使用本 Skill 自带的 `scripts/foundation_recovery.py`；不要把其他 Skill 能否运行作为恢复前提，也不要用临时 shell 替代确定性护栏。

## 开始前

完整读取 [恢复契约](references/recovery-contract.md)。需要处理宿主 Skill 安装位置、图形授权或宿主切换时，再读取 [宿主恢复](references/host-recovery.md)。

优先从本 Skill 自身位置发现 Agent 根。若用户把整个基座复制到新电脑，但本 Skill 尚未安装到用户级目录，直接读取复制后基座中的：

```text
<Agent 根>/GLOBAL/.agents/skills/restore-agent-foundation/SKILL.md
```

不得要求其他全局 Skill 先恢复。不得要求用户手工逐项执行安装、迁移、对齐或授权流程。

## 目标状态

无论当前是换机、换 Agent、换路径、权限丢失还是局部损坏，都把当前环境收敛到同一结果：

- 当前 Agent 根与 `GLOBAL/FOUNDATION_STATE.json` 一致；旧根精确残留被清除，GLOBAL 治理文本无 BOM、CRLF 或基座占位符。项目代码、项目自身模板和业务资产不被格式化。
- GLOBAL 核心入口、项目索引、项目三入口和独立 Git 边界可读取。
- `GLOBAL/.agents/skills/` 是自维护 Skill 权威源；当前宿主的安装副本逐文件一致。
- Junction/symlink 只重建链接本体，不复制、删除或递归遍历外部目标。
- GitHub、飞书、Obsidian、服务器连接和宿主能力均经过实时发现；缺权限时引导用户走官方授权或安全恢复，完成后独立回读。
- 用户项目、Git 历史、未提交内容、凭据和外部知识库内容不被覆盖。
- 最终 `verify` 及交互式门禁全部通过；未完成项不得表述为成功。

## 连续恢复流程

### 1. 发现与只读审计

1. 定位复制后的 Agent 根；若可从本 Skill 路径确定，不再询问。
2. 发现当前宿主可识别的全局 Skill 安装目录。宿主有多个目录时逐一列出，并让用户确认受管目标；不要猜写系统目录。
3. 执行 `audit`，输出当前根、历史根、核心文件、项目、链接、Skill 副本、运行时和交互授权门禁。
4. `audit` 和 `plan` 都只读；报告不得包含 token、App Secret、私钥、Cookie 或链接目标中的文件内容。为供用户确认，报告可以记录链接本体路径及目标目录路径。

```powershell
<python> scripts/foundation_recovery.py audit --root <agent-root> --skill-target <host-skill-dir> --report <temp-audit.json>
```

Python 必须为 3.11+。当前 Python 不满足时，展示当前系统的官方安装方案，取得用户确认后安装，再重新审计。

### 2. 形成单一恢复计划

根据审计结果补充必要参数：

- 旧根无法从 `FOUNDATION_STATE.json` 确认时才询问 `--old-root`。
- Obsidian 链接缺失或失效时，先确认真实 Vault，再传 `--obsidian-target`；不把 Vault 原始路径写入长期文档。
- Skill 安装目录无法由宿主确定时，请用户通过宿主设置或目录选择界面确认。

执行 `plan` 并展示：会修改的文件、路径替换数量、链接重建、Skill 安装/替换、Git 初始化、需要用户完成的授权和阻断项。

```powershell
<python> scripts/foundation_recovery.py plan --root <agent-root> --skill-target <host-skill-dir> --report <temp-plan.json>
```

计划带有 `plan_sha256`。只有用户明确确认当前计划后才能进入修复；计划后文件或环境变化时重新生成，不沿用旧确认。

### 3. 程序化修复

```powershell
<python> scripts/foundation_recovery.py repair --plan <temp-plan.json> --confirm-plan-sha256 <confirmed-sha256>
```

- 已安装同名 Skill 与权威源不一致时，默认阻断。展示差异范围并获得覆盖安装副本的明确确认后，才增加 `--replace-skill-installations`。
- 修复前只备份实际改动文件和被替换的 Skill 副本；备份位于 `GLOBAL/.foundation-recovery/<run-id>/`，被 `.gitignore` 排除。
- 不删除旧电脑副本，不清理旧 Agent 根，不提交、不 push、不创建 remote。
- 文件在计划后变化、链接目标不存在、Skill 目标是链接、核心文件缺失或出现占位符时立即停止。

### 4. 交互式恢复

确定性修复成功后，继续处理脚本标记的 `interactive_gates`。这些步骤由本 Skill 直接编排，不要求其他 Skill 已可调用：

- **GitHub**：发现 `gh`；执行 `gh auth status` 和 `gh api user`。缺失时使用 GitHub CLI 官方安装方式；未登录时打开官方登录流程。回读真实 login，核对 `GITHUB_ACCOUNTS.md`，不输出 token。
- **飞书**：发现 `lark-cli` 及用户级 shim；按 `LARK_PROFILES.md` 的每个 Profile 显式执行 `lark-cli auth status --verify --json --profile <Profile>`，并回读用户身份。`auth status` 不附加业务命令才使用的 `--as user`。失效时打开官方授权流程并等待用户完成；不得把 App Secret 写入报告或命令历史。
- **Obsidian**：检查 `GLOBAL/obsidian-resource` 链接本体和目标可达性；只把官方注册的 CLI（Windows 为 1.12.7+ 安装器随附的 `Obsidian.com` 重定向器）判定为 CLI，不把 GUI `Obsidian.exe` 误判为 CLI。有官方 CLI 时执行版本及有界只读检查，没有 CLI 时按官方设置完成注册，或以开放文件格式做最小只读验证。禁止递归遍历 Vault。
- **服务器**：读取 `SERVER_PROFILES.md` 的非敏感路由，发现 `ssh` 客户端；由用户明确选择需要恢复的服务器 Profile 后，检查本机 SSH 别名、身份文件是否存在但不读取私钥，先从可信渠道核验主机指纹，再以 `BatchMode` 做身份和目标服务的有界只读回读。缺少私钥或权限时引导用户通过安全渠道恢复或重新授权，不把私钥、密码、票据写入 GLOBAL、报告或命令历史。不得设置隐式默认服务器，也不得自动部署、重启、改网、改卷或修改远端配置。
- **宿主**：确认全部自维护 Skill 已被当前 Agent 发现；宿主需要重启或重新加载时明确提示并在恢复后复查。检查全局个性化提示词是否已设置，不能从界面回读时标记为待用户确认。

任何官方授权、软件安装、系统权限提升或宿主设置修改都要在执行前说明影响并取得确认。用户完成授权后，从中断门禁继续，不重新运行已经成功的写入。

### 5. 项目与最终验收

1. 逐项读取 `PROJECTS.md` 中登记项目的 `AGENTS.md`、`README.md`、`STATUS.md`，确认路径、GLOBAL 入口和 Git 仓库可用。
2. 对每个项目只读检查工作树、分支和 remote；不要求工作树必须干净，不自动 commit 或 push。
3. 执行最终验证：

```powershell
<python> scripts/foundation_recovery.py verify --root <agent-root> --skill-target <host-skill-dir> --old-root <previous-agent-root>
```

换机或换根后应把已确认的旧根传给 `--old-root`，对 native、正斜杠、反斜杠和 JSON 转义形式做最终残留扫描；原地修复且不存在旧根时可省略。

4. 汇总确定性 `verify` 与 GitHub、飞书、Obsidian、服务器、宿主授权回读。只有全部必要项通过，或用户明确选择某项暂不连接且 GLOBAL 如实记录，才能宣布恢复完成。

## 回滚

确定性文件修复需要撤销时，使用本次 `run-manifest.json`：

```powershell
<python> scripts/foundation_recovery.py rollback --run-manifest <agent-root>/GLOBAL/.foundation-recovery/<run-id>/run-manifest.json
```

回滚恢复该运行实际备份的受管文件和被替换的 Skill 副本；链接只在记录了原目标且目标仍可用时恢复。若修复后文件、Skill 副本或链接又被用户修改，回滚会拒绝覆盖这些新改动。外部授权、系统软件和远端 Git 状态不做猜测性回滚。回滚后重新执行 `audit` 并如实报告仍需人工处理的状态。

## 完成报告

报告只包含：

- 当前 Agent 根、宿主和恢复场景。
- 已自动修复项及验证证据。
- 用户完成的授权及官方身份回读结果。
- 保留的用户定制、项目 Git 状态和未修改边界。
- 未完成、用户选择跳过或当前宿主不支持的事项。
- `run-manifest.json` 路径和建议下一步。

不要输出凭据值、敏感配置内容、外部知识库内容或冗长命令日志。
