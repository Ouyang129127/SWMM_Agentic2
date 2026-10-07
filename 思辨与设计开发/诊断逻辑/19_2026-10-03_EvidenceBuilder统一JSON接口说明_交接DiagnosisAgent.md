# EvidenceBuilder统一JSON接口说明：交接DiagnosisAgent

编写日期：2026-10-03。对象：负责修改本项目DiagnosisAgent的下一位AI或开发者。

本说明依据编写时的实际Python代码及已保存的1.1版证据包。它描述已经实现的接口，另将待修改事项明确列出；不把讨论中的设想写成既有功能。本文只说明接口和交接要求，不代表已修改DiagnosisAgent，也不认证现有诊断的工程正确性。

## 1. 首先明确现在采用什么

项目根目录：`E:\SWMM_Agentic\SWMM-Agentic2`。

EvidenceBuilder的唯一持久化输出：

```text
models/<model_name>/runs/<run_id>/evidence/evidence_package.json
```

- 外层格式：`schema_name = "swmm_ca2d_evidence_package"`，`schema_version = "1.1"`。
- 构建是确定性程序，读取已保存结果，不调用LLM、不重新模拟。
- 文件是本地证据库，不等于一次发给LLM的完整输入。后续仍按原问题选证。
- 当前已经取消全部传输结构压缩：不再共享元数据/对象定义，不使用字段路径矩阵、对象时间表，不执行编码后的还原验证。发送的每条选中证据保留原JSON结构。
- 当前代码没有应用端输入字符上限或本地上限配置开关；旧材料里的120000字符及`DIAGNOSIS_MAX_CONTEXT_CHARACTERS`不应恢复。服务商限制和网络错误独立存在。
- 不允许恢复前60条、前N条、排名、比例筛选，也不能因取消压缩就把几万条全库记录逐行喂给LLM。
- 旧CSV、独立首轮JSON、旧事件目录、旧规则诊断链路已退出运行时，不做兼容回退。

正常流程：模拟完成 → 构建统一证据包 → 创建问题绑定的任务并冻结快照 → 发送选中原结构证据 → Diagnosis调查/补证需求/修订 → 引用核查 → 报告。

`EVIDENCE_READY`只表示证据就绪，绝不表示诊断、核查或报告完成。

## 2. 数据究竟来自哪里

| 来源 | 当前用途 | 可用性处理 |
|---|---|---|
| `summary.json` | 模型/运行校验、事件/情景名称、降雨路径、地表计算状态 | 构建必须能读取；运行身份冲突报错 |
| `swmm/model_with_event.inp` | 节点/管段结构、方向、断面、偏移口径、选项、设施和控制是否存在 | 统一构建要求存在且声明`FLOW_UNITS LPS` |
| `swmm/nodes.tsv` | 所有保存节点的深度、冒溢流量；全场标量、事件分段及事件窗口过程 | 必需；空表、非法时间、重复对象时间、非有限水力数值报错 |
| `swmm/links.tsv` | 所有保存管段的流量、深度；全场标量及选中范围过程 | 必需，执行相应数据检查 |
| `swmm/model.out` | 选中节点的native水头、总入流、侧向入流 | 缺失时显式标记；可由底高+保存深度补水头，但不能补造入流 |
| `ca2d/surface_depth.tsv` | 地表网格最大深度及积水时长标量 | 缺失只在summary明确`NO_SURFACE_INFLOW`时允许；否则失败 |
| 实际降雨文件 | 降雨背景汇总 | 可缺失，生成带缺项的背景记录 |

降雨路径按summary中的`simulation_rainfall_file`、`rainfall_event_copy`、`rainfall_file`顺序寻找可用文件；失败后使用运行目录下`rainfall_event.txt`。真实案例可能使用`swmm/rainfall_for_simulation.txt`，不能硬编码只读取一个固定名字。

构建前后对现有来源做SHA-256核对，并检查缺失来源集合是否变化，成功后原子替换唯一JSON。`source_hashes`表示来源绑定，不表示来源内容、诊断数值和因果解释已经获认证。

## 3. 顶层完整字段

| 字段 | 类型 | 内容与读取要求 |
|---|---|---|
| `schema_name` | string | 外层格式名称，严格识别 |
| `schema_version` | string | 当前`"1.1"`，不是数字1.1 |
| `model_name` | string | 本次运行所属模型 |
| `run_id` | string | 本次运行标识，不要与模拟时间混淆 |
| `event_name` | string | 降雨/模拟情景事件名，可能为空串；不是节点冒溢event_id |
| `scenario_name` | string | 模型情景名，可能为空串 |
| `source_hashes` | object | `来源路径 → SHA-256字符串`；通常相对运行目录，外部来源可为绝对路径 |
| `missing_sources` | array[string] | 构建时缺失的来源路径，不代表这些变量为零 |
| `event_detection` | object | 保存样本分辨率和冒溢判定口径，详见下文 |
| `overview` | object | 全运行计数、证据目录和可用性 |
| `packages` | array[object] | 每个节点事件对应的六个EvidenceID索引，没有另存事件事实 |
| `evidence_rows` | array[object] | 标量、六类事件结构化记录、降雨背景的统一集合 |

不要把内部子结构版本套用到外层。当前`event_detection.schema_version`为`"0.1"`，正常降雨背景内部版本为`"1.0"`；这不表示外层1.1版本错误。

### 3.1 event_detection

实际键：`schema_name`、`schema_version`、`positive_tolerance_Ls`、`resolution`。

当前值：`sampled_overflow_events`、`0.1`、`1e-9`、`saved_samples`。没有顶层完整`events`数组；每次事件事实在相应`event_context.value.event`中。

### 3.2 overview

| 字段 | 含义 |
|---|---|
| `event_count` | 冒溢事件数，同一节点可有多次事件 |
| `overflow_node_count` | 至少有一次已识别冒溢事件的不同节点数 |
| `event_scope_policy` | 当前`confluence_divergence_corridors_v1` |
| `node_count` / `link_count` | 保存TSV中的不同节点/管段数；不是冒溢或失效对象数 |
| `storage_node_count` | 从模型输入统计的STORAGE节点数；未知时可null |
| `facility_counts` | 全模型PUMPS、ORIFICES、WEIRS、OUTLETS的数量字典 |
| `facility_inventory_status` | 模型设施目录的可用性，当前正常为`available` |
| `native_status` | native输出读取状态及单位/原因 |
| `surface_status` | `available`或`not_simulated_no_surface_inflow` |
| `evidence_count` | `evidence_rows`记录数；不是模拟采样数 |
| `metrics` | `metric_name → 记录数`；目录计数不等于实际读取或验证结论 |

