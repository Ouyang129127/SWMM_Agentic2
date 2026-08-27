# 本体论启发的内涝关系证据网概念设计

## 1. 研究定位

当前 SWMM-CA2D Agentic 工作流已经能够从模拟结果中筛选地表积水元胞、冒溢检查井节点、高负荷管段和流向不稳定管段，并将其转化为结构化证据表和诊断结论。然而，现有证据组织方式仍以对象级证据为主，即分别回答“哪些 cell 积水严重”“哪些 node 发生冒溢”“哪些 link 处于高负荷状态”。这种方式适合风险对象识别，但对于进一步解释内涝成因仍不充分。

城市内涝成因往往不是单一对象异常造成的，而是地表汇流、节点冒溢、管段满流、上下游顶托、泵站调度和排口边界共同作用的结果。因此，若要让 DiagnosisAgent 从“异常对象识别”推进到“工程成因追溯”，需要在证据表基础上进一步构建对象之间的空间关系、拓扑关系和证据支撑关系。

本研究拟构建一种本体论启发的内涝关系证据网。这里的“本体论启发”并不是指建立完整的城市排水领域本体系统，而是借用本体论中对象、关系、属性和语义约束的思想，将 SWMM-二维地表模型中的关键对象及其诊断证据组织为可查询、可追溯、可核查的结构化证据底座。

该关系证据网的第一版目标不是覆盖所有排水系统概念，而是构建一个最小可行的地表-节点-管段关系网络。它以冒溢节点为诊断锚点，向地表 cell 积水响应和上下游管段流态两侧展开，为后续 DiagnosisAgent 生成关系型诊断结论提供输入。

## 2. 设计原则

### 2.1 诊断问题驱动

关系证据网不应为了“建图”而建图，而应由内涝诊断问题反向定义对象、关系和证据。现阶段优先服务以下问题：

1. 冒溢节点周边是否存在显著地表积水响应？
2. 冒溢节点附近积水 cell 是否形成连续淹没片区？
3. 冒溢节点直接相连的管段是否处于高充满度或满流状态？
4. 冒溢节点上游是否存在集中来水或高负荷输入？
5. 冒溢节点下游是否存在满流、顶托、排放受限或流向异常信号？

这五个问题对应当前最小关系证据网的核心诊断路径。

同时，诊断证据包需要纳入本次降雨事件的强度背景。同样的地表积水或节点冒溢，在小雨、中雨、大雨、暴雨和短时强降水条件下具有不同工程含义。若强降雨或超标准暴雨下出现积水，可能更多指向系统承载能力达到上限；若中小雨条件下仍出现显著积水或节点冒溢，则更可能提示局部管网缺陷、地形低洼、排水设施堵塞、下游顶托或模型结构问题。因此，降雨强度分析应作为 DiagnosisAgent 判断成因时的上游语境。

### 2.2 对象、关系、证据分离

关系证据网应区分三类内容：

- 对象层：定义系统中有哪些实体，例如 cell、node、link。
- 关系层：定义实体之间如何连接，例如邻近、邻接、上下游、连通。
- 证据层：定义每个对象或关系有哪些模拟结果支撑，例如积水深度、溢流量、充满度、流向变化。

这种分离可以避免把诊断结论提前写入证据构建环节。证据网构建环节只负责“把路修出来”，DiagnosisAgent 才负责“沿路判断问题”。

### 2.3 先局部追溯，再系统扩展

城市排水网络规模较大，如果直接对全网做多级追溯，容易造成证据冗余和解释噪声。第一版关系证据网应采用局部子图策略，以冒溢节点为中心，将追溯范围限定在：

- 地表侧：冒溢节点附近 cell 及其 4 邻域或 8 邻域积水扩展范围；
- 管网侧：与冒溢节点直接连接的上游、下游管段；
- 上游追溯：追溯至上一个汇流节点或起始节点；
- 下游追溯：追溯至下一个汇流节点、泵站或排口。

这样既能体现工程师式诊断逻辑，又能控制证据包规模。

### 2.4 可核查与可回溯

关系证据网中的每个对象、关系和诊断证据包都应尽量保留来源信息，包括 source_file、data_source、evidence_id、relation_id、trace_path 等字段。后续 VerificationAgent 不仅要核查 claim 是否有 evidence_id 支撑，还应进一步核查 claim 是否有 relation_path 支撑。

## 3. 三层结构

### 3.1 对象层 Object Layer

对象层负责回答“系统中有哪些可被诊断的工程对象”。第一版关系证据网优先包含三类对象。

