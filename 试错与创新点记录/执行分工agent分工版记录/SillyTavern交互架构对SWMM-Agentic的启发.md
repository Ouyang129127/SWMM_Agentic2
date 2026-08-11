# SillyTavern 交互架构对 SWMM-Agentic 的启发

## 记录背景

本记录用于总结 `E:\SillyTavern-release` 对当前 `SWMM-2D-Agentic` 项目的启发。

SillyTavern 是一个成熟的 LLM 交互平台。它的价值不在于角色扮演内容本身，而在于它将长期会话、提示词装配、角色设定、世界书、扩展、插件、多模型后端和用户配置组织成了一个稳定的 LLM 交互运行时。

SWMM-2D-Agentic 的目标不同。我们的核心不是构建通用聊天平台，而是提出一个面向大规模城市内涝模拟与诊断的证据约束多智能体决策支持框架。也就是说，SillyTavern 更像是一个通用 LLM 交互操作系统，而 SWMM-2D-Agentic 更像是一个水动力模型与应急诊断之间的智能编排层。

一句话概括：

> SillyTavern 强在 LLM 交互平台工程；SWMM-2D-Agentic 强在领域模型驱动的证据约束决策工作流。

因此，我们不应把目标设为“做一个 SWMM 版 SillyTavern”，而应学习它的交互架构、上下文组织、扩展机制和多后端适配能力，用于增强 SWMM-2D-Agentic 的可靠性、可扩展性和可演示性。

## 当前 SWMM-Agentic 的相对劣势

### 1. 交互平台层仍然较薄

当前项目已经具备命令行和 Web Chat 雏形，可以完成计划确认、工具调用、模拟运行和结果解释。但相比 SillyTavern，交互层仍偏研究原型。

目前缺少：

- 会话历史的结构化浏览；
- 模型项目、降雨事件、运行结果的统一工作台；
- 运行状态、工具调用、失败原因的可视化展示；
- 结果图、证据表、报告的并列查看；
- 用户可配置的模型参数、诊断规则、报告模板；
- 面向 benchmark 的任务执行面板。

这会导致一个问题：系统虽然能跑通流程，但用户很难从界面上清楚看到“Agent 做了什么、用的是什么证据、生成了哪些结果、哪些环节失败过”。

### 2. 上下文管理还停留在 prompt 字符串层面

当前 `prompts.py` 中已经写入了较完整的 Orchestrator、TaskExecutor、CodeRunner 和 DataAnalyzer 规则。但这些规则仍主要是静态 prompt。

随着系统变复杂，Agent 每次回答需要动态考虑：

- 当前模型项目基本信息；
- 当前降雨事件；
- 已有 run 结果；
- SWMM 输出摘要；
- CA2D 输出摘要；
- 诊断规则；
- 证据表；
- 历史对话；
- 用户当前任务目标；
- 报告面向对象。

如果这些内容都靠 prompt 手工拼接，会导致上下文冗长、重复、不可控，也难以解释每段上下文为什么进入模型。

### 3. 证据约束机制还没有完全工程化

论文构想中提出了 Evidence Verification Agent 和 unsupported recommendation rate，这是非常强的创新点。但当前代码中还缺少完整的证据链数据结构。

特别需要补足：

- `evidence_table.csv/json`；
- 诊断结论与证据的 claim-evidence linking；
- 每条建议对应的模型输出来源；
- 无证据建议的自动识别；
- 证据完整性评分；
- 面向论文实验的 hallucination / unsupported recommendation 统计。

也就是说，我们的理论叙事已经有了，但工程系统还需要把“有据可查”落实到结构化文件和评分器中。

### 4. 工具注册和扩展机制仍比较静态

当前工具主要集中在 `tools.py`，适合早期原型。但如果后续加入更多模块，例如泵站规则、道路风险、敏感点识别、历史灾情、专家规则库、不同二维模型、不同报告模板，单个工具文件会越来越臃肿。

