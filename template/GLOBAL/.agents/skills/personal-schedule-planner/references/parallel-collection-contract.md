# 并行采集契约

## 调度原则

运行环境支持会话内临时子智能体，且飞书、Obsidian、项目状态三类来源都需要采集时，默认并行启动三条只读分支：

- `feishu`：读取全部治理层 Profile 的 user 身份、任务、日历和忙闲；存在 `task_handoffs[]` 时先逐 GUID 回读这些任务，再完成全量采集。Profile 很多且仍有空闲槽位时，可继续按 Profile 并行，但最终合并成一份分支回报。
- `obsidian`：读取 `仪表盘.canvas`、其相关 Wikilink 和受限 Dataview 范围。
- `projects`：读取 `PROJECTS.md` 中活跃项目的 `AGENTS.md`、`README.md`、`STATUS.md`，按需读取候选任务证据。

主 Agent 同时读取当前时间、排程窗口和 `SCHEDULE_PREFERENCES.md`，等待全部分支回报后统一归一化、去重、决策、协商和写入。子智能体不可确认草案、修改来源、写日历或独立宣布排程完成。

如果子智能体不可用、槽位不足或采集规模很小，改为顺序采集，但使用相同回报结构和门禁；不要为了形式并行制造调度开销。

## 委派要求

每条委派都要：

1. 要求接收方读取当前项目 `AGENTS.md`、`README.md`、`STATUS.md`，以及分支所需的 GLOBAL 入口和专用规则。
2. 说明统一采集截止时间、排程窗口、观察窗口、当前时区和只读边界。
3. 限定来源范围，不让 Obsidian 或项目分支递归遍历无关目录。
4. 要求完成、阻塞或发现实质权限问题时主动回报主 Agent。

## 统一回报结构

每条分支写入临时 manifest 的 `collection.branches[]`：

```json
{
  "id": "feishu | obsidian | projects",
  "status": "complete | failed",
  "collected_at": "带时区 ISO 8601",
  "coverage": {},
  "items": [],
  "fixed_conflicts": [],
  "risks": [],
  "errors": []
}
```

- `coverage` 记录实际 Profile、Canvas/笔记或项目覆盖范围，不能只写“已完成”。
- `items` 使用来源稳定 ID；飞书任务保留 GUID，日程保留 Profile、calendar ID 和 event ID，项目事项保留项目路径和事实文件。
- `errors` 保留准确失败原因，不包含 token、App Secret 或客户秘密。
- 三条分支必须使用同一个 `collection.cutoff` 作为采集基线，并各自记录实际完成时间。

## 汇合门禁

- 主 Agent 必须等待 `feishu`、`obsidian`、`projects` 三条分支全部回报，再尝试进入 `draft`。
- 程序化护栏要求三条分支恰好各一份；缺失、重复或未知分支都会阻断。
- 分支失败时先尝试安全恢复或顺序补采。仍失败则向用户展示缺口和影响；只有用户明确接受不完整证据后，才能设置 `user_waived: true` 进入草案。
- 合并时按任务 GUID、日程事件 ID、项目路径和明确交付语义去重，不把三份列表直接拼接。
- handoff 与全量任务列表命中同一 Profile 和 GUID 时合并为一个候选事项；handoff 保留来源项目、变更原因和前态，全量回读提供当前事实，不得重复排程，也不得仅凭 Profile 猜测来源项目。
- 并行采集持续较久或进入写前预检时，重新回读近期日历和目标事件；采集快照不能替代写前实时冲突核验。