| 对象类型 | 含义 | 第一版用途 |
|---|---|---|
| `SurfaceCell` | 二维地表元胞或积水网格 | 表征地表积水深度、积水持续时间和邻域淹没扩展 |
| `JunctionNode` | SWMM 检查井或节点 | 表征节点水位、冒溢量、冒溢持续时间，是第一版诊断锚点 |
| `ConduitLink` | SWMM 排水管段 | 表征管段流量、充满度、满流状态和流向变化 |

后续扩展对象包括：

| 对象类型 | 含义 | 预期用途 |
|---|---|---|
| `PumpStation` | 泵站或泵组 | 判断泵站能力、频繁启停及其对上游水位波动的影响 |
| `Outfall` | 排口或出流边界 | 判断下游边界、尾水位和排放受限影响 |
| `DrainageDistrict` | 排水分区 | 支持从局部节点问题扩展到分区排水能力诊断 |
| `Subcatchment` | 汇水区 | 支持地表径流来源、产汇流路径和地表响应解释 |
| `RainfallEvent` | 降雨事件 | 支持峰值响应时间和不同降雨情景对比 |
| `SimulationRun` | 模拟批次 | 保留模型、降雨、情景和运行时间等溯源信息 |

### 3.2 关系层 Relation Layer

关系层负责回答“对象之间如何联系”。第一版关系类型如下。

| 关系类型 | source | target | 含义 | 来源 |
|---|---|---|---|---|
| `node_near_cell` | `JunctionNode` | `SurfaceCell` | 冒溢节点附近的地表 cell | 坐标距离或空间索引 |
| `cell_adjacent_to_cell` | `SurfaceCell` | `SurfaceCell` | cell 之间的 4 邻域或 8 邻域邻接 | 二维元胞网格结构 |
| `node_connected_to_link` | `JunctionNode` | `ConduitLink` | 节点与管段直接连接 | SWMM 管网拓扑 |
| `link_upstream_of_link` | `ConduitLink` | `ConduitLink` | 管段上游追溯关系 | SWMM 管网拓扑 |
| `link_downstream_of_link` | `ConduitLink` | `ConduitLink` | 管段下游追溯关系 | SWMM 管网拓扑 |

后续可扩展关系如下。

| 关系类型 | 含义 |
|---|---|
| `cell_within_subcatchment` | cell 属于某一汇水区 |
| `node_belongs_to_district` | 节点属于某排水分区 |
| `link_belongs_to_district` | 管段属于某排水分区 |
| `pump_serves_district` | 泵站服务某排水分区 |
| `outfall_receives_from_link` | 排口接收某管段或管网出流 |
| `downstream_backwater_affects_upstream` | 下游高水位或满流对上游形成顶托影响 |
| `pump_operation_affects_node` | 泵站启停与节点水位波动存在时间关联 |

### 3.3 证据层 Evidence Layer

证据层负责回答“每个对象或关系有什么模拟证据支撑”。第一版主要挂接以下证据。

| 对象 | 证据指标 | 含义 |
|---|---|---|
| `SurfaceCell` | `max_depth` | 最大地表积水深度 |
| `SurfaceCell` | `ponding_duration` | 积水持续时间 |
| `JunctionNode` | `total_flooding_volume` | 节点累计冒溢量 |
| `JunctionNode` | `max_flooding_flow` | 节点最大冒溢流量 |
| `JunctionNode` | `flooding_duration` | 节点冒溢持续时间 |
| `ConduitLink` | `max_fullness` | 管段最大充满度 |
| `ConduitLink` | `max_flow` | 管段最大流量 |
| `ConduitLink` | `flow_direction_changes` | 管段流向变化次数 |

后续建议补充：

| 对象 | 证据指标 | 用途 |
|---|---|---|
| `ConduitLink` | `fullness_duration` | 判断长期满流管段 |
| `JunctionNode` | `overflow_event_count` | 判断反复冒溢节点 |
| `ConduitLink` | `full_flow_capacity` | 判断流量是否超过满流能力 |
| `RainfallEvent` | `rainfall_peak_time` | 与节点/管段响应峰值时间对比 |
| `RainfallEvent` | `total_rainfall` | 判断本次事件累计雨量等级 |
| `RainfallEvent` | `max_intensity` | 判断是否存在短时强降水 |
| `RainfallEvent` | `rainfall_duration` | 区分短历时强降雨与长历时降雨 |
| `RainfallEvent` | `intensity_class` | 小雨、中雨、大雨、暴雨或短时强降水等事件类型 |
| `PumpStation` | `pump_start_count` / `pump_stop_count` | 判断泵站频繁启停 |
| `Outfall` | `tailwater_level` | 判断下游边界顶托 |

