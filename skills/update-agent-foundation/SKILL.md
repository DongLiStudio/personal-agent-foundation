---
name: update-agent-foundation
description: 检查并安全更新已经安装的 Personal Agent Foundation。用于用户要求更新基座、同步公开上游新版、升级 GLOBAL 模板或自维护 Skills、查看是否有新版本，或需要在保留项目、账号、Obsidian、服务器和个人规则的前提下完成版本迁移时；不用于首次安装、单纯换机恢复或普通项目代码更新。
---

# 更新 Personal Agent Foundation

把本 Skill 作为已有基座的唯一版本更新入口。首次安装使用 `install-agent-scaffold`；换机、迁移、损坏修复使用 `restore-agent-foundation`；只有从可信产品上游引入新版时使用本 Skill。

## 开始前

完整读取 [更新契约](references/update-contract.md)。更新脚本只负责确定性盘点、计划、受管 Skill/新增文件更新、备份、验证和回滚；GLOBAL 治理文本的语义合并由当前 Agent 在展示差异并取得确认后完成。

优先使用官方仓库 `https://github.com/DongLiStudio/personal-agent-foundation.git`。把指定 tag、commit 或默认分支克隆到系统临时目录，不在 Agent 根或 GLOBAL 内长期保存产品源码。记录实际 commit；不得把未经确认的 fork、工作树或网页片段当作更新源。

## 固定保护边界

- 不覆盖、删除或重建用户项目、项目 Git、未提交内容、外部知识库或链接目标。
- `PROJECTS.md`、`LARK_PROFILES.md`、`GITHUB_ACCOUNTS.md`、`ALIYUN_PROFILES.md`、`SERVER_PROFILES.md`、`servers/`、`OBSIDIAN_LINK.md`、`SCHEDULE_PREFERENCES.md` 和 `FOUNDATION_STATE.json` 始终视为用户状态，只做语义补充，不用公开模板替换。
- `GLOBAL/.agents/skills/` 中与上游同名的产品自维护 Skill 属于受管程序文件，可以在计划确认后逐文件更新；用户额外创建的 Skill 不删除。
- `README.md`、`GLOBAL_CONTEXT.md`、`SKILL_DEPENDENCIES.md`、`.gitignore` 等治理文件发生变化时进入人工可读的语义合并清单，保留用户个性化规则与真实路由。
- 不接受模板残留占位符，不跟随 Junction、symlink 或 reparse point，不把 token、PAT、AK/SK、密码、私钥或 Cookie 写入计划、备份说明或报告。
- 更新授权不等于远程仓库创建、MR 合并、Release、部署、账号授权或服务器变更授权。

## 更新流程

1. 读取 Agent 根下 `GLOBAL/README.md`、`GLOBAL_CONTEXT.md`、`FOUNDATION_STATE.json`，以及所有活跃项目三入口；记录各 Git 工作树，不要求其干净，也不改项目业务文件。
2. 获取可信产品源，执行产品仓库自身的模板审计；审计失败立即停止。
3. 使用脚本 `audit` 比较当前实例与新版模板，输出新增文件、受管 Skill 更新、用户状态保护项和治理语义合并项。
4. 使用 `plan` 生成带 `plan_sha256` 的计划。逐项向用户展示：来源 commit、会写入什么、会保留什么、需要语义合并什么、备份与回滚位置。
5. 用户确认当前计划后执行 `apply`；计划或文件变化后必须重新生成，不能沿用旧确认。
6. 对计划中的 `review_merge` 文件逐个做最小语义合并。不得复制公开模板覆盖整份真实 GLOBAL 文件；先保留用户内容，再补入新版规则。
7. 运行 `verify`，再调用 `restore-agent-foundation verify` 检查路径、Skill 安装副本、链接、宿主与授权门禁。
8. 按当前 GLOBAL Git 规则对 GLOBAL 和确有变更的项目分别检查、提交、push 并回读；产品源码临时目录不提交到用户基座。

```powershell
<python> scripts/foundation_update.py audit --root <agent-root> --source <product-repo> --report <temp-audit.json>
<python> scripts/foundation_update.py plan --root <agent-root> --source <product-repo> --report <temp-plan.json>
<python> scripts/foundation_update.py apply --plan <temp-plan.json> --confirm-plan-sha256 <sha256>
<python> scripts/foundation_update.py verify --root <agent-root> --source <product-repo>
```

## 回滚

确定性更新需要撤销时，使用本次 `run-manifest.json`：

```powershell
<python> scripts/foundation_update.py rollback --run-manifest <agent-root>/GLOBAL/.foundation-update/<run-id>/run-manifest.json
```

只回滚本次脚本实际写入且更新后未被再次修改的文件。语义合并、外部授权、Git push、Release、部署和用户后来产生的修改不做猜测性回滚。

## 完成判定

只有可信来源、模板审计、确定性更新、全部语义合并、更新脚本 `verify`、恢复器 `verify`、Git 提交/push 回读均完成，才能宣布版本更新完成。报告来源 commit、更新文件、保留内容、备份清单、验证证据和仍待人工处理的项目；不得把“检查到新版”表述成“已更新”。
