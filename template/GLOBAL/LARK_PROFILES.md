# 飞书 CLI 公司 / Profile 对应关系

本文件记录由用户决定在 GLOBAL 统一维护的飞书 CLI 身份映射和治理层默认 Profile。不要记录 App Secret、access token、refresh token 或其他密钥。

Profile 的新增、授权、恢复、迁移、重命名和删除统一使用全局 `feishu-profile` Skill。实时有效性以 CLI 回读为准。

## 当前约定

- GLOBAL 全局默认 Profile：`{{DEFAULT_LARK_PROFILE}}`。
- 项目未覆盖时，飞书命令显式传入 `--profile "{{DEFAULT_LARK_PROFILE}}"`。
- CLI active 只是本机运行状态，不得覆盖本文件的治理默认值。
- 首次安装连接飞书时，默认创建新的飞书应用和新的专用 Profile；不得自动复用本机已有 Profile、active Profile、旧应用或其他项目应用。
- 已有 Profile 最多用于只读冲突检查。复用已有飞书应用/Profile 只能作为用户明确选择的高级迁移/共用路径，并需先确认共享权限、身份路由和审计边界。
- 安装完成后，使用 `feishu-profile` 完成登录，并把授权回读到的真实公司/租户名称、App ID、App 名称和用途补充到下方列表。章节标题和公司名称不得使用程序自拟名称；CLI profile 名只记录在 profile 字段和命令示例中。

## 公司列表

### 待连接（授权后改为真实公司/租户名称）

- CLI profile：`{{DEFAULT_LARK_PROFILE}}`
- GLOBAL 全局默认：是
- 使用方式：`lark-cli --profile "{{DEFAULT_LARK_PROFILE}}" ...`
- 公司/租户名称：授权成功后用官方回读结果或用户确认的真实名称回填。
- App ID、App name：授权成功后由用户确认并回填；不得在公开模板中预置。
