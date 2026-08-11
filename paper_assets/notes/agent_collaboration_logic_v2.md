# SWMM-2D-Agentic 论文 Agent 协同工作逻辑图 V2

本版相对上一版做了两处调整：

1. 将 `CA2D 原始输出` 表达为由 `SWMM 原始输出` 和 `CA2D 二维地表积水模型` 共同生成，避免误解为 CA2D 输出只来自二维模型自身。
2. 将 `SWMM-2D 固定模拟管线调度` 改为 `SWMM-2D 固定模拟渠道调度`，避免审稿老师将“管线”误解为排水管网中的管线/管段。

## Agent 协同逻辑图

```mermaid
flowchart TD
    U["用户 / 专家任务<br/>自然语言问题、降雨情景、诊断需求"] --> O["Orchestrator Agent<br/>任务理解、流程拆解、工具选择"]

    O --> SCA["Scenario Agent<br/>降雨事件识别、情景配置、边界条件组织"]
    O --> SIM["Simulation Agent<br/>SWMM-2D 固定模拟渠道调度"]
    O --> EXT["Data Extraction Agent<br/>模型结果结构化抽取"]
    O --> DIA["Flood Diagnosis Agent<br/>热点识别、风险排序、致灾因子判断"]
    O --> VER["Evidence Verification Agent<br/>证据核查、无证据建议拦截"]
    O --> EXP["Evidence Explanation Agent<br/>结构化证据翻译成人话"]
    O --> REP["Report Agent<br/>证据约束应急简报生成"]

    SCA --> RF["降雨事件库 / 情景库<br/>events, scenario configs"]
    SIM --> SWMM["SWMM 管网模型<br/>节点、管段、泵站、子汇水区"]
    SIM --> CA2D["CA2D 二维地表积水模型<br/>DEM、网格、阻力、节点映射"]

    RF --> SIM
    SWMM --> RAW1["SWMM 原始输出<br/>nodes.tsv, links.tsv, node_flooding.tsv, rpt/out"]

    RAW1 --> RAW2["CA2D 原始输出<br/>由 SWMM 溢流输入与 CA2D 地表模型共同生成<br/>surface_depth.tsv, max depth map, final depth map"]
    CA2D --> RAW2

    RAW1 --> EXT
    RAW2 --> EXT

    EXT --> EVID["Evidence Table<br/>evidence_id, object_id, metric, value, time, source_file"]
    EVID --> DIA

    DIA --> CLAIMS["Diagnosis Claims<br/>热点、风险等级、优先级、致灾因子"]
    CLAIMS --> VER
    EVID --> VER

    VER --> VERIFIED["Verified Claims and Recommendations<br/>带 evidence_ids 的诊断和建议"]
    VER --> UNSUP["Unsupported Items<br/>无证据或证据不足的结论/建议"]

    VERIFIED --> EXP
    UNSUP --> EXP
    EXP --> REP

    REP --> BRIEF["Evidence-grounded Emergency Brief<br/>管理部门可读简报"]
    REP --> BENCH["Benchmark Outputs<br/>task success, F1, Spearman, unsupported rate"]

    BENCH --> PAPER["论文 Results<br/>Fig. 4, Fig. 5, Fig. 6, Fig. 7"]
    BRIEF --> PAPER

    classDef llm fill:#eef5ff,stroke:#4779c4,stroke-width:1px,color:#142033;
    classDef tool fill:#f1fbf4,stroke:#48a868,stroke-width:1px,color:#142033;
    classDef evidence fill:#fff7e8,stroke:#d5962f,stroke-width:1px,color:#142033;
    classDef output fill:#f5f0ff,stroke:#8662c7,stroke-width:1px,color:#142033;

    class O,SCA,DIA,VER,EXP,REP llm;
    class SIM,SWMM,CA2D,RAW1,RAW2,EXT,RF tool;
    class EVID,CLAIMS,VERIFIED,UNSUP evidence;
    class BRIEF,BENCH,PAPER output;
```

## 调整后的关键逻辑说明

### 1. CA2D 输出不是孤立产生的

CA2D 二维地表积水结果并不是只由 CA2D 静态模型独立生成，而是由两类输入共同决定：

- `SWMM 原始输出`：尤其是节点溢流时序、溢流量、溢流节点位置。
- `CA2D 二维地表积水模型`：包括 DEM、网格、阻力、建筑/流动掩膜、节点到网格的映射。

因此图中将 `SWMM 原始输出` 和 `CA2D 二维地表积水模型` 同时连接到 `CA2D 原始输出`，表达的是：

```text
SWMM 节点溢流边界 + CA2D 地表传播模型 -> 二维积水深度、范围和持续时间
```

这个表达更符合水动力耦合逻辑。

### 2. “固定模拟渠道调度”比“固定模拟管线调度”更稳妥

原来的“固定模拟管线调度”容易与排水管网中的“管线/管段”概念混淆。新图改成“固定模拟渠道调度”，强调的是 Agent 调用一条经过验证的模拟执行渠道：

```text
降雨事件写入 SWMM
-> PySWMM 运行
-> 导出节点溢流
-> CA2D 二维积水计算
-> 保存 runs 结果
```

这里的“渠道”不是水力管线，而是系统执行路径或任务通道。若后续觉得“渠道”仍然不够学术，也可以改成：

- 固定模拟流程调度
- 固定模拟路径调度
- 标准化模拟流程调度
- 标准模拟工作流调度

其中，面向论文审稿，我最推荐 `标准化模拟流程调度`。