更理想的方式是让每类能力成为可注册模块：

- 声明工具名称；
- 声明输入 schema；
- 声明输出 schema；
- 声明适用任务类型；
- 声明产生哪些证据；
- 声明如何进入报告；
- 声明如何参与 benchmark 评分。

这正是 SillyTavern 插件与扩展机制能提供启发的地方。

### 5. Benchmark 执行机制还需要落地

论文中已经提出 30-80 个 benchmark 任务，覆盖 simulation、extraction、diagnosis、decision-support 和 report。但当前项目还缺少一个正式的 benchmark runner。

后续需要：

- 标准任务集；
- 标准答案或人工标注；
- 期望工具调用；
- 评分规则；
- 自动执行日志；
- 指标汇总表；
- 失败类型统计。

否则系统容易停留在 demo 层面，而不是可评价的研究系统。

### 6. 多模型角色分工还可以更清晰

当前项目已经使用 DeepSeek 和 Qwen，但还可以进一步抽象不同模型角色：

- PlannerModel：任务理解与计划；
- ToolModel：工具调用；
- CodeModel：代码生成；
- VisionModel：图像与图表分析；
- VerifierModel：证据核查；
- ReportModel：报告生成。

这样可以避免把某一个模型供应商和系统架构绑定，也有利于论文中讨论模型替换、稳定性和成本。

## SillyTavern 最值得学习的机制

### 1. PromptManager 思想

SillyTavern 的 PromptManager 思想非常值得迁移。它不是只写一个大 prompt，而是把系统提示词、角色信息、世界书、扩展提示词、历史消息、用户输入等组合成最终请求。

SWMM-2D-Agentic 可以建立自己的 `ContextManager` 或 `PromptAssembler`，负责动态装配：

- 项目基本信息；
- 模型结构摘要；
- 可用工具列表；
- 当前任务计划；
- 当前 run 摘要；
- 关键 SWMM 输出；
- 关键 CA2D 输出；
- 诊断规则；
- 证据表；
- 报告模板；
- 历史对话摘要。

这可以形成一个新的工程机制：

> Evidence-aware context assembly for hydraulic-model agents.

中文可表述为：

> 面向水动力模型智能体的证据感知上下文装配机制。

### 2. World Info 思想

SillyTavern 的 World Info 本质上是一种按触发条件注入上下文的知识库。对 SWMM-2D-Agentic 来说，可以迁移为“领域规则库”或“工程知识库”。

可注入内容包括：

- 降雨重现期解释；
- 内涝风险等级规则；
- 积水深度阈值；
- 管段满流诊断规则；
- 节点溢流诊断规则；
- 学校、医院、地下空间、主干路等敏感对象；
- 历史积水点；
- 泵站联排联调规则；
- 专家经验规则。

触发条件不应只是关键词，而可以包括：

- 任务类型；
- 模型元素 ID；
- 空间区域；
- 降雨情景；
- 风险等级；
- 输出指标；
- 用户报告对象。

这可以让系统从“LLM 临时理解规则”转向“规则按需注入、证据按需引用”。

### 3. Extension Prompt 思想

SillyTavern 允许扩展模块向最终上下文注入额外提示词。SWMM-2D-Agentic 可以借鉴这一点，把不同诊断能力做成可插拔模块。

例如：

- 节点溢流诊断模块；
- 管段瓶颈诊断模块；
- 地表积水热点模块；
- 风险优先级排序模块；
- 应急建议模块；
- 报告生成模块；
- 证据核查模块；
- 泵站调度规则模块。

每个模块可以贡献：

- 自己的 prompt 片段；
- 自己的工具函数；
- 自己的证据 schema；
- 自己的评分指标；
- 自己的报告段落模板。

这比把所有规则写进一个总 prompt 更清晰，也更适合后续从第一篇论文扩展到第二篇泵站联排联调论文。

### 4. Slash Command / Macro 思想

SillyTavern 的 slash command 和 macro 机制对工程系统很有价值。

