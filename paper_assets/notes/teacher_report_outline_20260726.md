# SWMM-CA2D-Agentic 小论文阶段汇报大纲

汇报日期：2026-07-26  
目标论文方向：SWMM-CA2D-Agentic / SWMM-2D-Agentic  
目标期刊：Water Research  
主要对标工作：EPANET-Agentic

## 1. 研究定位

本研究主要脱胎于两位老师分享的 Water Research 论文 **EPANET-Agentic**。原论文展示了多 Agent 如何驱动 EPANET 供水模型，实现自然语言任务理解、工具调用、模型分析和结果生成。我的工作希望在该思路基础上，将研究对象从供水管网模型扩展到城市内涝模拟中的 **SWMM-CA2D 耦合模型**。

初步题目可考虑：

> **SWMM-CA2D-Agentic: Evidence-grounded multi-agent decision support for large-scale urban pluvial flood simulation and diagnosis**

中文可表述为：

> **SWMM-CA2D-Agentic：面向大规模城市内涝模拟与诊断的证据约束多智能体决策支持框架**

本文的重点不是直接做泵站联排联调优化，而是先构建一套可运行、可验证、可解释的 Agentic 框架，用于连接自然语言任务、SWMM 管网模型、CA2D 二维元胞积水模型、结果抽取、风险诊断和证据约束解释。

一句话定位：

> 本文试图证明：LLM-Agent 不只是 SWMM 或 CA2D 的自然语言交互界面，而是可以作为复杂城市内涝模型的任务编排层、证据组织层和结果解释层，将模型执行转化为可追踪、可评价的决策支持工作流。

## 2. 与 EPANET-Agentic 的对标关系

EPANET-Agentic 的核心对象是供水管网模型 EPANET，主要展示多 Agent 如何协同完成模型调用、代码生成、分析和问答。我的工作计划在以下方面进行扩展和推进。

| 对标维度 | EPANET-Agentic | 本研究计划推进 |
|---|---|---|
| 研究对象 | EPANET 供水管网模型 | SWMM-CA2D 城市内涝耦合模型 |
| 模型复杂度 | 一维供水网络仿真 | SWMM 管网 + CA2D 二维地表积水耦合 |
| Agent 作用 | 自然语言驱动模型、工具调用和分析 |细化agents分工，引导CA2D建模、多 Agent 协同驱动模型运行、结果抽取、内涝诊断和证据核查 |
| 结果解释 | 模型结果分析与响应 | 证据约束的风险诊断、优先级排序与应急简报 |
| 可靠性控制 | 成功率、工具调用准确率、代码尝试次数、人工干预次数等 | 在原有指标基础上增加 unsupported rate，用于度量无证据建议比例 |
| 后续拓展 | 可结合更多工具和知识库 | 引入 embedding 向量检索，与证据链协同工作 |

## 3. 拟形成的主要创新点

### 3.1 对象创新：多 Agent 协同驱动 SWMM-CA2D 耦合模型

EPANET-Agentic 面向 EPANET 供水模型，而本研究面向城市内涝场景中的 SWMM-CA2D 耦合模型。相比单一供水管网模型，SWMM-CA2D 涉及管网汇流、节点溢流、管段状态、二维地表积水扩散、积水深度和积水范围等更多类型的模型输入输出。

本研究的对象创新体现在：

1. 从供水网络扩展到排水防涝系统。
2. 从单一一维模型扩展到 SWMM + CA2D 耦合模型。
3. 从模型调用扩展到内涝结果诊断和应急解释。
4. 从小型演示网络扩展到大规模真实或准真实模型。

当前项目中，已经初步完成 LLM 驱动 SWMM-CA2D 进行元素检索与模拟计算，并能保存规范化结果。

### 3.2 架构创新：细化 Agent 分工，加入诊断与证据链溯源

原论文中的 Agent 架构主要强调模型调用、工具使用和分析协作。本研究计划进一步细化 Agent 分工，参考医学类 Agent 中常见的诊断与证据核查思路，形成更适合工程风险诊断的多 Agent 架构。

拟设计的核心 Agent 包括：

