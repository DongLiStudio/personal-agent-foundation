# 宿主 Agent 集成

## 图形交互

图形提问、目录选择和确认由当前 Agent 宿主提供。宿主有原生交互工具时使用它；没有时退回普通对话。不要随产品发布自制 GUI。

## 全局 Skill

- Codex：优先使用当前 Skill 安装器；只有明确解析到用户级全局 Skill 目录时才直接同步文件。
- 其他 Agent：读取该宿主当前官方 Skill/扩展说明或设置界面，不根据其他宿主路径猜测。
- 宿主不能安装 Skills 时，保留 GLOBAL 源稿，报告“源稿已安装、宿主尚未启用”，并给出人工入口。

## 全局个性化提示词

安装器不替宿主修改未确认的设置文件。引导用户在当前 Agent 设置中查找类似入口：

- Custom instructions
- Personalization
- Global instructions
- User rules
- System prompt / profile prompt

说明：GLOBAL 是磁盘治理基座；全局个性化提示词是宿主层偏好，两者应同时配置但不能互相替代。

建议用户填写的最小内容：

```text
开始项目工作前，先读取项目 AGENTS.md、README.md、STATUS.md；
GLOBAL 位于 <AGENT_ROOT>/GLOBAL，按任务范围读取对应规则；
不泄露凭据，不把 commit 等同于 push，不递归跟随知识库链接。
```

用户确认保存后，要求其说明已保存到哪个宿主设置入口；无法回读时明确标记为用户确认，而不是程序验证。