真实运行总览：

```json
{
  "event_count": 7,
  "overflow_node_count": 7,
  "event_scope_policy": "confluence_divergence_corridors_v1",
  "node_count": 100,
  "link_count": 97,
  "storage_node_count": 0,
  "facility_counts": {
    "PUMPS": 0,
    "ORIFICES": 0,
    "WEIRS": 0,
    "OUTLETS": 0
  },
  "facility_inventory_status": "available",
  "native_status": {
    "status": "available",
    "units": {
      "head": "m",
      "flow": "L/s"
    }
  },
  "surface_status": "available",
  "evidence_count": 39502,
  "metrics": {
    "depth_above_section_reference_duration": 97,
    "direct_source_composition": 7,
    "event_context": 7,
    "facilities_and_storage": 7,
    "flooding_duration": 100,
    "flow_direction_changes": 97,
    "fullness_ge_0_8_duration": 97,
    "fullness_ge_0_95_duration": 97,
    "local_process_series": 7,
    "local_structure": 7,
    "max_depth": 19140,
    "max_flooding_flow": 100,
    "max_flow": 97,
    "max_fullness": 97,
    "max_link_depth": 97,
    "max_node_depth": 100,
    "overflow_event_count": 100,
    "ponding_duration": 19140,
    "rainfall_context": 1,
    "surface_association": 7,
    "total_flooding_volume": 100
  }
}
```

这个案例有100个保存节点、97条保存管段，但只有7个冒溢节点/7次事件。`max_flooding_flow:100`表示100条该指标记录，其中可包含零值；不能据此声称100个节点冒溢。

## 4. packages与EvidenceID的关系

每项结构为`node_id`、`event_id`、`evidence_ids`。`packages`只是索引，真正数据通过EvidenceID从`evidence_rows`取出。

P6真实索引：

```json
{
  "node_id": "P6",
  "event_id": "P6:E001",
  "evidence_ids": [
    "FP_8e129c4432875c8d6658",
    "FP_9f87baa0f52caa135901",
    "FP_c4c728f01da5b11aec29",
    "FP_3fb4b88ab9463017ddfb",
    "FP_755a36d944d9acbc4448",
    "FP_154a85645e6a11c87bb0"
  ]
}
```

当前构建每次事件提供六类记录。不得依赖数组位置推断类别，应按查得记录的`metric_name`识别；索引之外还有全场指标和降雨记录。

EvidenceID规则：

- `STAT_`：当前根据对象类型、对象ID、指标名生成的全场标量编号。
- `FP_`：当前根据event_id和六类之一的metric_name生成，前缀仍保留，但不代表仍有独立first_pass文件。
- `CTX_RAINFALL`：本次运行的降雨记录。
- `SUM_`：后续准备全局任务时生成的统计记录，通常不在EvidenceBuilder原文件中。

必须引用文件提供的完整ID，不自行推测、缩写或重算。ID不是跨运行全局唯一身份：某些STAT/FP/CTX编号可以在不同运行中重复；完整引用上下文至少包括模型、运行和EvidenceID。

## 5. evidence_rows不是一种整齐的固定表

统一记录共同字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `evidence_id` | string | 本包内唯一证据编号 |
| `source_model` | string | 对应顶层model_name，注意字段名不同 |
| `run_id` | string | 对应顶层run_id |
| `object_type` | string | 当前生产者使用`node`、`link`、`cell`、`run` |
| `object_id` | string | 对象ID；cell也按字符串读取，勿因数字外观转整数 |
| `metric_name` | string | 指标/证据类别，决定value解释方式 |
| `value` | number或object | 标量数值或完整结构化证据；不能统一float转换 |
| `unit` | string | 标量单位，或结构化记录标记`structured`；后者不是内部全部变量同一单位 |
| `source_file` | string | 来源定位；结构化事件行指统一JSON，其底层原始来源由source_hashes等追溯 |

变体字段不能一概必填：

- 标量通常有`event_id:""`、`event_name`、`scenario_name`、`time_start`、`time_end`、`calculation_method`、`threshold`、`at_time`。
- 六类事件行有非空`event_id`，但没有标量时间/计算方法字段；应进入value找事件窗口或方法。
- 降雨行没有event_id键；不要直接`row["event_id"]`，使用`row.get("event_id")`。
- 断面代理指标额外有`depth_reference_m`、`reference_method`、`interpretation`。
- 全局任务生成的SUM行有`derivation`，不保证source_file存在。

真实标量完整记录：

```json
{
  "evidence_id": "STAT_034685b953fea0bbaede",
  "source_model": "urban_drainage",
  "run_id": "chicago_like_single_4h_80mm_5min__baseline__20261002_225904",
  "event_id": "",
  "event_name": "chicago_like_single_4h_80mm_5min",
  "scenario_name": "baseline",
  "object_type": "node",
  "object_id": "P6",
  "metric_name": "total_flooding_volume",
  "value": 16.282015116,
  "unit": "m3",
  "source_file": "swmm/nodes.tsv",
  "time_start": "2024-01-01 00:00:00",
  "time_end": "2024-01-01 07:00:00",
  "calculation_method": "sum_event_left_sample_volumes",
  "threshold": "",
  "at_time": null
}
```

标量中的`time_start/time_end`是该对象保存结果的覆盖窗口；`at_time`才是极值采样时刻，若无极值定位则null。全场total_flooding_volume与单次estimated_volume_m3在只有一个事件时可能恰好相等，不能因此认为二者适用范围相同。

## 6. 全场标量清单与计算口径

### 6.1 每个保存节点：5种

| metric_name | unit | calculation_method | 含义 |
|---|---|---|---|
| `total_flooding_volume` | m3 | `sum_event_left_sample_volumes` | 该节点全部识别事件的估算冒溢体积之和 |
| `max_flooding_flow` | L/s | `maximum_saved_sample` | 全保存过程最大冒溢流量，at_time为首个最大值时刻 |
| `flooding_duration` | min | `sum_event_left_interval_durations` | 该节点全部事件左区间持续时间之和 |
| `overflow_event_count` | count | `positive_saved_sample_segments` | 该节点正冒溢样本连续段数量；当前以JSON数值如1.0保存 |
| `max_node_depth` | m | `maximum_saved_sample` | 该节点全保存过程最大水深 |

