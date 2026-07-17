# Personal Agent Foundation

Personal Agent Foundation 将一套真实运行过的个人 Agent `GLOBAL` 治理基座通用化，并通过安装 Skill 以对话方式安装、验证和引导首次使用。

本仓库是公开产品工程，不是 Agent 管理项目。项目状态、任务、组织和发布协调保存在仓库之外的管理工作区；本仓库不使用 `AGENTS.md`、`STATUS.md`、`tasks/` 或 `archive/`。

## 内容

- `template/GLOBAL/`：由真实 GLOBAL 全部受管内容通用化得到的公开模板。
- `skills/install-agent-scaffold/`：对话式安装、验证和首次项目教程。
- `tests/`：模板完整性、脱敏、渲染、目标保护和幂等测试。
- `docs/`：通用化映射、安装契约和维护说明。

## 安装方式

在支持 Skills 的 Agent 中调用：

```text
$install-agent-scaffold
```

Skill 会根据宿主能力使用图形交互或普通对话，收集安装路径、默认飞书 Profile、默认 GitHub 账号、时区、通用助手项目名和可选 Obsidian Vault 路径；确认 dry-run 后再执行安装。

文件护栏及 GLOBAL 内置确定性脚本要求 Python 3.11+；安装 Skill 会预检所选 IANA 时区，并在系统缺少时区数据时把 `tzdata` 纳入经用户确认的安装计划。

安装完成后，Skill 会继续引导：

1. 设置当前 Agent 的全局个性化提示词。
2. 恢复或安装 GLOBAL Skills。
3. 配置并核验飞书、GitHub 和可选知识库连接。
4. 在 GLOBAL 同级创建第一个 Agent 项目。
5. 把项目打开到 Agent，创建项目总经理会话，并调用 `init-agent-project`。

## 安全模型

- 模板不包含真实项目、个人路径、组织、账号、App ID、token 或密钥。
- 模板只接受 `template-manifest.json` 声明的占位符。
- 渲染在临时 staging 中完成，不修改模板源目录。
- 已存在的目标目录默认拒绝覆盖。
- 安装前 dry-run，安装后独立验证并检查占位符残留。
- 不跟随模板中的 Junction 或 symlink。

## 验证

```powershell
python -m unittest discover -s tests -v
python skills/install-agent-scaffold/scripts/scaffold_guard.py audit-template --template template --manifest template-manifest.json
```

护栏脚本只负责确定性文件操作；安装决策、图形交互、账号授权和 onboarding 由 Skill 协调。

## License

Apache License 2.0。见 `LICENSE`。
