# 执行契约 v3

## 阶段与完成条件

| 阶段 | 必须留下的记录 | 可以进入下一阶段的条件 |
|---|---|---|
| 冻结 | run.json、inputs、plan.json | 四国或用户明确限定的站点、所有历史、四层、MoM/YoY、固定价格带与阈值可复核 |
| 全景扫描 | 每个计划任务的实际 SQL、全部结果页、开始/结束事件 | 所有必查任务成功；失败可恢复，不能从计划删除 |
| 独立观察 | checks / candidates / cases / samples.json | 自然月比较、贡献守恒、全体候选已经程序生成并冻结 |
| 调查 | decisions、补充 evidence、sample-reviews.json | 每个候选有有据处置；重要疑点缺证时明确待核、影响和行动 |
| 历史重验 | historical-recheck.json | 所有开放历史问题按本次证据复验；独立召回与历史提示召回分开 |
| 收尾 | 结束指纹、validation.json、报告.md、audit.html | 结束指纹在最后一次数据查询之后；独立核验无缺失才可称执行完成 |
| 封存 | sealed.json | 将执行状态与使用判断一起封存；不把“有文件”当业务通过 |

固定基础任务包括原始/标准指纹、原始完整路径逐月分布、完整键双向对账、国家与标准 L1/L2/L3 的四项结果、固定价格带、SPU 和品牌的正负变动/抵消/进出，以及按固定种子在当前各 L3 抽取的语义样本。抽样标题依次使用 product_title、product_title_cn、sku_title 的非空值，原始类目保留完整路径及路径数；聚合标题、链接和路径只是样本入口，多标题、多路径或父子归属变化必须展开原始 SKU，不能拿 MAX 字段代替全部子体核验。抽样覆盖的是当前商品身份与归属；历史语义错误尚需按风险补查，不能称全历史逐商品已核实。

标准层级同时观察但相互重叠，不跨层累加；价格带按 SPU 销售额/销量计算，仅正值且细行有效时入有效带，其他保留在 -1 未定价组。相邻观测不一定是相邻自然月。贡献中的单边缺失只表示观测进入/退出，不能推出市场销量为零。

## 命令

首次从安装目录运行 `start`，随后使用运行包冻结的脚本：

```sh
python3 .claude/skills/monthly-acceptance/scripts/acceptance_run.py start --month 2026-07 --base 验收
python3 <RUN>/inputs/skill/scripts/acceptance_run.py scan <RUN>
python3 <RUN>/inputs/skill/scripts/acceptance_run.py analyze <RUN>
python3 <RUN>/inputs/skill/scripts/acceptance_run.py drill <RUN> --candidate-id <ID>
python3 <RUN>/inputs/skill/scripts/acceptance_run.py query <RUN> --sql-file <SQL> --label <目的>
python3 <RUN>/inputs/skill/scripts/acceptance_run.py record <RUN> --file <处置JSON>
python3 <RUN>/inputs/skill/scripts/acceptance_run.py finish-scan <RUN>
python3 <RUN>/inputs/skill/scripts/acceptance_run.py validate <RUN>
python3 <RUN>/inputs/skill/scripts/acceptance_run.py render <RUN>
python3 <RUN>/inputs/skill/scripts/acceptance_run.py seal <RUN>
python3 <RUN>/inputs/skill/scripts/acceptance_run.py verify-seal <RUN>
```

`scan` 串行执行并自动跳过已有、完整且哈希有效的任务。一次失败有政策规定的有限重试，仍失败则记录后继续其他任务；修复原因后重跑相同命令。禁止为绕开失败在原包更改代码、政策、范围、SQL。方法变化新建运行；旧运行保留失败。`finish-scan` 在全部下钻完成后执行；之后如果补做查询，须重建收尾指纹（新关联运行，或未封存时显式再次执行并保存新证据，不能复用旧收尾）。

`query` 是自定义取证，返回有限行数，不自动增加全景覆盖率。需要完整明细时用 `drill` 的完整分页，或在新版本扩展受验证的任务计划。`drill` 返回候选单元的全部 SPU 双期结果；它不会自动确定原因。逐项核对前/后期头部和变动贡献群，尾部停止必须说明 SPU 数、价格带、销量、金额四项残余影响。

本地运行要求 Python 3.11+、PyYAML、MCP Python SDK，以及已有可用的 Doris MCP stdio 服务。默认读取 `~/.codex/config.toml` 的 `mcp_servers.doris`；可用 `--mcp-config` 指定相同结构的配置。仅使用已有凭据，配置值不进入运行包。没有该接入时不要伪造完成，可实现同一记录契约的工具适配器后实测。只读 SQL 校验是防误操作约束，数据库账户本身也应具有适合验收的只读权限。

