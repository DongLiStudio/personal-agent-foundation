# 飞书任务排程联动契约

## 目的

`feishu-task` 在任务写入并回读后，用本契约判断任务变更是否影响当前用户的个人排程。联动只授权只读重评和草案协商，不授权修改日历；任何日历写入仍必须走 `personal-schedule-planner` 的完整确认与状态机。

## 触发边界

只在当前用户是变更前或变更后的负责人/实际执行者时考虑触发。当前用户始终只是关注人、提出者、审核者或知悉者时不触发。

以下变化在影响窗口内触发：

- 新任务进入窗口。
- `start` 或 `due` 进入、离开窗口，或在窗口内移动。
- 当前用户获得或失去执行责任。
- 任务完成、取消、重新打开，或其他会改变可执行性的状态变化。
- 预计工作量发生足以改变时间块的变化。
- 用户明确要求把任务加入当前安排；没有日期时也可触发，但仍需由排程 Skill 判断能否安排。

只修改标题、描述、附件、关注人、验收文案等非排程字段时不触发。批量创建或更新时先完成全部任务写入和回读，再合并为一次联动，不逐条启动完整排程。

## 标准输入

在系统临时目录生成不含密钥和客户秘密的 JSON，交给 `scripts/task_schedule_handoff.py`：

```json
{
  "schema_version": 2,
  "now": "2026-07-16T10:00:00+08:00",
  "timezone": "{{DEFAULT_TIMEZONE}}",
  "window": {
    "start": "2026-07-16T00:00:00+08:00",
    "end": "2026-07-17T00:00:00+08:00"
  },
  "changes": [
    {
      "task_guid": "guid",
      "profile": "profile-name",
      "project_name": "project-name",
      "project_root": "{{AGENT_ROOT}}\\project-name",
      "current_user_open_id": "ou_current",
      "explicit_schedule_request": false,
      "before": {
        "assignee_open_ids": ["ou_current"],
        "start": "2026-07-16T13:00:00+08:00",
        "due": "2026-07-16T18:00:00+08:00",
        "status": "todo",
        "estimated_minutes": 60
      },
      "after": {
        "assignee_open_ids": ["ou_current"],
        "start": "2026-07-17T13:00:00+08:00",
        "due": "2026-07-17T18:00:00+08:00",
        "status": "todo",
        "estimated_minutes": 60
      }
    }
  ]
}
```

- `before`：更新前的已回读状态；新建任务时为 `null`。
- `after`：写入后的最终回读状态；不得用拟写 payload 代替。
- `project_name`、`project_root`：任务来源项目及其当前根目录，必须从当前项目入口或 `GLOBAL/PROJECTS.md` 取得；用于保持项目语义和身份路由，不得根据 Profile 猜测项目。
- `start`、`due`：先按会话时区归一化为带偏移 ISO 8601；无值为 `null`。
- `estimated_minutes`：只有任务信息或用户上下文提供可靠估时时填写；不得编造。
- 影响窗口使用当前已排程窗口；时间被移出当前窗口时，仍保留变更前状态以触发释放原时间块。
- 同一 Profile、同一任务 GUID 在一批操作中多次变化时，先折叠为最早 `before` 和最终 `after`；脚本拒绝重复 change，避免同一任务触发多次重排。

运行：

```powershell
python scripts/task_schedule_handoff.py --input <temp-change.json>
```

输出包含总体 `trigger`、需要联动的 `handoffs[]`、无需联动的 `ignored[]`，以及每项的 `reasons[]` 和 `impact`。脚本只做确定性筛选，不读取飞书、不修改任务或日历。

## 交接到排程 Skill

当输出 `trigger=true`：

1. 当前项目“项目任务协调员”把 handoff 交给{{GENERAL_ASSISTANT_PROJECT}}“个人时间管理员”，并继续调用 `personal-schedule-planner`；任一岗位缺失时先按对应 Skill 的按需岗位规则补充，不要让用户重新描述任务，也不能因缺少可调用岗位窗口而阻塞。
2. 将来源项目、`task_guid`、Profile、变更前后时间、执行归属、状态、估时、`reasons` 和 `impact` 作为 `task_handoffs[]` 放入采集 manifest。
3. 重新回读该任务、全部 Profile 当前任务和日历；handoff 是增量线索，不替代实时采集。
4. 排程范围至少覆盖现有受管时间块和变更前后受影响日期。时间移出今天时，要提出释放今天时间块的修订；是否在新日期创建时间块由完整规划决定。
5. 由“个人时间管理员”输出完整修订草案，明确 `create/update/retain/delete/none`；`none` 表示为休息或弹性保留空白，不进入日历。获得用户确认后才同步所有 Profile。项目任务所属 Profile、负责人和业务内容仍由原项目管理，不随 handoff 转移。

当 `trigger=false`，正常报告任务结果，不调用完整排程。仅当用户明确要求安排而脚本因输入缺失无法判断时，补齐输入后重跑，不能静默忽略。
