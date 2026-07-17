# 新增 Profile 与首次授权

## 选择流程

优先使用飞书 CLI 官方引导式配置流程。需要沿用既有企业应用时，先使用 `config init` 的模式选择采用原应用；明确需要创建新应用时，才使用 `config init --new --name <Profile>`。只有引导式流程不适用或用户明确选择手工应用时，才使用 App ID/App Secret 备用流程。

`config init --new` 是新建应用门禁，不是 workspace 恢复命令。执行前必须同时确认：当前 workspace 不可见并非临时配置或绑定冲突；GLOBAL、项目路由和已知其他 workspace 没有同一主体的既有应用证据；用户明确接受创建新应用。任一条件不成立时转入 [recovery-and-migration.md](recovery-and-migration.md)。非终端环境不支持采用原应用的交互模式，只说明当前入口受限，不授权改用 `--new`。

所有新增流程都必须满足“只追加、不覆盖”：开始前保存完整 `profile list` 结果；若目标名称已存在，停止创建并核验，不得调用任何可能更新该名称的命令。完成后再次读取完整清单，确认所有原有 Profile 的名称、应用标识和 active 状态未变化。

### 一键创建

1. 运行 `lark-cli config init --help` 核对当前版本参数。
2. 完成上述新建应用门禁并确认目标名称不存在后，使用 `config init --new --name <Profile>` 创建具名 Profile；不得用该命令更新已有同名 Profile。
3. Agent workspace 若拒绝并提示需要 `--force-init`，只有用户明确要求创建独立应用且确认主体后才能添加该参数。
4. 命令阻塞时在后台运行，提取并展示官方配置链接；用户在目标租户完成企业自建应用创建。
5. 回读 `profile list` 与 `config show --profile <Profile>`；不得输出 App Secret。
6. 按主 Skill 的 OAuth split-flow 发起 user 授权。

### 引导式采用原应用

1. 运行 `lark-cli config init --help`，确认当前版本支持的引导参数和 Profile 命名方式。
2. 确认目标 Profile 名称尚不存在，并保存新增前完整 Profile 清单。
3. 使用具名的 `config init` 引导模式，让用户在官方页面选择或采用目标租户的原应用；不要添加强制新建语义的 `--new`。
4. 完成后比较完整 Profile 清单，确认只是追加新 Profile，所有原有名称、应用标识和 active 状态未变化。
5. 回读新 Profile 的应用归属，再发起 user OAuth。

若当前 CLI 版本的引导模式无法以具名追加方式采用原应用，停止并说明限制，再由用户选择新建应用或使用安全凭据备用流程；不得为了复用原应用覆盖默认 Profile。

### 既有应用备用流程

1. 用户确认要复用哪个租户的既有企业自建应用。
2. App ID 可以作为非秘密标识提供；App Secret 不得粘贴到聊天、项目文件或普通参数。
3. 仅通过 CLI 支持的标准输入方式录入 App Secret，例如 `--app-secret-stdin`。
4. 创建具名 Profile 后回读应用与品牌，再发起 user OAuth。

## 命名与重复检查

- Profile 名使用稳定、可读的公司或业务主体名称，不直接用 App ID。
- 创建前运行 `profile list`。同名存在时立即停止新增并检查是否属于同一主体；不覆盖、不更新、不替换，也不创建“修正版”。
- 同一租户因权限边界确需多个应用时，在名称中加入稳定用途，如“公司-财务”；先说明原因和维护成本。
- 新 Profile 不自动设为全局 active；创建后确认原 active Profile 未变化，项目操作显式传 `--profile`。

## 首次授权完成条件

- Profile 出现在实时列表中；
- 新增前存在的全部 Profile 仍存在，名称、应用标识和 active 状态均未改变；
- `auth status --verify` 显示 user 可用且 token 有效；
- `whoami` 返回预期 Profile、应用和用户；
- 任务所需 scopes 已授予；
- 项目局部路由已按需登记，但没有任何秘密或动态 token。
