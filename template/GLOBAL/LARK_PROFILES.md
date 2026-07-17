# 飞书 CLI 公司 / Profile 对应关系

本文件记录由用户决定在 GLOBAL 统一维护的飞书 CLI 身份映射和治理层默认 Profile。不要记录 App Secret、access token、refresh token 或其他密钥。

Profile 的新增、授权、恢复、迁移、重命名和删除统一使用全局 `feishu-profile` Skill。实时有效性以 CLI 回读为准。

## 当前约定

- GLOBAL 全局默认 Profile：`{{DEFAULT_LARK_PROFILE}}`。
- 项目未覆盖时，飞书命令显式传入 `--profile "{{DEFAULT_LARK_PROFILE}}"`。
- CLI active 只是本机运行状态，不得覆盖本文件的治理默认值。
- 安装完成后，使用 `feishu-profile` 完成登录并把公司、App ID、App 名称和用途补充到下方列表。

## 公司列表

### 默认组织（安装时配置）

- CLI profile：`{{DEFAULT_LARK_PROFILE}}`
- GLOBAL 全局默认：是
- 使用方式：`lark-cli --profile "{{DEFAULT_LARK_PROFILE}}" ...`
- 公司、App ID、App name：授权成功后由用户确认并回填；不得在公开模板中预置。
