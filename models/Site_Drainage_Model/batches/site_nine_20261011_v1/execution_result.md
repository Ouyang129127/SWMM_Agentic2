# Site_Drainage_Model 九场全过程执行结果

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run
- Origin Date: 2026-10-11（Asia/Shanghai）
- Verification Status: UNVERIFIED（科学机制、工程准确性尚未人工验证；文件交付核对已完成）
- Version Label: site_nine_20261011_v1

## 执行概况

用户已授权新增 Site 专用入口并运行九场。批次顺序完成，主进程退出码 0；单峰、双峰、三峰 × 80、120、160 mm 的九场均执行一次模拟，保存证据、结构化诊断、Reference_checks 和当前 r1 HTML。执行锁已释放，未发现本批次残留工作进程。

运行时段：2026-10-11 20:07:49 至约 20:18:20（北京时间）。子进程轮询每 30 s，因此下表 elapsed_seconds 包括父进程等待下一轮检查的时间，不等于精确有效计算耗时，也不用于直接比较 Agent 性能。

- SWMM–CA2D 保存模拟完成：9/9。
- 当前结构化诊断/核验简报：9/9。
- 当前 HTML 交付与文件核对：9/9。
- 无溢流场景：9/9；正溢流事件：0。
- 自动补证：0 轮；没有符合条件的待补证动作，并非补证失败或人为跳过。
- 受控 completion 调用尝试共 10 次，全部属于 Report 环节；无冒溢初步诊断由项目现有确定性分支构建，没有调用 LLM 做逐事件机制推断。
- 其中双峰 160 mm 的报告第一次输出未通过叙述规则校验，内部修订后第二次通过。原始 failed attempt 保留；不是全场失败，不是补证，也不是重新模拟。
- 本批入口离线测试 13 项通过；85 个冻结输入/核心代码哈希运行后仍一致。新增入口和测试单列，未改原核心 Agent 或 urban 批次。

上述 9/9 只表示这一批九个无冒溢任务按当前成功定义完成；不能解释为通用自主 Agent 成功率、诊断准确率、M1–M4 机制覆盖率或 unsupported rate 为零。

## 统一结果与报告索引

| 运行 ID | 雨型 | 批次状态 | 溢流事件 | 采样溢流水量 m³ | 最大地表深度 m | 最大节点深度 m | 最大保存链接流量 L/s | completion 尝试次数 | 当前报告 |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| s9_1011_01 | 单峰 80 mm | completed | 0 | 0.00 | 0.000 | 0.707 | 6292.05 | 1 | [HTML 简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_01/diagnosis_tasks/66a0ad9df54e4ed4a0c67731d345c8c9/display_reports/r1/20261011_200817_efed4043/模拟诊断报告.html) |
| s9_1011_02 | 单峰 120 mm | completed | 0 | 0.00 | 0.000 | 0.891 | 10111.94 | 1 | [HTML 简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_02/diagnosis_tasks/7e73ea9abef24156ad905dcb475b14a8/display_reports/r1/20261011_200947_5625195e/模拟诊断报告.html) |
| s9_1011_03 | 单峰 160 mm | completed | 0 | 0.00 | 0.000 | 1.049 | 14077.33 | 1 | [HTML 简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_03/diagnosis_tasks/593d9a03acec402cbf9e4a63f25173a0/display_reports/r1/20261011_201047_e337f15d/模拟诊断报告.html) |
| s9_1011_04 | 双峰 80 mm | completed | 0 | 0.00 | 0.000 | 0.572 | 4057.74 | 1 | [HTML 简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_04/diagnosis_tasks/cde54f56787e4f2b819474b57437a626/display_reports/r1/20261011_201147_38dc2234/模拟诊断报告.html) |
| s9_1011_05 | 双峰 120 mm | completed | 0 | 0.00 | 0.000 | 0.722 | 6582.11 | 1 | [HTML 简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_05/diagnosis_tasks/cb984491fe4e40d386a96f581e97acc7/display_reports/r1/20261011_201248_d35d80a3/模拟诊断报告.html) |
| s9_1011_06 | 双峰 160 mm | completed | 0 | 0.00 | 0.000 | 0.852 | 9239.06 | 2 | [HTML 简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_06/diagnosis_tasks/671125f230d3401fa196527d03cad4cc/display_reports/r1/20261011_201347_52dea2ee/模拟诊断报告.html) |
| s9_1011_07 | 三峰 80 mm | completed | 0 | 0.00 | 0.000 | 0.554 | 3791.97 | 1 | [HTML 简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_07/diagnosis_tasks/9646540cffd94e90b700f10bd112d5c6/display_reports/r1/20261011_201518_65de4c94/模拟诊断报告.html) |
| s9_1011_08 | 三峰 120 mm | completed | 0 | 0.00 | 0.000 | 0.700 | 6165.10 | 1 | [HTML 简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_08/diagnosis_tasks/4b6fa89c0aef4397882942d796795f55/display_reports/r1/20261011_201618_d0db6814/模拟诊断报告.html) |
| s9_1011_09 | 三峰 160 mm | completed | 0 | 0.00 | 0.000 | 0.827 | 8688.05 | 1 | [HTML 简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_09/diagnosis_tasks/62fdd1bca1c4455089b12d3ab6270a23/display_reports/r1/20261011_201748_4e8a72f5/模拟诊断报告.html) |