## 4. 第一版诊断锚点：冒溢节点

第一版关系证据网建议以冒溢节点作为核心锚点，原因有三点。

第一，冒溢节点是地下管网压力向地表释放的直接位置。节点发生冒溢，说明管网局部水力状态已经达到或超过节点排水能力，是连接地下管网异常与地表积水响应的重要桥接对象。

第二，冒溢节点同时连接地表 cell 和管网 link。以节点为中心向两侧扩展，可以自然形成“地表积水响应-节点冒溢-上下游管段流态”的局部诊断子图。

第三，以冒溢节点为锚点能够控制证据范围。相比从所有 cell 或所有 link 出发追溯，以冒溢节点为中心可以优先关注最具工程诊断意义的异常位置，减少全网遍历带来的证据冗余。

需要注意的是，不能简单表述为“冒溢节点直接相连的地表 cell 一定积水”。更严谨的表述应为：

> 冒溢节点周边 cell 是优先检查的地表积水响应区域，是否形成显著积水仍需由 cell 积水深度、积水持续时间、地表高程、坡度和产汇流条件共同判定。

## 5. 第一版关系证据网的诊断路径

### 5.1 地表侧扩展

地表侧从冒溢节点出发，首先通过坐标距离或空间索引寻找附近 cell，然后利用二维元胞邻接结构继续扩展相邻积水 cell。

推荐路径为：

```text
overflow_node
-> nearby_surface_cells
-> adjacent_ponding_cells
-> ponding_cluster
```

其中，cell 邻域可以采用两种模式：

| 邻域模式 | 含义 | 特点 |
|---|---|---|
| 4-neighbor | 上、下、左、右四个方向 | 更保守，适合表达正交网格中的直接相邻 |
| 8-neighbor | 4 邻域加四个对角方向 | 更连续，适合表达二维积水斑块扩展 |

地表侧筛选条件可包括：

```text
max_depth >= depth_threshold
ponding_duration >= duration_threshold
distance_to_node <= search_radius
```

辅助解释因子可预留：

```text
ground_elevation
runoff_coefficient
slope
land_use
distance_to_overflow_node
```

第一版可以优先使用 `max_depth` 和 `ponding_duration`，地表高程、径流系数和土地利用作为后续增强。

### 5.2 管网侧扩展

管网侧从冒溢节点出发，首先寻找直接相连的上下游管段，然后沿管网拓扑进行短程追溯。

推荐路径为：

```text
overflow_node
-> connected_upstream_links
-> upstream_trace_until_previous_confluence_or_source

overflow_node
-> connected_downstream_links
-> downstream_trace_until_next_confluence_pump_or_outfall
```

上游追溯停止条件：

```text
previous_confluence_node
source_node
max_trace_depth
```

下游追溯停止条件：

```text
next_confluence_node
pump_station
outfall
max_trace_depth
```

管网侧重点证据包括：

```text
max_fullness
fullness_duration
max_flow
flow_direction_changes
peak_flow_time
```

第一版已具备 `max_fullness`、`max_flow` 和 `flow_direction_changes`，建议后续补充 `fullness_duration` 和 `peak_flow_time`。

## 6. 现有筛查机制与关系证据链的融合

现有筛查机制和关系证据网不是替代关系，而是前后衔接关系。

现有筛查机制负责从海量模拟结果中发现异常对象：

```text
high-risk SurfaceCell
major-overflow JunctionNode
high-load ConduitLink
unstable-flow-direction ConduitLink
```

关系证据网负责围绕这些异常对象构建局部诊断上下文：

```text
异常对象
-> 空间邻近关系
-> 管网拓扑关系
-> 相关证据挂接
-> 局部诊断子图
```

DiagnosisAgent 则负责基于局部诊断子图形成结构化诊断结论：

```text
局部诊断子图
-> 诊断证据包
-> 关系型 diagnosis claim
-> VerificationAgent 核查 evidence_id 与 relation_path
```

因此，可以将二者关系概括为：

> 筛查机制负责发现异常点，关系证据链负责解释异常点。

更完整的工作流为：

```text
海量模拟结果
-> EvidenceBuilderAgent 构建对象级 evidence_table
-> DiagnosisAgent 或筛查规则识别异常对象
-> EvidenceGraphBuilder 构建 relation_table
-> PackageBuilder 生成 diagnostic_evidence_packages
-> DiagnosisAgent 生成关系型诊断结论
-> VerificationAgent 核查证据和关系路径
-> ReportAgent 生成可解释报告
```

## 7. 诊断证据包设计

第一版诊断证据包建议命名为：

