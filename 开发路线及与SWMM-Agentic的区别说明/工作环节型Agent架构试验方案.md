# 工作环节型 Agent 架构试验方案

更新日期：2026-08-06  
定位：用于 SWMM-CA2D-Agentic 后续架构试验，不替代当前能力型执行底座，而是在其上尝试更贴近论文工作流的 task-specific agents。

## 1. 设计目标

当前系统主要采用能力型执行架构：

```text
Orchestrator
TaskExecutor
CodeRunner
DataAnalyzer
Evidence Explanation Agent
```

这种架构稳定、易实现、接近 EPANET-Agentic，但在复杂任务中容易出现职责混合。例如“执行模拟、保存结果、分析最大积水区、生成报告”可能同时触发 TaskExecutor、CodeRunner、DataAnalyzer 和解释层 Agent，导致路由漂移。

工作环节型 Agent 架构的目标是：

> 按 SWMM-CA2D 内涝诊断工作流划分 task-specific agents，让每个 Agent 只处理一个明确环节，并通过状态机、输入输出契约和工具白名单减少路由漂移。

核心原则：

> 真正减少路由漂移的不是把名字改成 Agent，而是为每个工作环节设置稳定输入、稳定输出、明确工具接口、越权禁止规则和可评价指标。

## 2. 总体架构

建议试验版采用 `StatefulOrchestrator + 7 个工作环节型 Agent`：

```text
User / Expert request
  -> StatefulOrchestrator
  -> ScenarioAgent
  -> SimulationAgent
  -> EvidenceBuilderAgent
  -> DiagnosisAgent
  -> VerificationAgent
  -> ReportAgent
  -> BenchmarkAgent
```

其中：

| 组件 | 核心职责 |
|---|---|
| StatefulOrchestrator | 理解用户目标，读取 workflow state，调用当前状态下合法的下一环节 |
| ScenarioAgent | 组织降雨事件、工程情景和运行参数 |
| SimulationAgent | 调用固定 SWMM-CA2D 标准化模拟流程 |
| EvidenceBuilderAgent | 从 SWMM/CA2D 输出构建 evidence table |
| DiagnosisAgent | 基于 evidence table 生成诊断结论和风险排序 |
| VerificationAgent | 核查诊断与建议是否有证据支撑 |
| ReportAgent | 生成证据约束的简报和论文案例材料 |
| BenchmarkAgent | 执行任务集、统计指标和方法对比 |

最小可行试验不必一次实现 7 个。建议先实现：

```text
EvidenceBuilderAgent
DiagnosisAgent
VerificationAgent
```

因为这三个最能支撑论文创新，也最容易建立稳定输入输出。

## 3. 状态机设计

工作环节型 Agent 不应由 Orchestrator 自由猜测调用顺序，而应由状态机驱动。这里不是取消 Orchestrator，而是把它改造成 StatefulOrchestrator：它仍然理解用户目标，但必须根据当前状态和产物可用性调用合法的下一环节。

推荐状态流：

```text
START
  -> SCENARIO_READY
  -> RUN_READY
  -> EVIDENCE_READY
  -> DIAGNOSIS_READY
  -> VERIFIED_READY
  -> REPORT_READY
  -> BENCHMARK_READY
```

状态与 Agent 对应关系：

| 当前状态 | 可调用 Agent | 目标状态 |
|---|---|---|
| `START` | ScenarioAgent | `SCENARIO_READY` |
| `SCENARIO_READY` | SimulationAgent | `RUN_READY` |
| `RUN_READY` | EvidenceBuilderAgent | `EVIDENCE_READY` |
| `EVIDENCE_READY` | DiagnosisAgent | `DIAGNOSIS_READY` |
| `DIAGNOSIS_READY` | VerificationAgent | `VERIFIED_READY` |
| `VERIFIED_READY` | ReportAgent | `REPORT_READY` |
| `REPORT_READY` | BenchmarkAgent | `BENCHMARK_READY` |

状态机规则：

1. 每个 Agent 只接受指定状态下的输入。
2. 每个 Agent 成功后必须写出目标状态所需文件。
3. 如果输入文件不存在，不允许跳步，应返回 missing prerequisite。
4. 如果工具失败，返回 error report，不允许编造成功。
5. Orchestrator 的职责从“自由选择 Agent”降级为“读取状态并推进下一环节”。

