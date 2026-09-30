---
name: mail-profile
description: 管理跨项目、多公司和个人邮箱的逻辑 Profile、授权恢复、身份路由与只读检索。用于连接、添加、验证、切换、迁移或移除飞书邮箱、Gmail、Outlook、163、QQ及其他 IMAP 邮箱，或从授权邮箱查找发票、账单和业务附件；不把凭据写入 GLOBAL，也不因已登录状态推断业务身份。
---

# 多租户邮箱 Profile 管理

## 核心边界

- 先读取 `GLOBAL/MAIL_PROFILES.md` 与当前项目身份规则，再解析唯一邮箱 Profile。用户当前明确指定优先，其次为项目条件化路由、项目默认和 GLOBAL 默认。
- 实际邮箱地址、所属主体和服务商必须通过实时回读确认。网页或客户端当前登录、系统默认账号和历史缓存目录都不是业务路由依据。
- 默认只读：搜索、读取和下载附件不得改变已读状态、文件夹、标签或邮件内容。发送、回复、转发、删除、移动及规则修改必须另行取得明确授权并使用对应邮件 Skill。
- 不在 Skill、GLOBAL、项目、Git、聊天或普通命令参数中保存密码、授权码、OAuth token、恢复码、Cookie 或解密后的凭据。
- 认证成功不扩大业务权限；不得跨公司、客户或个人主体混搜。项目写入仍使用项目自己的业务 Skill 和身份规则。

## Provider 路由

- 飞书邮箱：使用现有 `lark-mail`，显式指定对应飞书 `--profile` 与 `--as user`；先回读 `primary_email_address`。
- Gmail 或其他已安装邮箱连接器：使用服务商 OAuth，并核验连接所代表的实际地址；连接器状态不写入 GLOBAL。
- 163、QQ、Outlook或其他通用 IMAP：读取 [references/generic-imap.md](references/generic-imap.md)，使用本 Skill 的只读脚本和本机安全凭据注入，不使用明文配置。
- 发票与账单归集：读取 [references/invoice-collection.md](references/invoice-collection.md)。
- 项目路由和放置规则：读取 [references/project-routing.md](references/project-routing.md)。

## 生命周期

1. 读取 `MAIL_PROFILES.md` 与项目规则，确定目标主体和逻辑名称。
2. 新增前实时核对已有 Profile，禁止覆盖同名或借用其他主体。
3. 按 Provider 完成授权；仅申请当前任务需要的最小读取权限。
4. 回读真实邮箱地址并执行不改变状态的最小搜索。
5. 用户确认非敏感路由后，登记 `MAIL_PROFILES.md`；凭据留在服务商或本机安全存储。
6. 换机时只迁移非敏感路由，重新授权；本机密文不复制。
7. 删除时先列出项目引用和影响，取得明确确认后再移除授权和路由。

## 写后验证

- 报告逻辑 Profile、真实邮箱地址、所属主体、Provider、身份验证结果和只读搜索结果。
- 下载附件时报告邮件标识、原始文件名、哈希和保存路径；不输出邮件中的凭据或无关个人信息。
- 任何项目写入都必须回读目标记录并验证实际项目身份；邮箱查到附件不等于已完成记账、报销或OA。