```text
overflow_node_evidence_packages.json
```

每个证据包围绕一个冒溢节点组织，其结构包括：

| 模块 | 含义 |
|---|---|
| `package_id` | 证据包编号 |
| `anchor` | 诊断锚点，即冒溢节点 |
| `rainfall_context` | 本次降雨事件的强度、历时、峰值和类型判断 |
| `node_evidence` | 节点冒溢量、冒溢时长、最大冒溢流量等 |
| `surface_context` | 周边积水 cell、邻域扩展、淹没 cluster 信息 |
| `network_context` | 直接相连管段、上游追溯、下游追溯信息 |
| `relation_paths` | 可供核查的对象-关系-证据路径 |
| `diagnosis_ready_signals` | 供 DiagnosisAgent 使用的结构化布尔信号 |

示意结构如下：

```json
{
  "package_id": "pkg_node_C29YSG65184",
  "anchor": {
    "type": "node",
    "id": "C29YSG65184",
    "reason": "overflow_node",
    "evidence_ids": ["E_node_001"]
  },
  "rainfall_context": {
    "rainfall_event_id": "rain4",
    "total_rainfall_mm": null,
    "rainfall_duration_min": null,
    "max_intensity_mm_per_h": null,
    "rainfall_peak_time": null,
    "intensity_class": "unknown",
    "short_duration_heavy_rainfall": false,
    "classification_basis": "to_be_defined_by_local_standard_or_design_storm"
  },
  "node_evidence": {
    "total_flooding_volume_m3": 9801.6,
    "max_flooding_flow": 1.24,
    "flooding_duration_min": 42.0,
    "severity": "critical"
  },
  "surface_context": {
    "nearby_cells": [],
    "ponding_cluster": {
      "neighbor_mode": "8-neighbor",
      "cell_count": 0,
      "max_depth_m": null,
      "max_duration_min": null
    }
  },
  "network_context": {
    "connected_links": [],
    "upstream_trace": [],
    "downstream_trace": []
  },
  "relation_paths": [],
  "diagnosis_ready_signals": {
    "has_surface_ponding_nearby": false,
    "has_downstream_high_fullness": false,
    "has_upstream_high_load": false,
    "has_flow_direction_instability": false,
    "has_repeated_overflow": false,
    "rainfall_exceeds_design_or_warning_level": false
  }
}
```

需要强调的是，诊断证据包可以生成 `diagnosis_ready_signals`，但不应直接写入最终成因。例如，证据包可以写：

```json
{
  "has_downstream_high_fullness": true
}
```

但不建议在证据包阶段直接写：

```json
{
  "cause": "downstream_bottleneck"
}
```

最终成因判断应交给 DiagnosisAgent 完成。

降雨强度同样遵循这一原则。证据包可以判断本次降雨属于何种强度背景，例如：

```json
{
  "intensity_class": "heavy_rain",
  "short_duration_heavy_rainfall": true
}
```

但不应在证据包阶段直接写出“该积水一定由超标准暴雨导致”。更合理的做法是由 DiagnosisAgent 综合降雨强度、地表积水、节点冒溢、管段充满度和上下游关系后，再形成结构化成因判断。

## 8. 关系表字段设计

第一版关系表建议命名为：

```text
evidence_relation_table.csv
```

推荐字段如下。

| 字段 | 含义 |
|---|---|
| `relation_id` | 关系编号 |
| `run_id` | 模拟运行编号 |
| `source_type` | 起始对象类型 |
| `source_id` | 起始对象编号 |
| `target_type` | 目标对象类型 |
| `target_id` | 目标对象编号 |
| `relation_type` | 关系类型 |
| `direction` | 方向，例如 upstream、downstream、nearby、adjacent |
| `distance_m` | 空间距离，适用于空间邻近关系 |
| `topology_order` | 拓扑追溯阶数 |
| `weight` | 关系强度或优先级 |
| `confidence` | 关系可信度 |
| `data_source` | 关系来源，例如 geometry、swmm_topology、cell_grid |
| `evidence_ids` | 支撑该关系或对象状态的证据编号 |

其中，`confidence` 可采用保守分级：

| 关系来源 | 建议可信度 |
|---|---|
| SWMM 明确定义的管网拓扑 | `high` |
| 二维元胞网格结构定义的邻接关系 | `high` |
| 坐标距离推断的 node-cell 邻近关系 | `medium` |
| 模拟结果推断的水力影响关系 | `medium` 或 `low`，需后续规则细化 |

## 9. 与十个诊断问题的映射

用户已提出十个后续诊断问题。它们与关系证据网的关系如下。