全部保存节点都会有指标，包括零冒溢节点；不只抽取冒溢节点，也不只限映射到地表的节点。

### 6.2 每个保存管段：基本3种，断面可用时另有4种

| metric_name | unit | calculation_method | 定义/条件 |
|---|---|---|---|
| `max_flow` | L/s | `maximum_absolute_saved_flow` | max(abs(flow))，已经失去峰值方向；方向须看逐时signed_model_flow_Ls |
| `max_link_depth` | m | `maximum_saved_sample` | 最大保存水深 |
| `flow_direction_changes` | count | `sign_changes_ignoring_near_zero` | 去除abs(flow)<=1e-6 L/s样本后，相邻剩余符号的变化次数 |
| `max_fullness` | ratio | `maximum_depth_over_section_reference` | max(max(depth,0)/Geom1) |
| `fullness_ge_0_8_duration` | min | `saved_left_interval_threshold_duration` | 上述比值>=0.8的左区间时长 |
| `fullness_ge_0_95_duration` | min | 同上 | 比值>=0.95的左区间时长 |
| `depth_above_section_reference_duration` | min | 同上 | 比值>1.0的左区间时长，等于1不计入 |

后4种只在可解析的断面Geom1>0时生成，缺记录不表示指标为零。`reference_method = XSECTIONS_Geom1`；这只是深度参考代理，并非针对所有断面形状均完成工程认证的充满度定义。**不能自动称承压、高负荷、瓶颈或输送失效。** 当前没有旧名`surcharge_duration`。

流向变化次数也是全运行采样指标，不能直接写成“某个冒溢事件中频繁震荡”或推断震荡频率。

### 6.3 每个地表网格：2种

| metric_name | unit | 计算 |
|---|---|---|
| `max_depth` | m | 网格全保存过程最大Depth，含at_time |
| `ponding_duration` | min | Depth严格>0.005 m的左区间时长 |

这是网格状态，不含“来自哪个冒溢节点”的归因关系。地表数据缺失而明确NO_SURFACE_INFLOW时，不生成伪造零网格记录。

时长统一按左端状态权重：相邻时间差归属于前一个采样点，最后一点不额外贡献时长。单位换算L/s×秒/1000得到m3；mm/h×小时得到mm。不要用旧代码中的其他积分辅助函数重算当前字段。

## 7. 六类事件证据总览

所有六类行的外层`object_type=node`、`object_id=目标冒溢节点`、`event_id=该节点的本次事件`。内部可以包含大量其他节点和管段。

| metric_name | value主结构 | 当前已提供什么 | 不代表什么 |
|---|---|---|---|
| `event_context` | event、process_window、window_policy | 单次冒溢事实、采样分辨率、窗口 | 原始求解器连续时间精确起止 |
| `local_structure` | available、nodes、links、options、units_verified_LPS、topology_scope | 模型结构、路径、范围边界和角色 | 全部致因必在范围内 |
| `local_process_series` | series、native_status、missing_values、scope_policy、direct_source_scope | 同一事件窗口内的沿程水力过程 | 全模拟过程、已计算储量平衡 |
| `direct_source_composition` | status、event_window、sources及分母 | 目标节点直接正进入组成、负离开积分 | 冒溢贡献率、最终汇水地块来源 |
| `facilities_and_storage` | 设施目录及未提取标记 | 局部设施存在性、全模型是否有控制 | 泵闸运行正常、已知调蓄可用量 |
| `surface_association` | status、reason | 当前明确not_built | 已关联淹没网格、已经证明无地表积水 |

记录存在、六类齐全与实质内容完整是不同事情。`surface_association`虽有EvidenceID，但仍只是缺项说明。

## 8. event_context：事件背景与分段

真实P6完整记录：

```json
{
  "evidence_id": "FP_8e129c4432875c8d6658",
  "run_id": "chicago_like_single_4h_80mm_5min__baseline__20261002_225904",
  "source_model": "urban_drainage",
  "object_type": "node",
  "object_id": "P6",
  "event_id": "P6:E001",
  "metric_name": "event_context",
  "value": {
    "event": {
      "event_id": "P6:E001",
      "node_id": "P6",
      "run_id": "chicago_like_single_4h_80mm_5min__baseline__20261002_225904",
      "model_name": "urban_drainage",
      "occurrence": 1,
      "start": "2024-01-01 01:37:00",
      "end": "2024-01-01 01:42:00",
      "last_positive_time": "2024-01-01 01:41:00",
      "peak_time": "2024-01-01 01:40:00",
      "peak_flooding_Ls": 79.3601532,
      "duration_minutes": 5.0,
      "estimated_volume_m3": 16.282015116,
      "positive_sample_count": 5,
      "left_censored": false,
      "right_censored": false,
      "saved_step_seconds": 60.0,
      "integration_method": "left_sample_rectangle"
    },
    "process_window": {
      "start": "2024-01-01 01:36:00",
      "end": "2024-01-01 01:43:00"
    },
    "window_policy": "one saved neighbor before/after; may require longer investigation"
  },
  "unit": "structured",
  "source_file": "evidence/evidence_package.json"
}
```

`value.event`字段：

| 字段 | 含义 |
|---|---|
| `event_id` / `node_id` / `model_name` / `run_id` | 本次节点事件身份和运行绑定 |
| `occurrence` | 该节点在本场第几次事件；编号按时间排序 |
| `start` | 首个flow>1e-9 L/s的保存样本时刻 |
| `end` | 常规为首个不满足正值判据的采样时刻；右截断为最后保存时刻 |
| `last_positive_time` | 本段最后正值样本时刻，不要与end互换 |
| `peak_time` / `peak_flooding_Ls` | 本段最大保存冒溢流量及其首个出现时刻 |
| `duration_minutes` | 本段左区间时长 |
| `estimated_volume_m3` | 本段正冒溢左端流量×相邻时间差积分所得估算体积 |
| `positive_sample_count` | 正值样本点数量，不是时长 |
| `left_censored` | 第一个保存样本已正冒溢，起点可能早于可见记录 |
| `right_censored` | 记录结束时还正冒溢，结束可能晚于可见记录 |
| `saved_step_seconds` | 首个相邻样本间隔，单个样本时可能null |
| `integration_method` | 当前left_sample_rectangle |

分段不做插值，不跨零值自动合并，也不按暴雨峰数强制分段。保存节点序列通常等间隔，允许最后一个间隔更短；重复时间或其他不规则间隔会报错，尚未实现任意缺测间隔处理。

