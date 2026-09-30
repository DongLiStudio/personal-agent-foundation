# 来源与维护边界

- 初始材料：用户提供的 `wechat-readonly-analyst-windows.zip`。
- 初始包 SHA-256：`866538A341AA320DCFDE7B6BA5658DE40EE1404B8C8E7F9E7517689382E673C6`。
- 底层声明：Python `wechat-cli` 0.2.4，Apache-2.0；原包指向 `https://github.com/freestylefly/wechat-cli`，但未携带可验证 commit 或发布签名。
- 本加固版：仅保留 Windows 所需源码和 `init`、`sessions`、`history`、`search`、`stats` 命令；新增显式 Profile、DPAPI 绑定、双重授权、硬上限、异常残留清理和回归门禁。

由于初始包缺少确定上游 commit，本文件只记录可验证的输入哈希，不宣称源码与某个公开仓库版本逐字一致。后续更新必须重新审计 diff，并更新本文件的来源和验证证据。
