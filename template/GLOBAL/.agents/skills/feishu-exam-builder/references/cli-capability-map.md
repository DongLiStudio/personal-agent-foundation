# CLI 能力发现与证据等级

此表是操作入口，不是冻结 API 参数。每次执行先读当前安装的 `lark-shared` 与业务 Skill；版本不一致时用 `lark-cli skills read` 获取 CLI 内嵌说明，再查 `--help`/`schema`。业务调用始终显式 Profile 与 user；不要因能力表过期自动升级 CLI 或重授权。

| 任务 | 发现入口 | 必须获取/回读 |
|---|---|---|
| 身份 | `lark-cli auth whoami` | 当前 Profile、user、所属主体 |
| Wiki 定位/递归 | `wiki +node-get`、`wiki +node-list --help` | node/object token、父节点、分页完整性 |
| 文档读取/写入 | `docs +fetch` 与 `lark-doc` 当前创建/更新指南 | 正文、revision、附件、父节点 |
| Base/字段/视图 | `base --help`、`lark-base` 各对象指南 | 实际 base/table/field/view ID 与类型 |
| 公式 | `lark-base` field-formula | 支持语法、解析后表达、实际计算值 |
| Form 问题 | `base +form-questions-list/update --help` | 完整属性及顺序；update 可能全替换 |
| Form 名称/说明 | `base +form-get/update --help` | 名称、说明、真实 form/view ID |
| Form 分享范围 | `base +form-share-get/update --help` | enabled、access_scope、anonymous、require_login |
| Base 高级权限 | `lark-base` advanced-permission-and-role | 角色、成员/群、表/字段/记录权限 |
| 群创建与成员 | `im +chat-create --help`，成员方法先 `schema` | chat_id、群主、private、成员和权限 |
| Drive/Wiki 权限 | `lark-drive` / `lark-wiki` 对应权限指南 | 原继承及直接授权，防止扩大父目录权限 |

2026-09-30 在 CLI 1.0.96 的帮助中确认：`+form-update` 提供名称/说明；`+form-share-update` 提供 invite/tenant/anyone、是否启用、匿名与登录开关，单次只改一个属性且 false 必须显式传值；没有从这两个快捷入口确认到一页一题、每日限制、通知、结果跳转、指定邀请群。这只说明快捷入口的边界，不证明整个官方 API 无此能力。

缺能力按顺序：Shortcut → 已注册 API/schema → `lark-openapi-explorer` 官方索引与接口文档 → 获授权的 UI。原生接口必须确定方法、路径、参数、scope、支持 user 与否，不猜端点。优先获取 [飞书官方 OpenAPI 文档索引](https://open.feishu.cn/llms.txt)。

原生问卷并不自动拥有正确答案与分值，自动判分由关联 Base 公式/既有流程承载，见 [飞书问卷常见问题](https://www.feishu.cn/hc/zh-CN/articles/990945803159-飞书问卷常见问题)。未来产品变化以实时官方文档和实际界面为准。

证据等级必须明确：

- `API回读`：某设置或对象的真实返回值。
- `UI回读`：重新打开设置后看到真实控件值，记录表单和时间。
- `独立用户实测`：非拥有者账号的允许/拒绝与实际提交结果。
- `离线验证`：本地数学、manifest、映射快照检查，不等于前三者。
- `用户确认`：用户完成界面后确认；不能改写为独立实测。

不要为“全自动”承诺虚构能力；优先自动完成可完成部分，必需人工项逐项教学并等待回读后才放行。