常规事件按`[start,end)`解释区间：本例01:37—01:42持续5分钟，最后正值01:41。若最后保存点还为正，只积分能观察到的已有区间，不能补出结束后的体积或时长；单个末端正样本甚至可出现正峰值但估算体积/持续为零。

`process_window`在事件start前及end后各增加一个存在的保存邻点。本例01:36—01:43有8个采样点；这8点不是8分钟冒溢。模拟结果时间是2024年，run_id创建时间为2026年；不擅自改成当前日期或加UTC时区。

## 9. local_structure：结构和拓扑范围

### 9.1 对象字典

`nodes`是`节点ID → 结构对象或null`。结构基础字段：`node_type`、`invert_elevation`、`input_fields`。

- node_type包括JUNCTIONS、OUTFALLS、STORAGE、DIVIDERS。
- JUNCTIONS另有max_depth、initial_depth、surcharge_depth、ponded_area，未解析成功可null。
- OUTFALLS另有boundary_type；详细设置仍在input_fields中。
- STORAGE/DIVIDERS目前未全面拆出储量曲线、运行过程等字段，不得假定已提供。

当前SI/LPS模型中，invert_elevation为m高程，max_depth/initial_depth/surcharge_depth为m深度，ponded_area为m²面积。max_depth是模型节点字段，不是沿程时序最大值max_node_depth；ponded_area存在也不能单凭该字段断言ALLOW_PONDING已启用。

`links`是`管段/设施ID → 结构对象`。共同字段：link_type、from_node、to_node、input_fields、cross_section_fields、offset_convention。link_type可为CONDUITS/PUMPS/ORIFICES/WEIRS/OUTLETS。

- CONDUITS另有length、roughness、inlet_offset、outlet_offset。
- 断面存在时有cross_section.shape及geometry_fields。
- 原始input_fields、断面geometry_fields仍是字符串数组，不保证所有非CONDUITS类型均有长度等显式字段。
- 当前SI模型的length与管端偏移以m解释；roughness为模型输入的粗糙系数字段，不擅自替换成其他阻力指标。断面geometry_fields的各项含义随shape变化，不能统一把每个数字都解释为直径。
- offset_convention来自LINK_OFFSETS，默认DEPTH。ELEVATION表示管端偏移按绝对高程口径，不能再当相对底高的高度相加。
- 节点depth_m为深度，head_m为水头高程，不能直接混比。

P6节点及G4管段的真实结构节选（这里只节选对象，未列全部32节点/31管段）：

```json
{
  "nodes": {
    "P6": {
      "node_type": "JUNCTIONS",
      "invert_elevation": 1046.012,
      "input_fields": [
        "1046.012",
        "1.000",
        "0.0",
        "0.0",
        "0.85"
      ],
      "max_depth": 1.0,
      "initial_depth": 0.0,
      "surcharge_depth": 0.0,
      "ponded_area": 0.85
    }
  },
  "links": {
    "G4": {
      "link_type": "CONDUITS",
      "from_node": "P4",
      "to_node": "P6",
      "input_fields": [
        "50",
        "0.013",
        "1046.517",
        "1046.012",
        "0.0",
        "0.0"
      ],
      "cross_section_fields": [
        "CIRCULAR",
        "0.4",
        "0.0",
        "0.0",
        "0.0",
        "1"
      ],
      "offset_convention": "ELEVATION",
      "length": 50.0,
      "roughness": 0.013,
      "inlet_offset": 1046.517,
      "outlet_offset": 1046.012,
      "cross_section": {
        "shape": "CIRCULAR",
        "geometry_fields": [
          "0.4",
          "0.0",
          "0.0",
          "0.0",
          "1"
        ]
      }
    }
  }
}
```

`options`是模型OPTIONS字符串字典，不是程序全部已验证的工程假设。units_verified_LPS说明模型声明的流量单位检查；native数据另看native_status。

### 9.2 topology_scope完整字段

| 字段 | 内容 |
|---|---|
| `policy` | confluence_divergence_corridors_v1 |
| `target_node` | 目标冒溢节点 |
| `status` | complete_for_policy或partial，仅描述本选取规则 |
| `direction_basis` | 输入from/to方向用于搜索，不等于实际流向或因果方向 |
| `direct_links` | 所有直接连接目标的管段ID，决定直接来源统计范围 |
| `traces` | 各路径的origin_node、direction、role、nodes、links、stop_node、stop_reason |
| `boundary_nodes` | 停止节点ID→原因数组 |
| `node_roles` | 节点ID→target/boundary/corridor/interface_endpoint |
| `link_roles` | 管段ID→corridor/boundary_interface |
| `missing_node_definitions` | 选中范围内没有模型节点定义的ID |
| `limitations` | 边界、侧向入流与因果覆盖等限制说明 |

路径role为main或side_branch，direction为upstream或downstream。上游向模型前一汇流追踪，下游向下一分流追踪；下游沿程中间节点的其他进入支路再向上游追到其汇流边界。目标节点本身有分支不阻止每条直接路径起步。

当前汇流/分流判据数的是模型进入/离开链接数量；平行管段也分别计数，未把平行管段合并成一个几何分支。这个边界定义应原样说明，不把它冒充动态水力分析结果。

stop_reason包括confluence、divergence、terminal、facility_link、special_node:STORAGE/OUTFALLS/DIVIDERS、cycle、missing_node_definition、shared_path、target_reached。特殊停止优先于后续汇流/分流判断；shared_path表示同向共享段已展开，不是遗漏段。

所有已追踪节点（含停止节点）的直接交换管段均保留。接口管段对端标记interface_endpoint，保存其过程以计算水头差，但不由该对端继续向外扩展。上游路径经过模型分流节点时可保留其他外出接口，却不深入其他外出支路。

本例P6直接管段G4/G5/G6：上游到P4汇流和P5源头停止；下游途中没有分流，追到出水口E1；沿程侧支在P30/P54等汇流或源头停止。真实范围32节点/31管段。没有固定一层、固定层数或固定对象数量。

完整拓扑范围仍不保证足够解释原因；反向流、长传播时延或边界外约束都可能要求进一步调查。

## 10. local_process_series：逐时沿程水力过程

value包含series、native_status、missing_values、scope_policy、direct_source_scope。series是时间递增的普通JSON数组，没有编码矩阵。

