# SWMM-Agentic2 新旧 Agent 架构审计与整改沟通稿

## 1. 审计结论

当前 `SWMM-Agentic2` 不是纯粹的“工作环节型 Agent 架构”，而是一个过渡态：

```text
旧能力型 Agent 外壳
  + 新工作环节型 workflow_agents 内核
```

也就是说，新架构已经部分落地，但还没有成为系统的主入口和主路由。用户从 Web 或 CLI 进入系统时，仍然主要由旧的 `Orchestrator -> TaskExecutor / CodeRunner / DataAnalyzer` 进行任务分发；新的 `EvidenceBuilderAgent`、`DiagnosisAgent`、`VerificationAgent` 和 `StatefulOrchestrator` 目前更多是被包装成 `TaskExecutor` 可调用的工具。

这不是需求描述错误，而是实现策略偏保守：先把新工作流能力接入旧系统，保证不破坏原有功能。但如果本项目的目标是验证“第二种 Agent 工作结构”，后续需要把 `StatefulOrchestrator` 提升为主入口，并降低旧 Agents 对标准流程的路由权。

## 2. 已经完成的新架构部分

### 2.1 新工作流目录已经存在

当前已经新增：

```text
workflow_agents/
  state.py
  schemas.py
  evidence_builder.py
  diagnosis.py
  verification.py
  orchestrator.py
  rules/
    diagnosis_rules.json
    verification_rules.json
```

这说明第二种架构并不是只停留在概念层面，已经有了可运行的核心代码。

### 2.2 StatefulOrchestrator 已经实现

`workflow_agents/orchestrator.py` 中已经实现了 `run_workflow_stage()`，其核心逻辑是：

```text
RUN_READY
  -> evidence_building
  -> EVIDENCE_READY
  -> diagnosis
  -> DIAGNOSIS_READY
  -> verification
  -> VERIFIED_READY
```

它已经具备“状态机驱动”的基本特征：

- 读取或初始化 `workflow_state.json`
- 判断当前状态允许执行的下一步
- 阻止非法跳步
- 记录每个阶段的完成历史
- 失败时进入 `FAILED` 状态

这部分符合我们前面讨论的原则：

> 工作环节型 Agent 不应由 Orchestrator 自由猜测调用顺序，而应由状态机驱动。

### 2.3 三个核心工作环节 Agent 已经实现

当前已经实现：

| 工作环节 | 当前实现 | 输出 |
|---|---|---|
| EvidenceBuilderAgent | `workflow_agents/evidence_builder.py` | `evidence/evidence_table.csv`、`evidence/evidence_summary.json` |
| DiagnosisAgent | `workflow_agents/diagnosis.py` | `diagnosis/diagnosis_claims.json`、`diagnosis/risk_ranking.csv` |
| VerificationAgent | `workflow_agents/verification.py` | `verification/verification_report.json`、`verification/unsupported_rate.txt` |

这三个 Agent 的实现方式偏“确定性规则核心”，不是自由 LLM Agent。这是合理的，因为证据构建、诊断声明和证据核查都需要可复现、可评价、可审计。

## 3. 仍然保留旧架构的部分

### 3.1 Web 主入口仍然使用旧 Orchestrator

`main.py` 中的 Web 入口仍然是：

```python
tool_list = [] if planning_only else [TaskExecutor, CodeRunner, DataAnalyzer]
```

这意味着 Web 对话中的自然语言任务仍然先进入旧的 `Orchestrator`，由它在 `TaskExecutor`、`CodeRunner`、`DataAnalyzer` 之间选择。

因此，虽然新工作流 Agent 已经存在，但它们不是 Web 交互的第一层调度对象。

### 3.2 CLI 主入口也仍然使用旧 Agents

`main.py` 中的 CLI 入口仍然注册：

```python
tools=[TaskExecutor, CodeRunner, DataAnalyzer]
```

因此，命令行交互同样还没有完全切换到工作环节型架构。

### 3.3 prompts.py 仍然以旧 Agent 名单为主

`prompts.py` 中的可用 Agent 仍然主要写成：

```text
TaskExecutor
CodeRunner
DataAnalyzer
```

虽然文档中补充了：

```text
RUN_READY -> EvidenceBuilderAgent -> EVIDENCE_READY
EVIDENCE_READY -> DiagnosisAgent -> DIAGNOSIS_READY
DIAGNOSIS_READY -> VerificationAgent -> VERIFIED_READY
```

但这只是把新工作流作为旧 `TaskExecutor` 的工具调用规则嵌进去，而不是把主架构改成：