1. **Orchestrator Agent**：负责理解自然语言任务、拆解流程和选择工具。
2. **Scenario Agent**：负责识别降雨事件、情景参数和边界条件。
3. **Simulation Agent**：负责调度 SWMM-CA2D 标准化模拟流程。
4. **Data Extraction Agent**：负责从模型输出中抽取结构化指标。
5. **Flood Diagnosis Agent**：负责识别内涝热点、风险等级和可能致灾因子。
6. **Evidence Verification Agent**：负责检查每条诊断和建议是否有模型证据支撑。
7. **Evidence Explanation Agent**：负责将结构化证据翻译成人能理解的说明。
8. **Report Agent**：负责生成面向管理部门或论文实验的结构化报告。

其中，**Flood Diagnosis Agent** 与 **Evidence Verification Agent** 是区别于普通自然语言模型交互的重要新增模块。它们的目标不是让 LLM 自由生成判断，而是让每条诊断和建议都能回溯到模型输出证据。

核心指标为：

```text
unsupported rate = 无有效证据支撑的诊断或建议数量 / 总诊断或建议数量
```

该指标可用于评价 Agent 输出的可信度，也可作为论文中区别于 EPANET-Agentic 的可靠性控制指标。

### 3.3 功能创新 1：将 CA2D 二维元胞模型构建包装为 skill

目前 SWMM 模型的输入输出相对标准化，而 CA2D 二维元胞模型构建涉及 DEM、网格、阻力、建筑物掩膜、流动掩膜、节点到网格映射等多个步骤。普通用户很难一次性准备完整。

因此，计划将 CA2D 模型构建过程包装为一个可复用 skill，通过交互式方式引导用户完成：

1. 输入 DEM 或地形栅格。
2. 设置二维网格范围和分辨率。
3. 准备建筑物、道路或流动掩膜。
4. 设置地表阻力参数。
5. 建立 SWMM 节点到 CA2D 网格的映射。
6. 检查 CA2D 静态模型完整性。
7. 生成可被 SWMM-CA2D-Agentic 调用的标准模型目录。

这一创新的意义在于：不仅让 Agent 能调用已有模型，也让 Agent 能辅助用户完成二维地表模型的构建准备。

### 3.4 功能创新 2：引入 embedding 向量增强检索机制

计划后续引入 embedding 向量检索机制，与证据链协同工作。其目标不是替代模型计算，而是增强 Agent 对以下信息的检索和组织能力：

1. 模型项目说明。
2. 历史运行结果。
3. 诊断规则。
4. 专家报告。
5. 既往案例中的相似积水模式。
6. benchmark 任务与参考答案。

在论文表述中，可以将 embedding 机制定位为证据增强检索层：

> embedding-based retrieval is used to retrieve relevant model metadata, historical diagnostic cases, and rule descriptions, while final diagnostic claims must still be grounded in structured model evidence.

也就是说，embedding 用于帮助找资料、找规则、找类似案例；最终诊断仍必须接受 Evidence Verification Agent 的证据核查。

### 3.5 验证创新：对标四类任务并增加 unsupported rate

计划模仿 EPANET-Agentic 中的任务验证方式，构建适合 SWMM-CA2D 内涝场景的 benchmark。初步可分为四到五类任务：

1. **Model information task**：模型元素检索、节点/管段/雨量站信息查询。
2. **Simulation task**：通过自然语言指定降雨事件和情景，执行 SWMM-CA2D 模拟。
3. **Extraction task**：从标准输出中抽取节点溢流、管段状态、二维积水深度等指标。
4. **Diagnosis task**：识别内涝热点、风险等级和致灾因子。
5. **Report task**：生成证据约束的结构化简报。

评价指标计划包括：

| 指标 | 含义 |
|---|---|
| Task success rate | 任务是否成功完成 |
| Tool invocation accuracy | 工具调用是否正确 |
| Average code generation attempts | 平均代码生成尝试次数 |
| Average human intervention count | 平均人工干预次数 |
| Simulation success rate | 模拟流程是否成功执行 |
| Evidence citation completeness | 诊断和建议是否完整引用证据 |
| Unsupported rate | 无证据支撑的诊断或建议比例 |

其中，unsupported rate 是本研究计划新增的核心可靠性指标。

## 4. 当前已经完成的内容

目前项目已经完成以下基础工作。

### 4.1 LLM 驱动 SWMM-CA2D 元素检索

