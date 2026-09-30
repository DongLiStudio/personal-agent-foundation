# 安全接入与 API

## 版本与官方依据

开始时核查实际部署版本和对应官方源码；历史端点仅是查找线索。

- 官方仓库：https://github.com/allinssl/allinssl
- API 实现：backend/app/api/access.go、workflow.go、report.go、monitor/monitor.go。
- 前端接口：frontend/apps/allin-ssl/src/api/access.ts、workflow.ts、monitor.ts。
- 工作流引擎：backend/internal/workflow/workflow.go、executor.go、models.go。
- 续期：backend/internal/cert/apply；监控：backend/internal/monitor 和 backend/scheduler/monitor.go。
- 本流程在 2026-09-16 使用过 v1.1.2 环境；源码参考过 1.1.2/1.1.3。所有版本仍需现场核查，不自动升级。

## 接入步骤

1. 定位唯一 ALLinSSL 实例、受限管理端口与服务归属，实时核验宿主指纹、主体、容器及挂载；认证失败不隐式换账号。
2. 优先受保护 API Key/Secret 注入；没有 Key 时通过已授权本机/隧道后台建立或启用它。需要用户登录时打开正确入口，不读取浏览器 Cookie 或抓取令牌作为替代。
3. 经用户明确允许时可只读 settings.db 中 settings 表的 api_key 项，在进程内使用；核对版本 schema，参数化查询，仅取该项。不得复制整库或读取全部 settings。SQLite readonly/immutable 只能在已核查更新与 WAL 行为的条件下使用，避免误读旧值。
4. 先调用只读接口确认认证格式；401/404 不解释为产品无 API，不猜测多套 token。
5. 历史版本的签名为 api_token = MD5(timestamp + MD5(api_key))，timestamp 为 Unix 秒，作为 POST 表单字段发送，而非认证头。以对应版本 middleware 确认；管理 API 走本机/加密 SSH 隧道或已验证 HTTPS。
6. API Key、密码、云密钥、私钥不进入聊天、日志、Git、环境转储或命令行参数；在内存、受限 Secret 或受限临时文件中使用。需要持久化授权时只写入 ALLinSSL 的受保护授权存储，不额外生成“备份配置”。

## 最小接口路由（现场确认）

| 对象 | 发现 | 修改与验证 |
| --- | --- | --- |
| access | access/get_list | add_access、upd_access、test_access |
| workflow | workflow/get_list | add_workflow、upd_workflow、active、execute_workflow、get_workflow_history |
| report | report/get_list | 按当前 report API 确认添加、测试接口 |
| monitor | monitor/get_list | add_monitor、upd_monitor、set_monitor、get_monitor_info |

接口位于 /v1/ 下，HTTP 状态与业务 code 都应检查。更新 access 的历史接口要求同时提供 id、name、config；只改名称时 config 原样在内存传递，并比较前后语义相同。认证方式切换同样只改 mode/key/password 等必要字段，不改变 ID 或删除其他配置。不要把服务商 config 与 provider_data 混为一项，按版本验证真实存储和响应。

## 输出与入库限制

原始响应中的 config/content/provider_data 可能是嵌套对象，也可能是内嵌 JSON 字符串，含密码或私钥。不得打印或整体导出 access/report/证书/工作流数据；从完整响应递归删几个字段也不能证明无泄露。

从明确可信的目标字段重新构建最小摘要（对象 ID、类型、计划中的非敏感名称/域名、状态、周期、证书公开指纹与到期时间），不把原始字段集合批量拷贝。不输出任意错误 msg 或异常响应正文，日志只报告错误类别、接口路径和状态码；私密错误详情限受保护诊断。

持久化工作流模板从干净结构构建，只有授权 ID 引用，无 provider_data、私钥、Cookie、邮件密码或 webhook URL。参考现有工作流时在内存只复用经核对的通知结构与引用；不保存完整导出。遇审批拒绝完整导出，使用无凭据摘要和从零构建的模板，不通过另一路径完成同一导出。

使用临时 SSH 私钥时设权限与异常清理；写入 ALLinSSL、连接测试成功后删除临时副本。私钥存储必须另行安全备份，不能依赖 GLOBAL 恢复秘密。
