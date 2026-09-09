# 更新记录

## 0.2.10 — 2026-09-10

工具说明与能力路由改进已于 2026-09-09 部署并分发；2026-09-10 补齐正式 Release，并同步项目验收内容清理后的文档。

- 精简 MCP 全局说明，完整治理规则由主 Skill 或 `flywheel_describe_semantics` 按需读取；兼容尚未读到完整规则的旧版薄 Skill。
- 明确市场分析、数据时效、字段覆盖、SPU 指标缺口和项目验收的处理路径。字段覆盖不能证明采集完整，销量不能替代 SPU 数量。
- 移除误放在本仓库的项目验收模块及其安装链接；仅在当前环境确有支持相关问题的项目 Skill 时使用其入口。
- 保持 12 个工具的输入参数和原有分析计算口径。`describe_semantics` 保留 `rules` 字符串数组，并增加 `capabilities` 说明。

生产全局说明由 2,173 缩至 302 字符；这是说明长度变化，不是实际 token 或响应延迟测量。发布已核对工具参数一致性，并完成数据状态与德国类目趋势的前后对照。本轮没有增加 SPU 查询指标。

已有 Codex 用户更新：

```bash
codex plugin marketplace upgrade flywheel
codex plugin add flywheel-analytics@flywheel
```

更新后新建任务以加载新版 Skill 和工具说明；若应用仍显示旧版，完全退出并重新打开 Codex。首次安装与认证配置见 [README](README.md)。

## 0.2.9 — 2026-09-08

- 新增原生 Codex 插件清单，通过 `FLYWHEEL_MCP_TOKEN` 声明 MCP 认证，修复安装后缺少认证头导致的 HTTP 401。
- 保留 Claude Code 配置，两端共用 Skill 与 MCP 服务。
- 补充安装、升级和桌面客户端环境变量说明。

详情见 [v0.2.9 发行说明](https://github.com/ccchenhuohuo/flywheel-plugin/releases/tag/v0.2.9)。
