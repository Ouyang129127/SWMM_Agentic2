# SWMM-2D-Agentic 项目差距监视表

监视对象：

- 外部计划：`E:\博士生的未来\文献管理库\第一篇论文_SWMM-2D-Agentic导师汇报.md`
- 仓库内计划副本：`E:\SWMM_Agentic\SWMM-Agentic\第一篇论文_SWMM-2D-Agentic导师汇报.md`

最近更新日期：2026-07-23

## 1. 总判断

项目已经从“demo 原型”推进到“具备真实大规模案例雏形”的阶段。

目前最重要的变化是：`models/songhua_swmm_2d` 已经形成项目化模型目录，并完成过一次 `rain1 + baseline` 的 SWMM-2D 耦合运行。该运行摘要显示：

- SWMM 节点数：10040
- SWMM 管段/链接数：9877
- SWMM flooding records：49450
- CA2D matched flooding nodes：9890
- CA2D maximum depth：0.7592 m
- CA2D result records：598535

这说明论文计划中“真实 9000+ 节点、9000+ 管段的大规模 SWMM-2D 耦合模型”这一基础门槛已经基本跨过去。

现在的主要差距不再是“有没有模型能跑”，而是：

1. 是否能把模型输出稳定转成标准证据表。
2. 是否能做内涝热点、风险等级、致灾因子的确定性诊断。
3. 是否能让 Agent 的每条诊断和建议都绑定证据。
4. 是否能构建 30-80 个 benchmark 任务并量化比较。
5. 是否能产出 Fig. 1-Fig. 7 和论文 Results 所需表格。

一句话监视原则：

> 当前所有开发都应服务“证据约束的大规模 SWMM-2D 内涝诊断 benchmark”，而不是泛泛做聊天界面，也不是提前进入第二篇的泵站联排联调优化。

## 2. 当前已经完成的内容

### 2.1 项目结构

已具备长期模型库结构：

```text
models/
  songhua_swmm_2d/
    model.yaml
    static/
    swmm/
    mapping/
    events/
    runs/
```

这比旧的 `code_dir/data` demo 结构更接近论文实验工程。

### 2.2 真实/准真实大规模模型

已具备：

- `models/songhua_swmm_2d/swmm/scenarios/baseline/Model.inp`
- `models/songhua_swmm_2d/static/`
- `models/songhua_swmm_2d/static/node_to_cell_mapping.csv`
- `models/songhua_swmm_2d/events/rain1.txt`

一次成功运行位于：

```text
models/songhua_swmm_2d/runs/rain1__baseline__20260721_165600/
```

该运行输出：

- `summary.json`
- `run.yaml`
- `swmm/node_flooding.tsv`
- `swmm/nodes.tsv`
- `swmm/links.tsv`
- `ca2d/surface_depth.tsv`
- `ca2d/ca2d_run_summary.md`
- `ca2d/ca2d_max_depth.png`
- `ca2d/ca2d_final_depth.png`

### 2.3 Agent 与工具骨架

已具备：

- `Orchestrator`
- `TaskExecutor`
- `CodeRunner`
- `DataAnalyzer`
- web chat frontend：`web_app.py`
- tool-first execution 相关试错记录

这说明项目已经意识到一个关键点：论文不能只靠 LLM 自由发挥，必须优先调用确定性工具。

### 2.4 研究立论已经增强

仓库内导师汇报计划已经加入了核心立论：

> Agent 不是替代 SWMM，也不是替代传统编程，而是补上模型软件与应急决策之间缺失的“认知-组织-解释-协调层”。

这条立论非常关键。后续所有功能都要支撑它。

## 3. 与论文计划的差距矩阵

