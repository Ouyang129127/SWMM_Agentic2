# 五事件续跑结果（2026-10-11）

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run
- Origin Date: 2026-10-11
- Verification Status: UNVERIFIED（诊断因果准确性尚未经专家评估；已完成工件一致性及交付结构检查）
- Version Label: urban_five_recovery_result_v2

## 执行概况

- ID: urban_five_20261011_recovery_v2
- Type: analysis
- Status: partial completion（全部五组已处理；3 组当前简报交付，其中 1 组有缺口；2 组失败）
- Exit Code: 1（不表示模拟失败；表示未实现五组全部完成）
- Working Directory: E:\SWMM_Agentic\SWMM-Agentic2
- Duration: 各组顺序执行耗时合计 20.50 分钟，另有前置核验及进程切换开销。
- Simulation: 本次模拟调用次数为 0，五组均复用初次批处理的已完成结果。
- LLM application calls: 15；不是 SDK 内部 HTTP 请求/重试次数。
- Lock: 进程已结束，execution.lock 已移除。
- Scope: 排除 single 60 mm；不修改模型、不重新模拟、不执行生成代码；每组补证上限两轮、应用层调用上限 21 次、硬超时 1800 秒。没有超出这些限额。

```powershell
& 'E:\SWMM_Agentic\SWMM-Agentic2\.venv\Scripts\python.exe' 'E:\SWMM_Agentic\SWMM-Agentic2\scripts\run_urban_drainage_batch.py' --plan 'E:\SWMM_Agentic\SWMM-Agentic2\models\urban_drainage\batches\urban_five_20261011_recovery_v2\plan.json' --execute
```

## 各组结果

| 降雨事件 | 结果 | 诊断事件数 | 补证轮数 | 应用层调用次数 | 执行耗时 / s |
|---|---|---:|---:|---:|---:|
| 单峰 80 mm | 完成，保留证据缺口 | 7 | 1 | 6 | 510.031 |
| 单峰 120 mm | 失败，未交付补证后最终版 | 12 | 0 | 2 | 240.016 |
| 双峰 80 mm | 完成 | 0 | 0 | 1 | 60.016 |
| 双峰 160 mm | 失败，未交付补证后最终版 | 13 | 1 | 5 | 360.016 |
| 三峰 80 mm | 完成 | 0 | 0 | 1 | 60 |

零溢流案例的初次诊断为确定性处理，仍生成 HTML 简报；两个零溢流案例各发生 1 次 Report Agent 调用，没有诊断 LLM 调用。

## 简报入口

- [单峰 80 mm：当前交付版](<E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/runs/chicago_like_single_4h_80mm_5min__baseline__batch_20261011_v1_01/diagnosis_tasks/aa9af3e6908747e19d01fc31c6bdd4d2/display_reports/r2/20261011_100522_694f3631/模拟诊断报告.html>)；版本 r2，1563254 bytes，SHA256 8f5a78ff0302464e559b56a5d2ab21b40308010e7bd337f11ee4217060a4a483。
- [双峰 80 mm：当前交付版](<E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/runs/chicago_like_double_4h_80mm_5min__baseline__batch_20261011_v1_03/diagnosis_tasks/906325c1595844be8bbb4668b1babdb5/display_reports/r1/20261011_101305_c336331a/模拟诊断报告.html>)；版本 r1，813939 bytes，SHA256 ba1513a04f140fa347c70786d71a140c18424c3c7bb8d1c1a4d60613ae335292。
- [双峰 160 mm：历史初版（补证后未完成）](<E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/runs/chicago_like_double_4h_160mm_5min__baseline__batch_20261011_v1_04/diagnosis_tasks/b4ae203ad0984f0cadc48a968fa5b040/display_reports/r1/20261011_101613_fc3bd1a8/模拟诊断报告.html>)；版本 r1，3225321 bytes，SHA256 c97a57dd0fa45262c8575d406f0b8101c065b271631a7a162f95f3ce60f257af。
- [三峰 80 mm：当前交付版](<E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/runs/chicago_like_triple_4h_80mm_5min__baseline__batch_20261011_v1_05/diagnosis_tasks/23a14e7fecf3445b8da919066e889ace/display_reports/r1/20261011_102005_b6a89492/模拟诊断报告.html>)；版本 r1，811649 bytes，SHA256 ceb34cfab0722b30c20f1e408388e3d7e1e408e7aee212ef80048719e2a6f040。

