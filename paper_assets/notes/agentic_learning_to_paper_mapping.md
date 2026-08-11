# AgenticLearning 与 SWMM-CA2D-Agentic 论文映射表

更新日期：2026-08-05  
学习资料目录：`E:\博士生的未来\AgenticLearning`  
项目目录：`E:\SWMM_Agentic\SWMM-Agentic`

## 1. 总体判断

`AgenticLearning` 不是一组孤立的 LLM 学习笔记，而是可以直接服务第一篇 SWMM-CA2D-Agentic 论文的方法论准备材料。它已经形成了一条很清楚的研究逻辑：

> LLM 不替代 SWMM/CA2D 的物理计算，也不替代传统程序的确定性处理；Agent 的价值在于把自然语言任务、确定性模型工具、结构化证据、诊断规则、人工复核和结果报告组织成一个可执行、可追踪、可评价的工程工作流。

这条逻辑与当前论文的核心立论高度一致。论文中应避免把创新点表述为“可以用自然语言操作 SWMM-CA2D”，而应进一步提升为：

> 本研究提出一种 evidence-grounded multi-agent workflow，将 SWMM-CA2D 大规模内涝模拟从单次模型运行推进为可复现的任务编排、证据构建、风险诊断、证据核查与应急解释流程。

## 1.1 当前代码分工与论文分工不是同一层级

需要特别注意：当前项目里的 Agent 分工，和论文中为了说明方法创新而提出的 Agent 分工，不是同一种分类方向。

当前代码更接近“实现执行层”分工：

| 代码中的 Agent / 组件 | 当前实际含义 |
|---|---|
| `Orchestrator` | 理解用户任务、决定下一步调用哪个执行组件 |
| `TaskExecutor` | 调用固定 SWMM-2D/CA2D 工具，执行模型检查、情景处理和标准化模拟 |
| `CodeRunner` | 面向固定工具未覆盖的补充分析、绘图、文件处理和临时代码执行 |
| `DataAnalyzer` | 对图像、CSV、TXT、JSON 等结果进行多模态或文本解释 |
| `EvidenceExplainer` | 把固定验证器返回的结构化证据解释成人话 |
| `SimulationEvidenceExplainer` | 把固定模拟流程返回的结构化证据解释成人话 |

论文中提出的 Agent 分工更接近“方法功能层”分工：

| 论文中的功能型 Agent | 对应的功能 |
|---|---|
| Scenario Agent | 降雨事件、工程情景和边界条件组织 |
| Simulation Agent | SWMM-CA2D 标准化模拟流程调度 |
| Data Extraction Agent | 从原始模型输出中构建结构化结果和 evidence table |
| Flood Diagnosis Agent | 基于 evidence table 识别热点、风险等级和可能致灾因素 |
| Evidence Verification Agent | 检查诊断和建议是否有证据支撑，并计算 unsupported rate |
| Evidence Explanation Agent | 把结构化证据和核查结果解释成人类可读文本 |
| Report Agent | 生成证据约束的简报、图表说明或论文结果材料 |

因此，当前阶段不必为了论文概念立即把代码类名全部改成论文中的 Agent 名称。更合理的做法是：

1. 保留当前代码中的实现层组件，避免破坏已经可运行的 Orchestrator/TaskExecutor/CodeRunner/DataAnalyzer 架构。
2. 在论文中明确说明：实现层组件通过工具和流程承载了若干功能型 Agent 角色。
3. 后续当 evidence table、diagnosis、verification、report 逐步稳定后，再决定是否把它们拆成独立模块或独立 Agent。

推荐在论文中采用“two-level agent architecture”的表述：

> At the implementation level, the system consists of an orchestrator, fixed tool executor, code runner, data analyzer, and evidence explainers. At the methodological level, these components instantiate task-oriented agents for scenario organization, standardized simulation, data extraction, flood diagnosis, evidence verification, explanation, and reporting.

## 2. Day01-Day10 与论文的对应关系