| 诊断问题 | 所需对象 | 所需关系 | 所需证据 | 阶段建议 |
|---|---|---|---|---|
| 管道流量是否明显超过其满流能力 | `ConduitLink` | 可选上下游关系 | `max_flow`, `full_flow_capacity`, `max_fullness` | 第二阶段补充满流能力 |
| 节点水位是否超过地面高程 | `JunctionNode` | 节点-地表关系 | `hydraulic_head`, `ground_elevation`, `flooding_duration` | 第一版可用冒溢证据近似 |
| 哪些管段长期满流 | `ConduitLink` | 上下游拓扑 | `max_fullness`, `fullness_duration` | 第二阶段补充满流持续时间 |
| 哪些节点反复溢流 | `JunctionNode` | 节点-地表、节点-管段 | `overflow_event_count`, `total_flooding_volume` | 第二阶段补充事件计数 |
| 水位异常升高是否与下游边界有关 | `JunctionNode`, `ConduitLink`, `Outfall` | 下游追溯、排口关系 | `downstream_fullness`, `tailwater_level`, `flow_direction_changes` | 第三阶段扩展排口 |
| 泵站是否频繁启停 | `PumpStation` | 泵站-分区、泵站-节点 | `pump_start_count`, `pump_stop_count` | 后续扩展 |
| 泵站启停是否造成异常水位波动 | `PumpStation`, `JunctionNode` | 时间关联关系 | `pump_state`, `node_head_time_series` | 后续扩展 |
| 管道是否存在倒坡高程异常 | `ConduitLink` | from-node / to-node | `invert_elevation`, `pipe_slope` | 可放入模型检查阶段 |
| 模拟结果是否有不合理震荡 | `ConduitLink`, `JunctionNode` | 时间序列关系 | `flow_direction_changes`, `flow_oscillation_index`, `head_oscillation_index` | 第二阶段补充震荡指标 |
| 峰值流量时间是否符合降雨过程 | `RainfallEvent`, `ConduitLink`, `JunctionNode` | 事件-响应关系 | `rainfall_peak_time`, `peak_flow_time`, `peak_head_time` | 后续扩展 |

此外，降雨强度背景应作为前置诊断语境参与所有成因判断。例如，在短时强降水或超标准暴雨条件下，局部积水和节点冒溢可能首先被解释为系统承压响应；而在中小雨条件下出现同等级别积水，则应提高对局部排水能力不足、管段瓶颈、地形低洼、设施堵塞或模型异常的怀疑权重。

## 10. 第一阶段完成后的实施边界

第一阶段结束后，应形成两个明确结论。

第一，关系证据网的第一版不是完整知识图谱，而是以冒溢节点为中心的最小诊断子图。其对象范围先限定为：

```text
SurfaceCell
JunctionNode
ConduitLink
```

第二，关系证据网构建环节不直接输出最终成因，而是生成：

```text
evidence_relation_table.csv
overflow_node_evidence_packages.json
```

其中，`overflow_node_evidence_packages.json` 应包含 `rainfall_context`，用于描述本次降雨的累计雨量、历时、峰值强度、峰值时间和强度等级。DiagnosisAgent 后续再读取这些诊断证据包，输出关系型诊断结论，例如：

```text
node_overflow_with_surface_ponding
node_overflow_with_downstream_high_fullness
node_overflow_with_upstream_high_load
node_overflow_with_flow_direction_instability
```

VerificationAgent 后续需要从“核查 evidence_id”升级为“核查 evidence_id + relation_path”，从而判断诊断结论是否真正具有证据链支撑。

## 11. 可写入论文的方法表述

可在论文方法章节中初步表述为：

> 为克服对象级证据诊断难以表达地表-管网耦合成因链的问题，本研究进一步提出一种本体论启发的内涝关系证据网。该证据网以对象、关系和证据三层结构组织 SWMM-CA2D 模拟结果，其中对象层包括地表元胞、检查井节点和排水管段，关系层包括节点-地表邻近、元胞邻接、节点-管段连接以及管段上下游拓扑关系，证据层则挂接积水深度、积水持续时间、节点冒溢量、管段充满度和流向变化等模拟指标。第一版关系证据网以冒溢节点为诊断锚点，分别向周边地表积水响应和上下游管段流态扩展，形成局部诊断证据包。该设计使 DiagnosisAgent 能够在结构化证据约束下沿空间关系和水力拓扑追溯可能成因，并使 VerificationAgent 能够进一步核查诊断结论所依赖的 evidence_id 和 relation_path。

这段文字可以作为论文方法章节的初稿，也可以作为明天或后续向老师解释“为什么要做关系证据网”的核心表达。
