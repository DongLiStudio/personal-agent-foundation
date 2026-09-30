# 离线校验合同

`scripts/exam_guard.py` 不访问网络、不修改飞书，也不替代真实公式/UI/权限测试。输入 UTF-8 JSON；分值建议用十进制字符串，结果分值用字符串避免二进制浮点误差。

## Manifest

```json
{
  "schema_version": 1,
  "exam_id": "example-exam",
  "version": "1.0",
  "total_max": "100",
  "rounding": {"places": 2, "mode": "HALF_UP"},
  "sections": [
    {"id": "objective", "raw_max": "2", "contribution_max": "40"},
    {"id": "practice", "raw_max": "10", "contribution_max": "60"}
  ],
  "questions": [
    {
      "id": "S01", "section_id": "objective", "type": "single",
      "stem": "下面哪个数字等于一加一？", "source": "虚构工具演示",
      "max_score": "2", "required": true,
      "options": [{"key": "A", "text": "二"}, {"key": "B", "text": "三"}],
      "answer": "A"
    },
    {
      "id": "D01", "section_id": "practice", "type": "practical",
      "stem": "提交一份包含输入与计算过程的演示记录。", "source": "虚构工具演示",
      "max_score": "10", "required": true,
      "rubric": [
        {"id": "D01.1", "description": "输入完整", "max_score": "4"},
        {"id": "D01.2", "description": "过程可复核", "max_score": "6"}
      ]
    }
  ]
}
```

这只是数据结构示例，不是正式命题标准。正式单选按确认合同设置选项数。支持 `single`、`multi`、`fill`、`dynamic`、`essay`、`practical`：

- single：`options` 唯一 key/text，`answer` 为合法 key。
- multi：`answer` 为唯一 key 数组；严格集合相等得全分，顺序无关。部分分规则不在此工具范围内，需另外实现并测试，不能冒充支持。
- fill：`accepted_answers` 为明确批准的字符串集合，完全匹配；本工具不自动 trim、忽略大小写或模糊匹配。需要规范化时先经合同确认并保留原值及变换证据。
- dynamic/essay/practical：`rubric` 子项满分之和等于题满分；具体人工判定不由脚本执行。

各题 `max_score` 为正，模块原始满分等于其题目满分之和，模块最终贡献之和等于总满分。附加题作为独立模块表达。

## 已提交答卷与人工分

```json
{
  "exam_id": "example-exam",
  "version": "1.0",
  "submitted": true,
  "answers": {"S01": "A"},
  "manual_scores": {"D01": "6.5"}
}
```

`submitted:false` 是草稿/未提交，不能生成最终成绩；已提交客观漏答按未答0分，人工缺值保留 pending，不能用0占位。合法0就是已评分0分。人工总分须在0至该题满分之间；脚本只校验范围，证据及评分点由阅卷人复核。

实际飞书单选/多选可能储存完整选项对象或文本。归一化成 key 前必须通过稳定 field ID＋真实选项 ID/文本唯一映射，保留原始答卷快照，不用首字母猜答案；未知选项应报错。

## 映射审计

Manifest 的 `layout` 定义期望结构；snapshot 独立来自实际回读。最小字段：

每题可显式指定 `field_name`、`field_description`、`form_title`、`form_description`，默认分别为题号、stem、题号、stem；包含分值/级别/材料链接时在这些属性中保留完整原文。工具同时验证这些期望与题目合同一致，不能为通过检查而裁掉真实名称或描述中的差异。

- `fields`：`field_id, question_id（系统字段为null）, name, type, description, options[{key,text}]`。
- `forms`：`form_id, question_order[], questions[{question_id,field_id,title,description,type,options,required}]`。
- `grids`：`[{table_id,view_id,field_order:[field_id,...]}]`，用于多表/多Grid；此模式 `fields` 与 `forms` 每项均须带 `table_id`，脚本检查归表。兼容单表 `grid_order`；若同时提供，两者都检查。
- snapshot 另含 `evidence:{source,captured_at,reference}`，`source` 明确 `live_readback` 或 `synthetic`。即便声明为 live_readback，脚本也不能证明来源真实，需操作者审查原始回读引用。

不要从期望 layout 复制生成“线上实际快照”。输出只能称归一化快照匹配，不能称“线上全部验收通过”。公式、选项展示方向、页面模式、权限设置和跨表/多评委聚合仍需额外检查。

工具当前只支持每道逻辑题的一个主要表单控件。实操附件等辅助字段可列为 `question_id:null` 进行字段快照比对，但不代表已验证辅助控件与逻辑题的关联或分页；必须另做全控件清单审计，不能省略。平台原始字段类型须按已证实的控件语义映射为工具题型，保留原始API响应及类型映射证据；不得伪造实际类型。

## 运行

在 Skill 目录执行：

```text
python scripts/exam_guard.py validate manifest.json
python scripts/exam_guard.py grade manifest.json response.json
python scripts/exam_guard.py audit manifest.json snapshot.json
```

输出 JSON，退出码：0有效/完成/匹配；2输入无效；3审计差异；4待人工评分或未提交。调用者必须检查退出码和状态，不把合法 JSON 当成功。

运行全部行为回归：

```text
python -m unittest discover -s scripts -p "test_*.py"
```