| 学习笔记 | 核心概念 | 对论文的作用 | 对应项目模块 | 当前状态 | 下一步 |
|---|---|---|---|---|---|
| Day01 LLM 基础 | LLM 不是数据库、不是逻辑证明器、不是水动力模型 | 支撑 Introduction 和 Discussion 中“Agent 不替代 SWMM/CA2D”的论点 | LLM 解释层、工具调用层 | 已形成概念表述 | 在论文中明确写出 LLM、SWMM/CA2D、程序工具、人类专家的职责边界 |
| Day02 Prompt 工程 | 把模糊工程问题写成可执行任务 | 支撑 Orchestrator Agent 的任务理解与任务拆解 | Orchestrator、TaskExecutor | 已有自然语言任务入口 | 固化任务类型、槽位字段和失败回退规则 |
| Day03 结构化输出 | JSON/schema/evidence_ids/字段约束 | 支撑 evidence table、diagnosis_claims、verification_report | Data Extraction Agent、Evidence Verification Agent | 初步有规范化 run 输出 | 生成统一 `evidence_table.csv` 与 `diagnosis_claims.json` |
| Day04 幻觉与不确定性 | 事实、解释、假设、不确定性分离 | 支撑“降低元素检索与模拟执行幻觉”的论文贡献 | tool-first execution、Evidence Explanation Agent | 已发现并部分解决幻觉问题 | 把幻觉类型转成 benchmark 错误分类 |
| Day05 RAG 基础 | 先检索再回答，embedding 增强资料检索 | 支撑功能创新 2 | 未来 Embedding/RAG 模块 | 计划中 | 明确 RAG 只增强资料检索，不直接替代模型证据 |
| Day06 Agent 与工具调用 | Agent = LLM + Tools + State | 支撑 Methods 中 Agent 架构定义 | Orchestrator、Simulation、Extraction 等 | 已有多个工具和前端入口 | 给每个 Agent 写清 tool interface、输入、输出和约束 |
| Day07 ReAct 与 Plan-Execute | 观察反馈、分步执行、失败修正 | 支撑模拟任务的多步执行流程 | 标准化模拟流程调度 | 初步实现模型检查和模拟执行 | 增加执行轨迹、失败原因和重试记录 |
| Day08 Workflow 与状态管理 | 可复现、可审计、状态机、日志 | 支撑标准化模拟流程和可复现实验设计 | `runs/<run_id>/summary.json`、`run.yaml` | 已有标准化 run 目录 | 固定 run schema，补齐状态、耗时、工具链、错误信息 |
| Day09 约束机制与多 Agent | Guardrails、Human-in-the-loop、多 Agent 分工 | 支撑架构创新：Diagnosis + Verification + Explanation | Flood Diagnosis Agent、Evidence Verification Agent | 诊断与核查模块尚未完全实现 | 先实现规则版诊断和固定验证器，再让 LLM 做解释 |
| Day10 Agent 评估与系统设计 | task success、tool accuracy、unsupported rate 等 | 支撑 Benchmark 与 Results 评价体系 | benchmark runner、评价指标 | 指标体系已有雏形 | 建立 20 个初始 benchmark tasks，后续扩展到 30-80 个 |

## 3. 可直接写进论文的概念转换

### 3.1 从“自然语言交互”提升为“任务编排”

学习笔记中反复强调：LLM 的优势不是做数值模拟，而是理解意图、拆解任务、选择工具和组织结果。对应到论文中，可以写成：

> The proposed framework does not use the LLM as a surrogate hydrodynamic model. Instead, the LLM-based agents serve as an orchestration layer that converts user intents into executable model-inspection, simulation, extraction, diagnosis, verification, and reporting tasks.

中文解释：

> 本文不是让 LLM 代替 SWMM-CA2D 计算，而是让 Agent 把用户意图转化为可执行的模型检查、模拟运行、结果抽取、风险诊断、证据核查和报告生成任务。

### 3.2 从“结果解释”提升为“证据约束诊断”

Day03、Day04、Day09 对论文非常关键。它们共同支撑一个观点：

> 工程 Agent 的可靠性不来自语言回答看起来合理，而来自每条诊断结论都能回溯到结构化证据。

对应论文中的核心机制：

```text
SWMM/CA2D raw outputs
  -> evidence_table.csv
  -> diagnosis_claims.json
  -> verification_report.json
  -> emergency_brief.md
```

其中，`Evidence Verification Agent` 不负责自由发挥，而负责检查：

1. 每条 claim 是否有 `evidence_ids`。
2. 每个 evidence id 是否真实存在。
3. 引用证据是否与诊断对象一致。
4. 引用证据是否满足阈值或规则。
5. 无证据建议是否被计入 unsupported rate。

### 3.3 从“多 Agent 堆叠”提升为“分工明确的工程工作流”

论文中不宜只强调“Agent 数量多”，而应强调“分工边界明确”。推荐表述为：

| Agent 类型 | 论文中的职责 | 不应该做的事 |
|---|---|---|
| Orchestrator Agent | 理解任务、拆解流程、选择工具 | 不直接编造模型结果 |
| Scenario Agent | 识别降雨事件、情景参数、边界条件 | 不随意生成不存在的情景文件 |
| Simulation Agent | 调度 SWMM-CA2D 标准化模拟流程 | 不临时重写已验证的模拟流程 |
| Data Extraction Agent | 从 SWMM/CA2D 输出中抽取结构化指标 | 不做主观风险判断 |
| Flood Diagnosis Agent | 基于 evidence table 识别热点、等级、可能原因 | 不输出无证据结论 |
| Evidence Verification Agent | 检查 claim/recommendation 的证据支撑 | 不替代水动力模型计算 |
| Evidence Explanation Agent | 把结构化证据解释成人类可读文本 | 不新增证据中没有的事实 |
| Report Agent | 生成证据约束的简报或论文结果文本 | 不隐藏 unsupported 条目 |

## 4. 与当前项目差距的衔接

基于学习笔记和当前项目状态，接下来最应该优先补齐的不是更多聊天功能，而是下面这条证据链：

```text
标准化 run 输出
  -> evidence table
  -> rule-based diagnosis
  -> evidence verification
  -> evidence-grounded report
  -> benchmark evaluation
```