已实现通过自然语言交互完成模型项目检查和元素索引查验。系统能够围绕 SWMM-CA2D 项目目录，识别模型项目、降雨事件、静态 CA2D 模型和运行输出，而不是简单依赖固定 demo 路径。

这一点对真实工程模型非常重要，因为真实模型目录通常包含：

```text
models/
  model_name/
    model.yaml
    static/
    swmm/
    mapping/
    events/
    runs/
```

Agent 必须理解这些目录的工程语义，避免将项目根目录、静态模型目录、降雨事件文件和 run 输出目录混淆。

### 4.2 LLM 驱动 SWMM-CA2D 模拟计算

当前已初步实现通过自然语言触发 SWMM-CA2D 模拟计算。系统可以将降雨事件写入 SWMM 输入，运行 PySWMM，导出节点溢流结果，再驱动 CA2D 二维地表积水计算，并保存规范化运行结果。

已形成的标准化输出包括：

1. `summary.json`
2. `run.yaml`
3. SWMM 节点溢流输出
4. SWMM 节点和管段结果
5. CA2D 地表积水深度表
6. 最大积水深度图
7. 最终积水深度图

这为后续 evidence table、诊断 Agent 和 benchmark 打下基础。

### 4.3 初步落实规范化结果输出

目前已经从“临时脚本输出”推进到“标准化 run 目录输出”。每次运行可保存到：

```text
models/<model_name>/runs/<run_id>/
```

这有利于后续做多降雨事件、多情景对比，也有利于 benchmark 统一读取结果。

下一步需要在此基础上进一步生成：

```text
evidence_table.csv
diagnosis_claims.json
verification_report.json
emergency_brief.md
```

### 4.4 初步实现解释说明 Agent

目前 web 前端中已经实现了两个解释层 Agent：

1. `EvidenceExplainer`
2. `SimulationEvidenceExplainer`

它们的作用是把固定验证器或固定模拟流程返回的结构化结果解释成人能读懂的话。其核心原则是：

> LLM 只解释已有证据，不自己新增事实、不自己裁决模型是否成功。

后续可将这两个解释层合并为更通用的 **Evidence Explanation Agent**。

### 4.5 已完成一个轻量 Web 前端

目前已完成一个小型 web 前端，用于和 SWMM-CA2D-Agentic 进行交互。用户可以通过自然语言完成：

1. 模型项目检查。
2. 元素索引查验。
3. 降雨事件模拟计算。
4. 规范化结果保存。
5. 运行结果解释。

该前端不是论文的主要创新点，但可以作为系统可用性的展示入口。

## 5. 过程中发现并解决的新问题

在开发 SWMM-CA2D-Agentic 的过程中，发现并初步解决了一些 EPANET-Agentic 迁移到真实复杂工程模型时会遇到的问题。

### 5.1 元素检索中的幻觉问题

早期 Agent 容易在模型元素查询时生成不存在的节点、管段、路径或文件名。这类问题在真实大规模模型中尤其严重，因为模型元素数量大，文件结构复杂，LLM 很容易根据上下文“猜测”。

目前采取的改进思路是：

1. 优先调用确定性工具查询元素。
2. 不让 LLM 自己发明模型目录结构。
3. 将模型项目结构写成固定 schema。
4. 要求模型检查和元素检索必须来自真实文件。

### 5.2 模拟执行中的幻觉问题

早期 Agent 容易在执行模拟时绕过固定工具，转而让 CodeRunner 临时生成脚本，导致模拟流程不稳定、路径错误或工具调用不真实。

目前采取的策略是 **tool-first execution**：

> 对于降雨写入、SWMM 运行、节点溢流导出、CA2D 模拟等已经验证过的固定流程，不允许 LLM 每次临时重写工程代码，而应优先调用固定工具。

这可以降低模拟执行中的幻觉和流程漂移。

### 5.3 结果解释中的幻觉问题

为避免 LLM 在解释结果时编造额外事实，目前采用“证据保留式解释”策略：

1. 固定工具先返回结构化证据。
2. LLM 只解释证据中已经存在的字段。
3. 不允许 LLM 新增成功状态、缺失项、路径、指标或失败原因。

这为后续 Evidence Verification Agent 的实现打下基础。

## 6. 外部学习材料：OpenClaw 开发者专访

