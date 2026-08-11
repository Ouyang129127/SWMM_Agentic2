# 工作环节型 Agent 架构开发设计说明

更新日期：2026-08-06  
开发目标：在现有能力型执行架构上，试验一套更贴近 SWMM-CA2D 内涝诊断流程的 workflow-stage-oriented agents。  
试验优先级：先实现 evidence construction、flood diagnosis、evidence verification 三个高价值环节。

## 1. 设计判断

当前项目已经具备能力型执行底座：

```text
Orchestrator
TaskExecutor
CodeRunner
DataAnalyzer
EvidenceExplainer / SimulationEvidenceExplainer
```

这套架构适合完成模型检查、元素检索和标准化模拟，但复杂任务中可能出现路由漂移，例如官方模拟误入 CodeRunner、诊断绕过 evidence table、报告解释自由发挥。

本次试验的目标不是推翻现有架构，而是把 Orchestrator 从“自由工具选择者”升级为“受状态约束的工作流控制器”，并在其下增加一条状态清楚的工作环节型链条：

```text
User request
  -> StatefulOrchestrator
  -> read workflow_state.json
  -> call the next allowed stage agent

RUN_READY -> EvidenceBuilderAgent -> EVIDENCE_READY
EVIDENCE_READY -> DiagnosisAgent -> DIAGNOSIS_READY
DIAGNOSIS_READY -> VerificationAgent -> VERIFIED_READY
```

硬规则：

> 只有当某个功能环节具备稳定输入、稳定输出、明确工具接口和可评价指标时，才值得升级为独立 Agent。

## 2. 第一轮实现范围

第一轮采用 `StatefulOrchestrator + 3 个工作环节型 Agent`：

| 组件 | 输入 | 输出 | 目的 |
|---|---|---|---|
| `StatefulOrchestrator` | 用户目标 + `workflow_state.json` | 下一步合法 stage 调用 | 防止自由路由和跳步 |
| `EvidenceBuilderAgent` | 标准化 run 输出 | `evidence_table.csv`、`evidence_summary.json` | 将模型输出变成证据 |
| `DiagnosisAgent` | evidence table | `diagnosis_claims.json`、`risk_ranking.csv` | 生成证据绑定诊断 |
| `VerificationAgent` | diagnosis claims + evidence table | `verification_report.json`、`unsupported_rate.txt` | 核查证据支撑 |

其中第一轮真正新增的工作环节型 Agent 是三个：

| Agent | 输入 | 输出 | 目的 |
|---|---|---|---|
| `EvidenceBuilderAgent` | 标准化 run 输出 | `evidence_table.csv`、`evidence_summary.json` | 将模型输出变成证据 |
| `DiagnosisAgent` | evidence table | `diagnosis_claims.json`、`risk_ranking.csv` | 生成证据绑定诊断 |
| `VerificationAgent` | diagnosis claims + evidence table | `verification_report.json`、`unsupported_rate.txt` | 核查证据支撑 |

暂不优先实现：

```text
ScenarioAgent
SimulationAgent
ReportAgent
BenchmarkAgent
```

原因：

1. `ScenarioAgent` 和 `SimulationAgent` 当前可先由 TaskExecutor 承担。
2. `ReportAgent` 需要 verified claims 稳定后再做。
3. `BenchmarkAgent` 需要前面产物稳定后再评估。

## 3. 建议文件结构

建议新增：

```text
workflow_agents/
  __init__.py
  state.py
  schemas.py
  evidence_builder.py
  diagnosis.py
  verification.py
  orchestrator.py
  rules/
    diagnosis_rules.yaml
    verification_rules.yaml
```

如果暂时不想新建包，也可以先放在：

```text
tools.py
```

但更推荐独立目录，因为这是第二种架构试验，后续便于和现有 `TaskExecutor / CodeRunner / DataAnalyzer` 区分。

## 4. StatefulOrchestrator

### 4.1 职责

`StatefulOrchestrator` 仍然是上层决策层，但它不再自由猜测调用顺序，而是基于 `workflow_state.json` 判断下一步允许执行什么。

它负责：

1. 理解用户最终目标，例如“做诊断”“核查 unsupported rate”“生成报告”。
2. 读取当前 run 的 workflow state。
3. 检查目标任务所需前置产物是否存在。
4. 选择当前状态下允许调用的唯一或少数几个 Agent。
5. 在缺失前置产物时，先推进必要前置环节。
6. 调用成功后更新状态文件。

### 4.2 禁止行为

`StatefulOrchestrator` 不应：

1. 直接生成 evidence table。
2. 直接生成 diagnosis claims。
3. 直接计算 unsupported rate。
4. 绕过状态机跳到 ReportAgent。
5. 在缺少证据产物时让 LLM 自由写诊断。

### 4.3 核心逻辑

```text
用户想去哪：由 Orchestrator 理解。
现在能去哪：由 workflow_state.json 决定。
下一步怎么走：由状态机选择合法 Agent。
```

示例：

```text
用户目标：对 rain1 baseline 做内涝诊断
当前状态：RUN_READY
合法下一步：EvidenceBuilderAgent
禁止动作：直接调用 DiagnosisAgent 或 ReportAgent
```

