# 四组新增事件：计算与诊断全流程

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run
- Origin Date: 2026-10-11 (Asia/Shanghai)
- Verification Status: UNVERIFIED（实际执行状态见检查点；诊断因果准确性未由专家验证）
- Version Label: urban_four_20261011_v1

用户明确确认四组全部执行：单峰160 mm、双峰120 mm、三峰120 mm、三峰160 mm。此前五组、单峰60 mm及历史失败不重跑。

## 执行设置

- urban_drainage/baseline；新批次、新run_id，拒绝覆盖已有run。
- 情景准备 → SWMM–CA2D计算 → 模拟完成状态交接 → Evidence Builder → Diagnosis → Reference checks → Report；随后按需要执行最多两轮补证与修订。
- SWMM保存1分钟，边界5分钟区间平均，CA2D保存5分钟；降雨4小时、雨后延长3小时；其他模型与提示词设置保持原样。
- 自动补证仅已有结果、固定 evidence_lookup/saved_result_extract；不改变模型、不执行生成代码、不追加模拟。
- 每组应用层completion调用上限21（全批次最多84；SDK内部HTTP重试不是独立completion）；单组硬超时1800秒。
- 顺序执行；失败保留，不自动重试；HTTP401/403/429暂停剩余案例；日志无增长只提示，不自动终止。
- 新入口为已修复旧入口的独立四事件版本，历史入口不改。只改变授权事件集合、四组计数及Windows硬超时的子进程树终止方式；没有修复或压缩诊断输入，也没有改动诊断/报告核心。
- 按用户决定，既有结构化输出失败与上下文容量限制继续保留为可能的实验结果，不通过更换模型或增加重试消除。

## 执行前检查

四组输入的精确总雨量、49行、4小时历时、5分钟间隔、非负值、峰位与原曲线缩放已经验证。新入口及相关流程的94项联合离线测试通过。当前冻结85项输入/代码/元数据；原续跑计划中的77项输入与代码均未变化。

## 执行命令

```powershell
& 'E:\SWMM_Agentic\SWMM-Agentic2\.venv\Scripts\python.exe' 'E:\SWMM_Agentic\SWMM-Agentic2\scripts\run_urban_drainage_additions_20261011.py' --plan 'E:\SWMM_Agentic\SWMM-Agentic2\models\urban_drainage\batches\urban_four_20261011_v1\plan.json' --execute
```

不带--execute时只做只读前置校验。授权来源为本对话用户“都执行，刚刚是口误，请继续”，不重复要求启动确认。

## 记录与解释

每组.json检查点与.log日志、batch_summary.json、原生diagnosis_attempt审计、补证文件、verification与报告生成审计独立保存。完成、带缺口交付、初次失败、补证后失败、报告失败分别解释。引用校验不代替unsupported rate或专家因果准确性评分。