2026 年 7 月 20 日，B 站发布了一个关于 OpenClaw 开发者的专访，主题涉及“后 Claw 时代的到来与未来 Agentic 会如何发展”。该访谈内容涉及 Claw 产品的安全性、Memory 设计、Agentic 开发趋势等。

该材料对本研究的启发主要包括：

1. Agentic 系统不能只追求自动化，还必须重视安全边界。
2. Memory 设计不能只是“记住更多”，而应服务任务连续性、上下文恢复和证据追踪。
3. 工程型 Agent 应该具备工具调用审计和失败恢复机制。
4. 对复杂模型系统而言，Agent 的可靠性不仅体现在最终回答，还体现在执行轨迹是否真实、干净、可追踪。

后续计划仔细消化该访谈内容，将其中关于安全性、Memory 和 Agentic 发展趋势的思想转化为论文讨论或系统设计的一部分。

备注：后续可补充 B 站链接与关键摘录。

## 7. 正在推进的模块

目前正在推进或计划推进的模块如下。

### 7.1 Evidence table 生成

将 SWMM 与 CA2D 的原始输出统一整理为结构化证据表。初步字段包括：

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

### 7.2 Flood Diagnosis Agent

基于 evidence table 识别：

1. 关键溢流节点。
2. 高负荷或瓶颈管段。
3. 最大积水深度热点。
4. 长持续积水区域。
5. 风险等级和优先处置顺序。
6. 可能致灾因子。

### 7.3 Evidence Verification Agent

检查每条诊断和建议是否有 evidence_id 支撑，并计算 unsupported rate。

### 7.4 CA2D 构建 skill

将 CA2D 静态模型构建流程包装为 skill，引导用户逐步准备 DEM、网格、阻力、掩膜和节点映射。

### 7.5 Embedding 检索模块

引入 embedding 向量检索，用于增强对模型说明、历史结果、规则文档、专家报告和 benchmark 任务的检索能力。

### 7.6 Benchmark 验证体系

对标 EPANET-Agentic 的任务体系，构建 SWMM-CA2D-Agentic benchmark，比较任务成功率、工具调用准确率、代码尝试次数、人工干预次数和 unsupported rate。

## 8. 计划论文结构

### 8.1 Introduction

重点回答：

1. 城市内涝模拟为什么需要快速、可靠、可解释的决策支持。
2. SWMM-CA2D 耦合模型为什么适合城市内涝模拟，但结果解释门槛较高。
3. EPANET-Agentic 说明 Agentic 方法在水系统模型中的潜力。
4. 现有方法仍缺少面向内涝诊断的证据链约束和可信度评价。

### 8.2 Methods

建议包括：

1. Study area and model system。
2. SWMM-CA2D coupled model。
3. SWMM-CA2D-Agentic architecture。
4. Agent roles and tool interfaces。
5. Standardized simulation workflow。
6. Evidence-grounded diagnosis workflow。
7. Benchmark task design。
8. Evaluation metrics。

### 8.3 Results

建议包括：

1. 模型项目检查与元素检索能力。
2. 自然语言驱动 SWMM-CA2D 模拟能力。
3. 规范化结果输出能力。
4. 内涝热点诊断与证据链展示。
5. unsupported rate 可靠性分析。
6. benchmark 与对比实验。

### 8.4 Discussion

重点讨论：

1. Agent 不是替代 SWMM 或 CA2D，而是任务编排与解释层。
2. 与 EPANET-Agentic 的区别和推进。
3. 真实复杂模型中幻觉控制、工具优先执行和证据约束的重要性。
4. Memory、embedding 与安全边界对未来 Agentic 水系统模型的意义。
5. 后续如何接入泵站联排联调优化。


## 9. 汇报时可用的简短表述

可以对老师这样概括：

> 我这篇论文主要对标 EPANET-Agentic，但研究对象从 EPANET 供水模型转向 SWMM-CA2D 城市内涝耦合模型。当前已经实现自然语言驱动模型项目检查、元素检索和模拟计算，并初步形成标准化结果输出和解释说明 Agent。下一步的核心不是继续做聊天界面，而是补齐 evidence table、Flood Diagnosis Agent 和 Evidence Verification Agent，让每条内涝诊断和建议都能回溯到模型证据，并用 unsupported rate 评价 Agent 输出的可信度。计划 10 月完成初稿。