最大节点深度和最大链接流量是全系统保存记录的极值，可发生在不同对象和时刻；不能用它们单独认定具体瓶颈、节点超过井口或输水能力余量。管网中含地表排水设施/非圆管链接，最大链接流量也不能自动称为“最大管道流量”。

## 降雨与原生模拟核对

原生 SWMM 报告逐场记录的总降雨与事件输入一致。降雨驱动的节点深度和链接流量随情景变化，不是因为降雨没有读入而出现零溢流。

| 运行 ID | 原生总降雨 mm | 径流数量连续性误差 % | 管网演算连续性误差 % | 父进程记录时长 s | 原生报告 |
|---|---:|---:|---:|---:|---|
| s9_1011_01 | 80.000 | -0.216 | 0.003 | 90.015 | [原生 SWMM 报告](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_01/swmm/model.rpt) |
| s9_1011_02 | 120.000 | -0.206 | 0.014 | 60.000 | [原生 SWMM 报告](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_02/swmm/model.rpt) |
| s9_1011_03 | 160.000 | -0.200 | 0.015 | 60.000 | [原生 SWMM 报告](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_03/swmm/model.rpt) |
| s9_1011_04 | 80.000 | -0.340 | -0.007 | 60.016 | [原生 SWMM 报告](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_04/swmm/model.rpt) |
| s9_1011_05 | 120.000 | -0.330 | 0.014 | 60.000 | [原生 SWMM 报告](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_05/swmm/model.rpt) |
| s9_1011_06 | 160.000 | -0.323 | 0.018 | 90.016 | [原生 SWMM 报告](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_06/swmm/model.rpt) |
| s9_1011_07 | 80.000 | -0.473 | -0.008 | 60.016 | [原生 SWMM 报告](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_07/swmm/model.rpt) |
| s9_1011_08 | 120.000 | -0.465 | 0.007 | 90.000 | [原生 SWMM 报告](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_08/swmm/model.rpt) |
| s9_1011_09 | 160.000 | -0.465 | 0.015 | 60.015 | [原生 SWMM 报告](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_09/swmm/model.rpt) |

本次不修改模型参数、不增加雨量、不改变 CA2D 静态层、不自动重试模拟。全局连续性误差仅作结果核对，不替代局部数值稳定性、网格敏感性、真实观测或机理准确性评价。

## 文件与证据绑定核对

九场均通过以下检查：

1. summary.json 中降雨 SHA-256 与固定计划一致。
2. 原生报告实际总雨量与事件雨量一致。
3. 证据快照、diagnosis.json 和 verification.json 的文件哈希与任务记录一致。
4. 当前诊断、核验及结构化报告的 evidence_binding 与当前 task.json 一致。
5. 结构化报告和 HTML 修订号均与诊断 r1 一致。
6. HTML 文件哈希与任务记录一致。
7. 每份报告有 5 张嵌入图片（4 PNG + 1 GIF），Base64/文件类型签名核对通过；项目内置报告质量检查同样通过。
8. 每场无冒溢概览的 1 条引用检查通过，总共 9/9。此检查仅确认引用可追溯，未独立核实工程解释或因果。

完整核对数值、原始模拟产物哈希、报告失败尝试及对应文件路径见 [artifact_inspection.json](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/batches/site_nine_20261011_v1/artifact_inspection.json)。