## 4. Agent 详细设计

### 4.1 ScenarioAgent

职责：

组织降雨事件、工程情景和运行参数。

输入：

```text
user request
models/<model_name>/events/
models/<model_name>/swmm/scenarios/
```

输出：

```text
scenario_request.json
```

建议字段：

```json
{
  "model_name": "songhua_swmm_2d",
  "event_name": "rain1.txt",
  "scenario_name": "baseline",
  "run_id": "rain1__baseline__timestamp",
  "requested_outputs": ["summary", "swmm", "ca2d"]
}
```

工具白名单：

```text
list_swmm_2d_models
check_swmm_2d_project
list_rainfall_events
```

禁止行为：

1. 不得生成不存在的降雨事件。
2. 不得修改 SWMM 模型。
3. 不得执行模拟。
4. 不得诊断内涝原因。

评价指标：

```text
scenario recognition accuracy
missing-parameter detection rate
invalid-event hallucination rate
```

### 4.2 SimulationAgent

职责：

调用固定 SWMM-CA2D 标准化模拟流程。

输入：

```text
scenario_request.json
```

输出：

```text
runs/<run_id>/summary.json
runs/<run_id>/run.yaml
runs/<run_id>/swmm/
runs/<run_id>/ca2d/
```

工具白名单：

```text
run_swmm_2d_project_from_rainfall
run_swmm_2d_project_from_flooding
check_ca2d_model
```

禁止行为：

1. 不得调用 CodeRunner 临时重写官方模拟流程。
2. 不得在没有工具返回结果时宣称模拟成功。
3. 不得解释风险原因。
4. 不得直接生成 diagnosis claims。

评价指标：

```text
simulation success rate
tool invocation accuracy
official-pipeline adherence rate
incorrect CodeRunner routing rate
```

说明：

SimulationAgent 是高风险环节。第一版可以只是 TaskExecutor 的受控包装，而不是自由 LLM Agent。

### 4.3 EvidenceBuilderAgent

职责：

从 SWMM/CA2D 标准化输出构建 evidence table。

输入：

```text
runs/<run_id>/summary.json
runs/<run_id>/run.yaml
runs/<run_id>/swmm/node_flooding.tsv
runs/<run_id>/swmm/nodes.tsv
runs/<run_id>/swmm/links.tsv
runs/<run_id>/ca2d/surface_depth.tsv
```

输出：

```text
runs/<run_id>/evidence/evidence_table.csv
runs/<run_id>/evidence/evidence_summary.json
```

核心字段：

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

工具白名单：

```text
load_run_summary
parse_swmm_node_flooding
parse_swmm_nodes
parse_swmm_links
parse_ca2d_surface_depth
build_evidence_table
```

禁止行为：

1. 不得生成诊断结论。
2. 不得评价风险等级。
3. 不得补造缺失数值。
4. 不得用自然语言替代 evidence table。

评价指标：

```text
evidence generation success rate
source traceability rate
numerical extraction accuracy
missing-source-file detection rate
```

### 4.4 DiagnosisAgent

职责：

基于 evidence table 生成内涝诊断结论和风险排序。

输入：

```text
evidence_table.csv
evidence_summary.json
diagnosis_rules.yaml
```

输出：

```text
diagnosis/diagnosis_claims.json
diagnosis/risk_ranking.csv
```

诊断内容：

1. 溢流节点 Top-N。
2. 最大积水深度区域 Top-N。
3. 长历时积水区域。
4. 高负荷或瓶颈管段。
5. 风险等级：Low / Moderate / High / Critical。
6. 可能致灾因素。
7. 每条 claim 绑定 evidence_ids。

工具白名单：

```text
load_evidence_table
rank_overflow_nodes
rank_surface_depth_hotspots
rank_long_duration_ponding
classify_risk_level
generate_diagnosis_claims
```

禁止行为：

1. 不得直接读取原始 SWMM/CA2D 文件绕过 evidence table。
2. 不得输出没有 evidence_ids 的 claim。
3. 不得把可能原因写成确定事实。
4. 不得生成工程改造建议，除非证据和规则支持。

评价指标：

```text
hotspot detection precision/recall/F1
risk ranking agreement
claim evidence coverage
unsupported preliminary claim rate
```