```text
StatefulOrchestrator
ScenarioAgent
SimulationAgent
EvidenceBuilderAgent
DiagnosisAgent
VerificationAgent
ReportAgent
BenchmarkAgent
```

### 3.4 新 Agent 目前是“工具核心”，不是顶层对话 Agent

当前 `EvidenceBuilderAgent`、`DiagnosisAgent`、`VerificationAgent` 不是独立的 `AssistantAgent`。它们是确定性 Python 函数，被 `tools.py` 包装成：

```text
build_run_evidence
diagnose_run
verify_run_diagnosis
run_workflow_stage
```

这种做法本身没有问题，甚至对论文更有利，因为它更可复现。但在论文叙述中需要讲清楚：

> 这些 Agent 是工作环节型智能执行单元，其核心采用确定性工具和规则实现，LLM 主要负责目标理解、流程解释和人机交互，不直接自由生成诊断结论。

## 4. 当前版本容易造成的误解

### 4.1 容易误以为第二种架构已经完整替代旧架构

实际上还没有。更准确说法应是：

```text
SWMM-Agentic2 已经加入工作环节型 Agent 内核，
但 Web/CLI 入口仍沿用旧的能力型 Agent 路由。
```

### 4.2 容易把 TaskExecutor 误认为工作环节型 Agent

当前 `TaskExecutor` 仍然承担过多职责：

- 项目检查
- CA2D 检查
- 模拟运行
- 证据构建
- 诊断
- 核查

这会削弱第二种架构的说服力。因为按照工作环节型架构，至少应当区分：

```text
ScenarioAgent：负责模型、事件、情景检查与组织
SimulationAgent：负责标准化模拟流程
EvidenceBuilderAgent：负责证据表构建
DiagnosisAgent：负责诊断声明生成
VerificationAgent：负责证据核查与 unsupported rate
ReportAgent：负责报告组织
BenchmarkAgent：负责实验评价
```

### 4.3 旧 CodeRunner 仍可能引入路由漂移

当前 `CodeRunner` 仍然在默认工具列表中。如果用户要求“模拟、分析、图表、结果提取”，它仍可能被调用。

这会导致两个风险：

1. 官方 SWMM-CA2D 标准模拟流程绕过固定工具。
2. 证据构建、诊断、核查被临时代码替代。

这与第二种架构“降低路由漂移”的目标不完全一致。

## 5. 建议整改方向

### 5.1 保留旧版本作为对照组

建议不要删除 `SWMM-Agentic` 的旧架构。它可以作为论文中的第一种实验结构：

```text
能力型 Agent 架构：
Orchestrator + TaskExecutor + CodeRunner + DataAnalyzer
```

它适合说明系统从 EPANET-Agentic 思路迁移到 SWMM-CA2D 后，已经能完成元素检查、模型验证、模拟执行和结果解释。

### 5.2 将 SWMM-Agentic2 明确改成第二种架构

`SWMM-Agentic2` 应当定位为：

```text
工作环节型 Agent 架构：
StatefulOrchestrator + ScenarioAgent + SimulationAgent + EvidenceBuilderAgent + DiagnosisAgent + VerificationAgent + ReportAgent
```

第一阶段可先完成：

```text
StatefulOrchestrator
ScenarioAgent
SimulationAgent
EvidenceBuilderAgent
DiagnosisAgent
VerificationAgent
```

`ReportAgent` 和 `BenchmarkAgent` 可以后续继续补。

### 5.3 让 StatefulOrchestrator 成为主入口

建议新增或改造入口函数：

```text
run_workflow_orchestrator_agent_turn()
```

其职责是：

- 读取用户意图
- 读取 `workflow_state.json`
- 判断当前阶段
- 只允许调用合法的下一工作环节
- 不把标准流程交给 CodeRunner 自由生成

### 5.4 旧 Agents 应降级为底层能力或辅助通道

建议将旧 Agent 重新定位：

| 旧对象 | 新定位 |
|---|---|
| TaskExecutor | 固定工具集合，不再作为顶层 Agent 概念 |
| CodeRunner | 自定义分析/临时图表辅助工具，不参与标准流程 |
| DataAnalyzer | 解释辅助工具，不替代 DiagnosisAgent |
| Orchestrator | 被 StatefulOrchestrator 替代或改造成状态机驱动入口 |

### 5.5 论文中建议这样表述

建议论文里不要说“完全抛弃旧 Agent”，而是说：

