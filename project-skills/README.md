# 项目专用 Skills

## monthly-acceptance：月度大盘数据验收

[方法入口](monthly-acceptance/SKILL.md) · [可视化说明](monthly-acceptance/references/acceptance-guide.html)

从类目 SPU 数量、SPU 价格带、销量、销售额四项结果出发，按变化贡献定位重点，结合市场假设与原始数据核验形成完整报告。正常、异常和未完成环节均在正文可见。方法版本 2.0，发布内容按 Git commit 固定。

这是项目级治理工作流，安装到需要验收的项目后使用。普通市场分析仍由插件的 strategic-analytics 入口处理。此目录独立于默认插件 skills，便于按项目启用。

### 项目依赖

- 已配置可只读访问实际源表和公司映射视角的 Doris MCP；执行范围由项目授权决定。
- 项目根下 `验收/config.yaml`：国家、源表、标准视角、起始月份与核验约束等有效配置。
- 项目根下 `验收/项目范围.md`：当前项目约定的平台完整类目路径、有效时期与来源。
- 按需提供 `验收/内部数据/YYYY-MM/`。Sorftime 仅在具体 Amazon 问题需要时依既有费用授权调用。

项目配置和采购范围由项目自己维护；缺少时先补齐有效输入。敏感凭据使用 MCP/CLI 已有配置。

### 安装与更新

在目标项目根目录，通过 Codex 的 skill-installer 指定本仓库、路径 `project-skills/monthly-acceptance` 和目标 `.claude/skills`。命令行等价方式：

```bash
python3 "$HOME/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo ccchenhuohuo/flywheel-plugin \
  --path project-skills/monthly-acceptance \
  --ref main \
  --dest .claude/skills
mkdir -p .agents/skills
ln -s ../../.claude/skills/monthly-acceptance .agents/skills/monthly-acceptance
```

正式安装可将 `main` 换成已审核的具体 commit。已有同名安装或链接时先核对目标，归档旧版本再更新；安装器会拒绝覆盖既有目录。`.claude` 保存这一份项目方法，Codex 经 `.agents` 链接识别；运行助手据此定位当前项目的验收目录。Claude Code 可直接使用 `.claude` 入口。Codex 的项目目录和符号链接支持见[官方说明](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)。

### 触发

在安装的项目中向 Codex 明确调用 `$monthly-acceptance`，或提出“验收最新服务商月度大盘数据”的任务。Claude Code 中可调用 `/monthly-acceptance`。让执行者先确认到货月份与有效范围，再开始独立验收。

运行产物保存在 `验收/runs/YYYY-MM/<唯一运行号>/`：冻结方法与配置、独立观察、实际证据、报告及按需反馈草稿。历史报告在形成新观察后才按问题调取。`seal` 仅封存文件哈希，完整报告内容和业务放行需要分别复核；报告只落盘。