SWMM-2D-Agentic 可以设计面向模型工程师的快捷命令：

```text
/check_model songhua_swmm_2d
/list_events songhua_swmm_2d
/run_event model=songhua_swmm_2d event=rain1 scenario=baseline run_id=test01
/top_flood_nodes run_id=test01 n=20
/top_depth_cells run_id=test01 n=20
/diagnose_hotspots run_id=test01
/verify_evidence run_id=test01
/report run_id=test01 audience=emergency
```

这些命令不是为了替代自然语言，而是为了增强可复现性和可演示性。论文 benchmark 中也可以直接使用这类命令作为任务输入的一部分。

### 5. 多后端适配思想

SillyTavern 支持大量模型后端，并处理不同 API 的消息格式差异。SWMM-2D-Agentic 不需要支持那么多模型，但需要学习这种“模型后端与业务逻辑分离”的设计。

建议抽象：

```text
LLMProvider
  PlannerModel
  ToolCallingModel
  CodeModel
  VisionModel
  VerifierModel
  ReportModel
```

这样后续可以比较：

- DeepSeek Planner + Qwen Vision；
- OpenAI Planner + local CodeModel；
- Qwen ToolModel + DeepSeek ReportModel；
- 低成本模型用于工具路由，高能力模型用于解释和报告。

这对论文实验也有帮助，因为可以讨论不同 agent 角色对模型能力的需求。

### 6. 会话与运行历史持久化思想

SillyTavern 对聊天、角色、设置和用户数据都有持久化设计。SWMM-2D-Agentic 应把会话与模型运行结果打通。

建议形成如下链条：

```text
session
  -> user_request
  -> plan
  -> tool_calls
  -> run_id
  -> swmm_outputs
  -> ca2d_outputs
  -> evidence_table
  -> diagnosis
  -> report
  -> benchmark_scores
```

这样每次任务都能追踪：

- 用户问了什么；
- Agent 怎么拆解；
- 调用了哪些工具；
- 哪些文件被读取或生成；
- 结论来自哪些证据；
- 哪些建议无证据；
- 最终任务是否成功。

这正好支撑论文中的“可执行、可追踪、可评价”。

## 可转化为论文创新点的方向

### 方向 1：证据感知上下文装配

可以从 SillyTavern 的 PromptManager 得到启发，但转化为水动力模型场景：

> SWMM-2D-Agentic introduces an evidence-aware context assembly mechanism that dynamically selects model metadata, simulation summaries, diagnostic rules, evidence tables, and user task history under a controlled context budget.

中文：

> SWMM-2D-Agentic 引入证据感知上下文装配机制，在受控上下文预算下动态选择模型元数据、模拟摘要、诊断规则、证据表和用户任务历史，从而提高复杂工程任务中的上下文相关性与输出可靠性。

### 方向 2：领域规则的触发式注入

借鉴 World Info，但不叫 World Info，可以叫：

> Domain-rule triggering and injection.

中文：

> 领域规则触发与注入机制。

核心思想是：不同任务、区域、模型元素和风险对象触发不同规则，而不是每轮对话加载所有规则。

### 方向 3：模块化诊断扩展机制

借鉴 extension prompt 和 plugin 思想，将 SWMM-2D-Agentic 的诊断能力拆成多个模块：

```text
OverflowDiagnosisModule
PipeBottleneckModule
SurfaceInundationModule
RiskRankingModule
EvidenceVerificationModule
EmergencyReportModule
```

每个模块拥有自己的工具、规则、证据类型和输出模板。

这可以支撑第一篇论文的架构创新，也能自然衔接第二篇论文中的泵站联排联调规则模块。

### 方向 4：可复现的命令式任务接口

自然语言适合开放任务，但论文实验需要可复现。可以引入 slash-command-like 的任务接口：

```text
/run_event ...
/diagnose ...
/verify ...
/report ...
```

这既保留自然语言交互，又提供可控 benchmark 输入。