### 4.5 VerificationAgent

职责：

检查诊断结论和建议是否有证据支撑，并计算 unsupported rate。

输入：

```text
diagnosis_claims.json
evidence_table.csv
verification_rules.yaml
```

输出：

```text
verification/verification_report.json
verification/unsupported_rate.txt
```

核查内容：

1. claim 是否包含 evidence_ids。
2. evidence_id 是否真实存在。
3. evidence object 是否与 claim object 一致。
4. evidence metric 是否能支撑 claim type。
5. evidence value 是否满足阈值或排序规则。
6. claim 标记为 supported、partially_supported、unsupported 或 uncertain。

工具白名单：

```text
load_diagnosis_claims
load_evidence_table
validate_evidence_ids
validate_object_consistency
validate_metric_support
calculate_unsupported_rate
generate_verification_report
```

禁止行为：

1. 不得新增诊断结论。
2. 不得替 DiagnosisAgent 修改 claim 内容。
3. 不得把 unsupported claim 悄悄删除。
4. 不得用自然语言判断替代规则核查。

评价指标：

```text
evidence citation completeness
unsupported rate
partially supported rate
verification consistency
false support rate
```

### 4.6 ReportAgent

职责：

生成证据约束的应急简报和论文案例材料。

输入：

```text
run_summary.json
diagnosis_claims.json
verification_report.json
selected figures
```

输出：

```text
reports/emergency_brief.md
reports/emergency_brief.html
paper_case_summary.md
```

报告内容：

1. 降雨事件与情景说明。
2. 模型运行摘要。
3. 主要内涝热点。
4. 风险优先级。
5. 支持证据列表。
6. unsupported / uncertain 条目。
7. 面向管理者的简短说明。

工具白名单：

```text
load_verified_claims
load_run_summary
load_selected_figures
render_markdown_report
render_html_report
```

禁止行为：

1. 不得新增 verification report 中没有的结论。
2. 不得隐藏 unsupported 条目。
3. 不得把建议写得比证据更确定。
4. 不得声称报告内容已由专家确认，除非有人工确认记录。

评价指标：

```text
report evidence completeness
unsupported visibility rate
human readability score
report generation success rate
```

### 4.7 BenchmarkAgent

职责：

执行 benchmark 任务集，统计不同方法的表现。

输入：

```text
benchmark/tasks.jsonl
benchmark/reference_answers/
benchmark/grading_rules.yaml
```

输出：

```text
results/benchmark_scores.csv
results/method_comparison_summary.md
```

工具白名单：

```text
load_benchmark_tasks
run_task
grade_task_success
grade_tool_invocation
grade_extraction_accuracy
grade_diagnosis_quality
calculate_metrics
```

禁止行为：

1. 不得修改 benchmark 参考答案。
2. 不得在评分时读取被测方法不应获得的信息。
3. 不得跳过失败任务。
4. 不得只报告成功案例。

评价指标：

```text
task success rate
tool invocation accuracy
simulation success rate
numerical extraction accuracy
hotspot F1
risk ranking agreement
evidence citation completeness
unsupported rate
human intervention count
time cost
```

## 5. Orchestrator 在新架构中的角色

工作环节型架构下，Orchestrator 不再是自由选择任意 Agent，而是状态机控制器。

职责：

1. 读取当前任务状态。
2. 判断是否满足下一 Agent 的输入条件。
3. 调用当前状态允许的 Agent。
4. 保存状态转移记录。
5. 遇到缺失输入时停止并报告 missing prerequisite。

不建议让 Orchestrator 做：

1. 直接执行模拟。
2. 直接生成诊断。
3. 直接核查 evidence。
4. 在没有状态依据时自由跳步。

推荐状态记录：

```json
{
  "run_id": "rain1__baseline__20260806_001",
  "state": "EVIDENCE_READY",
  "completed_stages": [
    "scenario",
    "simulation",
    "evidence_building"
  ],
  "next_allowed_stage": "diagnosis",
  "artifacts": {
    "scenario_request": "...",
    "run_summary": "...",
    "evidence_table": "..."
  }
}
```

## 6. 与现有能力型架构的关系

工作环节型 Agent 不需要推翻现有架构。更合理的是复用现有能力组件：

