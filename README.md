# flywheel-analytics

Codex / Claude Code 插件：用受治理的只读 MCP 做大盘市场分析——趋势、份额、增长与贡献、排名与变化榜、
价格带、品牌集中度与单品牌多月序列、标准类目与平台原始类目导航、单 SKU 搜索与逐月轨迹。

装好之后直接用自然语言提问即可，例如：

> 最近三个月大盘整体表现怎么样？
> 2026-05 Amazon US 的品牌集中度如何，CR5 是多少？
> 搜一下 Amazon US 卖得最好的三脚架，看它今年以来的价格走势。

所有可见数字由服务端计算并携带复现戳（`release_id` + 参数回显）。当前合法发布链上的 release 可按相同参数复现聚合结果；可绑定列表见 `flywheel_data_status`。
晚到兄弟节点、冲突或失活可能使旧 release 不再可绑定。SKU 明细只保留发布链最近 3 个 release 的在线切片，归档后明确披露。

## 安装前准备

| 依赖 | 说明 |
|---|---|
| 客户端 | Codex 或 Claude Code，需支持插件；本次兼容性验证使用 Codex CLI 0.153.4、Claude Code 2.1.263 |
| 访问令牌 | 环境变量 `FLYWHEEL_MCP_TOKEN`，向插件维护者申请 |
| 网络 | 能访问 MCP 端点（默认 `https://voc.ulanzi.com:28081`） |

在 shell 配置（如 `~/.zshrc`）中加入下面一行，替换令牌占位符，**新开一个终端**后从该终端启动客户端：

```bash
export FLYWHEEL_MCP_TOKEN="你的令牌"
```

令牌只放在本机环境变量中，不写进插件、仓库或 `config.toml`。可以用
`test -n "$FLYWHEEL_MCP_TOKEN" && echo "令牌已设置"` 检查当前终端是否设置了变量，不打印令牌。

**桌面端 / IDE 注意**：从 Dock、开始菜单或 IDE 启动的进程不一定继承终端环境；只改 `.zshrc`
并重启应用未必生效。macOS 可在已加载令牌的终端中执行以下命令，再完全退出并重新打开客户端：

```bash
launchctl setenv FLYWHEEL_MCP_TOKEN "$FLYWHEEL_MCP_TOKEN"
```

该设置需在注销或重启系统后重新执行。Windows 请把 `FLYWHEEL_MCP_TOKEN` 配为用户环境变量，
并重启客户端及启动它的 IDE。CLI 用户直接从已设置变量的终端运行 `codex` 或 `claude`。

## 安装：Claude Code

在 Claude Code 会话里依次执行两条命令：

```
/plugin marketplace add ccchenhuohuo/flywheel-plugin
```

```
/plugin install flywheel-analytics@flywheel
```

按提示确认后重启 Claude Code。

## 安装：Codex

在终端执行：

```bash
codex plugin marketplace add ccchenhuohuo/flywheel-plugin
codex plugin add flywheel-analytics@flywheel
codex mcp get flywheel --json
```

输出的 `transport.bearer_token_env_var` 应为 `FLYWHEEL_MCP_TOKEN`，然后完全重启 Codex 并新建会话。
插件内已声明认证，不需要另外添加同名的用户级 MCP。两端共享 Skill 和同一个服务端。

### 已安装旧版的 Codex 用户

先更新市场快照，再重新安装插件，让原生清单进入插件缓存：

```bash
codex plugin marketplace upgrade flywheel
codex plugin add flywheel-analytics@flywheel
```

新版尚未发布或暂时无法升级时，可以用 Codex 官方 CLI 写入用户级认证配置：

```bash
codex mcp add flywheel \
  --url https://voc.ulanzi.com:28081/flywheel/mcp \
  --bearer-token-env-var FLYWHEEL_MCP_TOKEN
```

这会在 `~/.codex/config.toml`（自定义 `CODEX_HOME` 时在其目录下）创建或更新同名服务器，等价于：

```toml
[mcp_servers.flywheel]
url = "https://voc.ulanzi.com:28081/flywheel/mcp"
bearer_token_env_var = "FLYWHEEL_MCP_TOKEN"
```

如果之前给同名服务器设置过其他参数，先备份对应配置再执行。**不要修改插件缓存目录里的文件**，
更新插件会覆盖它们。保存配置后完全重启 Codex 并新建会话。

升级成功、确认缓存中已有 `.codex-plugin/plugin.json` 后，如果曾添加上述临时配置，执行
`codex mcp remove flywheel` 移除用户级覆盖，再运行 `codex mcp get flywheel --json`，确认插件本身
仍提供 `FLYWHEEL_MCP_TOKEN`。最后重启并做下面的端到端验证。

## 验证（两端相同）

```
/mcp
```

看到 Flywheel 服务器处于 connected（Claude 插件可能显示为 `plugin:flywheel-analytics:flywheel`）。
再问一句"数据是什么时候的？多久更新一次？"，
能返回当前数据范围与水位月份就说明端到端通了。

如果连接失败，依次检查：

1. Codex 的 `codex mcp get flywheel --json` 是否包含正确的 `bearer_token_env_var`；为空时先升级插件
   或使用上面的临时修复。
2. **客户端进程**是否能读取 `FLYWHEEL_MCP_TOKEN`；当前终端有变量，不代表已启动的桌面应用也有。
3. 令牌是否正确、能否访问上表里的端点。

