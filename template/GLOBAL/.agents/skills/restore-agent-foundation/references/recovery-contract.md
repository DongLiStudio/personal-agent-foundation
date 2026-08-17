# 恢复契约

## 适用对象

本 Skill 处理已经存在或部分存在的 Personal Agent Foundation。最常见输入是用户整体复制到新电脑或新 Agent 宿主的一棵 Agent 根目录，而不是空目录首次安装。

## 权威关系

- 当前复制后的 Agent 根是用户数据主体。
- `GLOBAL/.agents/skills/` 是自维护 Skill 权威源。
- `GLOBAL/FOUNDATION_STATE.json` 记录上次安装根，供换机后精确识别旧路径。
- 用户级 Skill 目录只是宿主安装副本；可以在确认和备份后由权威源恢复。
- 项目 Git 历史、未提交文件和外部知识库不属于可覆盖模板。

## 状态机

```text
discover → audit → plan → confirm → repair → interactive-gates → verify → complete
```

- `audit`、`plan` 和 `verify` 默认只读。
- `repair` 必须同时提供计划文件和用户确认的 `plan_sha256`。
- 计划后源文件发生变化时拒绝写入。
- 交互授权失败时停在对应门禁，保留已完成证据；恢复后继续，不重复安全写入。

## 自动修复边界

允许在确认后自动处理：

- 精确旧 Agent 根路径替换。
- UTF-8 BOM 与 CRLF 规范化。
- `FOUNDATION_STATE.json` 更新。
- 内部链接目标随根目录迁移；明确提供 Vault 目标时重建 Obsidian 链接本体。
- 缺失的宿主 Skill 安装副本；不同副本需额外确认后替换并备份。
- GLOBAL 缺少 `.git` 时初始化本地仓库，不提交、不创建 remote。

必须阻断或等待人工确认：

- GLOBAL 核心文件缺失且没有可信恢复源。
- 模板占位符残留。
- 目标、父目录或 Skill 安装路径包含未知链接/reparse point。
- 文件在计划后改变。
- GitHub、飞书、Obsidian、服务器、宿主登录或权限缺失。
- 任何覆盖项目文件、删除旧根、修改 Vault 内容、commit、push 或远程权限的动作。

## 扫描边界

- 不跟随 symlink、Junction 或 reparse point。
- 不进入 `.git`、`.idea`、构建目录、依赖目录或恢复备份目录。
- 不读取 `.env`、私钥、证书和已知凭据文件内容。
- 路径重写只处理受支持文本格式中的旧根精确形式，不做模糊字符串替换；换行、BOM 和基座占位符门禁只治理 `GLOBAL`，不格式化项目代码、项目模板或业务资产。
- 报告只记录相对路径、必要的链接目标目录路径、哈希、数量和状态，不读取或记录链接目标中的文件内容。

## 验收

确定性验收至少包含：

- GLOBAL 核心文件存在且状态文件指向当前根。
- 无 BOM、CRLF、基座白名单占位符和已知旧根的 native、正斜杠、反斜杠或 JSON 转义残留；项目自身普通模板语法不误报。
- 项目路径存在，三入口文件齐全。
- 自维护 Skill 权威源与所有受管宿主副本逐文件一致。
- GLOBAL Git 存在。
- 链接只验证链接本体和目标可达，不遍历外部目标。

交互验收至少包含 GitHub、飞书、Obsidian、服务器和当前宿主的实时发现与身份/可用性回读。服务器验收必须先选定 Profile、核验可信主机指纹，再做有界只读连接；不得仅因 `ssh` 命令存在就判定通过。不能自动验证的项目必须明确标记，不能推断为通过。