每个时间记录固定包含：time、nodes、links、signed_towards_node_Ls、positive_source_sum_Ls、source_sum_minus_total_Ls。

| 路径 | 单位/含义 |
|---|---|
| `nodes[node].head_m` | m，native水头；缺失且模型底高/保存深度可用时按二者和补算 |
| `nodes[node].head_method` | native_output或invert_plus_saved_depth；没有有效水头时该键可缺失 |
| `nodes[node].total_inflow_Ls` | L/s，native总入流，用于比较，不再作为独立来源相加 |
| `nodes[node].lateral_inflow_Ls` | L/s，该节点聚合侧向入流，未拆到各汇水地块 |
| `nodes[node].depth_m` | m，nodes.tsv保存水深 |
| `nodes[node].flooding_Ls` | L/s，nodes.tsv保存冒溢流量，常规非冒溢时确为数值0 |
| `links[link].signed_model_flow_Ls` | L/s，正值按输入from→to，负值反向 |
| `links[link].depth_m` | m，管段保存水深 |
| `links[link].from_minus_to_head_m` | m，from节点head减to节点head；任一水头缺失则null |
| `signed_towards_node_Ls[link]` | L/s，只对目标直接管段重定向；正为进入目标，负为离开 |
| `signed_towards_node_Ls.aggregate_lateral` | L/s，仅目标节点侧向入流 |
| `positive_source_sum_Ls` | 目标直接来源有符号值取正部后之和；直接来源缺失则null |
| `source_sum_minus_total_Ls` | 上述和减目标native总入流；任一不可用则null |

重定向公式：链接to_node为目标时取原flow，from_node为目标时取-flow。两个有符号流量字段不要混用；例如G6模型正向从P6排向P7，在signed_towards_node_Ls中因此为负。

P6峰值时刻过程的真实节选：仅保留目标节点及三条直接管段用于展示；原记录还有其余沿程对象，本文件的节选不能回写成完整证据。

```json
{
  "time": "2024-01-01 01:40:00",
  "nodes": {
    "P6": {
      "head_m": 1047.011962890625,
      "total_inflow_Ls": 294.9515380859375,
      "lateral_inflow_Ls": 47.30423355102539,
      "depth_m": 1.0,
      "flooding_Ls": 79.3601532,
      "head_method": "native_output"
    }
  },
  "links": {
    "G4": {
      "signed_model_flow_Ls": 188.809509,
      "depth_m": 0.400000006,
      "from_minus_to_head_m": 0.4124755859375
    },
    "G5": {
      "signed_model_flow_Ls": 58.8377991,
      "depth_m": 0.400000006,
      "from_minus_to_head_m": 0.005615234375
    },
    "G6": {
      "signed_model_flow_Ls": 215.579971,
      "depth_m": 0.400000006,
      "from_minus_to_head_m": 0.2249755859375
    }
  },
  "signed_towards_node_Ls": {
    "G4": 188.809509,
    "G5": 58.8377991,
    "G6": -215.579971,
    "aggregate_lateral": 47.30423355102539
  },
  "positive_source_sum_Ls": 294.95154165102537,
  "source_sum_minus_total_Ls": 3.5650878658088914e-06
}
```

峰值直接进入约294.95154 L/s，G6离开约215.57997 L/s，冒溢约79.36015 L/s。可以据此讨论同一时刻的过程对应，但该时刻接近相等不认证全事件储量平衡或唯一致因。source_sum_minus_total_Ls不是储量变化，也不是“入流−出流−冒溢”的完整连续性残差。

沿程每个节点都有自己的lateral_inflow_Ls。不能将它们和目标G4/G5所承载的流量再次累加进目标直接来源分母；需要的是沿程比较，而不是重复计水。

## 11. direct_source_composition：直接进入组成

真实P6完整value：

```json
{
  "status": "complete",
  "method": "left_sample_rectangle",
  "event_window": {
    "start": "2024-01-01 01:37:00",
    "end": "2024-01-01 01:42:00"
  },
  "volume_denominator_m3": 80.93834773367286,
  "peak_time": "2024-01-01 01:40:00",
  "peak_denominator_Ls": 294.95154165102537,
  "share_meaning": "direct entering composition, not flood contribution",
  "total_inflow_role": "comparison only; never added as a source",
  "sources": [
    {
      "source_id": "G4",
      "entering_volume_over_covered_intervals_m3": 51.52346652,
      "outgoing_volume_over_covered_intervals_m3": 0.0,
      "covered_seconds": 300.0,
      "event_volume_share": 0.6365767026717379,
      "peak_entering_Ls": 188.809509,
      "peak_flow_share": 0.6401373864436067
    },
    {
      "source_id": "G5",
      "entering_volume_over_covered_intervals_m3": 16.307106174,
      "outgoing_volume_over_covered_intervals_m3": 0.0,
      "covered_seconds": 300.0,
      "event_volume_share": 0.2014756494370065,
      "peak_entering_Ls": 58.8377991,
      "peak_flow_share": 0.1994829346225777
    },
    {
      "source_id": "G6",
      "entering_volume_over_covered_intervals_m3": 0.0,
      "outgoing_volume_over_covered_intervals_m3": 64.6365783,
      "covered_seconds": 300.0,
      "event_volume_share": 0.0,
      "peak_entering_Ls": 0,
      "peak_flow_share": 0.0
    },
    {
      "source_id": "aggregate_lateral",
      "entering_volume_over_covered_intervals_m3": 13.107775039672852,
      "outgoing_volume_over_covered_intervals_m3": 0.0,
      "covered_seconds": 300.0,
      "event_volume_share": 0.16194764789125554,
      "peak_entering_Ls": 47.30423355102539,
      "peak_flow_share": 0.1603796789338156
    }
  ]
}
```

### 11.1 顶层字段

- status：complete/partial；低层提取还支持unavailable，但正常统一构建的缺输入/非LPS首先会失败，不能要求正常包必须出现unavailable。
- method：left_sample_rectangle。
- event_window：start/end；与单次事件积分窗口一致，不包含为过程观察附加的前后邻点区间。
- volume_denominator_m3：全部直接来源正进入积分之和；覆盖不完整时null。
- peak_time：冒溢峰值时刻，**不是各来源各自峰值**。
- peak_denominator_Ls：该冒溢峰时刻全部直接来源正进入流量之和；峰时刻数据缺失时null。
- share_meaning：direct entering composition, not flood contribution。
- total_inflow_role：comparison only; never added as a source。
- sources：目标全部直接链接加aggregate_lateral，每个来源单独记录。