## 5. 状态文件

建议每个 run 目录下新增：

```text
runs/<run_id>/workflow_state.json
```

示例：

```json
{
  "schema_name": "swmm_ca2d_workflow_state",
  "schema_version": "0.1",
  "model_name": "songhua_swmm_2d",
  "run_id": "rain1__baseline__20260721_165600",
  "state": "RUN_READY",
  "completed_stages": [
    "simulation"
  ],
  "next_allowed_stage": "evidence_building",
  "artifacts": {
    "run_summary": "summary.json",
    "run_metadata": "run.yaml",
    "swmm_node_flooding": "swmm/node_flooding.tsv",
    "swmm_nodes": "swmm/nodes.tsv",
    "swmm_links": "swmm/links.tsv",
    "ca2d_surface_depth": "ca2d/surface_depth.tsv"
  },
  "errors": []
}
```

状态枚举：

```text
RUN_READY
EVIDENCE_READY
DIAGNOSIS_READY
VERIFIED_READY
FAILED
```

## 6. EvidenceBuilderAgent

### 5.1 职责

从标准化 run 输出中生成结构化 evidence table。

### 5.2 输入

```text
runs/<run_id>/summary.json
runs/<run_id>/run.yaml
runs/<run_id>/swmm/node_flooding.tsv
runs/<run_id>/swmm/nodes.tsv
runs/<run_id>/swmm/links.tsv
runs/<run_id>/ca2d/surface_depth.tsv
```

### 5.3 输出

```text
runs/<run_id>/evidence/evidence_table.csv
runs/<run_id>/evidence/evidence_summary.json
```

### 5.4 evidence_table.csv 字段

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

### 5.5 第一版证据类型

| evidence type | source file | object type | metric |
|---|---|---|---|
| 节点累计溢流 | `swmm/node_flooding.tsv` | node | total_flooding_volume |
| 节点最大溢流流量 | `swmm/node_flooding.tsv` | node | max_flooding_flow |
| 节点溢流持续时间 | `swmm/node_flooding.tsv` | node | flooding_duration |
| CA2D 最大水深 | `ca2d/surface_depth.tsv` | cell / area | max_depth |
| CA2D 积水持续时间 | `ca2d/surface_depth.tsv` | cell / area | ponding_duration |
| 管段高负荷指标 | `swmm/links.tsv` | link | max_flow_or_load |

### 5.6 禁止行为

1. 不生成风险等级。
2. 不生成致灾原因。
3. 不补造缺失数值。
4. 不输出自由文本作为证据替代品。

## 7. DiagnosisAgent

### 6.1 职责

基于 evidence table 生成内涝热点、风险等级和可能致灾因素。

### 6.2 输入

```text
runs/<run_id>/evidence/evidence_table.csv
workflow_agents/rules/diagnosis_rules.yaml
```

### 6.3 输出

```text
runs/<run_id>/diagnosis/diagnosis_claims.json
runs/<run_id>/diagnosis/risk_ranking.csv
```

### 6.4 diagnosis_claims.json 示例

```json
{
  "schema_name": "swmm_ca2d_diagnosis_claims",
  "schema_version": "0.1",
  "run_id": "rain1__baseline__20260721_165600",
  "claims": [
    {
      "claim_id": "C001",
      "claim_type": "surface_hotspot",
      "object_type": "cell",
      "object_id": "cell_0001",
      "severity": "high",
      "claim_text": "该区域为高风险积水热点。",
      "possible_cause": "local_depression_or_concentrated_overflow",
      "confidence": "medium",
      "evidence_ids": ["E_CA2D_DEPTH_001", "E_SWMM_FLOOD_012"],
      "status": "pending_verification"
    }
  ]
}
```

### 6.5 第一版规则

```text
max_depth >= 0.5 m -> high surface ponding risk
max_depth >= 0.3 m -> moderate surface ponding risk
node total_flooding_volume Top 5% -> major overflow node
ponding_duration >= threshold -> long-duration ponding area
```

规则先简单，不要追求过度复杂。第一版目标是让每条 claim 都能追溯 evidence IDs。

### 6.6 禁止行为

1. 不得直接读取原始 SWMM/CA2D 输出绕过 evidence table。
2. 不得输出没有 evidence_ids 的 claim。
3. 不得把 possible cause 写成确定事实。
4. 不得生成超出规则支持的工程建议。

## 8. VerificationAgent

### 7.1 职责

核查 diagnosis claims 是否被 evidence table 支撑，并计算 unsupported rate。

### 7.2 输入

```text
runs/<run_id>/diagnosis/diagnosis_claims.json
runs/<run_id>/evidence/evidence_table.csv
workflow_agents/rules/verification_rules.yaml
```

### 7.3 输出

```text
runs/<run_id>/verification/verification_report.json
runs/<run_id>/verification/unsupported_rate.txt
```

### 7.4 verification_report.json 示例

