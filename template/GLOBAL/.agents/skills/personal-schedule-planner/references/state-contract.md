# 程序化状态契约

## 强制顺序

每次真实排程都在系统临时目录创建一个 JSON manifest，并使用 `scripts/planner_guard.py` 按以下顺序逐级推进：

```text
collect -> draft -> confirm -> preflight -> dry-run -> write -> readback -> complete
```

只能前进一步，不能跳级。脚本返回非零时停止，修正 manifest 后重新走门禁；不得绕过脚本直接写日历，也不得用人工判断替代失败门禁。

## 最小 manifest

manifest 使用 `schema_version: 1`，至少包含：

- `state`、`schedule_key`、`revision`、`timezone`、`window`。
- `collection`：`parallel` 或 `sequential` 模式、统一截止时间，以及 `feishu`、`obsidian`、`projects` 三条分支的覆盖范围、状态和错误。
- `profiles[]`：目标 Profile 名称；预检前补齐实际 `app_id`、`user_open_id`、`calendar_id` 和 `calendar_write_scope`。
- `task_handoffs[]`：可选的飞书任务变更交接，包含来源项目名称与根目录、任务 GUID、Profile、变更前后排程字段、触发原因和影响方向；由 `feishu-task` 联动时必须记录，普通主动排程可为空。来源项目与 Profile 必须分别保留，不得互相推断。
- `blocks[]`：稳定 `block_key`、内部标题、开始/结束、动作、理由、来源和敏感级别。日历动作 `create/update/retain/delete` 还必须包含公开标题、可选公开描述以及 `public/busy/no_meeting` 和空参会人/会议室约束；留白动作 `none` 不得包含日历字段。全部字段都属于确认快照。
- `unplanned[]`、`risks[]`。
- 预检产生的 `matches[]`，真实 dry-run 产生的 `dry_runs[]`，写入返回的 `writes[]`，逐项回读产生的 `readbacks[]`。

运行文件不得包含 token、App Secret、device code、客户秘密或内部任务全文，不进入 Git；结束后可删除。

## 阶段含义

- `collect`：按 [并行采集契约](parallel-collection-contract.md) 执行只读采集。三条分支必须全部回报；失败分支未获用户明确接受时不能进入草案。
- `draft`：草案字段完整，但没有写入授权。
- `confirm`：必须显式传 `--user-confirmed`。脚本保存确定版本的 SHA-256；此后时间、标题、Profile、动作、公开口径、`task_handoffs[]` 或其他确认字段发生变化，后续门禁立即失败，必须运行 `reset-draft` 清除旧证据、递增修订号，再重新确认完整草案。
- `preflight`：每个 Profile 已核验 user 身份、写权限和真实主日历 ID；每个 `create/update/retain/delete` 时间块恰有一条匹配结果，重复匹配直接阻断；`retain` 的匹配结果必须保存已回读并验证过的完整旧稳定标记 `existing_marker` 和 `existing_revision`，该标记的 `schedule` 与 `block` 必须等于当前确认快照，`revision` 可早于当前修订；`none` 不参与匹配。
- `dry-run`：每个 `create/update/delete` 组合均有成功 dry-run 和实际请求 payload 文件的 SHA-256；少一个也不能写。
- `write`：只表示当前确认快照已取得写入许可。执行每项真实写入前都对同一个 payload 文件运行 `check-write`；只有文件 SHA-256 与 dry-run 记录完全相同才放行，不得扩大 change set。
- `readback`：所有写动作均已有成功结果。随后逐 Profile 回读全部日历动作；`none` 不参与回读。
- `complete`：所有 `create/update/retain` 均与确认标题、时间、时区、日历、标记、公开范围、忙闲、视频会议、参会人和会议室一致；其中 `create/update` 必须带当前 `revision` 的标记，`retain` 必须带预检保存的完整旧标记。旧 manifest 若已处于 `readback` 且缺少 `retain.existing_marker`，只允许执行器从实际回读事件描述中抽取同一 `schedule + block` 的完整标记并写回 matches，不能凭标题、时间或任意旧 revision 猜测通过；`delete` 已确认不存在；`none` 保持只存在于确认快照且没有任何日历流水。任一项不一致时保持未完成并报告“部分同步”。

## 护栏命令

```powershell
python scripts/planner_guard.py transition --manifest <temp-manifest.json> --to draft
python scripts/planner_guard.py transition --manifest <temp-manifest.json> --to confirm --user-confirmed
python scripts/planner_guard.py transition --manifest <temp-manifest.json> --to preflight
python scripts/planner_guard.py transition --manifest <temp-manifest.json> --to dry-run
python scripts/planner_guard.py transition --manifest <temp-manifest.json> --to write
python scripts/planner_guard.py check-write --manifest <temp-manifest.json> --profile <profile> --block-key <block_key> --payload <request.json>
python scripts/planner_guard.py transition --manifest <temp-manifest.json> --to readback
python scripts/planner_guard.py transition --manifest <temp-manifest.json> --to complete
```

## 正式同步执行器

Agent 完成身份、主日历和稳定标记匹配，把 `matches[]` 写入 manifest 并推进到 `preflight` 后，使用同一个专用临时请求目录执行：

```powershell
python scripts/schedule_sync.py prepare --manifest <temp-manifest.json> --request-root <temp-request-dir>
python scripts/schedule_sync.py dry-run --manifest <temp-manifest.json> --request-root <temp-request-dir>
python scripts/schedule_sync.py write --manifest <temp-manifest.json> --request-root <temp-request-dir>
python scripts/schedule_sync.py readback --manifest <temp-manifest.json>
```

- `prepare` 只生成请求信封，不调用飞书；请求目录必须专用于本次排程，出现非预期文件时阻断。
- `dry-run` 会重新确定性生成请求信封，兼容普通 JSON 与 `=== Dry Run ===` 输出，并记录整个请求信封的 SHA-256。
- `write` 只接受 `dry-run` 或中断后的 `write` 状态；每项调用前校验同一请求信封哈希，成功一项就原子保存一项，重跑时跳过已成功项。
- `readback` 逐项读取并交给原护栏验收；删除项只有回读状态为 `cancelled` 才视为不存在，查询错误不会被误判为删除成功。
- `none` 在以上四个执行阶段均被跳过，不生成请求文件，也不计入逐 Profile 日历项总数。
- CLI 默认按 PATH、`LARK_CLI`、Windows 用户级 npm shim 顺序发现；需要固定入口时显式传 `--lark-cli <path>`。

请求信封同时锁定 Profile、动作、`calendar_id`、`event_id` 或幂等键及 body，避免只校验 body 而遗漏命令参数变化。运行文件仍位于系统临时目录，完成后可删除。

确认后调整草案：

```powershell
python scripts/planner_guard.py reset-draft --manifest <temp-manifest.json>
```

幂等键固定使用 RFC 4122 `UUIDv5(NAMESPACE_URL, "app_id|calendar_id|schedule_key|block_key")`。通过脚本的 `idempotency-key` 子命令生成，不得改用 MD5、随机 UUID 或含开始/结束时间的输入。

## 旧事件修复

没有稳定标记的旧事件不进入普通同步。只有用户明确确认修复，且在单一 Profile、实际日历 ID、唯一 event ID、精确标题和起止时间上形成唯一证据时，才把它加入单独的修复 change set；先补标记再回读。证据不唯一时保留原事件并报告，不删除重建、不猜测匹配。
