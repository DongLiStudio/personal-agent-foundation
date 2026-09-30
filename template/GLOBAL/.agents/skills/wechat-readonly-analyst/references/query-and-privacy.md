# 查询与隐私门禁

## 持续授权模型

绑定 Profile 时一次性说明并确认：

1. 首次取钥及以后必要的密钥刷新会只读扫描当前微信进程的可读内存；不会写入、注入或修改微信。校验后的密钥目录由 DPAPI CurrentUser 加密持久保存。
2. 此 Profile 建立持续只读授权：用户后续提出的具体微信查询，可直接读取本机数据库并把必要语义放入当前 Agent/模型上下文。如果当前模型是云端模型，这不属于“数据完全不出机”。

授权随 Profile 保留，直到用户删除该 Profile；每个查询请求本身确定范围，不再重复弹出同意门禁。只有首次取钥或刷新密钥时需要传入 `--confirm-memory-read --grant-standing-read`。

## 查询命令

所有命令从用户级 Skill 目录执行，并显式使用 Profile：

```powershell
$py = '.\.runtime\Scripts\python.exe'
& $py .\scripts\wechat_readonly.py --profile "个人微信" sessions --limit 20
& $py .\scripts\wechat_readonly.py --profile "个人微信" history "群名" --limit 50
& $py .\scripts\wechat_readonly.py --profile "个人微信" history "群名" --limit 2000 --sender me --type text
& $py .\scripts\wechat_readonly.py --profile "个人微信" history "群名" --limit 2000 --sender me --type image --summary-only
& $py .\scripts\wechat_readonly.py --profile "个人微信" search "关键词" --chat "群名" --limit 30
& $py .\scripts\wechat_readonly.py --profile "个人微信" stats "群名"
```

首次取钥在上述任一命令前增加 `--confirm-memory-read --grant-standing-read`。先用 `sessions --limit 3` 做最小验证。大量总结按工具稳定性逐页推进，不设置隐私条数上限，直至覆盖用户指定的全部本机可用范围。

`history` 可用 `--sender` 做展示名级过滤，`--type` 按消息类型过滤；仅需数量时使用 `--summary-only`，避免无意义输出明细。`limit` 作用于群聊原始结果，因此按发送者分析时应让它覆盖目标时间段的全部本机可用消息。

## 输出纪律

- 根据用户目标输出明细、聚合主题、决策、行动项、日期、未决问题或风险；不以隐私规则擅自缩小已请求的读取范围。
- 不暴露 wxid、路径、密钥、候选值或内部 local_id；链接按任务需要保留或脱敏。
- 姓名只有在责任归属确实重要时出现；否则使用角色或匿名描述。
- HTML 报告的输入必须先由 Agent 生成脱敏汇总 JSON，不得把原始查询 JSON直接交给渲染器。
- 每次检查返回的 `cleanup_complete`；为 `false` 时停止后续查询，关闭占用进程并人工清理本次临时目录，但不得在报告中公开路径。