```json
{
  "schema_name": "swmm_ca2d_verification_report",
  "schema_version": "0.1",
  "run_id": "rain1__baseline__20260721_165600",
  "summary": {
    "total_claims": 10,
    "supported": 8,
    "partially_supported": 1,
    "unsupported": 1,
    "unsupported_rate": 0.1
  },
  "claim_checks": [
    {
      "claim_id": "C001",
      "verification_status": "supported",
      "checked_evidence_ids": ["E_CA2D_DEPTH_001", "E_SWMM_FLOOD_012"],
      "issues": []
    }
  ]
}
```

### 7.5 核查规则

1. `evidence_ids` 不为空。
2. 所有 `evidence_ids` 必须存在于 evidence table。
3. claim 的 `object_id` 与至少一条 evidence 匹配，或有明确空间映射关系。
4. claim type 所需 metric 必须存在。
5. metric value 必须满足诊断规则阈值。
6. 不满足则标记为 `unsupported` 或 `partially_supported`。

### 7.6 禁止行为

1. 不新增 claim。
2. 不删除 unsupported claim。
3. 不替 DiagnosisAgent 改写结论。
4. 不用自然语言感觉判断 evidence 是否足够。

## 9. 状态驱动调用流程

建议新增一个轻量函数：

```text
run_workflow_stage(model_name, run_id, target_stage)
```

行为：

1. 读取 `workflow_state.json`。
2. 检查 `target_stage` 是否允许执行。
3. 调用对应 Agent。
4. 检查输出文件是否生成。
5. 更新状态。
6. 返回结构化结果。

示例状态转移：

```text
RUN_READY + target=evidence_building
  -> EvidenceBuilderAgent
  -> EVIDENCE_READY

EVIDENCE_READY + target=diagnosis
  -> DiagnosisAgent
  -> DIAGNOSIS_READY

DIAGNOSIS_READY + target=verification
  -> VerificationAgent
  -> VERIFIED_READY
```

禁止：

```text
RUN_READY -> DiagnosisAgent
EVIDENCE_READY -> VerificationAgent
DIAGNOSIS_READY -> EvidenceBuilderAgent
```

除非用户显式要求 rerun，并记录覆盖原因。

## 10. 与现有代码的集成建议

### 9.1 第一版不接 LLM

建议第一版三个 Agent 都先做成确定性函数：

```text
build_evidence_for_run(...)
diagnose_run_from_evidence(...)
verify_diagnosis_claims(...)
```

这样更容易验证数据结构和指标，不会把问题混进 LLM 输出。

### 9.2 第二版再接 Agent 包装

当确定性函数稳定后，再让 LLM Agent 做三件事：

1. 解释结构化结果。
2. 选择下一阶段。
3. 在缺失输入时提出补救建议。

不要让 LLM 直接计算 evidence 或 unsupported rate。

### 9.3 推荐工具入口

后续可把这三个函数暴露给 `TaskExecutor` 或新的 workflow orchestrator：

```text
build_run_evidence(model_name, run_id)
diagnose_run(model_name, run_id)
verify_run_diagnosis(model_name, run_id)
```

## 11. 第一轮开发清单

### Step 1：新增目录、状态 schema 和 StatefulOrchestrator

```text
workflow_agents/
workflow_agents/state.py
workflow_agents/schemas.py
workflow_agents/orchestrator.py
workflow_agents/rules/
```

### Step 2：实现 EvidenceBuilderAgent 的确定性核心

输入已有 run：

```text
models/songhua_swmm_2d/runs/rain1__baseline__20260721_165600
```

输出：

```text
evidence/evidence_table.csv
evidence/evidence_summary.json
```

### Step 3：实现 DiagnosisAgent 的规则版核心

输出：

```text
diagnosis/diagnosis_claims.json
diagnosis/risk_ranking.csv
```

### Step 4：实现 VerificationAgent 的固定核查核心

输出：

```text
verification/verification_report.json
verification/unsupported_rate.txt
```

### Step 5：更新前端或命令行入口

先支持命令式调用：

```text
对 rain1__baseline__20260721_165600 构建证据
对该 run 进行内涝诊断
核查该 run 的诊断证据
```

## 12. 成功标准

第一轮试验成功的标准：

1. 已有 run 能自动生成 evidence table。
2. evidence table 中每条 evidence 可追溯到源文件。
3. diagnosis claims 中每条 claim 都有 evidence_ids。
4. verification report 能识别 supported / partially_supported / unsupported。
5. unsupported rate 能被稳定计算。
6. StatefulOrchestrator 能基于 `workflow_state.json` 推进合法下一步，而不是在 TaskExecutor / CodeRunner / DataAnalyzer 之间自由猜测这些环节。

## 13. 论文价值

如果第一轮试验跑通，可以支撑论文中的一个方法表述：

> In addition to the capability-oriented execution layer, we introduced workflow-stage-oriented task agents for evidence construction, flood diagnosis, and evidence verification. These agents operate on structured intermediate artifacts and restricted tool interfaces, reducing routing ambiguity and evidence-free reasoning.

中文：

> 在能力型执行层之外，本文进一步试验了面向证据构建、内涝诊断和证据核查的工作环节型任务 Agent。这些 Agent 基于结构化中间产物和受限工具接口运行，从而降低路由歧义和无证据推理风险。