| 运行 ID | 汇总 | 结构化简报 | 核验 |
|---|---|---|---|
| s9_1011_01 | [模拟汇总](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_01/summary.json) | [结构化诊断简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_01/diagnosis_tasks/66a0ad9df54e4ed4a0c67731d345c8c9/report.json) | [引用核验](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_01/diagnosis_tasks/66a0ad9df54e4ed4a0c67731d345c8c9/verification.json) |
| s9_1011_02 | [模拟汇总](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_02/summary.json) | [结构化诊断简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_02/diagnosis_tasks/7e73ea9abef24156ad905dcb475b14a8/report.json) | [引用核验](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_02/diagnosis_tasks/7e73ea9abef24156ad905dcb475b14a8/verification.json) |
| s9_1011_03 | [模拟汇总](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_03/summary.json) | [结构化诊断简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_03/diagnosis_tasks/593d9a03acec402cbf9e4a63f25173a0/report.json) | [引用核验](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_03/diagnosis_tasks/593d9a03acec402cbf9e4a63f25173a0/verification.json) |
| s9_1011_04 | [模拟汇总](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_04/summary.json) | [结构化诊断简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_04/diagnosis_tasks/cde54f56787e4f2b819474b57437a626/report.json) | [引用核验](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_04/diagnosis_tasks/cde54f56787e4f2b819474b57437a626/verification.json) |
| s9_1011_05 | [模拟汇总](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_05/summary.json) | [结构化诊断简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_05/diagnosis_tasks/cb984491fe4e40d386a96f581e97acc7/report.json) | [引用核验](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_05/diagnosis_tasks/cb984491fe4e40d386a96f581e97acc7/verification.json) |
| s9_1011_06 | [模拟汇总](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_06/summary.json) | [结构化诊断简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_06/diagnosis_tasks/671125f230d3401fa196527d03cad4cc/report.json) | [引用核验](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_06/diagnosis_tasks/671125f230d3401fa196527d03cad4cc/verification.json) |
| s9_1011_07 | [模拟汇总](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_07/summary.json) | [结构化诊断简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_07/diagnosis_tasks/9646540cffd94e90b700f10bd112d5c6/report.json) | [引用核验](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_07/diagnosis_tasks/9646540cffd94e90b700f10bd112d5c6/verification.json) |
| s9_1011_08 | [模拟汇总](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_08/summary.json) | [结构化诊断简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_08/diagnosis_tasks/4b6fa89c0aef4397882942d796795f55/report.json) | [引用核验](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_08/diagnosis_tasks/4b6fa89c0aef4397882942d796795f55/verification.json) |
| s9_1011_09 | [模拟汇总](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_09/summary.json) | [结构化诊断简报](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_09/diagnosis_tasks/62fdd1bca1c4455089b12d3ab6270a23/report.json) | [引用核验](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/runs/s9_1011_09/diagnosis_tasks/62fdd1bca1c4455089b12d3ab6270a23/verification.json) |

## 本组结果的可用范围

九场是同一管网的不同合成雨型/总量情景，不是九个独立管网。它们可以用于记录无溢流情景下的规范化执行、负例处理、引用与报告交付，以及不同降雨下的管网水深/流量响应。

当前诊断中的 M1–M6 状态均为 not_investigated，原因是未识别溢流事件。不应把无冒溢分支的 Q1–Q4 answered 标签当作四类致灾问题都经 LLM 正确解释。

地表积水零值是在现有溢流输入驱动与合成地形设定下得到的结果，不证明真实场地安全，也不代表对直接降雨地表积水、设施暴露或回流机制已作完整评价。九场没有触发逐事件致灾解释或补证闭环，不能单靠本批支撑这些能力的评价。

如果以后需要该管网出现受压/溢流过程，应另行讨论模型输入、评价对象和压力场景；本轮没有为了产生积水擅自增加雨量或修改模型。

## 批处理命令与约束

工作目录：E:/SWMM_Agentic/SWMM-Agentic2

```powershell
.\.venv\Scripts\python.exe -u scripts\run_site_drainage_batch_20261011.py --plan models\Site_Drainage_Model\batches\site_nine_20261011_v1\plan.json --execute
```

每场上限：2 轮已有结果补证、21 次受控 completion 尝试、1,800 s 墙钟。固定工具、独立进程、不覆盖、不自动重跑失败案例。运行监控与失败保留方式按 academic-research-suite 的实验执行流程记录。

[固定计划](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/batches/site_nine_20261011_v1/plan.json)；[批处理最终状态](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/batches/site_nine_20261011_v1/batch_summary.json)；[执行边界与预检说明](E:/SWMM_Agentic/SWMM-Agentic2/models/Site_Drainage_Model/batches/site_nine_20261011_v1/README.md)。