`codex mcp get` 只验证配置；`auth_status` 的 `Unknown` / `unsupported` 也不能单独证明令牌失效。
以实际连接和 `flywheel_data_status` 调用成功为准。
**插件不会用缓存或记忆中的数字兜底**——MCP 不可用时它会如实说明并停止。

## 更新与卸载

Claude Code 更新：

```
/plugin marketplace update flywheel
/plugin update flywheel-analytics@flywheel
```

Claude Code 卸载：

```
/plugin uninstall flywheel-analytics@flywheel
```

Codex 更新用上面的 `marketplace upgrade` + `plugin add`，卸载用：

```bash
codex plugin remove flywheel-analytics@flywheel
```

卸载插件不会删除手动添加的用户级 MCP；如果配置过临时修复，另执行 `codex mcp remove flywheel`。

## 能力边界

<!-- BEGIN GENERATED CAPABILITIES -->

| 用户问题 | 当前支持与处理路径 |
|---|---|
| 市场趋势、份额、增长、品牌、价格带、类目、SKU | 已支持，选择对应的受治理分析工具。 |
| 更新到哪月、发布是否陈旧、历史结果能否复现 | `flywheel_data_status`：可用月份、上游状态、可绑定 release 与 SKU 切片在线状态。 |
| 字段覆盖、未分类、检疫情况 | 使用分析响应的 `coverage_notes`、`caveats`；`data_status` 披露最新月部分字段空值率。仅限响应实际披露的月份与范围，全站点披露不能定位某类目或品牌，也不能证明采集完整。 |
| SPU 数量或变化 | 当前分析 MCP 未提供 SPU 去重数量；销量、源行数、SKU 搜索候选数都不能替代。明确说明指标缺口，不反复尝试销量工具。 |
| 漏采、采集完整性、异常验收 | 当前分析 MCP 不提供验收结论；字段覆盖与已有查询结果不足以判定漏采。 |

SPU／验收问题先说明上述边界。仅当当前环境确有相关项目验收 Skill 且其声明支持该问题时，
按其入口与前置条件处理；否则说明缺少可用验收入口，不编造安装路径。
项目验收不是普通市场分析的前置条件。
已有字段覆盖披露只能回答对应字段与范围，不能据此断言“没有漏采”或“验收通过”。
项目验收按其自身口径输出，不作为本插件市场分析的替代数据源。

<!-- END GENERATED CAPABILITIES -->

- **月度粒度**，没有周/日；数据起点 2024-01，上界为当前水位（最大完整月，按次月 16 日交付边界判断），实际范围以 `flywheel_data_status` 返回为准。
- 指标是**市场估算**：销量为估算件数、金额为价×量推导值，不是 GMV、实付或订单数。
- 贡献与结构变化是**数学分解，不是因果**；插件不做预测，也不给进入/退出、定价、预算类经营建议。
- **缺失不等于零**：'未分类' 是独立桶，映射存在但当月无观察表述为"无观察"，超出水位表述为"尚无完整数据"。
- 跨站点本币金额不可相加，需按站点分别展示或改用人民币口径（服务端按 release 冻结的汇率快照换算）。
- 价格带为政策固定分桶，不支持自定义；平台原始类目只到 L3；不接受任意 SQL。

这些不是 bug，是治理约束。插件遇到越界请求会拒绝并给出合规的替代路径。

## 给维护者

本仓库是**插件分发子集**，只包含使用者安装所需的内容。三层架构（Doris 治理表 + 薄 MCP + 方法论文本层）、构建管线、断言与验收手册在内部仓库，
不随插件分发。Skill 承载完整规则与能力路由；MCP instructions 保持简短，完整规则也可经 `flywheel_describe_semantics` 按需读取，具体查询附带响应警示。

### 双客户端打包约定

| 消费端 | 插件清单 | MCP 认证来源 |
|---|---|---|
| Claude Code | `.claude-plugin/plugin.json` | 根目录 `.mcp.json` 的 `headers.Authorization = "Bearer ${FLYWHEEL_MCP_TOKEN}"` |
| Codex | `.codex-plugin/plugin.json` | 原生清单内联 `mcpServers.flywheel.bearer_token_env_var = "FLYWHEEL_MCP_TOKEN"` |

Codex 清单内联声明完整的同名服务器，覆盖默认发现的 Claude MCP 条目，避免依赖 Claude `headers`
字段的自动转换。根目录 `.mcp.json` 保留 Claude 格式；Skill 共用 `skills/strategic-analytics/`。
现有 `.claude-plugin/marketplace.json` 已用两个 CLI 实测可安装，无需维护第二套市场目录。

发布制品必须同时包含 `.claude-plugin/`、`.codex-plugin/`、`.mcp.json`、`skills/` 与本 README，
注意打包时不要漏掉隐藏目录。两份 `plugin.json` 的名称和版本、两处 MCP 的 URL 与令牌变量必须一致。
当前源码版本为 0.2.10；发布时同步更新两份清单，旧版缓存不会因只修改源码而自动刷新。

配置依据：[Codex MCP 配置](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)、
[Codex 插件构建](https://learn.chatgpt.com/docs/build-plugins)、
[Claude Code 插件参考](https://code.claude.com/docs/en/plugins-reference)。
OpenAI 的 [Claude 插件提交转换说明](https://developers.openai.com/plugins/guides/submit-claude-plugin)
讲的是提交门户流程；本仓库的客户端兼容性以原生清单和实际 CLI 加载结果验证。
