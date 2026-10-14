# 五事件续跑记录

用户于 2026-10-11 明确授权修复批处理状态交接，并从已有模拟结果继续。初次失败记录保留在相邻 `urban_five_20261011_v1`，不覆盖、不隐瞒。

## 执行范围

仅复用原五组已完成模拟；排除 single 60 mm。恢复 RUN_READY 状态后运行证据构建、初次诊断、引用核验与 HTML 简报。补证仅使用已有结果与固定 evidence_lookup/saved_result_extract 工具，每组最多两轮；不修改模型、不生成执行代码、不重新模拟。每组最多 21 次应用层 LLM completion 调用；SDK 内部 HTTP 重试不计为独立 completion。每组硬超时 1800 秒，顺序执行。

## 冻结与测试

原冻结文件中除获授权修改的批处理入口外，其余 76 项均未改变。另冻结五组已有模拟产物共 85 个文件（不冻结需更新的 workflow_state.json）。执行前与每组开始前校验 SHA256；缺失、变化、事件身份不匹配或未完成的结果不允许续跑。

离线测试新增真实工件状态交接及“不调用模拟工具”的续跑检查。86 项联合测试首次运行出现 1 项既有用例失败；该用例单独复查通过，完整再次运行 86 项均通过。未修改既有诊断实现或该失败用例。

## 命令

```powershell
& 'E:\SWMM_Agentic\SWMM-Agentic2\.venv\Scripts\python.exe' 'E:\SWMM_Agentic\SWMM-Agentic2\scripts\run_urban_drainage_batch.py' --plan 'E:\SWMM_Agentic\SWMM-Agentic2\models\urban_drainage\batches\urban_five_20261011_recovery_v2\plan.json' --execute
```

仅 `--execute` 触发执行；本计划强制复用已有模拟，不调用情景准备或模拟工具。日志、检查点、汇总独立保存在本目录。失败不自动重试，401/403/429 暂停后续案例。

## 解释边界

引用核验和简报交付检查不等于因果诊断准确性或专家评估。允许带未解决证据缺口交付，但必须标记 `completed_with_gaps`，不得当作全部推论已确认。使用 academic-research-suite 的实验执行流程保留失败与续跑来源。
