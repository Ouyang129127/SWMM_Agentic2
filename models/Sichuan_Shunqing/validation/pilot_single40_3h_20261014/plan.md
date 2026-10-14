# 顺庆 40 mm 单峰雨：雨后 3 h 全流程重跑

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run
- Origin Date: 2026-10-14 (Asia/Shanghai)
- Verification Status: UNVERIFIED（执行计划，不代表物理或因果准确性验证）
- Version Label: shunqing-single40-3h-pilot-v1

用户已要求重新执行模拟诊断全过程。沿用同一场 4 h、40 mm、5 min 单峰雨、baseline 管网和连续道路 v2；唯一有意改变的物理计算设置是将雨后时段从 20 h 改为 3 h。run_id 为 `sq40_3h_20261014_p1`；拒绝覆盖已有目录。

- 计算时段：2020-07-15 00:00–07:00；降雨结束 04:00。
- SWMM 输出 1 min，耦合边界及 CA2D 输出 5 min，CA2D 内步长 10 s；原路由步长 1 s 不变。
- 使用既有 Scenario → Simulation → Evidence Builder → Diagnosis → Reference_checks → Report 流程；原生格式与引用修正逻辑保留。
- 自动补证仅使用 evidence_lookup / saved_result_extract / unavailable 与本场已保存结果，最多两轮；不追加模拟或新水力条件。
- 沿用项目当前配置的诊断和报告提供方，每场最多 21 次 configured_completion 调用；不额外启用跨模型评审。API 内部 HTTP 重试次数不冒充 configured_completion 次数。
- 每阶段硬时限 30 min，检查进程存活及产物增长；无输出不自动等于失败，超时终止前通知。真实执行错误保留，不自动重跑失败阶段、不切换降雨或截断证据。
- 记录输入、代码及旧运行关键文件哈希，旧的 `sq40_20261013_p1` 完整保留。19 个候选雨型清单不是本次任务完成清单。
- 模拟或证据成功不能替代完整交付：只有当前修订的诊断、引用核验、结构化报告与 HTML 均完成，才记全流程完成；引用通过不等于因果准确性通过。
- 对构造地形、封闭地表边界、单向耦合以及第 7 h 尚未完全退水的适用限制继续保留。无有效诊断时 unsupported rate / 诊断准确性记为 N/A，不记为零。