| 计划要求 | 当前状态 | 差距等级 | 下一步 |
|---|---|---:|---|
| 真实 9000+ 节点、9000+ 管段模型 | 已有 `songhua_swmm_2d`，一次运行显示 10040 节点、9877 链接 | 低 | 固化模型规模摘要脚本，用于 Fig. 1 和 Methods |
| SWMM-2D 耦合运行 | 已能完成 `rain1 + baseline` 运行 | 中低 | 增加多降雨、多情景运行矩阵 |
| 可复现运行目录 | 已有 `runs/<run_id>/summary.json` | 中低 | 统一 run schema，增加日志、耗时、失败原因 |
| Scenario Agent | 有降雨事件文件和 baseline 情景，但情景体系仍少 | 中 | 扩展 3-5 个降雨事件和 2-3 个工程情景 |
| Simulation Agent | 已有 tool-first 管线迹象 | 中 | 把 `run_swmm_2d_project_from_rainfall` 形成稳定公共接口和测试 |
| Data Extraction Agent | 已生成 nodes、links、node_flooding、surface_depth | 中高 | 统一为 `evidence_table.csv` 和 `scenario_summary.json` |
| Flood Diagnosis Agent | 尚未形成独立诊断模块 | 高 | 基于证据表实现热点识别、风险等级、致灾因子 |
| Evidence Verification Agent | 尚未形成独立模块 | 高 | 检查每条结论/建议的 evidence_ids，计算 unsupported recommendation rate |
| Report Agent | 仍缺结构化应急简报模板 | 高 | 生成 evidence-grounded Markdown/HTML 简报 |
| Benchmark 任务集 | 目前仍不是 30-80 个系统任务 | 高 | 建立 `benchmark/tasks.jsonl` 与参考答案 |
| 对比实验 | 尚未见 manual/plain LLM/tool LLM/full agent 对比 | 高 | 设计四类方法实验协议 |
| 评价指标 | 运行摘要有工程指标，但缺论文评分指标 | 高 | 实现 task success、extraction accuracy、F1、Spearman、unsupported rate |
| Fig. 1-Fig. 7 | 目前只有 CA2D 深度图等局部图 | 高 | 建立 `paper_assets/figures/` 可复现脚本 |

## 4. 一步一步需要完成的内容

### Step 1：固化真实案例摘要

目标：支撑论文 Fig. 1 和 Methods 的 “Study area and model system”。

需要完成：

1. 编写模型摘要脚本，读取 `Model.inp`、`model.yaml`、`static/config.json`。
2. 输出：
   - 节点数。
   - 链接数。
   - 子汇水区数。
   - 雨量站数。
   - CA2D 网格数量。
   - 映射节点数。
   - 可流动单元数量。
3. 保存到：
   - `paper_assets/tables/model_system_summary.csv`
   - `paper_assets/tables/model_system_summary.md`

完成标志：

- 一条命令可复现模型规模摘要。
- 摘要数值与 `summary.json` 一致。

### Step 2：统一运行结果 schema

目标：保证每次模拟都能进入后续诊断和 benchmark。

需要完成：

1. 固定 `summary.json` 字段。
2. 固定 `run.yaml` 字段。
3. 给每个 run 增加：
   - `run_id`
   - `event_name`
   - `scenario_name`
   - `model_name`
   - `created_at`
   - `execution_policy`
   - `tool_chain`
   - `elapsed_seconds`
   - `status`
   - `error_message`
4. 所有运行输出统一在：

```text
models/<model_name>/runs/<run_id>/
```

完成标志：

- 可以遍历 `runs/*/summary.json` 汇总成实验矩阵。

### Step 3：生成标准证据表

目标：把“模型输出”变成“诊断证据”。

建议建立：

```text
models/songhua_swmm_2d/runs/<run_id>/evidence/evidence_table.csv
models/songhua_swmm_2d/runs/<run_id>/evidence/evidence_summary.json
```

`evidence_table.csv` 建议字段：

```text
evidence_id
run_id
event_name
scenario_name
source_model
source_file
object_type
object_id
metric_name
value
unit
time_start
time_end
duration_minutes
rank
threshold
exceedance_flag
```

至少抽取这些证据：

- 节点最大溢流流量。
- 节点累计溢流量。
- 节点溢流持续时间。
- 节点最大水深。
- 链接最大流量或高负荷状态。
- CA2D 最大积水深度。
- CA2D 积水面积。
- CA2D 积水持续时间。
- CA2D 热点网格或片区排名。

完成标志：

- 每个 run 自动生成 evidence table。
- 后续诊断只引用 evidence table，不直接临时读散乱文件。

### Step 4：实现规则版 Flood Diagnosis Agent

目标：先不要追求 LLM 自由诊断，先用规则把论文创新点落稳。

诊断内容：

1. 关键溢流节点 Top-N。
2. 高风险积水区域 Top-N。
3. 长持续积水区域 Top-N。
4. 管网瓶颈或高负荷链接 Top-N。
5. 风险等级：
   - Low
   - Moderate
   - High
   - Critical
6. 初步致灾因子：
   - upstream node flooding
   - downstream link overload
   - local depression / low elevation
   - long-duration surface ponding
   - combined network-surface flooding

输出：

```text
diagnosis/diagnosis_claims.json
diagnosis/risk_ranking.csv
```

完成标志：

- 每条诊断都有 `evidence_ids`。

### Step 5：实现 Evidence Verification Agent

目标：把“有证据可查”变成可计算指标。

需要检查：

1. 每条 `claim` 是否有 `evidence_ids`。
2. 每条 `recommendation` 是否有 `evidence_ids`。
3. evidence id 是否真实存在于 `evidence_table.csv`。
4. 引用证据是否与结论对象一致。
5. 引用证据是否达到阈值。

输出：