### 11.2 每项sources字段

| 字段 | 含义 |
|---|---|
| source_id | 直接管段ID或aggregate_lateral |
| entering_volume_over_covered_intervals_m3 | 有数据区间内max(q,0)的左积分 |
| outgoing_volume_over_covered_intervals_m3 | 有数据区间内max(-q,0)的左积分 |
| covered_seconds | 这个来源实际可覆盖的积分秒数 |
| event_volume_share | 进入积分/共同进入分母；分母不可用或为零时null |
| peak_entering_Ls | 冒溢峰时刻max(q,0)，若峰数据不齐则null |
| peak_flow_share | 该时刻正进入值/该时刻共同分母；分母不可用或为零时null |

status=complete要求事件时长>0且每个来源积分覆盖时长等于事件时长；这不保证峰时刻项一定完整，仍须分别检查peak字段。status=partial时已有覆盖区间积分继续保存，但不得把它当完整事件积分。分母0是有效零分母，share=null；不要改为0%来掩盖不可定义。

本例G4约63.66%、G5约20.15%、目标侧向入流约16.19%是**直接进入体积组成**。约80.93835 m3是进入分母，不是冒溢体积16.28202 m3。G6本例是离开来源，进入占比0但排出体积约64.63658 m3，不能据零进入占比说“G6没有输水”。反向流时模型下游管段也可以成为正进入来源。

不提供：最终地块贡献、路径旅行时间、对冒溢的因果贡献、扩大某管段后的改善量。不能将“最大进入份额”直接写成“主要致涝因素”。

## 12. facilities_and_storage：设施及调蓄边界

真实value：

```json
{
  "local_facilities": {},
  "facility_presence_status": "checked_from_run_input",
  "controls_present": false,
  "facility_actions": "not_extracted",
  "storage_volume_process": "not_extracted",
  "initial_state_source": "input_fields in local_structure, not inferred from first report sample"
}
```

- local_facilities只列**本事件选中范围**内的非CONDUITS链接，结构来自模型；为空不是整个模型没有设施的充分证明，全模型看overview.facility_counts及目录可用性。
- facility_presence_status为checked_from_run_input表示检查过模型输入，不表示操作效果核验过。
- controls_present检查的是全模型CONTROLS章节是否有记录，并非“局部设施已受控或动作正常”。
- facility_actions当前固定not_extracted：泵启停、闸门开度、控制触发过程未提取。
- storage_volume_process当前固定not_extracted：没有逐时储量/可用调蓄过程。
- initial_state_source说明初始条件在local_structure输入字段，不把第一报告样本当模拟初值。

全模型设施目录确认为零时，可以有依据地将对应机制判断为无对象可调查；储量过程缺失时不能写“调蓄充分”或“设施正常”。

## 13. surface_association：明确未实现的归因

真实value：

```json
{
  "status": "not_built",
  "reason": "No source attribution inferred from nearest cell"
}
```

当前始终not_built，不提供node→cell关系、最近网格列表、淹没范围、地表来水来源或节点对地表体积贡献。即使全场cell指标存在，也不能自动断言“P6造成某网格积水”。因此第五总体问题中“从哪里冒出”可用节点事件回答，“淹没哪里”仍可能缺关联证据。

## 14. rainfall_context：独立的共同背景

本包只有一条`evidence_id=CTX_RAINFALL`、metric_name=rainfall_context、object_type=run的记录，所有任务范围都会提供。value不是完整逐时降雨曲线，只是汇总背景与原文件定位。

| 内部字段 | 含义 |
|---|---|
| schema_name / schema_version | 降雨子结构版本，与包外层不同 |
| model_name / run_id / event_name / scenario_name | 正常解析背景的运行身份 |
| rainfall_file / unit | 实际文件定位；当前解析口径mm/h |
| total_rainfall_mm | 相邻降雨点左强度×时间差积分，结果round到6位小数 |
| rainfall_duration_min | 最后一降雨时间减第一时间，包括其中零雨时段 |
| effective_rainfall_duration_min | 左强度>0的相邻区间总时长 |
| max_intensity_mm_per_h | 最大记录强度，不是短历时滑窗最大值 |
| mean_intensity_mm_per_h | 总雨量/完整降雨覆盖时长 |
| rainfall_start / rainfall_end / rainfall_peak_time | 雨量文件时间及首个最大记录强度时刻 |
| intensity_class / short_duration_heavy_rainfall | 内部阈值分类，非已校准当地标准结论 |
| classification_basis / classification_note | 分类依据及解释/缺项原因 |
| rainfall_points | 解析、按时间去重后的点数，不是输出曲线 |
| created_at | 背景生成时间，不是模拟起始时间 |

本例80mm、240min、最大记录强度146.732mm/h、平均20mm/h、峰时01:35；这只是本例，不可硬编码成所有模型事件。

缺文件或无可解析点时：关键统计为null、intensity_class=unknown、rainfall_points=0，classification_note说明原因；内部run_id、model_name、scenario_name、起止时间、created_at等键可能缺失。short_duration_heavy_rainfall=false在这种情况下不能作“已证实非短历时强雨”的依据。

当前降雨解析会跳过无法解析的行、重复时间保留最后一个值，单位按mm/h解释；没有全面验证其他单位和采样缺测。因此正常有汇总也不能当作逐行源数据质量已认证。

## 15. 所有缺项和状态应怎样理解

| 表达 | 正确含义 | 禁止推断 |
|---|---|---|
| 0 | 当前字段的已保存/已计算零值 | 不能推出全模型无风险 |
| null | 缺失、不可计算或不可定义，结合字段/status判断 | 不能自动换0 |
| 缺字段 | 此记录变体未提供该键 | 不擅自补“正常”或固定默认值 |
| complete_for_policy | 拓扑选择符合本规则 | 不是完整因果覆盖 |
| complete | 该组成/统计满足其覆盖规则 | 不是设施正常、诊断已验证 |
| partial | 部分可用，份额或比较可能不能完整求得 | 不把覆盖积分当完整积分 |
| missing / unsupported_units | native读取缺失或单位不支持 | 不以全零native数组替代 |
| not_extracted / not_built | 当前尚未生成对应内容 | 不表示现象不存在或机制被排除 |
| not_simulated_no_surface_inflow | 明确状态下未进行有地表入流的计算 | 不是全面地表安全认证 |

