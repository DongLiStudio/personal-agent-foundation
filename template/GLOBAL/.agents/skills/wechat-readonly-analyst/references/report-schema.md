# HTML 报告结构

`scripts/render_report.py` 接收已经脱敏的 UTF-8 JSON，输出单文件 HTML。输入不得包含密钥、wxid、数据库路径、认证材料、完整聊天或未经筛选的原始消息数组。

```json
{
  "title": "项目群沟通复盘",
  "subtitle": "基于已授权的本机可用记录",
  "date_range": "2026-09-01 至 2026-09-30",
  "total_messages": 320,
  "thesis": "一句核心判断",
  "metrics": [{"label": "行动项", "value": 8}],
  "sections": [{"title": "主题", "body": "聚合结论", "bullets": ["短要点"]}],
  "actions": [{"text": "下一步", "priority": "高"}],
  "warning": "必要风险",
  "data_note": "仅覆盖本机可用文本记录，未解析媒体附件。"
}
```

运行：

```powershell
.\.runtime\Scripts\python.exe .\scripts\render_report.py summary.json report.html
```