双峰 160 mm 的 r1 是补证前已通过检查的历史初版。之后增加了证据、再诊断失败；r1 不是补证后的完整交付版，不能计为该组最终成功。本组补证文件已保存，但不能将其效果说成“修订诊断已改善”。

## 失败与缺口

### 单峰 80 mm：已交付，但地表归属证据仍有缺口

r2 有 7 个事件，7 份补证文件，65 个可见证据 ID；最终引用检查 66/66 通过。停止原因为 capability_gaps，不是达到两轮上限。地表关联请求保留为 unavailable，没有进一步固定工具可执行的请求。

注意：event_packages.py 当前明确设置 surface_association.status=not_built，理由为不从最近网格推断来源归属。诊断文本将缺口描述成缺少可靠节点—网格映射；项目实际存在 static/node_to_cell_mapping.csv。因此，不能把该文本作为“项目不存在映射”的事实，应区分节点—网格定位和冒溢水源对受淹区域的因果归属。此次未修改这一诊断结论或核心代码。

### 单峰 120 mm：结构化诊断校验失败

首次返回 JSON 解析失败：Expecting ',' delimiter。既有有界修正后，M4 mechanism_assessments 的 applicability/support 缺少可见证据引用（references=None）。r0 未产生合格初次诊断和简报。两次诊断调用及原始返回均保存在 diagnosis_attempt_*.json，未自动重试失败案例。

### 双峰 160 mm：补证后上下文超限

r1 初次诊断、引用核验（110/110）及简报完成。补证阶段生成 3 份补证文件，可见证据增至 121 个。随后的诊断请求被供应商以 HTTP 400 拒绝：请求消息为 2,156,585 tokens，超过错误响应注明的最大上下文 1,048,576 tokens。该请求没有成功生成修订诊断，也没有补证后的简报。没有换模型、截断证据、扩大限额或自动重试。

这里暴露的是证据请求范围与输入预算之间的约束缺失。后续应讨论按事件/问题收窄输入、摘要与索引共存以及发送前预算检查；这些属于进一步改造，不在此次仅修复批处理状态交接的授权范围内。

## 工件检查与来源保留

- 修复仅发生于新增批处理入口，新增对应离线测试；既有诊断、核验及 Report Agent 核心代码没有更改。
- 原冻结文件中，其余 76 项保持不变；续跑前后核验五组已保存模拟产物共 85 项，SHA256 均未改变。
- 原批处理 urban_five_20261011_v1 的失败日志、计划及检查点保留，续跑记录独立保存，不能混成一次无干预成功执行。
- 86 项联合离线测试最终全通过；首次运行有 1 项既有用例失败，单独复查及再次完整运行通过，情况已记录在 README.md。
- 对三个当前交付版，独立调用现有工件验证与 HTML 检查：证据绑定/诊断版本、材料来源哈希、HTML 哈希、章节/事件覆盖、嵌入图像完整性均通过。
- 对双峰 160 mm 历史初版，仅检查其历史材料来源、HTML 哈希及文档结构；没有把它当作当前补证状态的合格报告。
- 三个当前交付版的引用检查分别为 66/66、1/1、1/1；这些是 reference checks，不是语义支持率、unsupported rate 或诊断准确率。
- 没有进行专家盲评或因果验证，不能将这些运行结果直接作为论文的准确性证明。
- 无硬超时，无未经授权的失败重试；等待供应商返回时出现日志无增长提示，进程未因此被杀死。

## 记录文件

- [批次汇总](E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/batches/urban_five_20261011_recovery_v2/batch_summary.json)：所有五组状态、耗时、调用次数、停止原因。
- [工件复查](E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/batches/urban_five_20261011_recovery_v2/artifact_inspection.json)：简报版本、哈希、结构检查、失败类型与已报告 token 使用。
- [冻结计划](E:/SWMM_Agentic/SWMM-Agentic2/models/urban_drainage/batches/urban_five_20261011_recovery_v2/plan.json)：输入/代码哈希、模拟产物哈希及执行限额。
- 每组同名 .json 为检查点，.log 为过程日志；诊断任务目录另保留尝试审计、补证、核验及简报生成审计。

已报告 usage 合计 prompt_tokens=2401823，completion_tokens=250590。这是有 usage 的审计记录之和；没有 usage 的失败请求未计入，不可据此直接作费用估计。