normal native_status为available并附head/flow单位。二进制缺失时head可按输入底高+TSV深度补算；侧向/总入流仍为null。不要仅检查文件中的六行“都存在”，必须检查里面的字段和状态。

## 16. JSON文件、快照与LLM实际输入的区别

| 层级 | 保存/提供什么 |
|---|---|
| evidence_package.json | 原始统一本地证据库：全场标量+全部事件六类+降雨+索引与来源 |
| evidence_snapshot.json | 任务冻结的**全库记录数组**，全局任务还追加程序生成的SUM记录；不是包顶层对象 |
| task.json.visible_ids | 当前允许发送/引用的EvidenceID集合，不能与全快照混淆 |
| LLM请求.visible_evidence | 从快照按visible_ids选出、深复制的原结构记录；未被选中记录未提供模型 |

当前LLM请求还含task、evidence_selection、evidence_overview、inventory、observations、previous_diagnosis、verification_feedback。原包的packages/source_hashes等不作为整个外层包自动发给LLM；来源完整性在任务准备阶段由程序处理。inventory只是快照的指标计数。

### 16.1 三种首轮选择

| 问题范围 | 当前选中内容 |
|---|---|
| 全局 | 全部节点事件六类记录+按同类指标程序生成的SUM统计+降雨；不逐行发送大量原始网格标量 |
| 单节点 | 该节点所有事件六类+其事件结构关联节点/管段的全部全场标量+降雨 |
| 单事件 | 指定事件六类+该事件关联节点/管段的全部全场标量+降雨 |

背景关联按local_structure.nodes/links完整集合选取，包括边界接口对端；不只选direct_links。无事件的单节点任务当前只有该节点全場标量与降雨，不自动构建该节点的非冒溢时序或拓扑包。

本例原包39502条=100×5节点标量+97×7管段标量+19140×2网格标量+7×6事件记录+1降雨。全局首轮57条=42事件记录+14分类统计+1降雨；P6首轮384条=6事件记录+32×5节点标量+31×7管段标量+1降雨。数量是实际选取结果，不是限制。

### 16.2 SUM统计不是旧式压缩

SUM是程序新生成的可引用统计证据，不是把时序压缩后让模型解码。按object_type、metric_name、unit、calculation_method、threshold分组；不混事件结构化value，不合并不同单位或阈值。

SUM的value保存source_metric、source_object_type、source_row_count、object_count、valid_count、missing_or_nonfinite_count、minimum、maximum、positive/zero/negative_value_count、status、interpretation和time_interpretation。

`by_source_window`是**汇总统计自身**的columns/records表，每组保留不同源time_start/time_end，列为start、end、rows、objects、valid、missing、minimum、maximum、positive、zero、negative。它不是已删除的水力时序传输编码。统计极值可能来自不同对象/不同各自时窗，不是同一时刻系统状态。

derivation含source=evidence_snapshot.json、selector、source_rows_sha256，绑定统计来源。SUM不提供所有源对象的逐项数值/峰值时刻，也不表示这些原对象已经被LLM逐项调查；需要具体对象时查询其原记录。

## 17. 补证：现在能做与不能做

当前`evidence_lookup`对**冻结快照中的既有记录**执行完整匹配，不回原始输出重新计算。

请求可用键：tool、object_type、object_id、metric_name、event_id、evidence_id、offset、reason。至少明确object_id/event_id/metric_name/evidence_id之一；不允许只按对象类别扫全库。offset只能省略或整数0，不能拿60、100等做行号分页。多个筛选条件为AND。

格式示例（示例查询，不是包内证据）：

```json
{
  "tool": "evidence_lookup",
  "object_type": "link",
  "object_id": "G6",
  "metric_name": "max_fullness",
  "reason": "核对该管段全运行断面深度代理指标，仅作为事件解释背景"
}
```

查管段全场标量时不要附P6:E001，因为管段标量event_id为空，附上则AND匹配不到。要取事件内部G6过程，应取P6:E001的local_process_series，G6没有独立的event_id过程行。

返回rows、total_matches、selection、complete_match_set；rows为完整匹配集合。运行时将找到的ID加入visible_ids，保留观察结果，再允许诊断修订。

若需要更长时窗、更远拓扑、泵动作、储量、地表归因：使用unavailable说明对象/变量/时窗/区分哪种解释。当前只是记录不可用请求，**不会自动完成新计算**。连续补证没有新增ID会触发无进展停止，不能伪装证据已经补齐。最多5个补证请求是当前诊断响应数量限制，不是筛选证据数量上限。

## 18. 供下一位AI直接使用的读取示例

这是程序读取示例，不是让LLM执行代码；在项目根目录使用，按索引而非数组顺序取六类。

```python
from pathlib import Path
from workflow_agents.evidence_package import load_package
from workflow_agents.evidence_selection import EVENT_GROUPS

def read_event_bundle(run_root: Path, event_id: str):
    package = load_package(run_root, verify_sources=True)
    by_id = {row["evidence_id"]: row for row in package["evidence_rows"]}
    entries = [item for item in package["packages"] if item["event_id"] == event_id]
    if len(entries) != 1:
        raise ValueError("Expected exactly one matching event index")
    index = entries[0]
    bundle = {}
    for evidence_id in index["evidence_ids"]:
        row = by_id[evidence_id]
        if (row.get("event_id") != event_id
                or row["object_type"] != "node"
                or row["object_id"] != index["node_id"]):
            raise ValueError("Event index binding mismatch")
        metric = row["metric_name"]
        if metric in bundle:
            raise ValueError("Duplicate event evidence group")
        bundle[metric] = row
    if set(bundle) != set(EVENT_GROUPS):
        raise ValueError("Missing or unexpected event evidence groups")
    return package, bundle
```

使用`bundle["event_context"]["value"]["event"]`读单次事实，用结构行的EvidenceID引用结构，用过程行的EvidenceID引用其内部具体时刻/对象；不要给内部每个数值臆造独立ID。

当前load_package实际只严格检查外层版本、运行绑定、rows/overview类型及行ID唯一/绑定。它**尚未自动认证全部嵌套字段、索引六类完整性、数值语义和因果解释**。上面示例增加的索引/六类读取校验属于交接建议，不能声称现有加载器已经全部做到。

## 19. 修改DiagnosisAgent时必须理解的约束与缺口

### 19.1 已有输出接口不要凭空改名

当前诊断响应要求JSON对象，含question_assessments、mechanism_assessments、claims、evidence_requests、stop_reason。

