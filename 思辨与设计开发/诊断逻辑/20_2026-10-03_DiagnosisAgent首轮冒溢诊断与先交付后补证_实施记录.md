# DiagnosisAgent 首轮冒溢诊断与先交付后补证（2026-10-03）

本次使用19号EvidenceBuilder交接说明及真实统一1.1证据包推进Diagnosis消费者。目标：无须用户提出初始问题，先交付全场概览及每个冒溢节点／事件的发生过程、可能机制和证据缺口；随后补证。不新增token／字符预算，不修改或重跑模拟，不改变原证据包接口。

## 实现

- `DiagnosisAgent(model_name, run_id)`无message/task_id时执行initial动作，内部准备默认全局任务、诊断、引用核查和初步报告。默认任务的original_question=null，objective为系统诊断目标。带message仍准备后续用户专项任务。
- `EVIDENCE_READY`下一动作为initial_diagnosis；运行状态仍止于证据就绪，诊断进度归属task_id。Web编排说明不再要求用户重复初始问题。
- 新增`workflow_agents/diagnosis_contract.py`，按事件索引校验六类证据绑定、目录与全场节点计数／峰值／体积存在性，冻结原始event_context事实。右截断且仅终端正样本时，零积分也合法；不能因体积零否认事件。
- 从事件事实确定性生成可引用的SUM_EVT全场事件汇总，作为任务派生证据，不回写EvidenceBuilder包。首轮模型必须提供run_overview及完整event_assessments；每次事件恰好一次，各有发生过程、M1—M6状态、竞争解释和缺口。原question_assessments/mechanism_assessments/claims/evidence_requests/stop_reason字段继续保留。
- 对象／事件校验识别所引用结构、过程及直接来源组成中的嵌套节点／管段；run级结论可汇总本运行的节点证据。不存在对象、错事件、无关对象引用仍拒绝，不放行全模型任意对象。
- 每轮diagnose保存diagnosis_attempt_<id>.json：原始响应、finish_reason、usage、解析结果、失败阶段及错误。失败写入task历史，不覆盖已交付诊断／报告。模型输出schema通过不代表报告已发布。
- 诊断有补证请求时也先进入ready_for_verification，再ready_for_report，交付后才awaiting_evidence_confirmation。没有请求则preliminary_delivered。报告保留report_rN.json和preliminary_report_rN.md；旧版本保留，修订中不把旧报告当当前版本。
- 无冒溢首轮任务在目录与完整节点指标一致时确定性输出说明，不调用模型，不推断绝对安全。
- 移除每轮最多5个evidence_requests的旧数量门槛；每项仍检查工具、查询参数和理由。补证仍只查冻结快照，未生成数据不自动计算。
- 新增review动作：明确问题须引用可见EvidenceID，反馈文件保留并绑定哈希；下一诊断接收反馈，无需先检索补证。它不是自动工程／因果核验。
- 验收脚本支持重放保存的真实provider响应。可显式复核一个错误ID的拼写，须声明目标证据的object_type/object_id/event_id/metric_name并精确匹配快照；保留原响应及修正记录，不作模糊自动匹配，不放松正式验证器。

## 真实验收

运行：`urban_drainage / chicago_like_single_4h_80mm_5min__baseline__20261002_225904`。

任务：`0fcc0ae5b58249c399280c522bf6844c`。

原证据包SHA-256：`25b7fb434fa15158d6085fece1aa288f5522b8c4e713a9a21e8e6c2e06b1f15a`。验收前后一致，原模拟来源哈希复核通过。未模拟、未重建证据、未检索或计算新证据。

原库39502条，首轮提供58条完整原结构记录：42条事件六类、14条全场标量派生统计、1条降雨、1条新的事件目录派生汇总。快照含全库及15条派生记录，共39517条。数量是实际选择结果，不是上限。没有截断、时序传输编码或token预算。

真实调用均使用当前llm.deepseek_flash，官方deepseek-flash、高推理设置，无本地输出token参数：

| 调用 | 输入／输出token（服务商用量记录） | finish_reason | 实际结果 |
|---|---|---|---|
| 首轮 | 183980 / 20524 | stop | 92.531秒返回7次事件分析、9条claims、6个补证请求；被旧最多5项请求规则拒绝。移除该规则后对原响应重放，交付r1。 |
| 明确反馈后的修订 | 200137 / 22471 | stop | 返回7次事件修订分析；全局M4的一个EvidenceID多写一个d，引用校验拒绝。保存原响应、显式核对P42结构证据定位并纠正一处拼写后重放，交付r2。 |

修订中还发现run级汇总结论引用节点输入/设施证据被过窄的对象绑定拒绝；补齐本运行run主体绑定，仍拒绝跨运行对象。每次失败原响应和历史均保留。

最终文件位于该任务目录：

- `preliminary_report_r2.md`：审阅反馈后的最新初步报告。
- `diagnosis_r2.json`、`verification_r2.json`、`report_r2.json`：相应结构化结果。
- `acceptance_replay_r2.json`：最终验收结果与显式引用拼写修正记录。
- `diagnosis_attempt_f65e5f70dd5741d0842369f4c2906abe.json`：第二次真实模型原响应；未修改。
- `preliminary_report_r1.md`及r1结构化文件：第一版保留。

最终覆盖P42/P43/P44/P46/P48/P6/P7全部7次事件。程序写入的事件事实逐项与event_context完全一致。所识别事件体积积分合计34.5267191556 m³，保存结果事件时间范围01:37—01:42。56项引用核查全部可追溯，6项补证请求保留，任务状态awaiting_evidence_confirmation。

## 正文复核与边界

第一版明确存在内容问题：P43邻近时刻入流混用、P44在01:39是否冒溢误述、已有水头被列为缺项、上游管内来水与已冒溢水混淆、无STORAGE/初始节点水深零被用来排除动态储水。复核反馈保存于同目录20号JSON及任务review文件，通过第二次真实模型调用修订。第二版已纠正这些指定问题，仍将局部约束、顶托及动态储量保持为候选／缺证。

引用拼写纠正只涉及1个引用字符串，不手工改写模型工程判断。原始响应、修正理由、精确证据定位及重放结果分别保存。

93项离线回归测试通过，`git diff --check`通过。新增测试覆盖默认目标、全部／重复事件、合法嵌套对象、错对象／错事件／无关引用、直接来源无source_type字段、run汇总主体、超过5项请求、先交付后补证、失败原响应保留、空provider响应、零事件、终端正样本零积分、明确review及版本保留、事实篡改拒绝、显式引用定位纠正。

验收认证的层次：接口／状态流转、全部事件覆盖、程序呈现事件事实一致、引用可追溯。正文作了针对性人工复核，不是所有自然语言数值的自动通用核验，更不是独立水力因果验证。模型下一次响应仍可能格式错误、引用拼错或解释不充分；现在可保存并明确定位。任意时窗新计算、设施动作／储量提取、可靠地表归因及因果验证仍属后续补证工作。

## Web运行状态

检查时未发现8001端口有项目Web服务监听。尝试用项目虚拟环境隐藏启动uvicorn并检查首页，但执行工具在创建进程前被自动审批策略拒绝，原因仅返回blocked by policy；因此本次没有启动／重启Web，也没有完成真实浏览器对话验收。CLI真实诊断和离线Web路由测试已完成。用户按原有run_web.bat或run_web.ps1启动后加载本次代码。