| 工作环节型 Agent | 复用的现有能力 |
|---|---|
| ScenarioAgent | TaskExecutor 的模型与事件检查工具 |
| SimulationAgent | TaskExecutor 的标准化模拟工具 |
| EvidenceBuilderAgent | CodeRunner 或未来固定 evidence builder 工具 |
| DiagnosisAgent | 新增规则诊断工具，必要时由 LLM 解释 |
| VerificationAgent | 新增固定核查工具 |
| ReportAgent | Evidence Explanation Agent + 报告渲染工具 |
| BenchmarkAgent | 固定 benchmark runner |

因此，新的系统不是：

```text
抛弃 TaskExecutor / CodeRunner / DataAnalyzer
```

而是：

```text
用工作环节型 Agent 包装和约束这些能力组件
```

## 7. 最小可行试验

建议第一轮只试三个 Agent：

```text
EvidenceBuilderAgent
DiagnosisAgent
VerificationAgent
```

原因：

1. 它们最贴近论文创新点。
2. 它们依赖的输入输出最容易稳定。
3. 它们能直接产生 Results 所需文件。
4. 它们能直接服务 unsupported rate。
5. 它们可以显著降低“诊断绕过证据表”和“报告自由发挥”的风险。

第一轮试验流程：

```text
已有 run
  -> EvidenceBuilderAgent
  -> DiagnosisAgent
  -> VerificationAgent
```

第一轮交付物：

```text
evidence_table.csv
evidence_summary.json
diagnosis_claims.json
risk_ranking.csv
verification_report.json
unsupported_rate.txt
```

## 8. 对路由漂移的预期影响

可能减少的漂移：

| 漂移类型 | 工作环节型架构如何缓解 |
|---|---|
| 模拟误入 CodeRunner | SimulationAgent 只允许调用固定模拟工具 |
| 诊断绕过 evidence table | DiagnosisAgent 只接受 evidence table |
| 报告自由发挥 | ReportAgent 只读取 verified claims |
| 核查变成自然语言解释 | VerificationAgent 只执行规则核查 |
| 任务重复执行 | 状态机记录 completed stages |

仍然可能存在的漂移：

| 风险 | 缓解办法 |
|---|---|
| 用户请求跨多个环节 | Orchestrator 按状态拆分任务 |
| 环节边界不清 | 每个 Agent 写清入口条件和禁止行为 |
| Agent 过多导致选择困难 | 使用状态机，不靠自由选择 |
| LLM 解释层过度发挥 | 解释层只能读取结构化证据 |

## 9. 论文中的表述方式

如果这个试验成功，论文中可以写：

> To reduce routing ambiguity and constrain task execution, the SWMM-CA2D workflow was organized into task-specific functional agents. Each agent operates only on predefined input artifacts, produces structured outputs, and invokes a restricted set of tools. The workflow state determines the next allowable agent, thereby reducing uncontrolled tool selection and evidence-free reasoning.

中文表述：

> 为降低路由歧义并约束任务执行，本文将 SWMM-CA2D 工作流组织为若干任务专属功能型 Agent。每个 Agent 只接收预定义输入产物，生成结构化输出，并调用受限工具集合。工作流状态决定下一步允许调用的 Agent，从而减少无控制工具选择和无证据推理。

如果试验只完成一部分，则稳妥写法是：

> The current implementation retains a capability-oriented execution layer while experimentally introducing task-specific stages for evidence construction, flood diagnosis, and evidence verification.

中文表述：

> 当前实现仍保留能力型执行层，同时试验性引入证据构建、内涝诊断和证据核查等任务专属环节。

## 10. 最终建议

可以尝试工作环节型 Agent 架构，但不要一次性全量重构。建议路线是：

```text
先做 EvidenceBuilderAgent
再做 DiagnosisAgent
再做 VerificationAgent
最后再扩展 ReportAgent 和 BenchmarkAgent
```

SimulationAgent 暂时可以只是 TaskExecutor 的受控包装，因为模拟执行是高风险环节，固定工具优先比自由 Agent 更重要。

最终目标不是“更多 Agent”，而是：

> 用工作环节型 Agent 把 SWMM-CA2D 内涝诊断流程变成状态清楚、证据清楚、职责清楚、评价清楚的工程工作流。
