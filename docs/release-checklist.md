# 发布检查

- 模板清单与 `template-manifest.json` 一致。
- 所有占位符属于白名单，fixture 渲染后无残留。
- 没有真实个人路径、项目、公司、Profile、账号、App ID、邮箱、token 或私钥。
- 全部文本 UTF-8 无 BOM、LF。
- 模板源目录在测试前后哈希一致。
- 已有目标拒绝覆盖，未知占位符阻断，中文和空格路径通过。
- Skill 结构、界面元数据、引用和脚本测试通过。
- Windows、macOS、Linux CI 全部通过后才能宣称跨平台实机验证。
- README、Apache-2.0 LICENSE 和安装说明与当前行为一致。
- 发布、remote、首次 push 和 Release 均具有当前用户明确授权。