- question_assessments要求各一个Q1—Q4：起溢时刻、位置、体积、持续/反复；状态answered/needs_evidence/not_requested。
- mechanism_assessments要求各一个M1—M6：来水集中、局部约束、下游顶托、位置水头条件、设施运行、初始/调蓄；状态supported/candidate/not_applicable/not_investigated/needs_evidence。supported及not_applicable必须引用当前可见ID。
- claims每项包含object_type、object_id、可选event_id、question_id、claim_kind、claim_text、evidence_ids、engineering_reason、alternatives、scope。claim_kind为fact/clue/process_explanation。
- 程序生成claim_id并保存诊断版本；LLM不能自称已发布报告。
- stop_reason必须说明可以回答的范围或缺什么，不用“已经完成”掩盖缺项。

修改消费者前同时检查响应验证器、状态推进和报告读取方，不能只改提示词。

### 19.2 当前对象/事件校验与嵌套证据可能对不上

实际`_validate_response`允许的对象只来自visible记录外层的`(object_type,object_id)`，**没有展开local_structure/series内部的其他对象**。

- 全局首轮虽然各事件内部包含G6等管段，但没有逐管段全场标量外层行。因此直接输出object_type=link/object_id=G6的claim可能被拒绝，不能误认为G6过程不存在。
- P6节点任务中有G6全場标量，所以link/G6对象可存在；但带event_id=P6:E001的G6 claim仍可能因外层缺“G6+该event_id”记录而被拒绝。过程证据外层归P6，而非G6。
- claims中嵌套关联节点+目标事件也有同类问题。

这是**已观察到的代码约束，尚未在本次文档任务中修复**。下一位AI应决定：保留事件目标节点为claim外层，并在文本说明G6过程；或同步修改验证器，以可见结构明确声明的关联对象及目标事件为受控关联允许集。若采用后者，不能无条件放行任意模型对象/事件，也不能把“位于范围内”当作“机制已支持”。

### 19.3 引用存在不等于诊断正确

当前Verification只检查引用是否在可见记录中。尚不逐句验证引用变量、对象、时刻、数值、单位与claim一致，也不验证水力因果。

因此AI修改应优先落实：事实与线索/解释分离；原事件事实直接读取；比较同窗口同口径；明确竞争解释及未知内容；不能把最大标量、零值缺项、组成份额或完整拓扑标签当唯一致因证据。必要的新事实聚合由确定性程序做，不能让LLM自由扫描/加总几万条。

若需要核验诊断正文中的具体数值，应设计受控的字段定位与程序复核，并同步验证/报告契约；这属于下一步实现建议，当前包尚无通用`evidence_path`结论字段。

### 19.4 无冒溢任务

在统一包来源有效、全场事件目录计数和节点正冒溢指标一致时，可确认“本场保存结果中未识别冒溢”，说明分辨率与模型边界。没有事件包本身不是充分依据，更不能推出绝对安全。

本篇重点仍为冒溢与地表积水。无冒溢时可简述背景及剩余未研究项；这个我们会在后面的功能中补充，现在不必专注于这点。但仍然不要，没有溢流就给我报错或者停不下来，不要这样。

## 20. 下一位AI的验收清单

1. 只消费统一1.1包/其任务快照；不读旧CSV、独立首轮JSON或旧规则结果回退。
2. 按metric_name区别number与object，正确处理可选键、null、零值和未实现状态。
3. 同一事件六类全部关联读取，保留采样、反向流、沿程侧向入流和明确范围边界。
4. 单次事件值从event_context读，不将全场指标误作单次值；不混同last_positive_time/end/过程窗口。
5. 直接来源不重复加目标总入流、不重复叠加沿程内部流量；组成不当因果贡献。
6. 解释拓扑方向与实际方向、水深与水头、断面代理与承压/失效的区别。
7. 全局SUM证据和个体事实分开，引用可见ID；没有逐项提供的源记录不自称已读。
8. 不恢复前N条/比例/固定层数、传输压缩和人为长度上限；大输入的服务商失败正常保留错误。
9. 补证只能声称查到快照既有内容，未生成内容明确待补，不能臆造工具结果。
10. 修改对象/事件允许集时，同时测试关联管段/节点的合法claim与任意对象/错事件拒绝。
11. 测试重复事件、零事件、右截断、缺native/侧向入流、零分母、单位/时窗混用、来源变化和错误引用。
12. 显式分开“离线接口测试通过”“真实LLM格式通过”“数值核验通过”“工程解释通过”；文档或文件存在不能证明后续阶段完成。

## 21. 本次核对的真实材料和代码定位

真实完整1.1包：

```text
E:\SWMM_Agentic\SWMM-Agentic2\models\urban_drainage\runs\chicago_like_single_4h_80mm_5min__baseline__20261002_225904\evidence\evidence_package.json
```

本文JSON例子取自该文件；overview、index、标量、event_context为对应完整对象，structure/process为明确标注的对象/单时刻节选，composition/facilities/surface为对应完整value。所有片段只用于说明，不能拼接或回写为完整生产证据。

证据包核对摘要SHA-256：`25b7fb434fa15158d6085fece1aa288f5522b8c4e713a9a21e8e6c2e06b1f15a`。源码版本会继续变化，收到本文后先核对当前代码及包版本，不以历史记录代替当前事实。

| 代码位置 | 核对职责 |
|---|---|
| workflow_agents/evidence_builder.py | 外层统一包、全场指标、降雨接入、原子写入 |
| workflow_agents/evidence_package.py | 名称/版本/绑定/来源加载检查 |
| workflow_agents/sampled_events.py | 事件分段、截断、左积分 |
| workflow_agents/event_packages.py | 六类记录、native/TSV过程、直接来水组成 |
| workflow_agents/topology_scope.py | 追踪路径、停止边界、对象角色 |
| workflow_agents/rainfall_context.py | 背景字段及缺项变体 |
| workflow_agents/evidence_selection.py | 三种范围选择、SUM统计、已有证据查询 |
| workflow_agents/investigation.py | 真正发送结构、响应验证、任务状态与修订 |
| workflow_agents/reference_checks.py | 当前引用核查的实际范围 |
| workflow_agents/task_scope.py | 原问题到global/node/event的范围绑定 |

此前设计意图见00—13号思辨记录；实际变更历史见14—18号。历史压缩及可选字符阈值描述已被后续决定替代，当前消费接口以本文核对的代码为准。本次只交付说明文档，不修改业务代码或模拟结果。