### 当前已经具备的基础

1. 已能通过自然语言触发模型项目检查、元素检索和模拟计算。
2. 已有 `runs/<run_id>/summary.json`、`run.yaml` 以及 SWMM/CA2D 输出。
3. 已初步实现两个解释层 Agent：`EvidenceExplainer` 和 `SimulationEvidenceExplainer`。
4. 已经形成 tool-first execution 思路，减少临时代码生成带来的执行幻觉。
5. 已有 web 前端作为演示入口。

### 当前最关键的缺口

1. `evidence_table.csv` 尚未成为每个 run 的标准产物。
2. Flood Diagnosis Agent 尚未形成稳定的规则版输出。
3. Evidence Verification Agent 尚未能计算 unsupported rate。
4. benchmark 任务集尚未建立。
5. 论文图表尚未与可复现脚本完全绑定。

## 5. 一步一步执行清单

### Step 1：固定 run schema

目标：让每次模拟都能被后续 evidence、diagnosis、benchmark 读取。

需要补齐字段：

```text
run_id
model_name
event_name
scenario_name
created_at
status
tool_chain
execution_policy
elapsed_seconds
error_message
output_files
```

论文位置：Methods - Standardized simulation workflow。

### Step 2：生成 evidence table

目标：把模型输出从“文件结果”转为“诊断证据”。

建议字段：

```text
evidence_id
run_id
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

论文位置：Methods - Evidence construction。

### Step 3：实现规则版 Flood Diagnosis Agent

目标：先用确定性规则完成热点识别、风险分级和原因初判。

建议先实现：

1. Top-N 溢流节点。
2. Top-N 最大积水深度区域。
3. 长历时积水区域。
4. 高负荷或瓶颈管段。
5. Low/Moderate/High/Critical 风险等级。
6. 每条诊断绑定 `evidence_ids`。

论文位置：Methods - Flood diagnosis workflow；Results - Case diagnosis。

### Step 4：实现 Evidence Verification Agent

目标：把“有证据”变成可计算指标。

输出文件：

```text
verification_report.json
unsupported_recommendation_rate.txt
```

核心指标：

```text
unsupported rate =
number of unsupported claims or recommendations /
total number of claims or recommendations
```

论文位置：Methods - Evidence verification；Results - Reliability evaluation。

### Step 5：合并解释层 Agent

当前 `EvidenceExplainer` 和 `SimulationEvidenceExplainer` 本质上都是 Evidence Explanation Agent。后续可以统一为：

```text
EvidenceExplanationAgent
```

它只做三件事：

1. 读取结构化证据。
2. 翻译成人类可读解释。
3. 明确不确定性和 unsupported 条目。

论文位置：Methods - Agent roles and tool interfaces。

### Step 6：建立初始 benchmark

目标：从演示系统推进到可评价系统。

第一阶段建议 20 个任务：

| 任务类型 | 数量 | 评价重点 |
|---|---:|---|
| Model information task | 4 | 元素检索是否正确 |
| Simulation task | 4 | 是否正确触发标准化模拟 |
| Extraction task | 4 | 指标提取是否正确 |
| Diagnosis task | 4 | 热点和风险等级是否合理 |
| Report task | 4 | 是否证据完整、unsupported 可见 |

论文位置：Methods - Benchmark design；Results - Benchmark performance。

### Step 7：形成论文图表资产

优先图表：

1. Fig. 1：研究区与 SWMM-CA2D 模型系统。
2. Fig. 2：SWMM-CA2D-Agentic 总体架构。
3. Fig. 3：Agent 协同工作流。
4. Fig. 4：Benchmark 任务体系。
5. Fig. 5：不同方法性能对比。
6. Fig. 6：典型内涝诊断案例。
7. Fig. 7：证据约束应急简报示例。

论文位置：Methods 和 Results。

## 6. 可以对老师汇报的提炼版

可以这样说：

> 我最近把 LLM 与 Agent 的基础知识重新梳理了一遍，发现它和当前论文的主线是对应的。Agent 的创新不应该只表述为自然语言交互，而应表述为一种 evidence-grounded workflow：LLM 负责理解任务、编排流程和解释结果，SWMM-CA2D 负责物理模拟，程序工具负责确定性解析，Evidence Verification Agent 负责检查诊断和建议是否有证据支撑。这样一来，论文的核心贡献就从“能聊天跑模型”提升为“能把大规模内涝模拟组织成可执行、可追踪、可评价的证据约束诊断流程”。

## 7. 后续监视规则

后续每次开发或写作，都应检查新增内容是否回答下面五个问题：

1. 是否服务第一篇 SWMM-CA2D-Agentic 论文？
2. 是否增强标准化模拟、证据构建、诊断、核查或 benchmark？
3. 是否减少 LLM 自由发挥，增加 tool-first 和 evidence-first？
4. 是否能进入论文 Methods、Results 或 Discussion？
5. 是否能回答“Agent 相比传统程序到底带来了什么”？

如果某项工作不能回答这些问题，它就不是当前第一篇论文的优先事项。