```text
verification/verification_report.json
verification/unsupported_recommendation_rate.txt
```

核心指标：

```text
unsupported recommendation rate =
无有效证据支撑的建议数 / 建议总数
```

完成标志：

- 无证据建议会被标记为 unsupported。
- 论文可报告 evidence citation completeness 和 unsupported recommendation rate。

### Step 6：生成证据约束应急简报

目标：支撑 Fig. 7 和 Report task。

简报结构：

1. 降雨事件与情景说明。
2. 模型运行摘要。
3. 主要内涝热点。
4. 关键溢流节点。
5. 关键管段或瓶颈。
6. 风险优先级。
7. 应急建议。
8. 每条建议对应证据。
9. Unsupported 或 low-confidence 条目单独列出。

输出：

```text
reports/emergency_brief.md
reports/emergency_brief.html
```

完成标志：

- 简报中每条结论/建议都带证据编号。

### Step 7：扩展事件与情景矩阵

目标：让实验不是单一案例。

建议最低配置：

- 降雨事件：3 个
  - 短历时强降雨。
  - 较长历时降雨。
  - 高峰提前或后移降雨。
- 工程情景：3 个
  - baseline。
  - rainfall stress。
  - conduit blockage 或局部节点压力情景。

形成至少：

```text
3 events x 3 scenarios = 9 runs
```

完成标志：

- `runs/` 下至少 9 个可复现 run。
- 每个 run 都有 summary、evidence、diagnosis、verification、report。

### Step 8：构建 benchmark 任务集

目标：支撑论文 Fig. 4 和方法评价。

建立：

```text
benchmark/tasks.jsonl
benchmark/reference_answers/
benchmark/grading_rules.yaml
```

任务类型：

1. Simulation task。
2. Extraction task。
3. Diagnosis task。
4. Decision-support task。
5. Report task。

第一阶段先做 20 个任务，最终扩展到 30-80 个。

完成标志：

- benchmark 任务能自动调用已有 runs 或触发新 runs。
- 每个任务有参考答案或人工核查标准。

### Step 9：实现 benchmark runner 和评价指标

目标：把 Agent 贡献量化。

指标：

- Task success rate。
- Tool invocation accuracy。
- Model run success rate。
- Numerical extraction accuracy。
- Node flooding extraction accuracy。
- Water-depth extraction accuracy。
- Hotspot detection precision/recall/F1。
- Risk-ranking Spearman correlation。
- Evidence citation completeness。
- Unsupported recommendation rate。
- Human intervention count。
- Time saving compared with manual workflow。

输出：

```text
results/benchmark_scores.csv
results/method_comparison_summary.md
```

完成标志：

- 可以比较 `plain LLM`、`tool-using LLM without verification`、`full SWMM-2D-Agentic`。

### Step 10：准备论文图表

目标：把工程结果转化为论文素材。

需要建立：

```text
paper_assets/
  figures/
  tables/
  scripts/
```

图表对应：

- Fig. 1：研究区与模型系统。
- Fig. 2：SWMM-2D-Agentic 总体架构。
- Fig. 3：Agent 工作流。
- Fig. 4：Benchmark 任务体系。
- Fig. 5：方法性能对比。
- Fig. 6：典型暴雨内涝诊断案例。
- Fig. 7：证据约束应急简报。

完成标志：

- 每张图都有源数据和生成脚本。

## 5. 当前最优先的 10 个任务

1. 写 `model_system_summary` 工具，固化 10040 节点、9877 链接等模型规模证据。
2. 写 `evidence_table` 生成器，把 nodes、links、node_flooding、surface_depth 合成统一证据表。
3. 给 `rain1__baseline__20260721_165600` 生成第一版 evidence table。
4. 实现规则版 `diagnosis_claims.json`。
5. 实现 `verification_report.json` 和 unsupported recommendation rate。
6. 生成第一份 evidence-grounded emergency brief。
7. 扩展至少 3 个降雨事件。
8. 扩展至少 3 个情景并跑出 9 个 run。
9. 建立第一批 20 个 benchmark tasks。
10. 生成 Fig. 1、Fig. 2、Fig. 3 的初稿图。

## 6. 每次开发时的监视规则

每次改代码、加工具、跑模型或写材料，都检查以下问题：

1. 是否服务第一篇论文，而不是提前进入泵站联排联调优化？
2. 是否增加了可复现 run、证据表、诊断结果、验证结果或 benchmark？
3. 是否减少 Agent 自由发挥，增加 tool-first 和 evidence-first？
4. 是否能进入论文评价指标？
5. 是否能支撑 Fig. 1-Fig. 7 或 Methods/Results 某一节？
6. 是否能回答“Agent 相比传统程序到底带来了什么”？

如果某项工作不能回答这些问题，它就不是当前优先事项。