> 本研究首先实现了能力型 Agent 架构，用于验证 SWMM-CA2D 耦合模型的自然语言驱动、元素检索和标准化模拟执行能力。在此基础上，进一步提出工作环节型 Agent 架构，将复杂内涝诊断任务拆解为情景组织、模拟执行、证据构建、风险诊断和证据核查等稳定环节，并通过状态机约束 Agent 调用顺序，以降低路由漂移和无证据诊断风险。

## 6. 给另一个工作区的整改沟通稿

下面这段可以直接复制给另一个工作区的 Codex：

```text
您好，请你帮我整改 E:\SWMM_Agentic\SWMM-Agentic2。

这个项目的目标不是继续沿用旧的 Orchestrator + TaskExecutor + CodeRunner + DataAnalyzer 架构，而是实验第二种“工作环节型 Agent 架构”。

请先阅读：
1. E:\SWMM_Agentic\SWMM-Agentic2\开发计划及与SWMM-Agentic的区别说明\workflow_stage_agent_architecture_dev_design.md
2. E:\SWMM_Agentic\SWMM-Agentic2\开发计划及与SWMM-Agentic的区别说明\工作环节型Agent架构试验方案.md
3. E:\SWMM_Agentic\SWMM-Agentic2\开发计划及与SWMM-Agentic的区别说明\SWMM-Agentic2_新旧Agent架构审计与整改沟通稿.md

请注意：目前 SWMM-Agentic2 已经有 workflow_agents 目录，其中实现了：
- StatefulOrchestrator
- EvidenceBuilderAgent
- DiagnosisAgent
- VerificationAgent

但当前 Web/CLI 主入口仍然是旧的 Orchestrator 调用 TaskExecutor、CodeRunner、DataAnalyzer。也就是说，新架构目前只是被包装进 TaskExecutor 工具里，并没有成为主路由。

我希望你做的是：

1. 不要删除旧代码，但要把它们降级为底层工具或 legacy 能力。
2. 新增或改造一个真正的 workflow-stage 主入口，例如 run_workflow_orchestrator_agent_turn。
3. 让 StatefulOrchestrator 成为第二架构的主调度者。
4. 标准流程不要由 Orchestrator 自由猜测 TaskExecutor、CodeRunner、DataAnalyzer 的调用顺序，而要由 workflow_state.json 控制合法状态转移。
5. 将模型检查、降雨事件选择、标准化模拟、证据构建、诊断、核查拆成清晰的工作环节。
6. CodeRunner 只能作为自定义分析或临时可视化辅助，不应参与官方标准模拟、证据构建、诊断和 unsupported rate 计算。
7. DataAnalyzer 只能作为解释辅助，不应替代 DiagnosisAgent 或 VerificationAgent。
8. 整改后请更新 README 和 prompts，使它们明确区分：
   - legacy capability agents
   - workflow-stage agents

最终目标是让 SWMM-Agentic2 可以被清楚地描述为：

用户自然语言任务
-> StatefulOrchestrator
-> ScenarioAgent
-> SimulationAgent
-> EvidenceBuilderAgent
-> DiagnosisAgent
-> VerificationAgent
-> ReportAgent

其中 ReportAgent 可以先留作后续扩展，但前面的标准化模拟、证据、诊断、核查流程需要尽量跑通。

请先做架构审计，不要一上来大规模删除。然后给出最小可行整改方案，并逐步实现。
```

## 7. 可以向老师汇报的稳妥说法

如果现在就要汇报，建议这样说：

> 目前我们已经完成了第一种能力型 Agent 架构，能够支持 SWMM-CA2D 耦合模型的自然语言交互、元素检查、模型完整性验证、标准化模拟执行和规范化结果保存。随后，我们进一步尝试第二种工作环节型 Agent 架构，目前已经实现了证据构建、诊断生成和证据核查三个环节的确定性 Agent 核心，并引入 `workflow_state.json` 对执行顺序进行状态约束。下一步将把 Web/CLI 入口从旧的自由路由方式改造为 `StatefulOrchestrator` 驱动，使模型检查、模拟执行、证据构建、诊断和核查形成更稳定、可追踪、可评价的 Agent 协同流程。

这句话比较稳，因为它没有夸大当前实现，也能体现你的路线是不断演进的。

## 8. 最重要的一句话

当前 `SWMM-Agentic2` 的问题不是“没有新 Agent”，而是：

```text
新 Agent 已经有了，但还没有成为系统主路由。
```

后续整改的核心，就是把新工作环节型 Agent 从 `TaskExecutor` 下面“提上来”，让它们真正成为 `SWMM-Agentic2` 的架构主体。