## 输入与政策

- `验收/config.yaml` 与 `项目范围.md` 是已有项目事实。
- `policies/default.json` 是初始排查政策；`验收/policy-overrides.json` 可显式覆盖阈值和价格带。阈值只是召回/优先级规则，不是已证明最优的统计异常阈值，也不自动构成缺陷。
- `验收/open-issues.json` 是开放问题数组：`issue_id, site, path`（JSON 数组字符串）, `kind`（可选）, `status, question`。在独立候选冻结后载入；逐项填写本次 review_state、evidence_ids、判断，关闭状态必须明确。没有清单则历史召回率未知。
- `验收/内部数据/YYYY-MM/` 有文件时冻结到 inputs/internal。比较前写清时间、币种、退货、平台、SPU/品牌口径；`internal-reconciliation.json` 应包含输入引用、计算、差异与限制。无文件不虚构内部对拍。
- 预期采集节点/有效期应在 `scope-contract.json` 中维护来源、节点完整路径、有效起止月和清单是否完整；当前交接文件含父节点与年份不明确的变更，不能从已观测路径反推所有应采节点。结构化契约接入前，该限制持续显式披露。

运行频率与数据粒度分开：每周可对同一月重推批次运行；当前 CLI 每次显式指定最新应验收月份，不自动建立定时任务，也不把未到货的当月数据当成必须已有。

## 记录结构

处置文件为一个对象或对象数组：

```json
{
  "candidate_ids": ["cand-实际ID"],
  "title": "结论短句",
  "scope": "国家、路径、月份与适用边界",
  "facts": "前后值、变化、影响及同范围证据",
  "reason": "为何继续、关闭或待核；只记可复核的简要依据",
  "counterevidence": "已检查的相反解释与尚未证实的部分",
  "next_action": "可执行的补证/修复请求，或停止理由",
  "evidence_ids": ["ev-实际ID"],
  "status": "needs_evidence",
  "business_verdict": "undetermined"
}
```

`status` 为 confirmed_defect / supported_change / low_impact / needs_evidence；低影响处置另需 residual_impact 对象，分别说明 spus / bands / units / amount。不能将重要未知降为低影响。一个处置可以解释同因同范围的一组候选，但必须保留全体候选 ID 并引用各候选基础证据；不能一句“已看过”批量关闭互不相关的问题。

`sample-reviews.json` 是对象数组，字段 sample_ids / status（checked、needs_evidence、defect）/ reason / evidence_ids。按身份、标题、原始类目与标准类目核对，可按有共同依据的类目组记录。自动抽出样本不等于已经完成语义核验。

`checked` 只表示明确描述的检查未见冲突，不自动证明真实销量、历史价格或原厂身份。混合父体必须按正式标准完整路径选择实际 SKU，再与原始完整键核对；缺陷影响只计算已举证子体。分类定义不清的边界不能仅凭类目名称判错。候选登记数、待补证数、已证实问题数分开呈现，不能把队列登记率当作原因闭环率。

`report-content.json` 包含 summary（结论分点）、normal_scope、limitations 与 findings 数组。每条 finding 含 title / scope / facts（段落数组）/ counterevidence / assessment / action / candidate_ids / evidence_ids。专业表达要求见 report-writing.md。

外部网页、内部文件或其他工具的真实响应通过 `attach --file ... --kind external-source --source <原始来源>` 纳入证据，文件内同时保留真实工具名、查询或 URL、访问时间、返回内容与失败信息。不得把手写推断伪装为工具响应。外部来源记录是可复核摘要，不是模型隐藏推理。初版 CLI 自动捕获覆盖 Doris 工具；其他工具尚需把真实响应归档，报告应披露这一观测边界。

只改变证据引用校验性能、状态计数或报告展示的修复，可以作为单独留档的后处理器读取旧运行：记录源码、版本、哈希和选择事件，保持原冻结查询计划、政策、分析计算及输入不变，并验证检查逻辑等价。查询、抽样、阈值或业务计算改变仍须新建运行；旧运行中的补充验证不得冒充新版全流程重跑。封存覆盖后处理器及其输出。

## 三个独立状态

- complete：程序义务和调查义务完成，必需证据齐备。
- limited：已执行规定工作，但存在明确待核或输入缺失。
- incomplete：必跑任务、候选处置、样本复核、结束指纹等存在未完成事项。

使用判断独立为 pass / qualified / reject / undetermined。证据缺失不能整体放行；已确认缺陷可以对受影响范围建议打回。封存只固定当时结果，不改变这些判断。事件哈希链和本地哈希能发现普通文件改动，不是第三方签名或对恶意重写的防篡改保证。
