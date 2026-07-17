# 跨 Profile 日历同步契约

## 稳定身份

为每个受管时间块在描述末尾保留三项纯文本标记：

```text
AGENT-SCHEDULE|schedule=<schedule_key>|block=<block_key>|revision=<n>
```

- `schedule_key`：排程所属的稳定日期或用户指定范围，例如 `2026-07-16`；修订计划时不改变。
- `block_key`：优先使用任务 GUID；没有 GUID 时使用稳定的“项目 + 交付”语义标识。不得把开始时间、结束时间或序号作为唯一身份，否则移动时间会制造新事件。
- `revision`：每次用户确认新版本时递增，只用于审计，不参与事件身份匹配。

标记不得包含 token、客户秘密或内部链接。更新日程时保留同一 `schedule_key + block_key`。

## 确定性幂等键

创建事件前，使用 `scripts/planner_guard.py idempotency-key` 生成 RFC 4122 UUIDv5。固定 namespace 为标准库 `NAMESPACE_URL`，name 为以下稳定输入按竖线连接：

```text
profile_app_id | calendar_id | schedule_key | block_key
```

不得用 MD5、随机 UUID、开始/结束时间或序号替代。幂等键保护同一次创建重试；跨会话更新仍以描述标记和实际 `event_id` 匹配为准。

## 写前预检

对全部目标 Profile 先完成以下动作，任何结果都记录到矩阵：

1. 显式 `--profile <name> --as user` 回读身份、授权和 calendar write scope。
2. 获取主日历 ID，不假设所有 Profile 都接受字面量 `primary`。
3. 读取当前 `lark-calendar`、创建/更新 reference、命令 `--help` 与 `calendar.events.create/patch` schema。
4. 获取排程窗口内事件；对候选事件回读详情，在描述中精确匹配 `schedule_key + block_key`。
5. 只为 `create/update/retain/delete` 生成逐 Profile change set，并为写动作执行 dry-run。全部 Profile 预检完成后才开始真实写入。

上述结果写入临时 manifest，并由 [程序化状态契约](state-contract.md) 逐级校验。进入 `preflight` 后统一使用 `scripts/schedule_sync.py` 生成请求、dry-run、写入与回读；没有实际日历 ID、完整唯一匹配和全部写动作的成功 dry-run 时，护栏不得进入 `write`。

匹配规则：

- 0 个匹配：`create`。
- 1 个匹配：保存其 `calendar_id + event_id`，按确认版本判断 `update` 或 `retain`；若为 `retain`，同时保存实际事件描述中的完整 `existing_marker` 与解析出的 `existing_revision`，并验证 `schedule_key + block_key` 与当前确认快照一致。
- 多个匹配：标记 duplicate，停止该时间块，不猜测、不自动删除。

## 个人时间块创建

当前 `lark-calendar +create` 可能自动附加飞书视频会议。个人专注、业务处理、用餐或确定性通勤时间块必须使用当前 schema 的原生 `calendar.events.create`，并显式设置：

- `summary`：用户确认的公开安全标题。
- `description`：最小公开说明和稳定标记。
- `start_time` / `end_time`：秒级时间戳与明确 IANA 时区。
- `free_busy_status: busy`。
- `visibility: public`，实现用户要求的跨组织时间透明；敏感内容先中性化。
- `vchat.vc_type: no_meeting`。
- 合理提醒；没有用户偏好时不堆叠多个提醒。
- `idempotency_key`：按本契约确定性生成。

不添加参会人、群聊或会议室。真实会议另走 `lark-calendar` 预约流程，并在用户确认时间和参与人后创建。

## 留白不写入

- 普通休息、任务切换、延误余量、突发容量和仅用于容错的通勤弹性使用 `action: none`。
- `none` 保留在用户确认快照中，用于证明计划没有排满；它没有公开标题、稳定事件标记、幂等键、匹配结果、请求文件、dry-run、写入或回读。
- 同步执行器不得把 `none` 转换为 `create`，也不得为它查询或制造日历事件。若用户后来明确希望把某段留白变为日历占用，应重置草案、改为日历动作并重新确认。

## 更新与删除

- 只更新已精确匹配的受管事件，显式传入要变更的字段；不能用空字段意外清空描述或标题。
- 移动时间时同时更新开始和结束，并保持草案确认的时长。
- 原事件含非本 Skill 生成的富文本或附加内容时停止，避免原生 patch 破坏内容。
- 新版本不再包含的旧受管事件默认 `retain`。只有草案明确列为 `delete` 且用户确认后才删除。
- CLI 返回高风险确认门禁时，展示准确动作和事件，再按门禁获得确认；不能自动追加 `--yes`。

## 部分失败

真实写入不是跨 Profile 事务：

- 在全部 dry-run 成功前不写任何 Profile。
- 写入时每个 Profile、每个时间块独立记录返回结构和事件 ID。
- 某项失败后，不删除已经成功的事件来模拟回滚。继续执行是否安全取决于失败是否局部且后续目标已经通过预检；不确定时停止剩余写入。
- 重试只针对失败的 `profile + block_key`，先重新搜索稳定标记；不得盲目再次创建。
- 正式执行器每成功一项立即原子写入 manifest；进程中断后可从 `write` 状态续跑。创建请求沿用确定性幂等键，防止服务端成功但本地尚未来得及记录时重复创建。

## 回读验收

本 Skill 的用户需求明确包含跨 Profile 同步验证，因此写后逐项回读，即使通用日历 Skill 通常允许只依赖写入返回结果。

每项核验：

- Profile、user 身份和主日历。
- `event_id` 与可点击链接。
- `schedule_key`、`block_key`、`revision`。`create/update` 要求当前确认修订号；`retain` 要求预检保存的既有稳定标记，可保留旧修订号但不得缺少完整标记。
- 标题、开始、结束、时区。
- `visibility=public`、`free_busy_status=busy`。
- 个人时间块为 `no_meeting`，且没有意外参会人或会议室。

最终输出逐 Profile 矩阵和总计。只有所有目标项回读一致且程序化护栏进入 `complete` 时，才能报告“全部同步完成”。写入每个 Profile 只证明日程存在；同事实际能否看到详情仍受组织日历权限影响，不能越权修改权限或过度承诺。