### 方向 5：模型后端与 agent 角色解耦

把不同 agent 角色与具体 LLM 供应商解耦，可形成更稳健的系统设计：

```text
Agent role -> model capability requirement -> provider implementation
```

这有利于系统扩展，也有利于论文讨论成本、稳定性和模型替换能力。

## 建议的工程落地优先级

### 第一优先级：Evidence Table

先实现结构化证据表，这是最贴合论文创新的部分。

建议字段：

```text
claim_id
claim_text
evidence_type
source_file
object_id
metric
value
unit
time
threshold
support_status
```

这一步完成后，Evidence Verification Agent 和 unsupported recommendation rate 才有可靠输入。

### 第二优先级：ContextManager

建立一个上下文装配层，替代单纯静态 prompt 拼接。

它应根据任务类型选择：

- 模型元数据；
- 当前 run 摘要；
- 相关证据；
- 相关规则；
- 相关历史对话；
- 报告模板。

### 第三优先级：Benchmark Runner

建立任务集和评分器，让系统从 demo 变成可评价实验。

建议目录：

```text
tasks/
  benchmark/
    simulation_tasks.json
    extraction_tasks.json
    diagnosis_tasks.json
    decision_support_tasks.json
    report_tasks.json
```

### 第四优先级：模块化工具注册

将 `tools.py` 中不断增长的工具逐步拆分为可注册模块。

例如：

```text
tools/
  registry.py
  swmm_tools.py
  ca2d_tools.py
  evidence_tools.py
  diagnosis_tools.py
  report_tools.py
```

### 第五优先级：工作台界面

Web UI 不必模仿 SillyTavern 的完整复杂度，但可以形成 SWMM 工程工作台：

- 左侧：模型项目、降雨事件、运行记录；
- 中间：对话与计划执行；
- 右侧：证据表、图件、报告、评分结果；
- 底部：工具调用日志与失败恢复记录。

## 论文表述建议

可以在论文 Discussion 中这样写：

> General-purpose LLM interaction platforms demonstrate the importance of persistent conversations, configurable prompt assembly, extensible knowledge injection, and multi-backend model adaptation. However, hydraulic decision-support agents require stronger domain-specific constraints than conversational platforms. SWMM-2D-Agentic adapts these interaction-engineering principles to a model-grounded workflow, where contextual information is selected from model metadata, simulation outputs, diagnostic rules, and evidence tables, and where every diagnostic recommendation is checked against traceable hydraulic evidence.

中文可写为：

> 通用 LLM 交互平台表明，长期会话、可配置提示词装配、可扩展知识注入和多模型后端适配对于稳定交互系统非常重要。然而，水动力决策支持智能体相比通用对话平台需要更强的领域约束。SWMM-2D-Agentic 将这些交互工程思想迁移到模型驱动工作流中，使上下文信息来自模型元数据、模拟输出、诊断规则和证据表，并要求每条诊断建议都接受可追踪水力证据的核查。

## 总体判断

SillyTavern 最值得学习的是平台化能力，而不是具体聊天内容。

它提醒我们，一个成熟的 LLM 应用不只是“调用一次模型”，而是要处理：

- 上下文如何进入模型；
- 长期会话如何保存；
- 用户配置如何影响输出；
- 扩展能力如何注册；
- 多模型后端如何适配；
- 工具和插件如何隔离；
- 交互过程如何可观察。

但 SWMM-2D-Agentic 的核心价值仍然不同。我们的关键创新应继续落在：

- 大规模 SWMM-2D 模型自动化调用；
- 模型结果结构化抽取；
- 内涝热点与风险诊断；
- 证据约束解释；
- unsupported recommendation rate；
- benchmark 量化评价。

最终目标不是复刻 SillyTavern，而是构建一个：

> 面向 SWMM-2D 内涝诊断的 evidence-grounded agentic decision-support workbench。

也就是：

> 面向 SWMM-二维内涝诊断的证据约束智能体决策支持工作台。

